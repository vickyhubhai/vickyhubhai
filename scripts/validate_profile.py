"""Local validation for the profile repository (run before committing).

Checks:
  1. YAML syntax of every file under .github/workflows/
  2. HTML tag balance of README.md (GitHub renders raw HTML blocks as-is)
  3. Local asset paths referenced from README.md exist
  4. Required README sections are present
  5. No obvious secrets / tokens committed
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
VOID = {"br", "img", "source", "hr", "input", "meta", "link", "area", "col"}
failures = []


def check_yaml():
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    if not files:
        failures.append("no workflow files found")
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"YAML error in {f.name}: {exc}")
            continue
        # PyYAML 1.1 parses the bare key `on` as boolean True
        if not any(k in doc for k in ("on", True)):
            failures.append(f"{f.name}: missing 'on' trigger block")
        if "jobs" not in doc:
            failures.append(f"{f.name}: missing 'jobs'")
        perms = doc.get("permissions")
        if perms not in ({"contents": "write"},):
            failures.append(f"{f.name}: unexpected permissions {perms!r}")
        print(f"  YAML OK: {f.relative_to(ROOT)} (triggers={sorted(map(str, [k for k in doc if k in ('on', True)]) )})")
    return files


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            failures.append(f"README: stray closing </{tag}>")
            return
        if self.stack[-1] != tag:
            failures.append(f"README: </{tag}> closes <{self.stack[-1]}> (unbalanced HTML)")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def check_readme():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    p = Balance()
    p.feed(text)
    p.close()
    if p.stack:
        failures.append(f"README: unclosed tags {p.stack}")

    required = [
        # original GitSkins sections (must stay untouched)
        "## Header", "## About Me", "## Skills", "## GitHub Stats", "## Projects",
        "## Connect", "## Streak",
        # appended sections
        "## Contribution Activity", "## Stats & Languages", "## Tech Stack",
        "## Featured Repositories", "## Links & Contact", "## Automation & Setup",
    ]
    for section in required:
        if section not in text:
            failures.append(f"README: missing section {section!r}")

    for ref in set(re.findall(r'src="((?!https?:)[^"]+)"', text)):
        target = ROOT / ref
        if not target.is_file():
            failures.append(f"README: local asset missing -> {ref}")
        else:
            print(f"  asset OK: {ref} ({target.stat().st_size} bytes)")

    for pattern in ("ghp_", "github_pat_", "AKIA", "sk-", "BEGIN RSA", "password="):
        if pattern in text:
            failures.append(f"README: possible secret pattern {pattern!r}")
    return text


def check_workflow_expectations():
    wf = (ROOT / ".github" / "workflows" / "snake.yml").read_text(encoding="utf-8")
    for needle in ("vickyhubhai", "target_branch: output", "workflow_dispatch", "github-contribution-grid-snake-dark.svg"):
        if needle not in wf:
            failures.append(f"snake.yml: expected content missing -> {needle}")
    if "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" not in wf:
        failures.append("snake.yml: GITHUB_TOKEN env missing")
    if "github_user_name" not in wf:
        failures.append("snake.yml: github_user_name missing")


if __name__ == "__main__":
    print("1) workflow YAML")
    check_yaml()
    print("2-5) README structure, assets, secrets")
    check_readme()
    check_workflow_expectations()
    print()
    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL LOCAL CHECKS PASSED")

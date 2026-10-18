"""Verify every external URL referenced from README.md actually resolves.

Also validates that the self-hosted banner is well-formed XML.
Run: python scripts/check_links.py
"""
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
UA = {"User-Agent": "profile-link-check"}

urls = set(re.findall(r'https?://[^\s"\'<>\)]+', README))
urls = {u.rstrip(".,") for u in urls}
# strip surrounding markdown/html leftovers
urls = {u.replace("&amp;", "&") for u in urls}


def head(url: str, attempts: int = 3):
    """GET `url` with a couple of retries: badge services occasionally drop TLS handshakes."""
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=UA, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                ctype = resp.headers.get("Content-Type", "")
                return url, resp.status, ctype, None
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(1.5 * (attempt + 1))
    return url, None, None, last


bad = []
with ThreadPoolExecutor(max_workers=8) as pool:
    for url, status, ctype, err in pool.map(head, sorted(urls)):
        if err or status != 200:
            bad.append((url, err or f"HTTP {status}"))
            print(f"  FAIL  {status or 'ERR':>4}  {url}  {err or ''}")
        else:
            print(f"  ok    {status:>4}  {ctype.split(';')[0]:<24} {url}")

try:
    ET.parse(ROOT / "assets" / "banner.svg")
    print("  ok      SVG    assets/banner.svg is well-formed XML")
except ET.ParseError as exc:
    bad.append(("assets/banner.svg", str(exc)))
    print(f"  FAIL  SVG invalid: {exc}")

print()
print(f"{len(urls)} external URLs checked, {len(bad)} problem(s)")
if bad:
    for url, why in bad:
        print("  -", url, "->", why)
    sys.exit(1)
print("ALL LINKS RESOLVE")

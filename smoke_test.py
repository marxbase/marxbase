#!/usr/bin/env python3
"""Smoke test of a LIVE MarxBase site (a network call; read-only GET requests only).

  python3 smoke_test.py https://marxbase.org/          (or the GitHub Pages address)

Crawls every internal link from the home page and checks: all pages answer 200; the hosted-build rules hold (security policy meta tag, no
test pages or gate files, the report form is configured and points only at the Supabase address); data.js and the two zip files download and
are valid zips (no private folder, no config or form code in the offline copy); no e-mail addresses appear in the data files.
"""
import io
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

EMAIL = re.compile(rb"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for k in ("href", "src"):
            if d.get(k):
                self.refs.append(d[k])


def get(url, tries=3):
    """GET with a short retry on network errors (a status of 0 means the request itself failed, not that the page is missing)."""
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": "marxbase-smoke-test"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, b"", {}
        except (urllib.error.URLError, OSError) as e:
            last = str(e).encode()
            time.sleep(1 + attempt)
    return 0, last, {}


def main(base):
    base = base.rstrip("/") + "/"
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(("PASS  " if ok else "FAIL  ") + name + (f"   ({detail})" if detail and not ok else ""))

    st, body, hdr = get(base)
    check("home page answers 200", st == 200, st)
    home = body.decode("utf-8", "replace")
    check("home page has the hosted-build security policy", "Content-Security-Policy" in home)
    m = re.search(r"connect-src 'self' (https://[\w.-]+)", home)
    check("security policy allows only the Supabase address for connections", bool(m), "no connect-src")
    st, cfg, _ = get(base + "config.js")
    check("report form configuration is present", st == 200 and b"supabaseUrl" in cfg and b"supabaseAnonKey" in cfg, st)
    check("configuration holds a publishable key, never a secret key", b"sb_secret_" not in cfg and b"service_role" not in cfg)
    if m and cfg:
        check("configuration and policy name the same Supabase project", m.group(1).encode() in cfg)
    for path in ("tests.html", "tests.js", "expected.js", "gate/GATE_ANSWERS.md", "gate/GATE_QUESTIONS.md"):
        check(f"{path} is not published", get(base + path)[0] == 404)

    # crawl
    seen, queue, bad = set(), [base], []
    while queue:
        batch, queue = queue, []
        batch = [u for u in batch if u not in seen]
        seen.update(batch)
        with ThreadPoolExecutor(8) as ex:
            fetched = list(ex.map(get, batch))
        for url, (st, body, h) in zip(batch, fetched):
            if st != 200:
                bad.append((url, st))
                continue
            if url.endswith(".html") or url.endswith("/"):
                p = Refs()
                p.feed(body.decode("utf-8", "replace"))
                for ref in p.refs:
                    if re.match(r"(https?:|mailto:|#|data:)", ref):
                        continue
                    target = urllib.parse.urldefrag(urllib.parse.urljoin(url, ref))[0].split("?")[0]
                    if target.startswith(base) and target not in seen:
                        queue.append(target)
    check(f"crawled {len(seen)} internal URLs and all answer 200", not bad, bad[:5])

    # downloads
    st, body, _ = get(base + "downloads.html")
    zips = sorted(set(re.findall(r'href="(downloads/[^"]+\.zip)"', body.decode("utf-8", "replace"))))
    check("Downloads page lists the data zip and the offline zip", len(zips) == 2, zips)
    for z in zips:
        st, data, _ = get(base + z)
        ok = st == 200 and zipfile.is_zipfile(io.BytesIO(data))
        check(f"{z} downloads and is a valid zip ({len(data) // 1024} KB)", ok, st)
        if ok:
            zf = zipfile.ZipFile(io.BytesIO(data))
            names = zf.namelist()
            check(f"{z} has no private folder", not [n for n in names if "private" in n])
            if "offline" in z:
                check("offline copy has no report form, keys or test pages", not [n for n in names if n.endswith(("config.js", "suggest.js", "tests.html", "expected.js"))])
            else:
                check("data zip has the licence notice and checksums", any(n.endswith("LICENCE.txt") for n in names) and any(n.endswith("SHA256SUMS") for n in names))
                blob = b"".join(zf.read(n) for n in names if n.endswith((".csv", ".json", ".md")))
                check("data zip contains no e-mail addresses", not EMAIL.search(blob))
    st, data, _ = get(base + "data.js")
    check("data.js loads and holds no e-mail addresses", st == 200 and data.startswith(b"window.MARXBASE") and not EMAIL.search(data), st)
    print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "https://marxbase.org/"))

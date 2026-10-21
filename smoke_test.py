#!/usr/bin/env python3
"""Smoke test of a LIVE MarxBase site (a network call; read-only GET requests only).

  python3 smoke_test.py https://marxbase.org/          (or the GitHub Pages address)
  python3 smoke_test.py https://marxbase.org/ --full   (every page; slow, and the host may answer 429 "too many requests" if you run it twice in a row)

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


MAX_SECONDS = 900     # the crawl gives up (and says so) after this long, so a test can never hang
PAUSE = 0.15          # seconds between requests per connection (GitHub Pages answers 429 to a fast crawler)


def get(url, tries=8):
    """GET with a short retry on network errors (a status of 0 means the request itself failed, not that the page is missing)."""
    for attempt in range(tries):
        time.sleep(PAUSE)
        req = urllib.request.Request(url, headers={"User-Agent": "marxbase-smoke-test"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < tries - 1:        # the host asks us to slow down: wait as long as it says (or a few seconds) and try again
                try:
                    wait = float(e.headers.get("Retry-After", ""))
                except ValueError:
                    wait = 5.0
                time.sleep(min(wait, 60) + attempt)
                continue
            return e.code, b"", {}
        except (urllib.error.URLError, OSError) as e:
            last = str(e).encode()
            time.sleep(1 + attempt)
    return 0, last, {}


def main(base, full=False):
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
    seen, queue, bad, started, fetched_count = set(), [base], [], time.time(), []
    while queue:
        batch, queue = queue, []
        if time.time() - started > MAX_SECONDS:
            bad.append(("time limit reached", 0))
            break
        batch = [u for u in dict.fromkeys(batch) if u not in seen]
        seen.update(batch)                                      # everything found counts as seen, so a skipped page is not queued again
        if not full:                                           # a polite default: every list and information page, but only a sample of the detail pages
            detail = sorted(u for u in batch if re.search(r"/(result|gene|paper|strain|product)/[^/]+\.html$", u))
            keep = set(detail[:: max(1, len(detail) // 60)])
            batch = [u for u in batch if u not in detail or u in keep]
        with ThreadPoolExecutor(2) as ex:
            fetched = list(ex.map(get, batch))
        fetched_count.extend(batch)
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
    check(f"checked {len(fetched_count)} internal URLs (of {len(seen)} found) and all answer 200", not bad, bad[:5])

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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0] if args else "https://marxbase.org/", full="--full" in sys.argv))

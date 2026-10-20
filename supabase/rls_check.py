#!/usr/bin/env python3
"""Check the live suggestion table's security from the outside (a NETWORK call; run it only on your Supabase project).

  python3 supabase/rls_check.py        (from this folder; standard library only)

Uses the public key from site-config.json to act as an anonymous visitor, and the secret key from .env (never printed) only to read back and delete its own test rows. It proves that an anonymous visitor can insert a valid suggestion and
can NOT read, change or delete anything, set the status, or send malformed or oversized rows.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def settings():
    """SUPABASE_URL and SUPABASE_SERVICE_KEY from the environment, or from a .env file in the current or parent folder (never printed)."""
    import os
    env = dict(os.environ)
    for folder in (Path.cwd(), Path.cwd().parent, HERE, HERE.parent):
        f = folder / ".env"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    env.setdefault(k.strip(), v.strip().strip("'\""))
            break
    url, key = env.get("SUPABASE_URL", "").rstrip("/"), env.get("SUPABASE_SERVICE_KEY", "")
    if not url.startswith("https://") or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY (in the environment or a .env file in this or the parent folder).")
    return url, key

TAG = "RLS-CHECK"
GOOD = {"kind": "error_report", "page_type": "result", "target_id": "MARXBASE-R000001", "release_version": "rls-check", "comment": TAG + " valid row"}


def call(url, key, method, path, body=None, prefer=None):
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):                      # old-style JWT keys also go in Authorization; the newer sb_ keys do not
        headers["Authorization"] = f"Bearer {key}"
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(url + path, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def main() -> int:
    cfg = json.loads((HERE / "site-config.json").read_text(encoding="utf-8"))
    url, anon = cfg["supabaseUrl"].rstrip("/"), cfg["supabaseAnonKey"]
    svc_url, svc = settings()
    if svc_url != url:
        sys.exit("site-config.json and .env point at DIFFERENT Supabase projects; fix one so they match, then run again (nothing was sent).")
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(("PASS  " if ok else "FAIL  ") + name + (f"   ({detail})" if detail and not ok else ""))

    st, _ = call(url, anon, "POST", "/rest/v1/suggestion", GOOD, "return=minimal")
    check("anonymous visitor can insert a valid suggestion", st in (200, 201), st)
    st, body = call(url, anon, "POST", "/rest/v1/suggestion", {**GOOD, "status": "accepted", "comment": TAG + " status"}, "return=minimal")
    check("anonymous visitor cannot set the status column", st >= 400, st)
    for name, bad in (("an unknown kind", {"kind": "delete_everything"}), ("an empty target", {"target_id": ""}), ("a 2001-character comment", {"comment": TAG + "x" * 2001}),
                      ("a too-short comment", {"comment": "ab"}), ("an unknown page type", {"page_type": "admin"})):
        st, _ = call(url, anon, "POST", "/rest/v1/suggestion", {**GOOD, **bad}, "return=minimal")
        check(f"{name} is refused", st >= 400, st)
    st, body = call(url, anon, "GET", "/rest/v1/suggestion?select=*")
    check("anonymous visitor cannot read suggestions", st >= 400 or body == [], f"{st} {str(body)[:80]}")
    st, body = call(url, anon, "PATCH", "/rest/v1/suggestion?id=gt.0", {"status": "accepted"}, "return=representation")
    check("anonymous visitor cannot update suggestions", st >= 400 or body == [], f"{st} {str(body)[:80]}")
    st, body = call(url, anon, "DELETE", "/rest/v1/suggestion?id=gt.0", None, "return=representation")
    check("anonymous visitor cannot delete suggestions", st >= 400 or body == [], f"{st} {str(body)[:80]}")
    st, rows = call(svc_url, svc, "GET", f"/rest/v1/suggestion?select=id,status,comment&comment=like.{TAG}*")
    mine = rows if isinstance(rows, list) else []
    check("the valid test row is stored and still open (nothing was changed or deleted)", len(mine) == 1 and mine[0]["status"] == "open", f"{st} {mine}")
    st, _ = call(svc_url, svc, "DELETE", f"/rest/v1/suggestion?comment=like.{TAG}*")
    print(f"cleanup: removed the test rows (status {st})")
    print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED: do not publish until fixed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

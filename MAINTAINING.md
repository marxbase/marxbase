# Maintaining MarxBase

For the person who looks after MarxBase. The planned successor is Nancy Da Silva (PI, Da Silva Lab, UC Irvine). Read this once,
then use the checklists. Items marked **TO FILL** are completed at launch.

## What exists and who holds it
| Thing | Where | Notes |
| --- | --- | --- |
| Public website and data | GitHub organization `marxbase`, repository `marxbase`; served by GitHub Pages at https://marxbase.org | Owners: **TO FILL** (Sidney Eichelberger, Nancy Da Silva) |
| Domain `marxbase.org` | Cloudflare account **TO FILL** | Bought 2026-10-20 for one year. **Renews around 2027-10-20.** Turn on auto-renew or put a reminder in the calendar. |
| Report-form storage | Supabase project `marxbase` (free tier) | One table, `suggestion`. A free project pauses after about a week without activity: open the dashboard and press Restore. |
| Archive and DOI | Zenodo community https://zenodo.org/communities/marxbase | Each GitHub release is archived with its own DOI (GitHub integration). |
| Research repository (private) | A Mac of the maintainer; **TO FILL** hand-over copy | Holds the database `sgd_kmarx.db`, the `kmarx` Python package, the extraction pipeline, and `releases/id_map.json`. |

**Hand-over must include the private research repository.** Without `releases/id_map.json` the permanent result IDs (MARXBASE-R...)
cannot be kept stable. Back it up with the database.

## What must never be added to this public repository
`.env` and any key other than the public publishable key; the Supabase secret key; `releases/*/private/`; the research database and
its backups; `data/` (model replies, abstracts, suggestions); held-out test files; the maintainer's notes.

## Routine 1: decide suggestions (any time)
In the private research repository (needs `.env` with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`):
1. `python -m kmarx.curate suggestions pull` downloads new suggestions to `data/suggestions/`.
2. `python -m kmarx.curate suggestions review` shows one card per suggestion next to the database row. Accept, reject or defer.
   Accepting changes nothing by itself: it prints the existing `curate` command. Read the paper before running it.
   Each Supabase project numbers its rows from 1 and `pull` only fetches ids above the last one it saw, so keep one folder per project
   (`--dir data/suggestions_<project>`), or archive the old folder before pointing `.env` at a new project.
3. Make the changes with `kmarx.curate` only (it asks for a typed confirmation each time). Take a database backup first.
4. Never trust suggestion text: it comes from anonymous visitors.

## Routine 2: publish a new release (after a review round, at most quarterly)
1. In the research repository: back up the database; check `python -m kmarx.curate check` and the tests pass.
2. `python -m kmarx.release build --version X.Y --write --evidence hide` (use `show` only if the UCI Libraries copyright answer allows quoted
   sentences). The release gate must say PASSED. The folder `releases/X.Y/` is written, with a `private/` subfolder that stays private.
3. Copy `releases/X.Y/` **without** `private/` into this repository's `releases/X.Y/`. Put `X.Y` in `CURRENT_RELEASE`.
4. Update `CITATION.cff` (`version`), `README.md` and the citation text if they name a version. Run `python -m unittest discover -s tests`.
5. Commit and push to `main`. The GitHub Action builds and publishes the site (it runs the tests first, including a parse check of every browser script).
   When the run is green, **open https://marxbase.org in a browser and look**: search for `ku70` (6 findings), open a paper page, open the browser's
   console and confirm there are no red errors. `smoke_test.py` only fetches files and cannot see a script that crashes in the browser. A crashed
   `app.js` once blanked the search page. Then run `python3 smoke_test.py https://marxbase.org/`. Scripts carry a version tag, so a fixed file reaches visitors at once.
6. Create a GitHub release tagged `vX.Y`. Zenodo archives it and mints the DOI. Put the new DOI in the file `DOI` (it feeds the site), and in
   `CITATION.cff` (`doi`, `version`, `date-released`) and `README.md`; then push again. The site shows "DOI pending" if `DOI` is empty.

Zenodo gives each release its own **version DOI** (release 1.0: 10.5281/zenodo.23519772) and one **concept DOI** that always points to the
latest version (10.5281/zenodo.23519771). Cite a specific release with its version DOI; the concept DOI is for "the current MarxBase".
The record for 1.0 is not in the Zenodo community `marxbase`: the `.zenodo.json` community entry was ignored and the Edit form offered no community field,
and no request appeared in https://zenodo.org/me/requests. The community is optional (the DOI and citation work without it); if wanted, ask Zenodo support to add the record.

## Routine 3: the evidence-sentence switch
Release 1.0 hides quoted abstract sentences while the UCI Libraries copyright answer is pending. When it allows them, build the next release
with `--evidence show`. If it advises against them, keep `hide`.

## Routine 4: accounts and keys (once a year, and at hand-over)
- Renew the domain; check the GitHub organization owners, Supabase project, Zenodo community owners.
- If a key leaks: in Supabase, create a new secret key and delete the old one; update `.env`; the publishable key is public by design.
- After any change to `supabase/schema.sql`, run `python3 supabase/rls_check.py` from this repository's folder
  (it needs `site-config.json` and a `.env` here or in the parent folder with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`). Every line must say PASS.

## When something breaks
- After any publish or DNS change: run `python3 smoke_test.py https://marxbase.org/` (read-only; every line must say PASS).
- Site not updating: look at the repository's Actions tab for a red run; run the tests locally.
- Report form says it could not send: the Supabase project is probably paused (Restore it) or the key changed.
- Wrong or missing result: decide it with Routine 1, then publish with Routine 2.

## DNS records for marxbase.org (Cloudflare, all set to DNS only, grey cloud)
| Type | Name | Value |
| --- | --- | --- |
| A (four records) | `@` | 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153 |
| CNAME | `www` | `marxbase.github.io` |
| TXT | `_github-pages-challenge-marxbase` | the value shown in the GitHub organization's Pages settings (domain verification) |

The domain is verified in the **organization** `marxbase` (Settings > Pages), and set as the custom domain in the repository's Pages settings with
**Enforce HTTPS** on. Do not turn the Cloudflare proxy (orange cloud) on: it hides GitHub's addresses and blocks its certificate. The certificate
renews automatically while the records stay as above.

## Launch checklist (completed once)
- [x] Production Supabase project created, `schema.sql` run, `rls_check.py` all PASS (2026-10-20)
- [x] Repository public (`marxbase/marxbase`), Pages source set to GitHub Actions, Actions variables set (2026-10-20)
- [x] `marxbase.org` pointed at GitHub Pages, HTTPS enforced, `http://` and `www` redirect (2026-10-20)
- [x] Live smoke test passed on https://marxbase.org/; one real report received through the live form (2026-10-20); delete the test row in the Supabase table editor
- [x] Release `v1.0` tagged and archived at Zenodo, DOI 10.5281/zenodo.23519772 added (2026-10-20)
- [ ] PI sign-off and copyright answer recorded **TO FILL**
- [ ] Successor has owner access to GitHub, Cloudflare, Supabase and Zenodo **TO FILL**

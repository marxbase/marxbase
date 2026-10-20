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
3. Make the changes with `kmarx.curate` only (it asks for a typed confirmation each time). Take a database backup first.
4. Never trust suggestion text: it comes from anonymous visitors.

## Routine 2: publish a new release (after a review round, at most quarterly)
1. In the research repository: back up the database; check `python -m kmarx.curate check` and the tests pass.
2. `python -m kmarx.release build --version X.Y --write --evidence hide` (use `show` only if the UCI Libraries copyright answer allows quoted
   sentences). The release gate must say PASSED. The folder `releases/X.Y/` is written, with a `private/` subfolder that stays private.
3. Copy `releases/X.Y/` **without** `private/` into this repository's `releases/X.Y/`. Put `X.Y` in `CURRENT_RELEASE`.
4. Update `CITATION.cff` (`version`), `README.md` and the citation text if they name a version. Run `python -m unittest discover -s tests`.
5. Commit and push to `main`. The GitHub Action builds and publishes the site. Check https://marxbase.org.
6. Create a GitHub release tagged `vX.Y`. Zenodo archives it and mints the DOI. Add the DOI to `CITATION.cff`, `README.md` and the
   Downloads text, and push again.

## Routine 3: the evidence-sentence switch
Release 1.0 hides quoted abstract sentences while the UCI Libraries copyright answer is pending. When it allows them, build the next release
with `--evidence show`. If it advises against them, keep `hide`.

## Routine 4: accounts and keys (once a year, and at hand-over)
- Renew the domain; check the GitHub organization owners, Supabase project, Zenodo community owners.
- If a key leaks: in Supabase, create a new secret key and delete the old one; update `.env`; the publishable key is public by design.
- After any change to `supabase/schema.sql`, run `python3 supabase/rls_check.py` from this repository's folder
  (it needs `site-config.json` and a `.env` here or in the parent folder with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`). Every line must say PASS.

## When something breaks
- Site not updating: look at the repository's Actions tab for a red run; run the tests locally.
- Report form says it could not send: the Supabase project is probably paused (Restore it) or the key changed.
- Wrong or missing result: decide it with Routine 1, then publish with Routine 2.

## Launch checklist (completed once)
- [ ] Production Supabase project created, `schema.sql` run, `rls_check.py` all PASS **TO FILL**
- [ ] Repository public, Pages source set to GitHub Actions, Actions variables set **TO FILL**
- [ ] `marxbase.org` pointed at GitHub Pages, HTTPS enforced **TO FILL**
- [ ] Live smoke test passed; one real report received and deleted **TO FILL**
- [ ] Release `v1.0` tagged, DOI added **TO FILL**
- [ ] PI sign-off and copyright answer recorded **TO FILL**
- [ ] Successor has owner access to GitHub, Cloudflare, Supabase and Zenodo **TO FILL**

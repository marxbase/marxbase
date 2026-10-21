# MarxBase

MarxBase is a searchable, citable collection of gene–phenotype results for *Kluyveromyces marxianus* metabolic engineering.
Each result was extracted from a published paper's abstract and checked by a person. The site is a static website; the data
are released as versioned snapshots.

- Website: https://marxbase.org
- Cite: Eichelberger S. MarxBase: gene–phenotype results for *Kluyveromyces marxianus* metabolic engineering, release 1.1. 2026. https://doi.org/10.5281/zenodo.23548295
  (the version DOI of release 1.1; https://doi.org/10.5281/zenodo.23519771 always points to the latest release; `CITATION.cff` has the same reference).
- Report a problem or suggest a change: use "Report or suggest" on any result, gene, paper or strain page.
- Made in the Da Silva Lab, University of California, Irvine. Home page photograph of *K. marxianus* colonies: © Sidney Eichelberger.

## What is in this repository
| Path | What it is |
| --- | --- |
| `releases/<version>/` | The released data bundle (CSV, SQLite, CSL-JSON, data dictionary, checksums). Public files only. |
| `build.py`, `pages.py`, `src/` | The site generator (Python standard library only) and the browser code (plain JavaScript). |
| `supabase/` | The one-table schema for the report form and a security check. |
| `tests/`, `src/tests.js` | Generator tests and in-browser tests of the search and export code. |
| `MAINTAINING.md` | How to run a release, decide suggestions, and keep the accounts alive. |

The research database, extraction pipeline, held-out test sets and model outputs are not part of this repository.

## Build and test locally
```
python3 build.py --bundle releases/1.0 --out dist        # add --public for the hosted build (policy on, no test pages)
python3 serve.py 8765                                    # then open http://localhost:8765
python3 -m unittest discover -s tests                    # generator tests
```
Open `http://localhost:8765/tests.html` (not in the `--public` build) for the in-browser tests. To switch on the report form
locally, copy `site-config.example.json` to `site-config.json` and add your Supabase project URL and its public (publishable) key.
Never put a secret or service key in that file.

## Licences
- Data: Creative Commons Attribution 4.0 (CC BY 4.0), see `DATA_LICENCE.md`.
- Code: MIT, see `LICENSE`.
- Quoted evidence sentences, when a release includes them, are third-party text and are not covered by the data licence.

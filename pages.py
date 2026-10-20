"""MarxBase session-4 pages: Summary (charts as inline SVG), Methods, Downloads, and the two zip files.
Standard library only. Charts count FINDINGS (a multi-gene combination counted once) in K. marxianus hosts only."""
import html
import io
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

HOME = "K. marxianus"
CLASSES = ["positive", "negative", "context-dependent"]
FILL = {"positive": "#2a78d6", "negative": "#eb6834", "context-dependent": "#1baf7a"}   # also set as attributes so charts keep their colour even if the stylesheet is stale or blocked
CLASS_NAME = {"positive": "Positive", "negative": "Negative", "context-dependent": "Context-dependent"}
ZIP_TIME = (2026, 1, 1, 0, 0, 0)          # fixed so a rebuild of identical content gives identical zip bytes
DEV_FILES = {"tests.html", "tests.js", "expected.js"}
OFFLINE_SKIP = {"config.js", "suggest.js"}        # the offline copy has no report form and no keys


def strip_report_form(text: str) -> str:
    text = re.sub(r'<section id="suggest-box"[^>]*></section>', "", text)
    return re.sub(r'<script src="[^"]*(?:config|suggest)\.js"></script>', "", text)


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def pretty(s) -> str:
    return (s or "").replace("_", " ")


# ----------------------------------------------------------------------------------------- numbers
def km_findings(site) -> list:
    """One entry per finding with at least one row in a K. marxianus host: (first row, all rows)."""
    out = []
    for fid, rows in site.findings.items():
        if any(r["host_organism"] == HOME for r in rows):
            out.append((rows[0], rows))
    return out


def chart_data(site) -> dict:
    fs = km_findings(site)
    cat = defaultdict(Counter)
    for r0, rows in fs:
        cat[r0["phenotype_category"]][r0["result_class"]] += 1
    types = defaultdict(Counter)
    for r0, rows in fs:
        for t in {r["intervention_type"] for r in rows}:
            types[t][r0["result_class"]] += 1
    prod = defaultdict(Counter)
    for r0, rows in fs:
        if r0["product"]:
            prod[r0["product"]][r0["result_class"]] += 1
    papers_year = Counter()
    seen = set()
    for r0, rows in fs:
        if r0["pmid"] not in seen:
            seen.add(r0["pmid"])
            papers_year[int(site.papers[r0["pmid"]]["year"] or 0)] += 1
    return {"n": len(fs), "n_papers": len(seen), "cat": cat, "types": types, "prod": prod, "years": papers_year}


# ----------------------------------------------------------------------------------------- SVG
def _legend() -> str:
    return "".join(f'<span class="lg"><svg width="12" height="12" aria-hidden="true"><rect width="12" height="12" rx="2" class="seg-{c}" fill="{FILL[c]}"/></svg> {CLASS_NAME[c]}</span>' for c in CLASSES)


def hbars(rows: list, label_w: int = 250, width: int = 720, bar_h: int = 18, gap: int = 8, names: dict = None) -> str:
    names = names or CLASS_NAME
    """rows = [(label, {class: n})]; stacked horizontal bars, total printed at the end of each bar."""
    mx = max((sum(c.values()) for _, c in rows), default=1) or 1
    plot_w = width - label_w - 50
    h = len(rows) * (bar_h + gap) + 6
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" class="viz" focusable="false">']
    for i, (label, cnt) in enumerate(rows):
        y = 3 + i * (bar_h + gap)
        out.append(f'<text x="{label_w - 8}" y="{y + bar_h - 5}" text-anchor="end" class="axl" font-size="12" fill="#52514e">{esc(label)}</text>')
        x = label_w
        for c in CLASSES:
            n = cnt.get(c, 0)
            if not n:
                continue
            w = max(n / mx * plot_w, 1)
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="{bar_h}" rx="2" class="seg-{c}" fill="{FILL[c]}"><title>{esc(label)}: {n} {names[c].lower()}</title></rect>')
            x += w
        out.append(f'<text x="{x + 4:.1f}" y="{y + bar_h - 5}" class="val" font-size="12" fill="#1a1a1a">{sum(cnt.values())}</text>')
    out.append("</svg>")
    return "".join(out)


def columns(years: dict, width: int = 720, height: int = 220) -> str:
    ys = list(range(min(years), max(years) + 1))
    mx = max(years.values())
    left, bottom, top = 34, 26, 14
    plot_w, plot_h = width - left - 8, height - bottom - top
    step = plot_w / len(ys)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" class="viz" focusable="false">']
    for tick in range(0, mx + 1, 4 if mx > 8 else 2):
        y = top + plot_h - tick / mx * plot_h
        out.append(f'<line x1="{left}" x2="{width - 8}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{left - 5}" y="{y + 4:.1f}" text-anchor="end" class="axl">{tick}</text>')
    for i, yr in enumerate(ys):
        n = years.get(yr, 0)
        x = left + i * step
        if n:
            hh = n / mx * plot_h
            out.append(f'<rect x="{x + 1:.1f}" y="{top + plot_h - hh:.1f}" width="{max(step - 3, 1):.1f}" height="{hh:.1f}" rx="2" class="seg-positive" fill="{FILL["positive"]}"><title>{yr}: {n} papers</title></rect>')
        if yr % 5 == 0 or yr in (ys[0], ys[-1]):
            out.append(f'<text x="{x + step / 2:.1f}" y="{height - 8}" text-anchor="middle" class="axl">{yr}</text>')
    out.append("</svg>")
    return "".join(out)


def table(headers: list, rows: list) -> str:
    return ("<details><summary class=\"small\">Show as a table</summary><table class=\"kv\"><thead><tr>" + "".join(f"<th scope=\"col\">{esc(h)}</th>" for h in headers) +
            "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></details>")


def build_summary(site) -> str:
    d = chart_data(site)
    cats = sorted(d["cat"].items(), key=lambda kv: -sum(kv[1].values()))
    c1 = [(pretty(k), v) for k, v in cats]
    top_cat, top_n = c1[0][0], sum(c1[0][1].values())
    types = sorted(d["types"].items(), key=lambda kv: -sum(kv[1].values()))
    c2 = []
    for k, v in types:
        tot = sum(v.values())
        c2.append((pretty(k), tot, tot - v.get("positive", 0)))
    prods = sorted(d["prod"].items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:12]
    yrs = d["years"]
    total_cls = Counter()
    for v in d["cat"].values():
        total_cls.update(v)

    # chart 2: share that is not positive, drawn as stacked "positive vs not" bars with counts
    t_rows = [(f"{k} (n={tot})", {"positive": tot - bad, "negative": bad}) for k, tot, bad in c2]
    body = (
        f'<h1>Summary</h1><p>What the collection holds, counting <strong>findings in <em>K. marxianus</em> host organisms only</strong> '
        f'({d["n"]} findings from {d["n_papers"]} papers; release {esc(site.version)}). A multi-gene combination is one finding. '
        f'These charts describe what abstracts report, which is not the same as what is true of the species: negative results are rarely reported.</p>'
        f'<p class="legend" aria-hidden="true">{_legend()}</p>'
        f'<h2>Findings per phenotype category</h2>'
        f'<p class="small">{total_cls["positive"]} positive, {total_cls["negative"]} negative and {total_cls["context-dependent"]} context-dependent findings. '
        f'The largest category is {esc(top_cat)} with {top_n} findings.</p>'
        f'<figure>{hbars(c1)}<figcaption class="small">Findings per phenotype category, split by result class.</figcaption></figure>'
        + table(["Category", "Positive", "Negative", "Context-dependent", "Total"], [(k, v.get("positive", 0), v.get("negative", 0), v.get("context-dependent", 0), sum(v.values())) for k, v in c1])
        + '<h2>How often a type of change did not simply help</h2>'
        f'<p class="small">For each type of genetic change, the findings that were negative or context-dependent (orange) against positive ones (blue). '
        f'A combination counts under each type it contains, so the totals add up to more than {d["n"]}. Small counts mean wide uncertainty.</p>'
        f'<figure>{hbars(t_rows, names={**CLASS_NAME, 'negative': 'negative or context-dependent'})}<figcaption class="small">Positive findings versus negative or context-dependent findings, by type of change.</figcaption></figure>'
        + table(["Type of change", "Findings", "Negative or context-dependent", "Share"], [(k, tot, bad, f"{bad / tot:.0%}") for k, tot, bad in c2])
        + '<h2>Papers per year</h2>'
        f'<p class="small">Papers with at least one finding in a <em>K. marxianus</em> host, by publication year ({min(yrs)}–{max(yrs)}; {max(yrs.values())} at most in a year).</p>'
        f'<figure>{columns(yrs)}<figcaption class="small">Number of papers per publication year.</figcaption></figure>'
        + table(["Year", "Papers"], [(y, yrs.get(y, 0)) for y in range(min(yrs), max(yrs) + 1)])
        + '<h2>Most studied products</h2>'
        '<p class="small">The twelve products with the most findings, split by result class.</p>'
        f'<figure>{hbars([(k, v) for k, v in prods])}<figcaption class="small">Findings per product, split by result class.</figcaption></figure>'
        + table(["Product", "Positive", "Negative", "Context-dependent", "Total"], [(k, v.get("positive", 0), v.get("negative", 0), v.get("context-dependent", 0), sum(v.values())) for k, v in prods])
    )
    # accessible names for the SVGs
    names = ["Findings per phenotype category", "Positive versus negative or context-dependent findings by type of change", "Papers per year", "Findings per product"]
    parts = body.split('class="viz"')
    body = "".join(p + (f'class="viz" aria-label="{esc(names[i])}"' if i < len(names) else "") for i, p in enumerate(parts))
    return body


# ----------------------------------------------------------------------------------------- methods
def build_methods(site) -> str:
    n_res, n_papers = len(site.results), len(site.papers)
    return f"""<h1>Methods</h1>
<p class="weak"><strong>Draft for the curators to edit.</strong> This page was drafted from the project notes; check every figure before the site is published.</p>
<h2>Where the papers come from</h2>
<p>Papers were found in PubMed with the broad query <code>("Kluyveromyces marxianus"[All Fields] OR "K. marxianus"[All Fields])</code>, followed by screening for papers about genetic or metabolic engineering. Only the title and abstract of each paper are read; full texts are not.</p>
<h2>How results were extracted</h2>
<p>A large language model (Claude Sonnet) read each abstract with a fixed written prompt (version 5) and returned structured results: the gene, the type of change (for example knockout, overexpression, point mutation), the effect, the phenotype, any stated numbers, the host organism and strain, and the sentence in the abstract that supports it. Each result was then reviewed by a person before it was accepted. Results marked <em>manual</em> were entered by a curator.</p>
<h2>Gene identifiers</h2>
<p>Gene names were matched to the <em>K. marxianus</em> DMKU3-1042 genome (RefSeq GCF_001417885.1) and given KLMA_ locus tags. Where a name matches several copies and the paper does not say which was used, the gene is marked <em>undetermined paralog</em>. <em>S. cerevisiae</em> orthologs were assigned by reciprocal BLAST against SGD. Names that are enzyme or protein labels rather than gene symbols are kept but marked, and have no locus tag.</p>
<h2>Strains, products and conditions</h2>
<p>Strain names were merged only when sources (culture collections and papers) show they are the same strain. Derived strains are shown under their parent strain. Products are grouped into classes. Culture conditions are recorded only when the abstract states them.</p>
<h2>How accurate is it?</h2>
<ul>
<li>Of the first 465 rows the model proposed, 95.5% were accepted by the reviewer. This says little about missing results.</li>
<li>In a re-run on papers whose results people had already found, the current prompt recovered about 72% of results exactly and about 83% at the level of gene and effect. This figure is optimistic because the prompt was tuned on the same papers.</li>
<li>On the first set of papers held back from tuning, recall was 0.82 and precision 0.82 (0.88 and 0.98 after adjudication). On a second held-back set, which contained very few results, the extraction found none of 3 results and invented none from 12 papers with no results; this set is too small to say more.</li>
<li>Gene identifier enrichment was reviewed with an accept-all default; no edits were made, so the review is weak evidence of correctness.</li>
</ul>
<h2>What is not captured</h2>
<ul>
<li>Anything stated only in the full text, figures or supplementary material.</li>
<li>Heterologous protein or enzyme expression and promoter or signal-sequence work are the weakest areas.</li>
<li>A strain is recorded for only about a third of results.</li>
<li>Negative results are rarely reported in abstracts.</li>
</ul>
<h2>This release</h2>
<p>Release {esc(site.version)} ({esc(site.date)}): {n_res} results from {n_papers} papers. Each release is a fixed, checked snapshot; see <a href="downloads.html">Downloads</a> for the data files and a data dictionary.</p>
"""


# ----------------------------------------------------------------------------------------- downloads and zips
LICENCE = """MarxBase data licence notice
============================
Data (the CSV, SQLite and JSON files): Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/
Code (the website generator and search code): MIT licence.

{evidence_note}
Cite MarxBase as: {citation}
"""

EVIDENCE_NOTE = """Exception: the "evidence_sentence" columns quote sentences from paper abstracts. That text belongs to the original authors
and publishers and is NOT covered by the data licence. Cite the original paper when you reuse it.
"""
NO_EVIDENCE_NOTE = "This release does not include quoted evidence sentences; every result links to its source paper.\n"


def doi_html(site) -> str:
    return f'DOI <a href="https://doi.org/{esc(site.doi)}">{esc(site.doi)}</a>.' if site.doi else "DOI pending."


def citation_text(site) -> str:
    return (f"Eichelberger S. MarxBase: gene–phenotype results for Kluyveromyces marxianus metabolic engineering, release {site.version}. "
            f"{site.date[:4]}. " + (f"https://doi.org/{site.doi}" if site.doi else "DOI pending."))


def data_zip_name(site) -> str:
    return f"marxbase-{site.version}-data.zip"


def offline_zip_name(site) -> str:
    return f"marxbase-{site.version}-offline-site.zip"


def make_zip(path: Path, files: list) -> None:
    """files = [(archive name, bytes)]; sorted and with fixed times so that identical content gives an identical zip."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files):
            zi = zipfile.ZipInfo(name, ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)


def build_data_zip(site) -> Path:
    folder = f"marxbase-{site.version}"
    files = []
    for p in sorted(site.bundle.iterdir()):
        if p.is_file():
            files.append((f"{folder}/{p.name}", p.read_bytes()))
    files.append((f"{folder}/LICENCE.txt", LICENCE.format(evidence_note=EVIDENCE_NOTE if site.has_evidence else NO_EVIDENCE_NOTE, citation=citation_text(site)).encode("utf-8")))
    out = site.out / "downloads" / data_zip_name(site)
    out.parent.mkdir(parents=True, exist_ok=True)
    make_zip(out, files)
    site.count += 1
    return out


def downloads_body(site, offline: bool) -> str:
    dz = data_zip_name(site)
    size = (site.out / "downloads" / dz).stat().st_size
    kb = lambda n: f"{n / 1024 / 1024:.1f} MB" if n > 1_000_000 else f"{n / 1024:.0f} KB"
    off = ""
    if not offline:
        oz = offline_zip_name(site)
        off = (f'<h2>Use MarxBase without internet</h2><p><a href="downloads/{esc(oz)}">{esc(oz)}</a> (about 2–3 MB) is a copy of this whole website. '
               f'Unzip it, open the folder and double-click <code>index.html</code>. Search, filters and downloads all work without a connection; '
               f'links to PubMed and DOIs need internet. If your browser blocks the search page from a local file, use Chrome, Firefox or Safari.</p>')
    return (f'<h1>Downloads</h1><p class="small">Release {esc(site.version)} ({esc(site.date)}). {doi_html(site)}</p>'
            f'<h2>Data files</h2><p><a href="downloads/{esc(dz)}">{esc(dz)}</a> ({kb(size)}) holds the results, genes, orthologs, strains, papers (without abstracts), '
            f'products and comparisons as CSV files that open in Excel, a SQLite database, citations in CSL-JSON, a data dictionary, checksums and a licence notice.</p>'
            f'<p>From the search page you can also download <strong>the results you are looking at</strong> as a CSV file, and export the papers behind them as references '
            f'(BibTeX, RIS, CSL-JSON, or formatted AMA, APA, MLA and NLM).</p>'
            f'{off}'
            f'<h2>Licence</h2><ul><li>Data: CC BY 4.0. Please cite MarxBase and the original papers.</li><li>Code: MIT.</li>'
            + ('<li>Evidence sentences quote paper abstracts and are not covered by the data licence.</li>' if site.has_evidence else '<li>This release does not include quoted evidence sentences; every result links to its paper.</li>') + '</ul>'
            + f'<h2>How to cite MarxBase</h2><p id="cite-self">{esc(citation_text(site))}</p>'
            f'<p class="small">The DOI will be added when the first release is archived at Zenodo.</p>'
            f'<h2>Cite a single paper or result</h2><p>Every paper page has a citation block, and every result page ends with “Cite as: MarxBase result …, release …”.</p>')


def build_offline_zip(site) -> Path:
    files = []
    for p in sorted(site.out.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(site.out).as_posix()
        if rel in DEV_FILES or rel in OFFLINE_SKIP or rel.startswith("gate/") or rel == "downloads.html" or rel == offline_zip_name(site) or rel == f"downloads/{offline_zip_name(site)}":
            continue
        data = p.read_bytes()
        if rel.endswith(".html"):
            data = strip_report_form(data.decode("utf-8")).encode("utf-8")
        files.append((f"marxbase-{site.version}-offline/{rel}", data))
    files.append((f"marxbase-{site.version}-offline/downloads.html", site.layout("Downloads", downloads_body(site, True), 0, "downloads").encode("utf-8")))
    files.append((f"marxbase-{site.version}-offline/START_HERE.txt", ("MarxBase offline copy\n\nOpen index.html (double-click it). Everything needed to search is in this folder.\n"
                                                                      "Links to PubMed and DOIs need internet.\n").encode("utf-8")))
    out = site.out / "downloads" / offline_zip_name(site)
    make_zip(out, files)
    site.count += 1
    return out

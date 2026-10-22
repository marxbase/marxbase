#!/usr/bin/env python3
"""MarxBase static site builder (Python standard library only; no network, no installs).

  python3 build.py --bundle ../releases/1.0 --out dist

Reads ONLY a released bundle (CSV files written by kmarx.release), never the research database, and writes a complete
static website: an interactive search page plus one stable page per gene, strain, paper, product and result.
User-derived text is HTML-escaped; only the pre-sanitised <i>, <sub>, <sup> markup is passed through.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import urllib.parse
import shutil
import sys
import pages
import species
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "src"
KIND_LABEL = {
    "locus_tagged": "Locus-tagged K. marxianus gene", "scerevisiae_gene": "S. cerevisiae gene", "undetermined_paralog": "Undetermined paralog",
    "enzyme_or_protein_label": "Enzyme or protein label, not a gene symbol", "heterologous_gene": "Heterologous gene",
    "unmapped_name": "Name without a genome identifier"}
KIND_HELP = {
    "undetermined_paralog": "K. marxianus has several copies of this gene and the papers do not say which one was used.",
    "enzyme_or_protein_label": "The paper's own name for an enzyme or protein, not an established gene symbol; no locus tag is assigned.",
    "unmapped_name": "No reliable genome identifier could be assigned to this name.",
    "heterologous_gene": "A gene from another species, expressed in the host recorded for each result."}
CLASS_LABEL = {"positive": "Positive", "negative": "Negative", "context-dependent": "Context-dependent"}
CLASS_ICON = {"positive": "+", "negative": "−", "context-dependent": "∼"}
QUAL = {"greater_than": "> ", "less_than": "< ", "approx": "≈ ", "exact": "", "": ""}
LIMITS = ("Results come from paper abstracts only. In a re-run on reviewed papers the extraction recovered roughly 72–83% of the results a person "
          "had found; it is weakest for heterologous protein or enzyme expression and promoter or signal-sequence work. A strain is recorded for "
          "only about a third of results.")


def load_config(path):
    """Supabase address and public (anon) key for the report form, from site-config.json; None when absent."""
    if not path or not Path(path).exists():
        return None
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    url, key = (cfg.get("supabaseUrl") or "").strip(), (cfg.get("supabaseAnonKey") or "").strip()
    if not (url.startswith("https://") and key):
        raise SystemExit(f"{path}: supabaseUrl must start with https:// and supabaseAnonKey must be set (use the public anon key, never the service key).")
    if "service" in key.lower() or key.startswith("sb_secret_"):
        raise SystemExit(f"{path}: that looks like a service key; only the public anon key belongs here.")
    return {"supabaseUrl": url.rstrip("/"), "supabaseAnonKey": key}


LOOKS = ("neutral", "uci")
MARK = ('<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><rect class="mark-bg" width="32" height="32" rx="7"/>'
        '<ellipse class="mark-cell" cx="14.5" cy="19" rx="9" ry="8.2" transform="rotate(-25 14.5 19)"/><circle class="mark-cell" cx="23.6" cy="9.4" r="4.8"/><circle class="mark-nuc" cx="16.6" cy="16.9" r="2.3"/></svg>')


def look_tokens(look: str) -> dict:
    """The --name: value pairs of a look file (used for the favicon and the style tile)."""
    text = (SRC / "looks" / f"{look}.css").read_text(encoding="utf-8") + (SRC / "style.css").read_text(encoding="utf-8")
    tok = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", text))
    if tok.get("--font-head", "").startswith("var("):
        tok["--font-head"] = tok["--font-body"]
    return tok


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def safe_html(html_value, plain_value) -> str:
    """Pre-sanitised HTML if it only contains <i>, <sub>, <sup> and valid entities; otherwise the escaped plain text."""
    v = html_value or ""
    tags = re.findall(r"<[^>]*>", v)
    if all(re.fullmatch(r"</?(i|sub|sup)>", t) for t in tags) and not re.search(r"&(?!amp;|lt;|gt;|quot;|#39;)", v) and "<" not in re.sub(r"<[^>]*>", "", v):
        return v
    return esc(plain_value)


def read_csv(path: Path) -> list:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(s):
    if s in (None, ""):
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    return int(x) if x == int(x) else round(x, 6)


# A small line icon for each product class (20x20, drawn in the current text colour)
CLASS_ICONS = {
    "Aromatics and flavor compounds": '<path d="M4.5 9h9v3.5a4.5 4.5 0 0 1-9 0zM13.5 10.5h1.2a2 2 0 0 1 0 4h-1.7M7 7c-1.2-1.2 1.2-2.3 0-3.8M10.5 7c-1.2-1.2 1.2-2.3 0-3.8"/>',
    "Enzymes": '<circle cx="5.5" cy="15" r="2.3"/><circle cx="14.5" cy="15" r="2.3"/><path d="M7.2 13.4L14.5 2.8M12.8 13.4L5.5 2.8"/>',
    "Fuels and solvents": '<path d="M10 1.8c.8 3.4-5.2 5.2-5.2 10a5.2 5.2 0 0 0 10.4 0c0-2-1-3.2-2.2-4.4-.2 1.7-1 2.4-1.8 2.4C11 9.6 11.6 5 10 1.8z"/><path d="M10 17.2a2.6 2.6 0 0 1-2.6-2.6c0-1.6 1.4-2.4 2.6-3.6 1.2 1.2 2.6 2 2.6 3.6a2.6 2.6 0 0 1-2.6 2.6z"/>',
    "Organic acids": '<circle cx="10" cy="10" r="7.5"/><text x="10" y="13" text-anchor="middle">H+</text>',
    "Other recombinant proteins": '<circle cx="4.5" cy="13.5" r="2.2"/><circle cx="10" cy="6.5" r="2.2"/><circle cx="15.5" cy="13.5" r="2.2"/><path d="M5.9 11.8l2.8-3.6M11.3 8.2l2.8 3.6M6.7 13.5h6.6"/>',
    "Pigments and bioactives": '<path d="M10 2.5a7.5 7.5 0 1 0 0 15c1.4 0 2-.9 2-1.8 0-1.4-1.2-1.5-1.2-2.7 0-.9.8-1.5 1.7-1.5H15a2.5 2.5 0 0 0 2.5-2.5C17.5 5.8 14.2 2.5 10 2.5z"/><circle cx="6.3" cy="9.3" r=".8"/><circle cx="8.8" cy="5.8" r=".8"/><circle cx="12.8" cy="6.3" r=".8"/>',
    "Specialty sugars": '<path d="M10 2.5l6.5 3.5v8L10 17.5 3.5 14V6zM3.5 6L10 9.5 16.5 6M10 9.5v8"/>',
    "Sugar alcohols and polyols": '<path d="M2.5 13.5l3-4 3 4 3-4 3 4 3-4M5.5 9.5v-4M11.5 9.5v-4M8.5 13.5v4M14.5 13.5v4"/>',
}


# The word(s) in a result statement that name its product (the link text). Also sent to the browser in data.js.
PRODUCT_WORDS = {
    "Xylitol": "xylitol", "Ethanol": "ethanol", "Succinic acid": "succinic acid|succinate", "2-Phenylethanol": "2-phenylethanol|phenylethanol|2-pe\\b",
    "Esters (ethyl acetate and other aroma esters)": "ethyl acetate|isoamyl acetate|phenylethyl acetate|esters?", "L-Lactic acid": "lactic acid|lactate",
    "Glycerol": "glycerol", "Acetic acid / acetate": "acetic acid|acetate", "Myo-inositol": "myo-inositol|inositol", "Pyruvate / PEP": "pyruvate",
    "Triacetic acid lactone (TAL)": "triacetic acid lactone|\\btal\\b", "p-Coumaric acid": "p-coumaric acid|coumaric acid", "Glutathione": "glutathione",
    "Mannitol": "mannitol", "Fructose": "fructose", "Fumaric acid": "fumaric acid|fumarate", "Indole-3-acetic acid": "indole-3-acetic acid|indole",
    "3-HP": "3-hp", "D-Allulose": "allulose", "6-MSA": "6-msa", "Violacein": "violacein"}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def plural(n, word: str) -> str:
    return f"{n} {word}" + ("" if str(n) == "1" else "s")


def pretty(s) -> str:
    return (s or "").replace("_", " ")


class Site:
    def __init__(self, bundle: Path, out: Path, csp: bool = False, config: Path = None, public: bool = False, look: str = "uci", preview: bool = False):
        self.bundle, self.out, self.csp, self.public = bundle, out, csp or public, public
        if look not in LOOKS:
            raise SystemExit(f"--look must be one of {', '.join(LOOKS)}")
        self.look, self.preview = look, preview and not public
        self.config = load_config(config)
        names = ["results", "genes", "gene_orthologs", "gene_aliases", "gene_candidate_loci", "strains", "strain_aliases", "citations", "products", "comparisons"]
        self.t = {n: read_csv(bundle / f"{n}.csv") for n in names}
        notes = (bundle / "RELEASE_NOTES.md").read_text(encoding="utf-8") if (bundle / "RELEASE_NOTES.md").exists() else ""
        m = re.match(r"# MarxBase release (\S+) \(([^)]+)\)", notes)
        self.version, self.date = (m.group(1), m.group(2)) if m else (bundle.name, "")
        for r in self.t["results"]:
            for k in ("new_value", "baseline_value", "percent_change", "fold_change", "temperature_c", "ph", "volume_l", "cultivation_time_h", "n_replicates", "year", "n_members"):
                r[k] = num(r.get(k))
        self.results = self.t["results"]
        self.by_id = {r["public_id"]: r for r in self.results}
        self.genes = {g["gene_id"]: g for g in self.t["genes"]}
        self.strains = {s["strain_id"]: s for s in self.t["strains"]}
        self.papers = {c["pmid"]: c for c in self.t["citations"]}                  # every text-mined paper
        self.papers_with = {pm: c for pm, c in self.papers.items() if int(c["n_results"] or 0) > 0}   # papers with at least one finding
        self.products = {p["product_name"]: p for p in self.t["products"]}
        self.findings = defaultdict(list)
        for r in self.results:
            self.findings[r["finding_id"]].append(r)
        self.aliases = defaultdict(list)
        for a in self.t["gene_aliases"]:
            self.aliases[a["gene_id"]].append(a)
        self.orthologs = defaultdict(list)
        for o in self.t["gene_orthologs"]:
            self.orthologs[o["gene_id"]].append(o)
        self.cands = defaultdict(list)
        for c in self.t["gene_candidate_loci"]:
            self.cands[c["gene_id"]].append(c)
        self.salias = defaultdict(list)
        for a in self.t["strain_aliases"]:
            self.salias[a["strain_id"]].append(a)
        self.comps = defaultdict(list)
        for c in self.t["comparisons"]:
            self.comps[c["public_id"]].append(c)
        self.children = defaultdict(list)
        for s in self.strains.values():
            if s["parent_strain_id"]:
                self.children[s["parent_strain_id"]].append(s["strain_id"])
        self.strain_root = {sid: self._root(sid) for sid in self.strains}
        self.count = 0
        doi_file = HERE / "DOI"
        self.doi = doi_file.read_text(encoding="utf-8").strip() if doi_file.exists() else ""   # the Zenodo DOI of this release; empty = "DOI pending"
        self.species = species.names_from({r[k] for r in self.t["results"] for k in ("host_organism", "gene_organism")} | {g["organism"] for g in self.t["genes"]} | {s["species"] for s in self.t["strains"]})
        self.has_evidence = any(r.get("evidence_sentence") for r in self.t["results"])
        self.asset_tag = ""            # set at the start of build(): a hash of every browser file, so a changed file is never served from a visitor's cache

    def _root(self, sid: str) -> str:
        seen = set()
        while sid not in seen and self.strains[sid]["parent_strain_id"] in self.strains:
            seen.add(sid)
            sid = self.strains[sid]["parent_strain_id"]
        return sid

    def strain_link(self, sid: str, depth: int) -> str:
        root = self.strain_root[sid]
        return f'<a href="{"../" * depth}strain/{esc(root)}.html">{esc(self.strains[root]["strain_name"])}</a>'

    # ----- helpers -----
    def write(self, rel: str, text: str) -> None:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.count += 1

    def asset(self, name: str, root: str = "") -> str:
        """A file address with a version tag, so a browser fetches a changed file at once instead of reusing its cached copy."""
        return f"{root}{name}?v={esc(self.version)}-{self.asset_tag}"

    def layout(self, title: str, body: str, depth: int, active: str = "", suggest: tuple = None, body_class: str = "") -> str:
        root = "../" * depth
        if suggest and self.config:
            body += (f'<section id="suggest-box" data-page-type="{esc(suggest[0])}" data-target-id="{esc(suggest[1])}" data-release="{esc(self.version)}"></section>'
                     f'<script src="{self.asset("config.js", root)}"></script><script src="{self.asset("suggest.js", root)}"></script>')
        nav = "".join(f'<a href="{root}{href}"{" aria-current=\"page\"" if key == active else ""}>{label}</a>' for key, href, label in (
            ("search", "index.html", "Search"), ("genes", "genes.html", "Genes"), ("strains", "strains.html", "Strains"),
            ("papers", "papers.html", "Papers"), ("products", "products.html", "Products"), ("summary", "summary.html", "Summary"), ("methods", "methods.html", "Methods"),
            ("downloads", "downloads.html", "Downloads"), ("about", "about.html", "About &amp; limits")))
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                + (f'<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; img-src \'self\' data:; style-src \'self\'; script-src \'self\'{"; connect-src \'self\' " + self.config["supabaseUrl"] if self.config else ""}">' if self.csp else '') +
                f'<title>{esc(title)} – MarxBase</title><link rel="icon" href="{root}favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{self.asset("style.css", root)}"><script src="{self.asset("site.js", root)}"></script></head><body{(" class=\"" + body_class + "\"") if body_class else ""}>'
                f'<a class="skip" href="#main">Skip to content</a>'
                f'<header class="top"><div class="bar"><a class="brand" href="{root}index.html">{MARK}<span>MarxBase</span></a>'
                f'<button type="button" id="menu-toggle" class="menu-toggle" aria-expanded="false" aria-controls="site-nav" aria-label="Menu"><svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M2 5h16M2 10h16M2 15h16"/></svg></button>'
                f'<nav id="site-nav" aria-label="Main">{nav}</nav></div></header><main id="main">{species.italicize(body, self.species)}</main>'
                f'<footer><div class="bar"><span class="release">MarxBase {esc(self.version)}</span><span>{esc(self.date)}</span>'
                f'<span>{len(self.results)} results from {len(self.papers_with)} papers</span>'
                + (f'<a href="https://doi.org/{esc(self.doi)}">DOI {esc(self.doi)}</a>' if self.doi else '<span>DOI pending</span>') +
                f'<a href="{root}about.html">About &amp; limits</a><a href="{root}downloads.html">Downloads</a></div></footer></body></html>')

    def chip(self, cls: str) -> str:
        return f'<span class="chip chip-{esc(cls)}"><span aria-hidden="true">{CLASS_ICON.get(cls, "")}</span> {esc(CLASS_LABEL.get(cls, cls))}</span>'

    def kind_badge(self, g: dict) -> str:
        kind = g["gene_kind"]
        label = KIND_LABEL.get(kind, kind)
        if kind == "heterologous_gene":
            label = f"Heterologous gene from {g.get('organism') or g.get('gene_organism')}"
        elif kind == "locus_tagged" and g.get("locus_tag"):
            label = f"Locus tag {g['locus_tag']}"
        return f'<span class="badge badge-{esc(kind)}" title="{esc(KIND_HELP.get(kind, ""))}">{esc(label)}</span>'

    def value_text(self, r: dict) -> str:
        parts = []
        if r["new_value"] is not None:
            parts.append(f"{QUAL.get(r['value_qualifier'], '')}{r['new_value']} {r['value_unit']}".strip())
            if r["baseline_value"] is not None:
                parts.append(f"(baseline {r['baseline_value']} {r['value_unit']}".strip() + (f", {r['comparator']}" if r["comparator"] else "") + ")")
        if r["percent_change"] is not None:
            parts.append(f"{r['percent_change']}% change" + (f" vs {r['comparator']}" if r["comparator"] and r["new_value"] is None else ""))
        if r["fold_change"] is not None:
            parts.append(f"{r['fold_change']}-fold" + (f" vs {r['comparator']}" if r["comparator"] and r["new_value"] is None else ""))
        return " ".join(parts) or ""

    def gene_link(self, r: dict, depth: int) -> str:
        return f'<a href="{"../" * depth}gene/{esc(r["gene_id"])}.html">{esc(r["gene_name"])}</a>'

    def paper_cite(self, pmid: str) -> str:
        p = self.papers.get(pmid, {})
        first = (p.get("first_author") or (p.get("authors") or "").split(";")[0]).strip()
        many = len([a for a in (p.get("authors") or "").split(";") if a.strip()]) > 1
        return f"{first or 'Unknown'}{' et al.' if many else ''} {p.get('year') or ''}".strip()

    def phenotype_html(self, r: dict, depth: int) -> tuple:
        """The phenotype text with the word naming the product linked to its page; (html, linked?)."""
        text, rx = r["phenotype"], PRODUCT_WORDS.get(r["product"] or "")
        m = re.search(rx, text, re.I) if rx else None
        if not m:
            return esc(text), False
        return f'{esc(text[:m.start()])}<a href="{"../" * depth}product/{slug(r["product"])}.html">{esc(m.group(0))}</a>{esc(text[m.end():])}', True

    def finding_line(self, rows: list, depth: int, current_gene: str = "") -> str:
        r0 = rows[0]
        members = " + ".join(f'{self.gene_link(m, depth)} <span class="chg">{esc(pretty(m["intervention_type"]))}</span>' for m in rows)
        meta = []
        if r0["strain_name"]:
            meta.append(f'strain {self.strain_link(r0["strain_id"], depth)}')
        meta.append(f'<a href="{"../" * depth}paper/{esc(r0["pmid"])}.html">{esc(self.paper_cite(r0["pmid"]))}</a>')
        pheno, linked = self.phenotype_html(r0, depth)
        if r0["product"] and not linked:        # no word in the statement names it (e.g. "protein secretion"): link it from the details line
            meta.append(f'product <a href="{"../" * depth}product/{slug(r0["product"])}.html">{esc(r0["product"])}</a>')
        val = self.value_text(r0)
        return (f'<li class="finding cls-{esc(r0["result_class"])}"><a class="cardlink" href="{"../" * depth}result/{esc(r0["public_id"])}.html"><span class="sr-only">Details of this result</span></a><div class="fl1">{members} → <strong>{esc(r0["effect_direction"])}</strong> {pheno}{(" (" + esc(val) + ")") if val else ""} <span class="sr-only">({esc(CLASS_LABEL.get(r0["result_class"], r0["result_class"]))})</span></div>'
                + (f'<div class="fl3"><span class="badge badge-host">Host: {esc(r0["host_organism"])}</span></div>' if r0["host_organism"] != "K. marxianus" else "")
                + f'<div class="fl2">{" · ".join(meta)}'
                f'</div></li>')

    def findings_list(self, rows: list, depth: int) -> str:
        seen, items = set(), []
        for r in sorted(rows, key=lambda x: (x["result_class"] == "positive", -(x["year"] or 0), x["public_id"])):
            if r["finding_id"] in seen:
                continue
            seen.add(r["finding_id"])
            items.append(self.finding_line(self.findings[r["finding_id"]], depth))
        return f'<ul class="findings">{"".join(items)}</ul>' if items else "<p>No results.</p>"

    def class_counts(self, rows: list) -> str:
        fids = {}
        for r in rows:
            fids[r["finding_id"]] = r["result_class"]
        c = {k: sum(1 for v in fids.values() if v == k) for k in CLASS_LABEL}
        return ", ".join(f"{n} {CLASS_LABEL[k].lower()}" for k, n in c.items() if n) or "none"

    # ----- page parts shared by the detail pages -----
    def crumbs(self, trail: list, depth: int = 1) -> str:
        """Breadcrumb: trail = [(label, href or None), ...]; the last item is the current page."""
        root = "../" * depth
        parts = [f'<a href="{root}{h}">{label}</a>' if h else f'<span aria-current="page">{label}</span>' for label, h in trail]
        return '<nav class="crumbs" aria-label="Breadcrumb">' + ' <span aria-hidden="true">›</span> '.join(parts) + '</nav>'

    def facts(self, items: list) -> str:
        """A definition list of label / value pairs (values are HTML); empty values are left out."""
        rows = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in items if v not in ("", None))
        return f'<dl class="facts">{rows}</dl>' if rows else ""

    def card(self, title: str, inner: str, extra: str = "") -> str:
        return f'<section class="infocard{(" " + extra) if extra else ""}"><h2>{title}</h2>{inner}</section>' if inner else ""

    def page_head(self, title_html: str, sub_html: str = "", cls: str = "") -> str:
        return f'<header class="page-head{(" cls-" + cls) if cls else ""}"><h1>{title_html}</h1>{("<p class=\"head-sub\">" + sub_html + "</p>") if sub_html else ""}</header>'

    def detail_layout(self, main: str, side: str) -> str:
        return f'<div class="detail-layout"><div class="detail-main">{main}</div>{("<aside class=\"detail-side\">" + side + "</aside>") if side else ""}</div>'

    def link_buttons(self, p: dict, pmid: str) -> str:
        links = [f'<a class="linkbtn" href="https://pubmed.ncbi.nlm.nih.gov/{esc(pmid)}/">PubMed</a>']
        if p.get("doi"):
            links.append(f'<a class="linkbtn" href="https://doi.org/{esc(p["doi"])}">DOI</a>')
        if p.get("pmcid"):
            links.append(f'<a class="linkbtn" href="https://www.ncbi.nlm.nih.gov/pmc/articles/{esc(p["pmcid"])}/">PMC</a>')
        return '<p class="linkbtns">' + " ".join(links) + "</p>"

    def count_chips(self, rows: list) -> str:
        fids = {}
        for r in rows:
            fids[r["finding_id"]] = r["result_class"]
        out = [f'<span class="cnt cnt-{k}">{n} {CLASS_LABEL[k].lower()}</span>' for k in CLASS_LABEL if (n := sum(1 for v in fids.values() if v == k))]
        return f'<span class="cnt">{plural(len(fids), "finding")}</span> ' + " ".join(out)

    # ----- pages -----
    def build_result_page(self, r: dict) -> None:
        g = self.genes[r["gene_id"]]
        gd = {**g, "gene_organism": g["organism"]}
        details = self.facts([
            ("Gene", f'{self.gene_link(r, 1)} {self.kind_badge(gd)}'),
            ("Name in the paper", esc(r["reported_gene_name"]) if r["reported_gene_name"] else ""),
            ("Gene from", esc(r["gene_organism"])), ("Change", esc(pretty(r["intervention_type"]))),
            ("Effect", esc(r["effect_direction"])), ("Phenotype", f'{esc(r["phenotype"])} ({esc(pretty(r["phenotype_category"]))})'),
            ("Host", esc(r["host_organism"])),
            ("Strain", (self.strain_link(r["strain_id"], 1) + (f' <span class="small">(recorded as {esc(r["strain_name"])})</span>' if self.strain_root[r["strain_id"]] != r["strain_id"] else "")) if r["strain_id"] else "not stated"),
            ("Product", f'<a href="../product/{slug(r["product"])}.html">{esc(r["product"])}</a> ({esc(r["product_class"])})' if r["product"] else ""),
            ("Condition tag", esc(r["condition_label"]) if r["condition_label"] and r["condition_label"] != "default" else "")])
        quant = self.facts([("Value", esc(self.value_text(r))), ("Size as written", esc(r["effect_magnitude_text"])), ("Metric", esc(pretty(r["metric_type"]))),
                            ("Statistics", esc(pretty(r["statistics_reported"]))), ("Replicates", esc(r["n_replicates"]))])
        cond = self.facts([(k, esc(v)) for k, v in [
            ("Temperature", f'{r["temperature_c"]} °C' if r["temperature_c"] is not None else r["temperature_note"]),
            ("pH", r["ph"]), ("Scale", pretty(r["scale"])), ("Volume (L)", r["volume_l"]), ("Process", pretty(r["process_mode"])),
            ("Carbon source", r["carbon_source"]), ("Medium", r["feedstock_medium"]), ("Oxygen", r["oxygen_level"]),
            ("Time (h)", r["cultivation_time_h"]), ("Stressor", " ".join(x for x in (r["stressor_type"], r["stressor_level"]) if x))]])
        p = self.papers.get(r["pmid"], {})
        others = [m for m in self.findings[r["finding_id"]] if m["public_id"] != r["public_id"]]
        combo = ("<ul>" + "".join(f'<li>{self.gene_link(m, 1)} {esc(pretty(m["intervention_type"]))} (<a href="{esc(m["public_id"])}.html">{esc(m["public_id"])}</a>)</li>' for m in others) + "</ul>") if others else ""
        comp = ("<ul>" + "".join(
            f'<li><strong>{esc(pretty(c["relation"]))}</strong> vs {esc(c["other_organism"])}' + (f': “{safe_html(c["evidence_sentence_html"], c["evidence_sentence"])}”' if c["evidence_sentence"] else "") + '</li>'
            for c in self.comps[r["public_id"]]) + "</ul>") if self.comps.get(r["public_id"]) else ""
        evidence = (f'<blockquote>{safe_html(r["evidence_sentence_html"], r["evidence_sentence"])}</blockquote><p class="small">From the abstract. '
                    f'Evidence sentences are third-party text and are not covered by the data licence.</p>'
                    if r["evidence_sentence"] else f'<p>{esc(r["provenance_note"])}</p>')
        main = (self.card("Details", details) + self.card("Measured", quant or "<p>No quantified value stated.</p>") + self.card("Conditions", cond)
                + self.card("Changed together", combo) + self.card("Compared with other yeasts (authors' statement)", comp) + self.card("Evidence", evidence))
        side = self.card("Paper", f'<p><a href="../paper/{esc(r["pmid"])}.html">{safe_html(p.get("title_html"), p.get("title"))}</a></p>'
                         f'<p class="small">{esc(p.get("authors"))}<br>{esc(p.get("journal"))} {esc(p.get("year"))}</p>{self.link_buttons(p, r["pmid"])}')
        body = (self.crumbs([("Search", "index.html"), (esc(r["public_id"]), None)])
                + self.page_head(f'{esc(r["gene_name"])} {esc(pretty(r["intervention_type"]))}',
                                 "", r["result_class"])
                + self.detail_layout(main, side))
        self.write(f"result/{r['public_id']}.html", self.layout(f"{r['gene_name']} {pretty(r['intervention_type'])}", body, 1, suggest=("result", r["public_id"])))

    def build_gene_page(self, g: dict) -> None:
        rows = [r for r in self.results if r["gene_id"] == g["gene_id"]]
        gd = {**g, "gene_organism": g["organism"]}
        al = [a["alias_name"] for a in self.aliases.get(g["gene_id"], [])]
        reported = sorted({r["reported_gene_name"] for r in rows if r["reported_gene_name"]})
        ident = self.facts([("Organism", esc(g["organism"])), ("Locus tag", esc(g["locus_tag"])), ("Identity method", esc(pretty(g["id_method"]))), ("Confidence", esc(g["id_confidence"])),
                            ("Also known as", esc(", ".join(al))), ("Named in the papers as", esc(", ".join(reported)))])
        notes = (f'<p>{esc(g["identity_note"])}</p>' if g["identity_note"] else "") + (f'<p class="small">{esc(KIND_HELP[g["gene_kind"]])}</p>' if g["gene_kind"] in KIND_HELP else "")
        orth = self.orthologs.get(g["gene_id"], [])
        def orth_id(o):          # the ortholog's name is shown only when it differs from this gene's name (e.g. DNL4 and LIG4)
            nm = (o["ortholog_gene_name"] or "").strip()
            return esc(o["ortholog_systematic_id"]) + (f' ({esc(nm)})' if nm and nm.lower() != g["gene_name"].lower() else "")
        orth_html = ("<table class='kv'><tr><th>ID</th><th>Identity</th><th>Coverage</th><th>Rank</th></tr>" +
                     "".join(f"<tr><td>{orth_id(o)}</td><td>{esc(o['identity_pct'])}%</td><td>{esc(o['coverage_pct'])}%</td><td>{esc(o['rank'])}</td></tr>" for o in orth) + "</table>") if orth else ""
        cand = self.cands.get(g["gene_id"], [])
        cand_html = ""
        if g["gene_kind"] == "undetermined_paralog" and cand:
            cand_html = ("<p><strong>Undetermined:</strong> the papers do not say which copy was used.</p><ul>" +
                         "".join(f"<li>{esc(c['locus_tag'])} – {esc(c['product'])}{(' (' + esc(c['hint']) + ')') if c['hint'] else ''}</li>" for c in cand) + "</ul>")
        by_cat = defaultdict(list)
        for r in rows:
            by_cat[r["phenotype_category"]].append(r)
        sections = "".join(f"<h3>{esc(pretty(cat))}</h3>{self.findings_list(rs, 1)}" for cat, rs in sorted(by_cat.items()))
        n_find = len({r["finding_id"] for r in rows})
        main = f'<section class="infocard"><h2>Results ({plural(n_find, "finding")})</h2>{sections}</section>'
        side = self.card("Identity", ident + notes) + self.card("<i>S. cerevisiae</i> ortholog", orth_html) + self.card("Candidate loci", cand_html)
        body = (self.crumbs([("Genes", "genes.html"), (esc(g["gene_name"]), None)])
                + self.page_head(esc(g["gene_name"]), "" if g["gene_kind"] == "locus_tagged" else self.kind_badge(gd))
                + self.detail_layout(main, side))
        self.write(f"gene/{g['gene_id']}.html", self.layout(g["gene_name"], body, 1, "genes", suggest=("gene", g["gene_id"])))

    def build_strain_page(self, s: dict) -> None:
        sid = s["strain_id"]
        root = self.strain_root[sid]
        if root != sid:       # a derived strain: its results are compiled under the root strain
            r = self.strains[root]
            body = (self.crumbs([("Strains", "strains.html"), (esc(s["strain_name"]), None)])
                    + self.page_head(esc(s["strain_name"]))
                    + f'<div class="infocard"><p>Results from this strain are included under <a href="{esc(root)}.html">{esc(r["strain_name"])}</a>.</p></div>')
            self.write(f"strain/{sid}.html", self.layout(s["strain_name"], body, 1, "strains"))
            return
        members = [x for x in self.strains if self.strain_root[x] == sid]
        rows = [r for r in self.results if r["strain_id"] in members]
        derived = [self.strains[x]["strain_name"] for x in members if x != sid]
        al = self.salias.get(sid, [])
        side = self.card("Strain", self.facts([("Species", esc(s["species"])), ("Other designations", esc(", ".join(a["alias"] for a in al)))])
                         + ('<p class="small">Includes results recorded under derived strains: ' + esc(", ".join(sorted(derived))) + ".</p>" if derived else ""))
        main = (f'<section class="infocard"><h2>Results ({plural(len({r["finding_id"] for r in rows}), "finding")})</h2>'
                f'{self.findings_list(rows, 1) if rows else "<p>No result in the current release uses this strain directly.</p>"}</section>')
        body = (self.crumbs([("Strains", "strains.html"), (esc(s["strain_name"]), None)]) + self.page_head(esc(s["strain_name"]))
                + self.detail_layout(main, side))
        self.write(f"strain/{sid}.html", self.layout(s["strain_name"], body, 1, "strains", suggest=("strain", sid)))

    def build_paper_page(self, p: dict) -> None:
        rows = [r for r in self.results if r["pmid"] == p["pmid"]]
        links = [f'<a href="https://pubmed.ncbi.nlm.nih.gov/{esc(p["pmid"])}/">PubMed</a>']
        if p["doi"]:
            links.append(f'<a href="https://doi.org/{esc(p["doi"])}">DOI</a>')
        if p["pmcid"]:
            links.append(f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/{esc(p["pmcid"])}/">PMC</a>')
        info = f'{esc(p["journal"])} {esc(p["year"])}{(" \u00b7 " + esc(p["country"])) if p["country"] else ""} \u00b7 {" \u00b7 ".join(links)}'
        plain = f'{esc(p["authors"])}. {esc(p["title"])}. {esc(p["journal"])}. {esc(p["year"])}.{(" doi:" + esc(p["doi"])) if p["doi"] else ""}'
        findings = (f'<section class="infocard"><h2>Results ({plural(len({r["finding_id"] for r in rows}), "finding")})</h2>{self.findings_list(rows, 1)}</section>' if rows
                    else '<p class="nofind-note">No findings extracted</p>')
        body = (self.crumbs([("Papers", "papers.html"), (esc(p["pmid"]), None)])
                + self.page_head(safe_html(p["title_html"], p["title"]), esc(p["authors"]) + "<br>" + info)
                + findings
                + '<p class="head-actions"><button type="button" id="cite-open" class="cite-btn" hidden>Cite this paper</button>'
                  f'<noscript><span class="small">{plain}</span></noscript></p>'
                + '<script type="application/json" id="paper-data">' + json.dumps({k: p[k] for k in ("pmid", "title", "authors", "journal", "year", "doi", "pmcid")}, ensure_ascii=False).replace("</", "<\\/") + '</script>'
                f'<script src="{self.asset("cite.js", "../")}"></script><script src="{self.asset("paperpage.js", "../")}"></script>')
        self.write(f"paper/{p['pmid']}.html", self.layout(p["title"] or p["pmid"], body, 1, "papers", suggest=("paper", p["pmid"])))

    def build_product_page(self, name: str, p: dict) -> None:
        rows = [r for r in self.results if r["product"] == name]
        worked = [r for r in rows if r["result_class"] == "positive"]
        failed = [r for r in rows if r["result_class"] != "positive"]
        body = (self.crumbs([("Products", "products.html"), (esc(p["product_class"]), f'products.html#{self.class_slug(p["product_class"])}'), (esc(name), None)])
                + self.page_head(esc(name), f'<span class="small">{esc(p["product_class"])}</span>')
                + '<div class="worked-failed">' + self.card("What worked", self.findings_list(worked, 1), "cls-positive")
                + self.card("What failed or depended on conditions", self.findings_list(failed, 1), "cls-negative") + '</div>')
        self.write(f"product/{slug(name)}.html", self.layout(name, body, 1, "products", suggest=("product", name)))

    def km_strain_ids(self) -> set:
        """Strains used in K. marxianus hosts, plus their ancestors (so a lineage is never cut)."""
        ids = {r["strain_id"] for r in self.results if r["strain_id"] and r["host_organism"] == "K. marxianus"}
        for sid in list(ids):
            cur = self.strains[sid]["parent_strain_id"]
            while cur and cur in self.strains and cur not in ids:
                ids.add(cur)
                cur = self.strains[cur]["parent_strain_id"]
        return ids

    def class_slug(self, name: str) -> str:
        return slug(name)

    def build_lists(self) -> None:
        def page(title, key, body_html, intro=""):
            self.write(f"{key}.html", self.layout(title, f"<h1>{esc(title)}</h1>{intro}{body_html}", 0, key))
        # genes: K. marxianus genes / other species' genes expressed in K. marxianus / genes only studied in other hosts
        km_host_genes = {r["gene_id"] for r in self.results if r["host_organism"] == "K. marxianus"}
        genes = sorted(self.genes.values(), key=lambda g: g["gene_name"].lower())

        def gene_item(g, show_org):
            extra = [esc(g["organism"])] if show_org else []
            extra += [esc(KIND_LABEL.get(g["gene_kind"], "")), plural(g["n_results"], "result")]
            return f'<li><a href="gene/{esc(g["gene_id"])}.html">{esc(g["gene_name"])}</a> <span class="small">{" \u00b7 ".join(extra)}</span></li>'
        A = [g for g in genes if g["organism"] == "K. marxianus" and g["gene_kind"] != "enzyme_or_protein_label"]
        B = [g for g in genes if g["organism"] != "K. marxianus" and g["gene_id"] in km_host_genes]
        body = (f'<details open><summary>K. marxianus genes ({len(A)})</summary><ul class="plain">{"".join(gene_item(g, False) for g in A)}</ul></details>'
                f'<details><summary>Genes from other species expressed in K. marxianus ({len(B)})</summary>'
                f'<ul class="plain">{"".join(gene_item(g, True) for g in B)}</ul></details>')
        page("Genes", "genes", body)
        # strains: K. marxianus strains only; derived strains are compiled under their parent and not listed
        keep = self.km_strain_ids()
        roots = sorted({self.strain_root[sid] for sid in keep}, key=lambda k: self.strains[k]["strain_name"].lower())
        items = []
        for rid in roots:
            n = sum(1 for r in self.results if r["strain_id"] and self.strain_root[r["strain_id"]] == rid)
            items.append(f'<li><a href="strain/{esc(rid)}.html">{esc(self.strains[rid]["strain_name"])}</a> <span class="small">{plural(n, "result")}</span></li>')
        page("Strains", "strains", f'<p class="small">K. marxianus strains. Results from derived strains are included under their parent strain. '
             f'Strains used only in other host organisms are not listed here; they appear in search results when other hosts are switched on.</p>'
             f'<ul class="plain">{"".join(items)}</ul>')
        by_year = defaultdict(list)
        for p in self.papers.values():
            by_year[num(p["year"]) or 0].append(p)
        blocks = []
        for yr in sorted(by_year, reverse=True):
            ps = sorted(by_year[yr], key=lambda p: p["pmid"])
            lis = "".join(f'<li{"" if int(p["n_results"] or 0) else " class=\"nofind\""}><a href="paper/{esc(p["pmid"])}.html">{safe_html(p["title_html"], p["title"])}</a> '
                          f'<span class="small">{esc(p["authors"].split(";")[0] if p["authors"] else "")}'
                          f'{(" \u00b7 " + plural(p["n_results"], "result")) if int(p["n_results"] or 0) else ""}</span></li>' for p in ps)
            blocks.append(f'<section class="year"><h2>{yr or "Year unknown"} <span class="small count">({plural(len(ps), "paper")})</span></h2><ul class="plain">{lis}</ul></section>')
        page("Papers", "papers", '<div id="papers-toggle" class="papers-toggle" hidden><label class="switch-label"><input type="checkbox" id="only-findings" class="switch" checked>'
             '<span class="dot dot-yes" aria-hidden="true"></span> Only papers with findings</label>'
             '<span class="legend small" aria-label="Key"><span class="dot dot-yes" aria-hidden="true"></span> with findings <span class="dot dot-no" aria-hidden="true"></span> none extracted</span></div>'
             + "".join(blocks) + f'<script src="{self.asset("papers.js")}"></script>')
        # products: one page, each class is a dropdown that lists its specific products
        by_class = defaultdict(list)
        for n, p in self.products.items():
            by_class[p["product_class"]].append(n)
        items = []
        # alphabetical, except that the other-proteins dropdown sits right after Enzymes
        order = sorted(c for c in by_class if c != "Other recombinant proteins")
        if "Other recombinant proteins" in by_class:
            order.insert(order.index("Enzymes") + 1 if "Enzymes" in order else 0, "Other recombinant proteins")
        for cls in order:
            lis = "".join(f'<li><a href="product/{slug(n)}.html">{esc(n)}</a></li>' for n in sorted(by_class[cls]))
            items.append(f'<details class="pclass" id="{self.class_slug(cls)}"><summary><svg class="cicon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">{CLASS_ICONS.get(cls, "<circle cx='10' cy='10' r='6'/>")}</svg>{esc(cls)}</summary><ul class="plain">{lis}</ul></details>')
        page("Products", "products", "".join(items))

    def build_about(self) -> None:
        cls = {k: sum(1 for r in self.results if r["result_class"] == k) for k in CLASS_LABEL}
        body = (f'<h1>About &amp; limits</h1><p>MarxBase collects gene–phenotype results for <em>Kluyveromyces marxianus</em> metabolic engineering. '
                f'Release {esc(self.version)} ({esc(self.date)}) holds {len(self.results)} results ({len(self.findings)} findings, counting a multi-gene combination once): '
                f'{cls["positive"]} positive, {cls["negative"]} negative, {cls["context-dependent"]} context-dependent, from {len(self.papers_with)} papers. {len(self.papers)} papers were text-mined in all; the others yielded no finding.</p>'
                f'<h2>Limits</h2><ul><li>{esc(LIMITS)}</li><li>Temperature, scale and other conditions are recorded only when the abstract states them.</li>'
                f'<li>Some gene names are enzyme or protein labels used by authors, not gene symbols; they are marked. Some K. marxianus genes have several copies and the paper '
                f'does not say which one was used; they are marked as undetermined.</li><li>Negative results are scarce in abstracts, so absence of a failed attempt is not evidence that it worked.</li>'
                f'<li>A paper listed without findings may still contain relevant work: only abstracts are read, and the extraction misses some results.</li></ul>'
                f'<h2>Reporting a problem</h2><p>On a result, gene, paper or strain page, <strong>Report or suggest</strong> sends a message to the MarxBase maintainers: something looks wrong, a field should change, a result is missing, or a gene identifier is known. Messages are anonymous unless you add a name or email so we can reply, are read only by the maintainers and are never shown on this site. A suggestion changes nothing by itself; the maintainer checks it against the paper before any change reaches a later release.</p>'
                f'<p class="small">See <a href="methods.html">Methods</a> for how the data were made and <a href="downloads.html">Downloads</a> for the files. '
                f'Home page photograph: K. marxianus colonies on agar, \u00a9 Sidney Eichelberger.</p>')
        self.write("about.html", self.layout("About and limits", body, 0, "about"))

    def data_js(self) -> str:
        hide = {"evidence_sentence_html"} | (set() if self.has_evidence else {"evidence_sentence", "evidence_source"})
        cols = [c for c in self.t["results"][0].keys() if c not in hide]
        self.csv_columns = cols
        home = self.km_strain_ids()
        data = {
            "version": self.version, "date": self.date, "hasEvidence": self.has_evidence, "doi": self.doi, "species": self.species, "productWords": PRODUCT_WORDS,
            "columns": cols,
            "results": [{k: r[k] for k in cols if r.get(k) not in ("", None)} for r in self.results],
            "genes": {gid: {"name": g["gene_name"], "organism": g["organism"], "kind": g["gene_kind"], "locus": g["locus_tag"],
                            "aliases": [a["alias_name"] for a in self.aliases.get(gid, [])],
                            "orthologs": [[o["ortholog_gene_name"], o["ortholog_systematic_id"]] for o in self.orthologs.get(gid, [])]} for gid, g in self.genes.items()},
            "strains": {sid: {"name": s["strain_name"], "parent": s["parent_strain_id"], "species": s["species"], "home": sid in home, "root": self.strain_root[sid],
                              "aliases": [a["alias"] for a in self.salias.get(sid, [])]} for sid, s in self.strains.items()},
            "papers": {pm: {"pmid": pm, "title": p["title"], "authors": p["authors"], "journal": p["journal"], "year": num(p["year"]), "country": p["country"],
                            "first_author": p["first_author"], "doi": p["doi"], "pmcid": p["pmcid"]} for pm, p in self.papers_with.items()}}
        return "window.MARXBASE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\n"

    EXAMPLES = ("KU70", "xylitol", "NBRC 1777", "lactose")

    def hero(self) -> str:
        """The headline and example searches above the search bar (hidden by the page script once someone presses Search or browses)."""
        ex = " ".join(f'<a href="index.html?q={urllib.parse.quote(e)}">{esc(e)}</a>' for e in self.EXAMPLES)
        return ('<section id="hero" class="hero"><h1><i>Kluyveromyces marxianus</i> metabolic engineering database</h1>'
                f'<p class="examples"><span>Try</span> {ex}</p></section>'
                '<h1 id="results-title" class="results-title" hidden>Search results</h1>')

    def hero_extras(self) -> str:
        """The scrolling part of the home page, below the search bar: a link to all findings, a band of boxes for the four browse pages, and a band for the information pages."""
        n_find = len({r["finding_id"] for r in self.results if r["host_organism"] == "K. marxianus"})
        n_genes = len([g for g in self.genes.values() if g["organism"] == "K. marxianus" and g["gene_kind"] != "enzyme_or_protein_label"])
        n_strains = len({self.strain_root[s] for s in self.km_strain_ids()})
        browse = [(len(self.papers), "Papers", "papers.html", f"Abstracts text-mined; {len(self.papers_with)} with findings"),
                  (n_find, "Findings", "index.html?browse=1", "Each gene change and what happened"),
                  (n_genes, "Genes", "genes.html", "Every gene that was changed, with its locus tag and S. cerevisiae ortholog"),
                  (n_strains, "Strains", "strains.html", "The strains used, with derived strains grouped under their parent"),
                  (len(self.products), "Products", "products.html", "What the strains make, grouped by type")]
        about = [("Summary", "summary.html", "Charts of what the collection contains"), ("Methods", "methods.html", "How papers were found, read and checked"),
                 ("Downloads", "downloads.html", "Data files, citations and an offline copy"), ("About &amp; limits", "about.html", "How accurate the results are, and what they cannot tell you")]
        c1 = "".join(f'<li><a href="{h}"><b>{n:,}</b><strong>{t}</strong><span>{esc(d)}</span></a></li>' for n, t, h, d in browse)
        c2 = "".join(f'<li><a href="{h}"><strong>{t}</strong><span>{esc(d)}</span></a></li>' for t, h, d in about)
        return (f'<div id="hero-extras" class="home-sections">'
                f'<section class="band" aria-labelledby="h-browse"><div class="inner"><h2 id="h-browse">Browse the data</h2><ul class="cards cards-browse">{c1}</ul></div></section>'
                f'<section class="band band-photo" aria-labelledby="h-about"><div class="inner"><h2 id="h-about">About MarxBase</h2><ul class="cards cards-plain">{c2}</ul></div></section></div>')

    def style_tile(self, tok: dict) -> str:
        """A page of the look's colors, type, buttons, chips and a sample card, for judging identity (preview builds only)."""
        names = ("--bar", "--accent", "--highlight", "--heading", "--link", "--ink", "--muted", "--surface", "--line-strong", "--pos", "--neg", "--ctx")
        sw = "".join(f'<div class="sw"><span class="sw-c" data-c="{esc(tok.get(n, ""))}"></span><b>{n[2:]}</b> <code>{esc(tok.get(n, "see style.css"))}</code></div>' for n in names)
        css = "".join(f'.sw-c[data-c="{tok.get(n, "")}"]{{background:{tok.get(n, "#fff")}}}' for n in names)
        sample = self.finding_line(self.findings[self.results[0]["finding_id"]], 0)
        return (f'<style>.sw{{display:flex;align-items:center;gap:10px;margin:4px 0}}.sw-c{{width:44px;height:28px;border-radius:6px;border:1px solid #0003}}{css}</style>'
                f'<h1>Style tile: look "{esc(self.look)}"</h1><p class="small">Preview only; not part of the published site.</p>'
                f'<h2>Colors</h2>{sw}<h2>Type</h2><p><b>Heading font:</b> {esc(tok["--font-head"])}</p><h1>Heading one</h1><h2>Heading two</h2><h3>heading three</h3>'
                f'<p>Body text: paired genetic changes and their measured effects, with links to the source paper. <a href="#">A link</a> and <code>code</code>. <span class="small">Small muted text.</span></p>'
                f'<h2>Buttons and inputs</h2><p><button type="submit">Primary action</button> <button type="button">Secondary</button> <button type="button" disabled>Disabled</button> '
                f'<button type="button" class="linklike">link-style button</button></p><p><input type="search" value="KU70" aria-label="sample search" class="sample-input"></p>'
                f'<h2>Result chips</h2><p>{self.chip("positive")} {self.chip("negative")} {self.chip("context-dependent")} <span class="badge">Locus tag KLMA_10274</span></p>'
                f'<h2>A result</h2><ul class="findings">{sample}</ul>'
                f'<blockquote>A quoted line.</blockquote><table class="kv"><tr><th>Gene</th><td>KU70</td></tr><tr><th>Host</th><td>K. marxianus</td></tr></table>')

    def build(self) -> int:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        files = ("search-core.js", "cite.js", "app.js", "paperpage.js", "suggest.js", "site.js", "papers.js")
        data_text = self.data_js()
        css = (SRC / "looks" / f"{self.look}.css").read_text(encoding="utf-8") + "\n" + (SRC / "style.css").read_text(encoding="utf-8")
        self.asset_tag = hashlib.sha256(b"".join((SRC / f).read_bytes() for f in files) + b"".join(p.read_bytes() for p in sorted((SRC / "img").glob("*"))) + css.encode("utf-8") + data_text.encode("utf-8") + json.dumps(self.config).encode("utf-8")).hexdigest()[:8]
        for f in files:
            shutil.copy(SRC / f, self.out / f)
        self.write("style.css", css)
        (self.out / "img").mkdir(exist_ok=True)
        for p in sorted((SRC / "img").glob("*")):                   # the home-page photo (resized copies; the full-size original is not part of the site)
            shutil.copy(p, self.out / "img" / p.name)
            self.count += 1
        tok = look_tokens(self.look)
        self.write("favicon.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="{tok["--accent"]}"/>'
                   f'<g fill="{tok["--accent-ink"]}"><ellipse cx="14.5" cy="19" rx="9" ry="8.2" transform="rotate(-25 14.5 19)"/><circle cx="23.6" cy="9.4" r="4.8"/></g>'
                   f'<circle cx="16.6" cy="16.9" r="2.3" fill="{tok["--accent"]}"/></svg>\n')
        if self.look == "uci":                     # the self-hosted font files and their licence
            for f in sorted((SRC / "fonts").iterdir()):
                (self.out / "fonts").mkdir(exist_ok=True)
                shutil.copy(f, self.out / "fonts" / f.name)
                self.count += 1
        if self.preview:
            self.write("_look.html", self.layout("Style tile", self.style_tile(tok), 0))
        self.write("data.js", data_text)
        if self.config:
            self.write("config.js", "window.MARXBASE_CONFIG = " + json.dumps(self.config) + ";\n")
        index = (self.hero() + f'<div id="app" class="landing"><noscript>This page needs JavaScript to search. You can still browse <a href="genes.html">genes</a>, <a href="strains.html">strains</a>, <a href="papers.html">papers</a> and <a href="products.html">products</a>.</noscript></div>' + self.hero_extras() +
                 f'<script src="{self.asset("data.js")}"></script><script src="{self.asset("search-core.js")}"></script><script src="{self.asset("cite.js")}"></script><script src="{self.asset("app.js")}"></script>')
        self.write("index.html", self.layout("Search", index, 0, "search", body_class="home"))
        for r in self.results:
            self.build_result_page(r)
        for g in self.genes.values():
            self.build_gene_page(g)
        for s in self.strains.values():
            self.build_strain_page(s)
        for p in self.papers.values():
            self.build_paper_page(p)
        for n, p in self.products.items():
            self.build_product_page(n, p)
        self.build_lists()
        self.build_about()
        self.write("summary.html", self.layout("Summary", pages.build_summary(self), 0, "summary"))
        self.write("methods.html", self.layout("Methods", pages.build_methods(self), 0, "methods"))
        pages.build_data_zip(self)
        self.write("downloads.html", self.layout("Downloads", pages.downloads_body(self, False), 0, "downloads"))
        if not self.public:                       # the public build carries no test pages or gate answers
            import gate_questions
            gate_questions.write_all(self, HERE / "gate", self.out)
            shutil.copy(SRC / "tests.js", self.out / "tests.js")
        pages.build_offline_zip(self)
        if not self.public:
          self.write("tests.html", "<!doctype html><meta charset=utf-8><title>MarxBase tests</title><style>.ok{color:#0a6b2f}.bad{color:#a1260b;font-weight:700}body{font:15px system-ui;margin:20px}</style>"
                   "<h1>Search-core tests</h1><p id=summary>running...</p><ul id=out></ul><div id=app hidden></div><script src=data.js></script><script src=search-core.js></script><script src=cite.js></script><script src=suggest.js></script>"
                   "<script src=expected.js></script><script src=app.js></script><script src=tests.js></script>")
        return self.count


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True, help="a releases/<version> folder")
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--config", default=str(HERE / "site-config.json"), help="site-config.json with supabaseUrl and supabaseAnonKey (public anon key only); optional")
    ap.add_argument("--public", action="store_true", help="the hosted build: content-security policy on, no test pages or gate files")
    ap.add_argument("--look", default="uci", choices=LOOKS, help="the visual look (colors and fonts); the published site uses one of them")
    ap.add_argument("--preview", action="store_true", help="also write _look.html, a style tile (never in a --public build)")
    ap.add_argument("--csp", action="store_true", help="add a Content-Security-Policy meta tag (for the hosted build; test it before use: some browsers apply 'self' differently to file:// pages)")
    a = ap.parse_args(argv)
    site = Site(Path(a.bundle), Path(a.out), csp=a.csp, config=Path(a.config), public=a.public, look=a.look, preview=a.preview)
    n = site.build()
    print(f"built {n} files into {a.out} from release {site.version}: {len(site.results)} results, {len(site.findings)} findings, "
          f"{len(site.genes)} genes, {len(site.strains)} strains, {len(site.papers)} papers, {len(site.products)} products")
    return 0


if __name__ == "__main__":
    sys.exit(main())

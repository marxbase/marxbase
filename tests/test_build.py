"""Tests for the MarxBase static site builder (build.py). They build from the draft release bundle in the research
repository (skipped if it is not there) and from a mutated copy to prove that hostile text cannot inject markup."""
import csv
import json
import re
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402

def _bundle() -> Path:
    """The release the site is built from: the one named in CURRENT_RELEASE, in releases/ here (public repository) or next to this folder (development)."""
    ver = (HERE / "CURRENT_RELEASE").read_text(encoding="utf-8").strip() if (HERE / "CURRENT_RELEASE").exists() else "1.0"
    for base in (HERE / "releases", HERE.parent / "releases"):
        if (base / ver).exists():
            return base / ver
    return HERE.parent / "releases" / ver


BUNDLE = _bundle()
VERSION = BUNDLE.name


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.scripts, self.inline_scripts, self.attrs = [], [], 0, []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for k in d:
            self.attrs.append(k)
        if tag == "script":
            if d.get("type") == "application/json":
                pass
            elif d.get("src"):
                self.scripts.append(d["src"])
            else:
                self.inline_scripts += 1
        for k in ("href", "src"):
            if d.get(k):
                self.refs.append(d[k])


@unittest.skipUnless(BUNDLE.exists(), "draft release bundle not found")
class BuiltSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "dist"
        cls.site = build.Site(BUNDLE, cls.out)
        cls.site.build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_page_counts_match_the_bundle(self):
        s = self.site
        for folder, n in (("result", len(s.results)), ("gene", len(s.genes)), ("strain", len(s.strains)), ("paper", len(s.papers)), ("product", len(s.products))):
            self.assertEqual(len(list((self.out / folder).glob("*.html"))), n, folder)
        for page in ("index", "genes", "strains", "papers", "products", "about", "tests"):
            self.assertTrue((self.out / f"{page}.html").exists(), page)

    def test_every_internal_link_resolves(self):
        bad = []
        for page in self.out.rglob("*.html"):
            p = Links()
            p.feed(page.read_text(encoding="utf-8"))
            for ref in p.refs:
                if re.match(r"(https?:|mailto:|#|data:)", ref):
                    continue
                target = (page.parent / ref.split("#")[0].split("?")[0]).resolve()
                if not target.exists():
                    bad.append((page.name, ref))
        self.assertEqual(bad[:5], [])

    def test_only_our_own_scripts_and_no_event_handlers(self):
        own = {"data.js", "search-core.js", "cite.js", "app.js", "paperpage.js", "suggest.js", "site.js", "papers.js", "config.js", "expected.js", "tests.js"}
        for page in self.out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            p = Links()
            p.feed(text)
            self.assertEqual(p.inline_scripts, 0, page.name)
            self.assertTrue(all(Path(s.split("?")[0]).name in own for s in p.scripts), (page.name, p.scripts))
            self.assertFalse([a for a in p.attrs if a.startswith("on")], page.name)
            self.assertNotIn("javascript:", text.lower())

    def test_data_js_is_valid_and_complete(self):
        text = (self.out / "data.js").read_text(encoding="utf-8")
        data = json.loads(text[len("window.MARXBASE = "):].rstrip().rstrip(";"))
        self.assertEqual(len(data["results"]), len(self.site.results))
        self.assertEqual(len(data["genes"]), len(self.site.genes))
        self.assertFalse([k for k in data["papers"][next(iter(data["papers"]))] if "abstract" in k])   # no abstract field is shipped
        self.assertFalse(any("abstract" in k for r in data["results"][:50] for k in r))

    def test_known_content(self):
        s = self.site
        gene = {g["gene_name"]: g for g in s.genes.values()}
        lac = (self.out / "gene" / f"{gene['LAC12']['gene_id']}.html").read_text(encoding="utf-8")
        self.assertIn("Undetermined", lac)
        self.assertIn("KLMA_", lac)
        gda = (self.out / "gene" / f"{gene['GDA']['gene_id']}.html").read_text(encoding="utf-8")
        self.assertIn("not a gene symbol", gda)
        dnl = (self.out / "gene" / f"{gene['DNL4']['gene_id']}.html").read_text(encoding="utf-8")
        self.assertIn("LIG4", dnl)
        self.assertIn("YOR005C", dnl)
        nb = next(st for st in s.strains.values() if st["strain_name"] == "NBRC 1777")
        page = (self.out / "strain" / f"{nb['strain_id']}.html").read_text(encoding="utf-8")
        self.assertIn("Includes results recorded under derived strains", page)
        xyl = (self.out / "product" / "xylitol.html").read_text(encoding="utf-8")
        self.assertIn("What worked", xyl)
        self.assertIn("What failed", xyl)
        r = s.results[0]
        res = (self.out / "result" / f"{r['public_id']}.html").read_text(encoding="utf-8")
        self.assertIn(f"pubmed.ncbi.nlm.nih.gov/{r['pmid']}/", res)
        self.assertIn(r["public_id"], res)
        self.assertIn("third-party text" if s.has_evidence else "Evidence sentences are not included in this release", res)
        combo = next(rs for rs in s.findings.values() if len(rs) > 1)
        page = (self.out / "result" / f"{combo[0]['public_id']}.html").read_text(encoding="utf-8")
        self.assertIn("Changed together", page)

    def test_strains_page_lists_only_k_marxianus_parent_strains_and_compiles_derived(self):
        s = self.site
        page = (self.out / "strains.html").read_text(encoding="utf-8")
        hosts = {}
        for r in s.results:
            if r["strain_id"]:
                hosts.setdefault(r["strain_id"], set()).add(r["host_organism"])
        other_only = [s.strains[i]["strain_name"] for i, h in hosts.items() if "K. marxianus" not in h]
        self.assertTrue(other_only)
        for name in other_only:
            self.assertNotIn(f">{build.esc(name)}</a>", page, name)
        self.assertIn(">NBRC 1777</a>", page)
        derived = [st for st in s.strains.values() if st["parent_strain_id"]]
        self.assertTrue(derived)
        for st in derived:                                                 # derived strains are not listed at all
            self.assertNotIn(f">{build.esc(st['strain_name'])}</a>", page, st["strain_name"])
        nb = next(st for st in s.strains.values() if st["strain_name"] == "NBRC 1777")
        members = [x for x in s.strains if s.strain_root[x] == nb["strain_id"]]
        self.assertGreater(len(members), 1)
        n = sum(1 for r in s.results if r["strain_id"] in members)
        self.assertIn(f">NBRC 1777</a> <span class=\"small\">{n} results</span>", page)
        strain_page = (self.out / "strain" / f"{nb['strain_id']}.html").read_text(encoding="utf-8")
        self.assertIn("Includes results recorded under derived strains", strain_page)
        for x in members:                                                  # every derived strain page points to its parent
            if x != nb["strain_id"]:
                self.assertIn(f'href="{nb["strain_id"]}.html"', (self.out / "strain" / f"{x}.html").read_text(encoding="utf-8"))
        res = next(r for r in s.results if r["strain_id"] in members and r["strain_id"] != nb["strain_id"])
        line = (self.out / "result" / f"{res['public_id']}.html").read_text(encoding="utf-8")
        self.assertIn(f'recorded as {build.esc(res["strain_name"])}', line)
        self.assertIn(f'strain/{nb["strain_id"]}.html', line)

    def test_genes_page_has_two_sections_and_hides_labels_and_other_host_only_genes(self):
        s = self.site
        page = (self.out / "genes.html").read_text(encoding="utf-8")
        self.assertEqual(page.count("<details"), 2)
        self.assertIn("<details open><summary><i>K. marxianus</i> genes (", page)                         # the first section is open and can be folded
        self.assertIn("<details><summary>Genes from other species expressed in <i>K. marxianus</i> (", page)
        self.assertNotIn("Genes studied only in other host organisms", page)
        self.assertNotIn("the result was obtained in a K. marxianus host", page)
        a, b = page.index("<i>K. marxianus</i> genes ("), page.index("Genes from other species expressed in <i>K. marxianus</i>")
        km_host = {r["gene_id"] for r in s.results if r["host_organism"] == "K. marxianus"}
        for g in s.genes.values():
            listed = f'href="gene/{g["gene_id"]}.html"' in page
            if g["gene_kind"] == "enzyme_or_protein_label":
                self.assertFalse(listed, g["gene_name"])
            elif g["organism"] == "K. marxianus":
                self.assertTrue(listed and a < page.index(f'href="gene/{g["gene_id"]}.html"') < b, g["gene_name"])
            elif g["gene_id"] in km_host:
                self.assertTrue(listed and page.index(f'href="gene/{g["gene_id"]}.html"') > b, g["gene_name"])
            else:
                self.assertFalse(listed, g["gene_name"])                                              # other species in other hosts only
        km_names = {g["gene_name"] for g in s.genes.values() if g["organism"] == "K. marxianus"}
        other_only = [g["gene_name"] for g in s.genes.values() if g["organism"] != "K. marxianus" and g["gene_id"] not in km_host and g["gene_name"] not in km_names]
        self.assertGreaterEqual(len(other_only), 5)
        for name in other_only + ["GDA"]:
            self.assertNotIn(f">{build.esc(name)}</a>", page, name)

    def test_products_page_lists_classes_and_class_pages_list_products(self):
        s = self.site
        page = (self.out / "products.html").read_text(encoding="utf-8")
        classes = {p["product_class"] for p in s.products.values()}
        self.assertEqual(len(re.findall(r'href="product-class/', page)), len(classes))
        self.assertNotIn('href="product/', page)                            # specific products only on the class pages
        cls = (self.out / "product-class" / "sugar-alcohols-and-polyols.html").read_text(encoding="utf-8")
        self.assertIn("Xylitol", cls)
        self.assertIn('href="../product/xylitol.html"', cls)
        self.assertIn('href="../product-class/sugar-alcohols-and-polyols.html"', (self.out / "product" / "xylitol.html").read_text(encoding="utf-8"))

    def test_strain_flags_in_data_js(self):
        text = (self.out / "data.js").read_text(encoding="utf-8")
        data = json.loads(text[len("window.MARXBASE = "):].rstrip().rstrip(";"))
        self.assertTrue(any(s["home"] for s in data["strains"].values()))
        self.assertTrue(any(not s["home"] for s in data["strains"].values()))

    def test_gate_answers_are_written(self):
        answers = (HERE / "gate" / "GATE_ANSWERS.md").read_text(encoding="utf-8")
        self.assertIn("KU70", answers)
        self.assertTrue((self.out / "expected.js").exists())
        self.assertEqual(len((HERE / "gate" / "GATE_QUESTIONS.md").read_text(encoding="utf-8").split("\n1. ")), 2)

    # ----- session 4: downloads, charts, Methods, offline copy -----
    def test_session4_pages_exist_and_are_in_the_nav(self):
        for page in ("summary", "methods", "downloads"):
            text = (self.out / f"{page}.html").read_text(encoding="utf-8")
            self.assertIn(f'href="{page}.html"', text)
        self.assertIn("Draft for the curators to edit", (self.out / "methods.html").read_text(encoding="utf-8"))

    def test_data_zip_has_public_files_and_no_private_folder(self):
        import zipfile
        with zipfile.ZipFile(self.out / "downloads" / f"marxbase-{self.site.version}-data.zip") as z:
            names = z.namelist()
            self.assertEqual(z.testzip(), None)
        base = {n.split("/", 1)[1] for n in names}
        for need in ("results.csv", "citations.csv", "marxbase_public.sqlite", "citations.csl.json", "DATA_DICTIONARY.md", "SHA256SUMS", "LICENCE.txt"):
            self.assertIn(need, base)
        self.assertFalse([n for n in names if "private" in n])
        self.assertFalse([n for n in base if "abstract" in n.lower()])

    def test_offline_zip_is_self_contained(self):
        import zipfile
        site = self.site
        with zipfile.ZipFile(self.out / "downloads" / f"marxbase-{site.version}-offline-site.zip") as z:
            names = set(z.namelist())
            top = next(iter(names)).split("/")[0] + "/"
            rel = {n[len(top):] for n in names}
            for dev in ("tests.html", "tests.js", "expected.js"):
                self.assertNotIn(dev, rel)
            self.assertFalse([n for n in rel if n.startswith("gate/")])
            self.assertFalse([n for n in rel if "offline-site.zip" in n])
            self.assertIn(f"downloads/marxbase-{site.version}-data.zip", rel)
            self.assertNotIn("offline-site.zip", z.read(top + "downloads.html").decode("utf-8"))
            self.assertIn("offline-site.zip", (self.out / "downloads.html").read_text(encoding="utf-8"))
            bad = []
            for n in sorted(rel):
                if not n.endswith(".html"):
                    continue
                parser = Links()
                parser.feed(z.read(top + n).decode("utf-8"))
                for ref in parser.refs:
                    if re.match(r"(https?:|mailto:|#|data:)", ref):
                        continue
                    target = (Path(n).parent / ref.split("#")[0].split("?")[0]).as_posix()
                    target = str(Path(target)) if ".." not in target else __import__("posixpath").normpath(target)
                    if target and target not in rel:
                        bad.append((n, ref))
            self.assertEqual(bad[:5], [])

    def test_zip_build_is_reproducible(self):
        import zipfile
        pages = __import__("pages")
        a = [("x/b.txt", b"2"), ("x/a.txt", b"1")]
        with tempfile.TemporaryDirectory() as d:
            pages.make_zip(Path(d) / "1.zip", a)
            pages.make_zip(Path(d) / "2.zip", list(reversed(a)))
            self.assertEqual((Path(d) / "1.zip").read_bytes(), (Path(d) / "2.zip").read_bytes())

    def test_chart_numbers_match_a_recount(self):
        pages = __import__("pages")
        d = pages.chart_data(self.site)
        km_rows = [r for r in self.site.results if r["host_organism"] == "K. marxianus"]
        fids = {r["finding_id"] for r in km_rows}
        self.assertEqual(d["n"], len(fids))
        self.assertEqual(sum(sum(v.values()) for v in d["cat"].values()), len(fids))
        self.assertEqual(d["n_papers"], len({r["pmid"] for r in km_rows}))
        self.assertEqual(sum(d["years"].values()), d["n_papers"])
        text = (self.out / "summary.html").read_text(encoding="utf-8")
        self.assertIn(f'{d["n"]} findings from {d["n_papers"]} papers', text)
        self.assertEqual(text.count('class="viz"'), 4)
        self.assertEqual(text.count("Show as a table"), 4)

    def test_doi_appears_in_the_citation_and_the_data_when_a_doi_file_exists(self):
        doi = (HERE / "DOI").read_text(encoding="utf-8").strip() if (HERE / "DOI").exists() else ""
        down = (self.out / "downloads.html").read_text(encoding="utf-8")
        data = (self.out / "data.js").read_text(encoding="utf-8").replace(" ", "")
        if doi:
            self.assertIn(f"https://doi.org/{doi}", down)
            self.assertIn(f'"doi":"{doi}"', data)
            self.assertNotIn("DOI pending", down)
        else:
            self.assertIn("DOI pending", down)

    def test_every_script_and_stylesheet_carries_the_same_version_tag(self):
        tags = set()
        for page in [self.out / "index.html", next((self.out / "paper").glob("*.html")), next((self.out / "result").glob("*.html")), self.out / "genes.html"]:
            text = page.read_text(encoding="utf-8")
            refs = re.findall(r'(?:<script src|<link rel="stylesheet" href)="([^"]+)"', text)
            self.assertTrue(refs, page.name)
            for ref in refs:
                self.assertRegex(ref, r"\.(js|css)\?v=" + re.escape(VERSION) + r"-[0-9a-f]{8}$", f"{page.name}: {ref}")
                tags.add(ref.split("?v=")[1])
        self.assertEqual(len(tags), 1, tags)

    def test_home_page_boxes_match_the_pages_they_link_to(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="hero"', home)
        boxes = {label: (int(n.replace(",", "")), href) for href, n, label in re.findall(r'<li><a href="([^"]+)"><b>([\d,]+)</b><strong>(\w+)</strong>', home)}
        self.assertEqual(set(boxes), {"Findings", "Genes", "Strains", "Papers", "Products"})
        self.assertEqual(boxes["Papers"][0], len(self.site.papers))
        self.assertEqual(boxes["Products"][0], len(self.site.products))
        self.assertEqual(boxes["Genes"][0], int(re.search(r"K\. marxianus</i> genes \((\d+)\)", (self.out / "genes.html").read_text(encoding="utf-8")).group(1)))
        self.assertEqual(boxes["Strains"][0], (self.out / "strains.html").read_text(encoding="utf-8").count('<li><a href="strain/'))
        for label, (n, href) in boxes.items():
            self.assertTrue((self.out / href.split("?")[0]).exists(), href)
        km_findings = {r["finding_id"] for r in self.site.results if r["host_organism"] == "K. marxianus"}
        self.assertEqual(boxes["Findings"], (len(km_findings), "index.html?browse=1"))
        self.assertNotIn("Browse all", home)
        self.assertIn("<h1><i>Kluyveromyces marxianus</i> metabolic engineering database</h1>", home)
        for example in build.Site.EXAMPLES:
            self.assertIn(f'index.html?q={build.urllib.parse.quote(example)}"', home)

    def test_landing_page_structure(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('<body class="home">', home)                      # the navigation bar is hidden on the home page by this class
        # centered headline and the examples first, then the search app, then the scrolling sections
        self.assertLess(home.index('id="hero"'), home.index('class="examples"'))
        self.assertLess(home.index('class="examples"'), home.index('id="app"'))
        self.assertLess(home.index('id="app"'), home.index('id="hero-extras"'))
        self.assertLess(home.index('id="hero-extras"'), home.index("<script src=\"data.js"))
        self.assertNotIn("Read from paper abstracts", home)
        extras = home[home.index('id="hero-extras"'):]
        self.assertLess(extras.index("Browse the data"), extras.index("About MarxBase"))
        about = extras[extras.index("About MarxBase"):]
        for page in ("summary.html", "methods.html", "downloads.html", "about.html"):
            self.assertIn(f'<a href="{page}">', about)
        self.assertNotIn('class="examples"', extras)
        # every other page keeps its navigation and is not a "home" page
        self.assertNotIn('<body class="home">', (self.out / "genes.html").read_text(encoding="utf-8"))

    def test_home_page_photo_is_the_background_of_the_about_band_and_resized(self):
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("photo-band", home)
        self.assertNotIn("<img", re.sub(r'<svg.*?</svg>', "", home, flags=re.S))      # the picture is a CSS background, not an image element
        self.assertIn('<section class="band band-photo" aria-labelledby="h-about">', home)
        css = (self.out / "style.css").read_text(encoding="utf-8")
        for name in ("km-colonies-wide.jpg", "km-colonies-tall.jpg"):
            self.assertIn(f"img/{name}", css)
            f = self.out / "img" / name
            self.assertTrue(f.exists(), name)
            self.assertLess(f.stat().st_size, 250_000, f"{name} is resized for the web")
        self.assertEqual(sorted(p.name for p in (self.out / "img").iterdir()), ["km-colonies-tall.jpg", "km-colonies-wide.jpg"])   # no full-size original, no stale files
        self.assertFalse((self.out / "Km_colonies_1.jpeg").exists())
        # the heading is white over a dark veil, and the boxes are in front
        self.assertRegex(css, r"\.band-photo::before \{[^}]*rgba\(0, 0, 0, \.5\)")
        self.assertRegex(css, r"\.band-photo \.inner \{ position: relative; \}")

    def test_every_page_has_the_menu_button_and_the_site_script(self):
        for page in [self.out / "index.html", self.out / "genes.html", next((self.out / "paper").glob("*.html")), next((self.out / "result").glob("*.html"))]:
            text = page.read_text(encoding="utf-8")
            self.assertIn('id="menu-toggle"', text, page.name)
            self.assertIn('id="site-nav"', text, page.name)
            self.assertRegex(text, r'<script src="[^"]*site\.js\?v=' + re.escape(VERSION) + r'-[0-9a-f]{8}"></script></head>', page.name)

    def test_papers_page_has_year_headings_with_counts_and_the_toggle(self):
        text = (self.out / "papers.html").read_text(encoding="utf-8")
        years = re.findall(r'<section class="year"><h2>(\d{4}) <span class="small count">\((\d+) papers?\)</span></h2>', text)
        self.assertEqual(sum(int(n) for _, n in years), len(self.site.papers))
        self.assertEqual([y for y, _ in years], sorted((y for y, _ in years), reverse=True))
        self.assertIn('id="only-findings" class="switch" checked', text)           # a switch, on by default
        self.assertIn("dot-yes", text); self.assertIn("dot-no", text)               # the key beside the switch
        self.assertNotIn("papers-summary", text)                                    # the two summary lines were removed
        self.assertNotIn("newest first", text)
        self.assertRegex(text, r'<script src="papers\.js\?v=' + re.escape(VERSION) + r'-[0-9a-f]{8}"></script>')

    def test_data_js_carries_every_result_column_and_paper_citation_fields(self):
        js = (self.out / "data.js").read_text(encoding="utf-8")
        data = json.loads(js[len("window.MARXBASE = "):].rstrip().rstrip(";"))
        hidden = {"evidence_sentence_html"} | (set() if self.site.has_evidence else {"evidence_sentence", "evidence_source"})
        self.assertEqual(set(data["columns"]), set(self.site.t["results"][0]) - hidden)
        self.assertEqual(len(data["results"]), len(self.site.results))
        p = next(iter(data["papers"].values()))
        for k in ("pmid", "title", "authors", "journal", "year", "doi", "pmcid"):
            self.assertIn(k, p)
        self.assertFalse([k for k in data["columns"] + list(p) if "abstract" in k])

    def test_paper_page_has_citation_data_that_cannot_break_out(self):
        page = (self.out / "paper" / f"{next(iter(self.site.papers))}.html").read_text(encoding="utf-8")
        self.assertIn('id="paper-data"', page)
        self.assertIn("../cite.js", page)


@unittest.skipUnless(BUNDLE.exists(), "draft release bundle not found")
class HostileTextTests(unittest.TestCase):
    def test_injected_markup_is_escaped_or_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            bundle = Path(d) / "b"
            shutil.copytree(BUNDLE, bundle, ignore=shutil.ignore_patterns("private", "*.sqlite"))
            rows = list(csv.DictReader(open(bundle / "results.csv", encoding="utf-8-sig")))
            cols = list(rows[0])
            evil = '<script>alert(1)</script><img src=x onerror=alert(2)>'
            for r in rows[:3]:
                r["phenotype"] = evil
                r["evidence_sentence_html"] = evil
                r["evidence_sentence"] = evil
                r["comparator"] = evil
            with open(bundle / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            out = Path(d) / "dist"
            build.Site(bundle, out).build()
            for page in out.rglob("*.html"):
                text = page.read_text(encoding="utf-8")
                self.assertNotIn("<script>alert", text, page.name)
                self.assertNotIn("<img", text, page.name)
            self.assertNotIn("</script><img", (out / "data.js").read_text(encoding="utf-8"))
            page = (out / "result" / f"{rows[0]['public_id']}.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;", page)


class ReportFormTests(unittest.TestCase):
    """The report form appears only when a site configuration exists, never in the offline copy, and never carries a service key."""

    def build(self, tmp, config=None, **kw):
        cfgpath = None
        if config is not None:
            cfgpath = Path(tmp) / "cfg.json"
            cfgpath.write_text(json.dumps(config), encoding="utf-8")
        site = build.Site(BUNDLE, Path(tmp) / "dist", config=cfgpath, **kw)
        site.build()
        return site

    def test_no_config_means_no_form(self):
        with tempfile.TemporaryDirectory() as d:
            self.build(d)
            self.assertFalse((Path(d) / "dist" / "config.js").exists())
            self.assertNotIn("suggest-box", next((Path(d) / "dist" / "result").glob("*.html")).read_text(encoding="utf-8"))

    def test_config_adds_the_form_to_detail_pages_and_csp_allows_only_that_address(self):
        cfg = {"supabaseUrl": "https://abc.supabase.co/", "supabaseAnonKey": "anon-public-key"}
        with tempfile.TemporaryDirectory() as d:
            site = self.build(d, cfg, csp=True)
            out = Path(d) / "dist"
            self.assertIn("https://abc.supabase.co", (out / "config.js").read_text(encoding="utf-8"))
            for folder in ("result", "gene", "paper", "strain", "product"):
                page = next((out / folder).glob("*.html")).read_text(encoding="utf-8")
                self.assertIn('id="suggest-box"', page, folder)
                self.assertIn(f'data-release="{VERSION}"', page, folder)
                self.assertIn("connect-src 'self' https://abc.supabase.co", page, folder)
            self.assertNotIn("suggest-box", (out / "genes.html").read_text(encoding="utf-8"))
            # the offline zip has no form, no keys, and no dangling script references
            import zipfile
            with zipfile.ZipFile(out / "downloads" / f"marxbase-{site.version}-offline-site.zip") as z:
                names = z.namelist()
                self.assertFalse([n for n in names if n.endswith(("config.js", "suggest.js"))])
                blob = b"".join(z.read(n) for n in names if n.endswith(".html"))
                self.assertNotIn(b"suggest-box", blob)
                self.assertNotIn(b"config.js", blob)
                self.assertNotIn(b"anon-public-key", b"".join(z.read(n) for n in names))

    def test_a_service_key_or_insecure_address_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for cfg in ({"supabaseUrl": "http://x.supabase.co", "supabaseAnonKey": "k"},
                        {"supabaseUrl": "https://x.supabase.co", "supabaseAnonKey": "my-service_role-key"},
                        {"supabaseUrl": "https://x.supabase.co", "supabaseAnonKey": ""}):
                with self.assertRaises(SystemExit):
                    self.build(d, cfg)


class EvidenceSwitchTests(unittest.TestCase):
    """With sentences hidden the site says so and quotes nothing; with sentences present it shows them and states the licence exception."""

    def build_with(self, d, sentence):
        bundle = Path(d) / "b"
        shutil.copytree(BUNDLE, bundle, ignore=shutil.ignore_patterns("private", "*.sqlite"))
        path = bundle / "results.csv"
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0])
        for r in rows:
            r["evidence_sentence"] = sentence
            r["evidence_sentence_html"] = sentence
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, cols)
            w.writeheader()
            w.writerows(rows)
        site = build.Site(bundle, Path(d) / "dist")
        site.build()
        return site, Path(d) / "dist"

    def test_hidden_release(self):
        with tempfile.TemporaryDirectory() as d:
            site, out = self.build_with(d, "")
            self.assertFalse(site.has_evidence)
            self.assertNotIn("Evidence sentences quote", (out / "downloads.html").read_text(encoding="utf-8"))
            data = (out / "data.js").read_text(encoding="utf-8")
            self.assertNotIn('"evidence_sentence"', data)
            self.assertIn('"hasEvidence":false', data.replace(" ", ""))

    def test_released_sentences(self):
        with tempfile.TemporaryDirectory() as d:
            site, out = self.build_with(d, "A sentence from the abstract.")
            self.assertTrue(site.has_evidence)
            self.assertIn("Evidence sentences quote", (out / "downloads.html").read_text(encoding="utf-8"))
            page = (out / "result" / f"{site.results[0]['public_id']}.html").read_text(encoding="utf-8")
            self.assertIn("A sentence from the abstract.", page)
            self.assertIn("third-party text", page)
            self.assertIn('"hasEvidence":true', (out / "data.js").read_text(encoding="utf-8").replace(" ", ""))


def _lum(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class LookTests(unittest.TestCase):
    """The two looks: every text pair meets WCAG AA, the result-class colors are shared, fonts are self-hosted, and nothing is fetched from outside."""

    TEXT_PAIRS = [("--bar-ink", "--bar"), ("--bar-ink-2", "--bar"), ("--accent-ink", "--accent"), ("--accent-ink", "--accent-hover"), ("--ink", "--bg"), ("--ink", "--surface"),
                  ("--heading", "--bg"), ("--heading", "--surface"), ("--muted", "--bg"), ("--muted", "--surface"), ("--link", "--bg"), ("--link", "--surface"), ("--bar-accent", "--bar")]
    UI_PAIRS = [("--line-strong", "--bg")]

    def test_every_text_pair_meets_AA_in_both_looks(self):
        for look in build.LOOKS:
            tok = build.look_tokens(look)
            for a, b in self.TEXT_PAIRS:
                need = 3.0 if a == "--bar-accent" else 4.5
                self.assertGreaterEqual(contrast(tok[a], tok[b]), need, f"{look}: {a} on {b}")
            for a, b in self.UI_PAIRS:
                self.assertGreaterEqual(contrast(tok[a], tok[b]), 3.0, f"{look}: {a} on {b}")
            for cls in ("pos", "neg", "ctx"):
                self.assertGreaterEqual(contrast(tok[f"--{cls}-ink"], tok[f"--{cls}-tint"]), 4.5, f"{look}: {cls} chip")
                self.assertGreaterEqual(contrast(tok[f"--{cls}-ink"], "#ffffff"), 4.5, f"{look}: {cls} ink on white")

    def test_class_colors_are_the_same_in_both_looks(self):
        a, b = build.look_tokens("neutral"), build.look_tokens("uci")
        for k in ("--pos", "--neg", "--ctx", "--pos-ink", "--neg-ink", "--ctx-ink"):
            self.assertEqual(a[k], b[k], k)

    def test_both_looks_build_with_favicon_and_only_uci_ships_fonts(self):
        for look in build.LOOKS:
            with tempfile.TemporaryDirectory() as d:
                site = build.Site(BUNDLE, Path(d) / "dist", look=look, preview=True)
                site.build()
                out = Path(d) / "dist"
                self.assertIn(build.look_tokens(look)["--accent"], (out / "favicon.svg").read_text(encoding="utf-8"))
                self.assertIn('rel="icon"', (out / "index.html").read_text(encoding="utf-8"))
                self.assertTrue((out / "_look.html").exists())
                css = (out / "style.css").read_text(encoding="utf-8")
                self.assertIn("--accent:", css)
                self.assertIn(".brand", css)
                if look == "uci":
                    self.assertTrue((out / "fonts" / "OFL.txt").exists() and (out / "fonts" / "montserrat-latin.woff2").exists())
                    self.assertIn("fonts/montserrat-latin.woff2", css)
                else:
                    self.assertFalse((out / "fonts").exists())
                    self.assertNotIn("Montserrat", css)
                # nothing is loaded from another server
                self.assertFalse(re.findall(r"url\(\s*['\"]?https?:", css))
                self.assertFalse(re.findall(r"@import", css))

    def test_public_build_has_no_style_tile_and_keeps_the_policy(self):
        with tempfile.TemporaryDirectory() as d:
            site = build.Site(BUNDLE, Path(d) / "dist", public=True, preview=True)
            site.build()
            self.assertFalse((Path(d) / "dist" / "_look.html").exists())
            self.assertIn("Content-Security-Policy", (Path(d) / "dist" / "index.html").read_text(encoding="utf-8"))

    def test_an_unknown_look_is_refused(self):
        with self.assertRaises(SystemExit):
            build.Site(BUNDLE, Path("x"), look="neon")


class SpeciesItalicsTests(unittest.TestCase):
    """Species names are italicised in page text only: never in tags, attributes, scripts or dropdown options."""

    NAMES = None

    @classmethod
    def setUpClass(cls):
        import species
        cls.sp = species
        cls.names = species.names_from(["K. marxianus", "Homo sapiens", "Gerbera hybrida", "Other"])

    def test_names_in_text_are_wrapped(self):
        out = self.sp.italicize("<p>Host K. marxianus and S. cerevisiae; Gerbera hybrida &amp; Homo sapiens.</p>", self.names)
        for n in ("K. marxianus", "S. cerevisiae", "Gerbera hybrida", "Homo sapiens"):
            self.assertIn(f"<i>{n}</i>", out)

    def test_nothing_is_touched_in_tags_attributes_scripts_or_options(self):
        html_in = ('<a href="x" title="K. marxianus">link</a><script>var a="K. marxianus"</script><select><option>K. marxianus</option></select>'
                   '<code>S. cerevisiae</code><i>E. coli</i><svg><text>K. marxianus</text></svg><title>K. marxianus</title>')
        self.assertEqual(self.sp.italicize(html_in, self.names), html_in)

    def test_word_boundaries_and_idempotence(self):
        self.assertEqual(self.sp.italicize("<p>NotK. marxianusX and K. marxianusish</p>", self.names), "<p>NotK. marxianusX and K. marxianusish</p>")
        once = self.sp.italicize("<p>K. marxianus</p>", self.names)
        self.assertEqual(self.sp.italicize(once, self.names), once)

    def test_the_built_site_italicises_hosts_and_genes_page_sections(self):
        site = build.Site(BUNDLE, Path(tempfile.mkdtemp()) / "dist")
        site.build()
        genes = (site.out / "genes.html").read_text(encoding="utf-8")
        self.assertIn("<i>K. marxianus</i> genes (", genes)
        result = (site.out / "result" / f"{site.results[0]['public_id']}.html").read_text(encoding="utf-8")
        self.assertIn("<i>K. marxianus</i>", result)
        data = (site.out / "data.js").read_text(encoding="utf-8")
        self.assertIn('"species":[', data.replace(" ", ""))
        shutil.rmtree(site.out.parent, ignore_errors=True)


class MinedPapersTests(unittest.TestCase):
    """Papers that were text-mined but have no finding are listed (Papers page, their own pages) and counted in the Papers box, but stay out of the
    search data and of the 'results from N papers' counts."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        bundle = Path(cls.tmp) / "b"
        shutil.copytree(BUNDLE, bundle, ignore=shutil.ignore_patterns("private", "*.sqlite"))
        path = bundle / "citations.csv"
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0])
        cls.n_with = sum(1 for r in rows if int(r["n_results"] or 0) > 0)        # the bundle may already list text-mined papers without findings
        cls.n_all = len(rows)
        for i, (year, title) in enumerate(((2024, "A mined paper about <i>K. marxianus</i> without findings"), (1999, "An old mined paper"))):
            r = dict.fromkeys(cols, "")
            r.update(pmid=f"9000000{i}", title=title, title_html=title, authors="Nobody N; Else E", journal="J Test", year=str(year), n_results="0", doi="", pmcid="", first_author="Nobody N")
            rows.append(r)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, cols)
            w.writeheader()
            w.writerows(rows)
        cls.site = build.Site(bundle, Path(cls.tmp) / "dist")
        cls.site.build()
        cls.out = Path(cls.tmp) / "dist"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_counts(self):
        self.assertEqual(len(self.site.papers), self.n_all + 2)
        self.assertEqual(len(self.site.papers_with), self.n_with)
        home = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn(f"<b>{self.n_all + 2:,}</b><strong>Papers</strong><span>Abstracts text-mined; {self.n_with} with findings</span>", home)
        self.assertIn(f"results from {self.n_with} papers", home)                   # the footer counts papers with findings only

    def test_papers_page_lists_them_marked_and_the_pages_exist(self):
        text = (self.out / "papers.html").read_text(encoding="utf-8")
        self.assertEqual(text.count('<li class="nofind">'), self.n_all - self.n_with + 2)
        self.assertEqual(text.count("No findings extracted"), 0)                 # not repeated on every row: a hollow marker says it
        self.assertIn("1999", text)
        for pmid in ("90000000", "90000001"):
            page = (self.out / "paper" / f"{pmid}.html").read_text(encoding="utf-8")
            self.assertIn("No findings extracted", page)
            self.assertNotIn("<h2>Results (", page)
            self.assertIn('id="paper-cite"', page)
        self.assertIn("<i>K. marxianus</i>", (self.out / "paper" / "90000000.html").read_text(encoding="utf-8"))

    def test_search_data_holds_only_papers_with_findings(self):
        data = json.loads((self.out / "data.js").read_text(encoding="utf-8")[len("window.MARXBASE = "):].rstrip().rstrip(";"))
        self.assertEqual(len(data["papers"]), self.n_with)
        self.assertNotIn("90000000", data["papers"])


class BrowserScriptSyntaxTests(unittest.TestCase):
    """Every script the browser loads must parse. (A syntax error in app.js once blanked the live search page.)
    Uses Node if present (GitHub's runners have it) or macOS's built-in JavaScript engine; skipped where neither exists."""

    def test_scripts_parse(self):
        import shutil as sh
        import subprocess
        files = sorted(str(p) for p in (HERE / "src").glob("*.js"))
        self.assertTrue(files)
        node, osa = sh.which("node"), sh.which("osascript")
        if node:
            for f in files:
                r = subprocess.run([node, "--check", f], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{f}: {r.stderr}")
        elif osa:
            r = subprocess.run([osa, "-l", "JavaScript", str(HERE / "tests" / "syntax_check.js"), *files], capture_output=True, text=True)
            self.assertNotIn("FAIL", r.stdout + r.stderr, r.stdout + r.stderr)
            self.assertEqual(r.stdout.count("OK"), len(files), r.stdout + r.stderr)
        else:
            self.skipTest("neither node nor osascript is available")


class HelperTests(unittest.TestCase):
    def test_safe_html_and_numbers(self):
        self.assertEqual(build.safe_html("a <i>b</i> 10<sup>6</sup>", "x"), "a <i>b</i> 10<sup>6</sup>")
        self.assertEqual(build.safe_html("<b>bold</b>", "plain & <text>"), "plain &amp; &lt;text&gt;")
        self.assertEqual(build.safe_html("<i onclick=1>x</i>", "p"), "p")
        self.assertEqual(build.safe_html("a < b", "p"), "p")
        self.assertEqual(build.num("2.50"), 2.5)
        self.assertEqual(build.num("3"), 3)
        self.assertIsNone(build.num(""))
        self.assertEqual(build.slug("Esters (ethyl and other acetates)"), "esters-ethyl-and-other-acetates")


if __name__ == "__main__":
    unittest.main()

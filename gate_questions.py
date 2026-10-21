"""Computes the expected answers to the ten gate questions DIRECTLY from the release bundle (independent of the site's
JavaScript), and writes: gate/GATE_QUESTIONS.md (for testers), gate/GATE_ANSWERS.md (for the maintainer) and the
expected.js that the in-browser tests compare against."""
import json
from collections import defaultdict
from pathlib import Path

CLASS_NAMES = ("positive", "negative", "context-dependent")


def descendants(strains: dict, root: str) -> set:
    out, queue = {root}, [root]
    while queue:
        cur = queue.pop()
        for sid, s in strains.items():
            if s["parent_strain_id"] == cur and sid not in out:
                out.add(sid)
                queue.append(sid)
    return out


def compute(site) -> dict:
    F = site.findings                                   # finding_id -> member rows
    is_home = lambda rows: any(r["host_organism"] == "K. marxianus" for r in rows)
    classes = lambda fids: {c: sum(1 for f in fids if F[f][0]["result_class"] == c) for c in CLASS_NAMES}
    e = {"total_findings": len(F), "total_results": len(site.results), "home_findings": sum(1 for f in F.values() if is_home(f))}
    ku70 = [fid for fid, rows in F.items() if any(r["gene_name"] == "KU70" and r["gene_organism"] == "K. marxianus" for r in rows)]
    e["q1"] = {"findings": sorted(ku70), "n": len(ku70), "classes": classes(ku70)}
    xyl = [fid for fid, rows in F.items() if any(r["product"] == "Xylitol" for r in rows)]
    e["q2"] = {"n": len(xyl), "not_positive": sorted(f for f in xyl if F[f][0]["result_class"] != "positive"), "classes": classes(xyl)}
    nb = next((sid for sid, s in site.strains.items() if s["strain_name"] == "NBRC 1777"), None)
    if nb:
        d = descendants(site.strains, nb)
        e["q3"] = {"strain": nb, "with_derived": sum(1 for rows in F.values() if any(r["strain_id"] in d for r in rows)),
                   "without_derived": sum(1 for rows in F.values() if any(r["strain_id"] == nb for r in rows)),
                   "derived": sorted(site.strains[s]["strain_name"] for s in d if s != nb)}
    def genes_named(name):
        ids = {o["gene_id"] for o in site.t["gene_orthologs"] if name in (o["ortholog_gene_name"], o["ortholog_systematic_id"])}
        ids |= {a["gene_id"] for a in site.t["gene_aliases"] if a["alias_name"] == name}
        ids |= {r["gene_id"] for r in site.results if r["reported_gene_name"] == name}
        return ids
    for key, name in (("q4", "SUC2"), ("q4b", "YIL162W"), ("q5", "LIG4")):
        gids = genes_named(name)
        fids = sorted(fid for fid, rows in F.items() if any(r["gene_id"] in gids for r in rows))
        e[key] = {"query": name, "genes": sorted(site.genes[g]["gene_name"] for g in gids), "findings": fids}
    e["q6"] = sorted(g["gene_name"] for g in site.genes.values() if g["gene_kind"] == "undetermined_paralog")
    e["q7"] = sum(1 for rows in F.values() if any(r["host_organism"] == "Saccharomyces cerevisiae" for r in rows))
    e["q8"] = sum(1 for p in site.papers_with.values() if (int(p["year"]) if p["year"] else 0) >= 2025)
    dnl = next((g for g in site.genes.values() if g["gene_name"] == "DNL4" and g["organism"] == "K. marxianus"), None)
    if dnl:
        orth = [o for o in site.t["gene_orthologs"] if o["gene_id"] == dnl["gene_id"] and o["rank"] == "1"]
        e["q9"] = {"locus": dnl["locus_tag"], "ortholog": [(o["ortholog_gene_name"], o["ortholog_systematic_id"]) for o in orth]}
    gda = next((g for g in site.genes.values() if g["gene_name"] == "GDA"), None)
    if gda:
        e["q10"] = {"kind": gda["gene_kind"], "n_results": gda["n_results"]}
    return e


QUESTIONS = [
    "Open the gene page for KU70. How many findings does it list, and how many of them are negative or context-dependent?",
    "Open the product page for Xylitol. How many findings are listed under 'What failed or depended on conditions'?",
    "On the search page, choose the strain NBRC 1777 and switch on 'include results in other host organisms'. How many findings are shown with 'include derived strains' ticked, and how many with it unticked?",
    "Search for SUC2. Which gene's results come first? Then search for YIL162W: do you get the same gene?",
    "Search for LIG4. Which gene's results do you get (the database uses a different name)?",
    "On the Genes page, which genes carry the badge 'Undetermined paralog'?",
    "Switch on 'include results in other host organisms' and look at the Host organism filter. How many findings are in Saccharomyces cerevisiae?",
    "On the Papers page, how many papers published in 2025 or 2026 have results?",
    "Open the gene page for DNL4. What is its locus tag, and what is its S. cerevisiae ortholog (name and ID)?",
    "Open the gene page for GDA. What does its badge say, and how many results does it have?"]


def write_all(site, gate_dir: Path, dist: Path) -> dict:
    e = compute(site)
    gate_dir.mkdir(exist_ok=True)
    (gate_dir / "GATE_QUESTIONS.md").write_text(f"# MarxBase gate: ten questions (release {site.version})\n\nAnswer using only the website. A \"finding\" is one result, or one multi-gene combination counted once.\n\n" +
                                                "\n".join(f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1)) + "\n", encoding="utf-8")
    a = [f"# Answers (release {site.version}) - do not show testers", ""]
    a.append(f"1. KU70: {e['q1']['n']} findings; {e['q1']['classes']}")
    a.append(f"2. Xylitol: {len(e['q2']['not_positive'])} findings under 'What failed or depended on conditions' ({e['q2']['n']} in total; {e['q2']['classes']})")
    if "q3" in e:
        a.append(f"3. NBRC 1777 (all hosts): {e['q3']['with_derived']} with derived strains {e['q3']['derived']}; {e['q3']['without_derived']} without")
    a.append(f"4. SUC2 -> {e['q4']['genes']} ({len(e['q4']['findings'])} findings); YIL162W -> {e['q4b']['genes']}")
    a.append(f"5. LIG4 -> {e['q5']['genes']} ({len(e['q5']['findings'])} findings)")
    a.append(f"6. Undetermined paralogs: {', '.join(e['q6'])}")
    a.append(f"7. Findings in S. cerevisiae hosts: {e['q7']}")
    a.append(f"8. Papers from 2025 or later with results: {e['q8']}")
    if "q9" in e:
        a.append(f"9. DNL4 locus {e['q9']['locus']}; S. cerevisiae ortholog {e['q9']['ortholog']}")
    if "q10" in e:
        a.append(f"10. GDA: badge 'Enzyme or protein label, not a gene symbol' ({e['q10']['kind']}); {e['q10']['n_results']} results")
    (gate_dir / "GATE_ANSWERS.md").write_text("\n".join(a) + "\n", encoding="utf-8")
    (dist / "expected.js").write_text("window.EXPECTED = " + json.dumps(e) + ";\n", encoding="utf-8")
    return e

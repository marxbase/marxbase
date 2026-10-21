/* MarxBase search core: pure functions (no DOM), so the same code is tested in tests.html and used by app.js.
   A "finding" is one result, or one multi-gene combination counted once (all its member rows share finding_id). */
(function (root) {
  'use strict';
  const norm = (s) => (s == null ? '' : String(s)).toLowerCase();
  const squash = (s) => norm(s).replace(/[^a-z0-9]/g, '');
  const wordsOf = (s) => norm(s).split(/[^\p{L}\p{N}_\-.]+/u).filter(Boolean);
  const pretty = (s) => (s == null ? '' : String(s)).replace(/_/g, ' ');
  const HOME_HOST = 'K. marxianus';

  const FACETS = {
    classes: (f) => [f.cls], cats: (f) => [f.cat], products: (f) => f.products, pclasses: (f) => f.pclasses, types: (f) => f.types,
    dirs: (f) => [f.dir], gorgs: (f) => f.gorgs, hosts: (f) => f.hosts, countries: (f) => [f.country]
  };

  function defaultState() {
    return { q: '', classes: [], cats: [], products: [], pclasses: [], types: [], dirs: [], gorgs: [], hosts: [], countries: [],
             allHosts: false, strain: '', derived: true, ymin: null, ymax: null, sort: 'relevance' };
  }

  function descendants(data, id) {
    const kids = {};
    for (const [sid, s] of Object.entries(data.strains)) if (s.parent) (kids[s.parent] = kids[s.parent] || []).push(sid);
    const out = new Set([id]); const queue = [id];
    while (queue.length) { for (const k of kids[queue.pop()] || []) if (!out.has(k)) { out.add(k); queue.push(k); } }
    return out;
  }

  function build(data) {
    const groups = new Map();
    for (const r of data.results) {
      if (!groups.has(r.finding_id)) groups.set(r.finding_id, []);
      groups.get(r.finding_id).push(r);
    }
    const findings = [];
    for (const [fid, rows] of groups) {
      const idents = [], words = new Set();
      const addId = (v) => { if (v) { const n = norm(v); idents.push({ n, s: squash(v) }); for (const w of wordsOf(v)) words.add(w); } };
      const addText = (v) => { for (const w of wordsOf(v)) words.add(w); };
      const r0 = rows[0];
      const paper = data.papers[r0.pmid] || {};
      addId(fid); addId(r0.pmid);
      for (const r of rows) {
        addId(r.public_id); addId(r.gene_name); addId(r.reported_gene_name); addId(r.locus_tag);
        const g = data.genes[r.gene_id] || { aliases: [], orthologs: [] };
        for (const a of g.aliases) addId(a);
        for (const [n, i] of g.orthologs) { addId(n); addId(i); }
        if (r.strain_id) {
          const s = data.strains[r.strain_id];
          if (s) { addId(s.name); for (const a of s.aliases) addId(a); }
        }
        addText(r.phenotype); addText(r.product); addText(r.product_class); addText(pretty(r.phenotype_category));
        addText(pretty(r.intervention_type)); addText(r.host_organism); addText(r.gene_organism);
      }
      addText(r0.effect_direction); addText(r0.result_class); addText(paper.title); addText(paper.first_author); addText(paper.authors);
      const uniq = (fn) => [...new Set(rows.map(fn).filter((x) => x != null && x !== ''))];
      findings.push({
        id: fid, rows, idents, words: [...words], cls: r0.result_class, cat: r0.phenotype_category, dir: r0.effect_direction,
        products: uniq((r) => r.product), pclasses: uniq((r) => r.product_class), types: uniq((r) => r.intervention_type),
        gorgs: uniq((r) => r.gene_organism), hosts: uniq((r) => r.host_organism), strains: uniq((r) => r.strain_id),
        year: r0.year, country: paper.country || '', pmid: r0.pmid
      });
    }
    return { data, findings };
  }

  function scoreToken(f, t) {
    const sq = squash(t);
    let best = 0;
    for (const id of f.idents) {
      if (id.n === t || (sq && id.s === sq)) return 100;
      if (t.length >= 2 && (id.n.startsWith(t) || (sq.length >= 2 && id.s.startsWith(sq)))) best = Math.max(best, 60);
    }
    for (const w of f.words) {
      if (w === t) best = Math.max(best, 40);
      else if (t.length >= 2 && w.startsWith(t)) best = Math.max(best, 20);
    }
    return best;
  }

  function queryScore(f, tokens) {
    let total = 0;
    for (const t of tokens) { const s = scoreToken(f, t); if (!s) return 0; total += s; }
    return total;
  }

  function matches(index, f, st, skip, strainSet, tokens) {
    for (const key of Object.keys(FACETS)) {
      if (key === skip || key === 'hosts' || !st[key].length) continue;
      if (!FACETS[key](f).some((v) => st[key].includes(v))) return false;
    }
    if (skip !== 'hosts') {
      if (st.hosts.length) { if (!f.hosts.some((h) => st.hosts.includes(h))) return false; }
      else if (!st.allHosts && !f.hosts.includes(HOME_HOST)) return false;
    }
    if (strainSet && !f.strains.some((s) => strainSet.has(s))) return false;
    if (st.ymin != null && !(f.year >= st.ymin)) return false;
    if (st.ymax != null && !(f.year <= st.ymax)) return false;
    if (tokens.length && !queryScore(f, tokens)) return false;
    return true;
  }

  function prepare(index, st) {
    const tokens = norm(st.q).split(/\s+/).filter(Boolean);
    const strainSet = st.strain ? (st.derived ? descendants(index.data, st.strain) : new Set([st.strain])) : null;
    return { tokens, strainSet };
  }

  function run(index, state) {
    const st = Object.assign(defaultState(), state);
    const { tokens, strainSet } = prepare(index, st);
    const out = [];
    for (const f of index.findings) {
      if (!matches(index, f, st, null, strainSet, tokens)) continue;
      out.push({ f, score: tokens.length ? queryScore(f, tokens) : 0 });
    }
    const sort = st.sort === 'relevance' && !tokens.length ? 'year' : st.sort;
    out.sort((a, b) => {
      if (sort === 'relevance' && b.score !== a.score) return b.score - a.score;
      if (sort === 'class') { const x = a.f.cls === 'positive' ? 1 : 0, y = b.f.cls === 'positive' ? 1 : 0; if (x !== y) return x - y; }
      if ((b.f.year || 0) !== (a.f.year || 0)) return (b.f.year || 0) - (a.f.year || 0);
      return a.f.id < b.f.id ? -1 : 1;
    });
    return { items: out.map((o) => o.f), nFindings: out.length, nRows: out.reduce((n, o) => n + o.f.rows.length, 0) };
  }

  function facets(index, state) {
    const st = Object.assign(defaultState(), state);
    const { tokens, strainSet } = prepare(index, st);
    const result = {};
    for (const key of Object.keys(FACETS)) {
      const counts = {};
      for (const f of index.findings) {
        if (!matches(index, f, st, key, strainSet, tokens)) continue;
        for (const v of FACETS[key](f)) if (v) counts[v] = (counts[v] || 0) + 1;
      }
      result[key] = counts;
    }
    return result;
  }

  const PARAMS = { q: 'q', classes: 'class', cats: 'cat', products: 'product', pclasses: 'pclass', types: 'type', dirs: 'dir', gorgs: 'gorg', hosts: 'host', countries: 'country' };

  function toParams(state) {
    const st = Object.assign(defaultState(), state), p = new URLSearchParams();
    if (st.q) p.set('q', st.q);
    for (const [k, name] of Object.entries(PARAMS)) if (k !== 'q') for (const v of st[k]) p.append(name, v);
    if (st.allHosts) p.set('allhosts', '1');
    if (st.strain) { p.set('strain', st.strain); if (!st.derived) p.set('derived', '0'); }
    if (st.ymin != null) p.set('ymin', st.ymin);
    if (st.ymax != null) p.set('ymax', st.ymax);
    if (st.sort !== 'relevance') p.set('sort', st.sort);
    return p.toString();
  }

  function fromParams(search) {
    const p = new URLSearchParams(search), st = defaultState();
    st.q = p.get('q') || '';
    for (const [k, name] of Object.entries(PARAMS)) if (k !== 'q') st[k] = p.getAll(name);
    st.allHosts = p.get('allhosts') === '1';
    st.strain = p.get('strain') || '';
    st.derived = p.get('derived') !== '0';
    st.ymin = p.get('ymin') ? Number(p.get('ymin')) : null;
    st.ymax = p.get('ymax') ? Number(p.get('ymax')) : null;
    st.sort = p.get('sort') || 'relevance';
    return st;
  }

  // ---- suggestions for the search box (typed prefix -> a few likely terms) ----
  const KIND_RANK = { gene: 0, alias: 1, reported: 1, ortholog: 1, strain: 2, product: 3, locus: 4 };
  function suggestionTable(index) {
    if (index._sugg) return index._sugg;
    const data = index.data, table = new Map();
    const kmHostGenes = new Set(data.results.filter((r) => r.host_organism === HOME_HOST).map((r) => r.gene_id));
    for (const f of index.findings) {
      const home = f.hosts.includes(HOME_HOST), seen = new Set();
      const add = (label, kind, hint) => {
        if (!label) return;
        const key = kind + '|' + norm(label) + '|' + hint;
        if (seen.has(key)) return; seen.add(key);
        let e = table.get(key);
        if (!e) { e = { label, kind, hint, n: norm(label), s: squash(label), all: 0, home: 0 }; table.set(key, e); }
        e.all++; if (home) e.home++;
      };
      for (const r of f.rows) {
        const g = data.genes[r.gene_id];
        if (!g || g.kind === 'enzyme_or_protein_label' || (g.organism !== HOME_HOST && !kmHostGenes.has(r.gene_id))) continue;
        add(r.gene_name, 'gene', 'gene');
        if (r.reported_gene_name && r.reported_gene_name !== r.gene_name) add(r.reported_gene_name, 'reported', 'name used in the paper \u2192 ' + r.gene_name);
        for (const a of g.aliases) add(a, 'alias', 'also known as \u2192 ' + r.gene_name);
        for (const [n, id] of g.orthologs) { add(n, 'ortholog', 'S. cerevisiae ortholog of ' + r.gene_name); add(id, 'ortholog', 'S. cerevisiae ortholog of ' + r.gene_name); }
        if (r.locus_tag) add(r.locus_tag, 'locus', 'locus tag of ' + r.gene_name);
      }
      for (const sid of f.strains) {
        const st = data.strains[sid]; if (!st || st.parent) continue;
        add(st.name, 'strain', 'strain'); for (const a of st.aliases) add(a, 'strain', 'strain ' + st.name);
      }
      for (const p of f.products) add(p, 'product', 'product');
      for (const p of f.pclasses) add(p, 'product', 'product class');
    }
    index._sugg = [...table.values()];
    return index._sugg;
  }

  function suggest(index, text, opts) {
    const o = Object.assign({ allHosts: false, limit: 10 }, opts);
    const t = norm(text).trim(); if (!t) return [];
    const sq = squash(t), out = [];
    for (const e of suggestionTable(index)) {
      const count = o.allHosts ? e.all : e.home;
      if (!count) continue;
      let m = -1;
      if (e.n.startsWith(t) || (sq.length >= 2 && e.s.startsWith(sq))) m = 0;
      else if (e.n.split(/[^\p{L}\p{N}]+/u).some((w) => w && w.startsWith(t))) m = 1;
      if (m < 0) continue;
      out.push({ e, m, count });
    }
    out.sort((a, b) => a.m - b.m || KIND_RANK[a.e.kind] - KIND_RANK[b.e.kind] || b.count - a.count || a.e.label.localeCompare(b.e.label));
    const seen = new Set(), res = [];
    for (const x of out) { const k = norm(x.e.label) + '|' + x.e.hint; if (seen.has(k)) continue; seen.add(k); res.push({ label: x.e.label, hint: x.e.hint, kind: x.e.kind, count: x.count }); if (res.length >= o.limit) break; }
    return res;
  }

  // ---- species names: split a text into [piece, isSpeciesName] so the page can italicise them (the list comes from data.js) ----
  function speciesParts(text, names) {
    const str = String(text == null ? '' : text);
    if (!names || !names.length) return [[str, false]];
    if (!names._re) names._re = new RegExp('(^|[^\\w])(' + names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')(?![\\w])', 'g');
    const re = names._re; re.lastIndex = 0;
    const out = []; let last = 0, m;
    while ((m = re.exec(str))) {
      const start = m.index + m[1].length;
      if (start > last) out.push([str.slice(last, start), false]);
      out.push([m[2], true]); last = start + m[2].length; re.lastIndex = last;
    }
    if (last < str.length) out.push([str.slice(last), false]);
    return out.length ? out : [[str, false]];
  }

  root.MarxSearch = { speciesParts, build, run, facets, suggest, defaultState, toParams, fromParams, descendants, scoreToken, squash, wordsOf, pretty, HOME_HOST };
})(typeof window !== 'undefined' ? window : globalThis);

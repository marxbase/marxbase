/* MarxBase search page. Builds the interface with DOM calls and textContent only (no innerHTML), so no data can inject markup. */
(function () {
  'use strict';
  const S = window.MarxSearch, data = window.MARXBASE;
  const index = S.build(data);
  const root = document.getElementById('app'), extras = document.getElementById('hero-extras');
  if (!root) return;
  let state = S.fromParams(location.search);
  const hero = document.getElementById('hero'), resultsTitle = document.getElementById('results-title');
  let browseAll = new URLSearchParams(location.search).get('browse') === '1';        // "browse all findings" from the home tiles
  const hasFilters = (st) => !!(st.q || st.strain || st.ymin != null || st.ymax != null || st.allHosts || FACET_DEFS.some(([k]) => st[k].length));
  // The home page stays a landing page until the person presses Search (or arrives with a search in the address); after that the list updates live.
  let engaged = false;                                   // set below, once the filter definitions exist
  let shown = 50;

  const KIND = { locus_tagged: 'Locus tag', scerevisiae_gene: 'S. cerevisiae gene', undetermined_paralog: 'Undetermined paralog', enzyme_or_protein_label: 'Enzyme or protein label, not a gene symbol', heterologous_gene: 'Heterologous gene', unmapped_name: 'Name without a genome identifier' };
  const KIND_HELP = { undetermined_paralog: 'K. marxianus has several copies of this gene and the papers do not say which one was used.', enzyme_or_protein_label: "The paper's own name for an enzyme or protein, not an established gene symbol.", unmapped_name: 'No reliable genome identifier could be assigned to this name.', heterologous_gene: 'A gene from another species.' };
  const CLASS = { positive: ['+', 'Positive'], negative: ['−', 'Negative'], 'context-dependent': ['∼', 'Context-dependent'] };
  const QUAL = { greater_than: '> ', less_than: '< ', approx: '≈ ' };
  const WEAK_TYPES = ['heterologous_expression', 'promoter_swap'];

  const sp = (text) => S.speciesParts(text, data.species).map(([t, isSp]) => (isSp ? el('i', { text: t }) : t));   // species names in italics

  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'text') e.textContent = v; else if (k in e && k !== 'class' && k !== 'for' && k !== 'list') e[k] = v; else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return e;
  }

  const FACET_DEFS = [
    ['classes', 'Result class', (v) => (CLASS[v] ? CLASS[v][1] : v), ['positive', 'negative', 'context-dependent']],
    ['cats', 'Phenotype category', S.pretty], ['pclasses', 'Product class', (v) => v], ['products', 'Product', (v) => v],
    ['types', 'Type of change', S.pretty], ['dirs', 'Effect', (v) => v], ['gorgs', 'Gene from', (v) => v],
    ['hosts', 'Host organism', (v) => v], ['countries', 'Country of last author', (v) => v]
  ];
  const FACET_KEY = { cats: 'cat', classes: 'cls', dirs: 'dir' };
  const allValues = {};
  for (const [key, , , fixed] of FACET_DEFS) {
    const set = new Set();
    for (const f of index.findings) {
      const v = key === 'classes' ? [f.cls] : key === 'cats' ? [f.cat] : key === 'dirs' ? [f.dir] : key === 'countries' ? [f.country] : f[key];
      for (const x of v) if (x) set.add(x);
    }
    allValues[key] = fixed ? fixed.filter((x) => set.has(x)) : [...set].sort((a, b) => a.localeCompare(b));
  }

  engaged = browseAll || hasFilters(state);

  // ---- static controls ----
  const q = el('input', { id: 'q', type: 'search', value: state.q, placeholder: 'Search gene, strain, product…', autocomplete: 'off', role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'false', 'aria-controls': 'suggest' });
  const sugg = el('ul', { id: 'suggest', class: 'suggest', role: 'listbox', 'aria-label': 'Suggestions', hidden: true });
  const allHosts = el('input', { id: 'allhosts', type: 'checkbox', checked: state.allHosts });
  const sortSel = el('select', { id: 'sort' }, [['relevance', 'Relevance (or newest first)'], ['year', 'Newest first']].map(([v, t]) => el('option', { value: v, text: t, selected: state.sort === v })));
  const strainSel = el('select', { id: 'strain' });
  const usedStrains = new Set(index.findings.flatMap((f) => f.strains));
  function fillStrains() {
    const showOther = allHosts.checked, cur = state.strain;
    const root = Object.entries(data.strains).filter(([id, s]) => usedStrains.has(id) && !s.parent);
    const opt = (id, s) => el('option', { value: id, text: s.name, selected: cur === id });
    const byName = (a, b) => a[1].name.localeCompare(b[1].name);
    const home = root.filter(([, s]) => s.home).sort(byName).map(([id, s]) => opt(id, s));
    const other = root.filter(([, s]) => !s.home).sort(byName).map(([id, s]) => opt(id, s));
    const curEntry = cur && data.strains[cur] && data.strains[cur].parent ? [opt(cur, data.strains[cur])] : [];   // a shared link to a derived strain still works
    strainSel.replaceChildren(el('option', { value: '', text: 'Any strain' }), ...curEntry, ...home, ...(showOther || (cur && data.strains[cur] && !data.strains[cur].home) ? [el('optgroup', { label: 'Strains in other host organisms' }, other)] : []));
    strainSel.value = cur || '';
  }
  const derived = el('input', { id: 'derived', type: 'checkbox', checked: state.derived });
  const ymin = el('input', { id: 'ymin', type: 'number', min: 1900, max: 2100, value: state.ymin == null ? '' : state.ymin, 'aria-label': 'From year' });
  const ymax = el('input', { id: 'ymax', type: 'number', min: 1900, max: 2100, value: state.ymax == null ? '' : state.ymax, 'aria-label': 'To year' });
  const clear = el('button', { type: 'button', class: 'linklike clear-all', text: 'Clear all' });
  const count = el('p', { id: 'count', role: 'status', 'aria-live': 'polite' });
  const note = el('p', { class: 'weak', hidden: true });
  const list = el('ol', { class: 'findings' });
  const more = el('button', { type: 'button', class: 'more' });
  const groups = {};
  const C = window.MarxCite;
  const picked = new Set();       // finding ids ticked with "cite"
  let lastView = { items: [], nRows: 0 };

  const filterBox = el('aside', { id: 'filters', 'aria-label': 'Filters' });
  const accordions = {};                                  // key -> { box, badge } for the selected-count badges
  const accordion = (key, title, body, open) => {
    const badge = el('span', { class: 'selcount', hidden: true });
    const box = el('details', { class: 'facet', 'data-facet': key, open }, el('summary', {}, el('span', { text: title }), badge), el('div', { class: 'facet-body' }, body));
    accordions[key] = { box, badge };
    return box;
  };
  filterBox.append(el('div', { class: 'filters-head' }, el('span', { text: 'Filter results' }), clear));
  filterBox.append(accordion('_strain', 'Strain', [el('div', { class: 'row' }, strainSel), el('label', { class: 'inline' }, derived, ' include derived strains')], false),
    accordion('_year', 'Publication year', [ymin, ' to ', ymax], false));
  for (const [key, title, labelFn] of FACET_DEFS) {
    const body = el('div', {});
    const box = accordion(key, title, body, key === 'classes' || key === 'cats');
    groups[key] = { box, inputs: {} };
    for (const v of allValues[key]) {
      const cb = el('input', { type: 'checkbox', value: v });
      const n = el('span', { class: 'n' });
      const lab = el('label', { class: 'opt' }, cb, ' ', sp(labelFn(v)), ' ', n);
      groups[key].inputs[v] = { cb, n, lab };
      body.append(lab);
    }
    filterBox.append(box);
  }
  const searchBtn = el('button', { type: 'submit', text: 'Search' });
  const sortLab = el('label', { class: 'inline', for: 'sort' }, 'Sort ', sortSel);
  const hostSwitch = el('label', { class: 'hostswitch', for: 'allhosts' }, allHosts, ' ', sp('Include other hosts expressing K. marxianus genes'));
  const form = el('form', { class: 'searchbar', role: 'search' },
    el('label', { for: 'q', class: 'sr-only', text: 'Search genes, strains, products and papers' }),
    el('div', { class: 'searchrow' }, el('div', { class: 'combo' }, q, sugg), searchBtn),
    el('div', { class: 'toolbar' }, hostSwitch));
  const fmtSel = el('select', { id: 'fmt' }, Object.entries(C.FORMATS).map(([k, v]) => el('option', { value: k, text: v.label })));
  const scopeSel = el('select', { id: 'scope' });
  const richBox = el('input', { id: 'rich', type: 'checkbox' });
  const csvBtn = el('button', { type: 'button', text: 'Download results as CSV' });
  const refBtn = el('button', { type: 'button', text: 'Download references' });
  const exportMsg = el('p', { class: 'small', role: 'status' });
  const exportPanel = el('div', { class: 'exportbox', id: 'export-panel', hidden: true },
    el('p', { class: 'small', text: 'The CSV holds every result column for the findings you are looking at, one row per result.' + (data.hasEvidence ? ' Evidence sentences quote abstracts and are not covered by the data licence.' : '') }),
    el('p', {}, csvBtn),
    el('div', { class: 'row' }, el('label', { for: 'fmt', text: 'References for' }), scopeSel, el('label', { for: 'fmt', text: 'Format' }), fmtSel,
      el('label', { class: 'inline' }, richBox, ' also keep italics (opens as a web page you can paste into Word; AMA, APA, MLA, NLM only)')),
    el('p', {}, refBtn), el('p', { class: 'small', text: 'Volume, issue and page numbers are not stored; each reference carries the DOI instead.' }), exportMsg);
  const exportToggle = el('button', { type: 'button', class: 'export-toggle', 'aria-expanded': 'false', 'aria-controls': 'export-panel', text: 'Download or cite' });
  exportToggle.addEventListener('click', () => { exportPanel.hidden = !exportPanel.hidden; exportToggle.setAttribute('aria-expanded', exportPanel.hidden ? 'false' : 'true'); });
  const resultsBar = el('div', { class: 'resultsbar' }, count, el('div', { class: 'resultsactions' }, sortLab, exportToggle));
  const resultsArea = el('div', { id: 'results-area' }, resultsBar, exportPanel, note, el('div', { class: 'layout' }, el('details', { class: 'filterwrap', open: !window.matchMedia('(max-width: 760px)').matches || !!(state.strain || state.ymin != null || state.ymax != null || FACET_DEFS.some(([k]) => state[k].length)) }, el('summary', { text: 'Filters' }), filterBox), el('section', { 'aria-label': 'Results' }, list, more)));
  root.append(form, resultsArea);

  // ---- rendering ----
  const valueText = (r) => {
    const out = [];
    if (r.new_value != null) {
      out.push(((QUAL[r.value_qualifier] || '') + r.new_value + ' ' + (r.value_unit || '')).trim());
      if (r.baseline_value != null) out.push('(baseline ' + r.baseline_value + ' ' + (r.value_unit || '') + ')');
    }
    if (r.percent_change != null) out.push(r.percent_change + '% change');
    if (r.fold_change != null) out.push(r.fold_change + '-fold');
    return out.join(' ');
  };
  const badge = (g, prefix) => {
    const label = g.kind === 'locus_tagged' && g.locus ? 'Locus tag ' + g.locus : g.kind === 'heterologous_gene' ? 'Heterologous gene from ' + g.organism : KIND[g.kind] || g.kind;
    return el('span', { class: 'badge badge-' + g.kind, title: KIND_HELP[g.kind] || '' }, sp((prefix ? prefix + ': ' : '') + label));
  };

  const productUrl = (name) => 'product/' + name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') + '.html';   // same slug rule as build.py
  const productLink = (name, text) => el('a', { href: productUrl(name), text });
  // the phenotype text with the word that names the product linked to the product page
  function phenotypeNodes(r) {
    const words = (data.productWords || {})[r.product || ''], m = words && new RegExp(words, 'i').exec(r.phenotype);
    if (!m) return { nodes: [r.phenotype], linked: false };
    return { nodes: [r.phenotype.slice(0, m.index), productLink(r.product, m[0]), r.phenotype.slice(m.index + m[0].length)], linked: true };
  }

  function renderFinding(f) {
    const r0 = f.rows[0];
    const members = [];
    f.rows.forEach((r, i) => {
      if (i) members.push(' + ');
      members.push(el('a', { href: 'gene/' + r.gene_id + '.html', text: r.gene_name }), ' ', el('span', { class: 'chg', text: S.pretty(r.intervention_type) }));
    });
    const seen = new Set(), badges = [];
    const nGenes = new Set(f.rows.map((r) => r.gene_id)).size;
    for (const r of f.rows) if (!seen.has(r.gene_id)) { seen.add(r.gene_id); if (data.genes[r.gene_id].kind !== 'locus_tagged') badges.push(badge(data.genes[r.gene_id], nGenes > 1 ? r.gene_name : ''), ' '); }   // a proper KLMA locus needs no flag
    const label = (CLASS[r0.result_class] || ['', r0.result_class])[1];
    const p = data.papers[r0.pmid] || {};
    const parts = [];
    if (r0.strain_id) { const rs = data.strains[r0.strain_id].root || r0.strain_id; parts.push(['strain ', el('a', { href: 'strain/' + rs + '.html', text: data.strains[rs].name })]); }
    parts.push([el('a', { href: 'paper/' + r0.pmid + '.html', text: (p.first_author || 'Paper') + (p.authors && p.authors.split(';').length > 1 ? ' et al.' : '') + ' ' + (r0.year || '') })]);
    const vt = valueText(r0);
    const pheno = phenotypeNodes(r0);
    if (r0.product && !pheno.linked) parts.push(['product ', productLink(r0.product, r0.product)]);   // no word in the statement names it
    const metaEl = el('div', { class: 'fl2' });
    parts.forEach((x, i) => metaEl.append(...(i ? [' \u00b7 '] : []), ...x));
    // only a host other than K. marxianus is flagged
    if (r0.host_organism !== S.HOME_HOST) badges.unshift(el('span', { class: 'badge badge-host' }, 'Host: ', sp(r0.host_organism)), ' ');
    const cb = el('input', { type: 'checkbox', 'aria-label': 'Select for citation export' });
    cb.checked = picked.has(f.id);
    cb.addEventListener('change', () => { if (cb.checked) picked.add(f.id); else picked.delete(f.id); updateExport(); });
    return el('li', { class: 'finding cls-' + r0.result_class },
      el('a', { class: 'cardlink', href: 'result/' + r0.public_id + '.html' }, el('span', { class: 'sr-only', text: 'Details of this result' })),
      el('label', { class: 'pick small' }, cb, ' cite'),
      el('div', { class: 'fl1' }, members, ' → ', el('strong', { text: r0.effect_direction }), ' ', ...pheno.nodes, vt ? ' (' + vt + ')' : '', ' ',
        el('span', { class: 'sr-only', text: '(' + label + ')' })),
      el('div', { class: 'fl3' }, badges), metaEl);
  }

  const currentState = () => Object.assign({}, state);

  // ---- export ----
  function describeState(st) {
    const bits = [];
    if (st.q) bits.push('search "' + st.q + '"');
    const names = { classes: 'class', cats: 'category', products: 'product', pclasses: 'product class', types: 'change', dirs: 'effect', gorgs: 'gene from', hosts: 'host', countries: 'country' };
    for (const k of Object.keys(names)) if (st[k].length) bits.push(names[k] + ' ' + st[k].join('/'));
    if (st.strain) bits.push('strain ' + (data.strains[st.strain] ? data.strains[st.strain].name : st.strain) + (st.derived ? ' (with derived strains)' : ''));
    if (st.ymin != null || st.ymax != null) bits.push('years ' + (st.ymin == null ? '' : st.ymin) + '-' + (st.ymax == null ? '' : st.ymax));
    bits.push(st.allHosts || st.hosts.length ? 'all host organisms' : 'K. marxianus hosts only');
    return bits.join('; ');
  }
  const stamp = () => data.version.replace(/[^A-Za-z0-9._-]/g, '_');
  function viewPapers(items) {
    const seen = new Set(), out = [];
    for (const f of items) for (const r of f.rows) if (!seen.has(r.pmid) && data.papers[r.pmid]) { seen.add(r.pmid); out.push(data.papers[r.pmid]); }
    return C.sortPapers(out);
  }
  function updateExport() {
    const n = lastView.nFindings || 0;
    const cur = scopeSel.value;
    scopeSel.replaceChildren(el('option', { value: 'view', text: 'all ' + n + ' findings in this view' }),
      ...(picked.size ? [el('option', { value: 'picked', text: picked.size + ' ticked finding' + (picked.size === 1 ? '' : 's') })] : []));
    scopeSel.value = cur === 'picked' && picked.size ? 'picked' : 'view';
    csvBtn.disabled = !n; refBtn.disabled = !n && !picked.size;
  }
  csvBtn.addEventListener('click', () => {
    const items = lastView.items, rows = items.flatMap((f) => f.rows);
    const line = 'MarxBase release ' + data.version + ' (' + data.date + '), ' + (data.doi ? 'DOI ' + data.doi + '. ' : 'DOI pending. ') + items.length + ' findings, ' + rows.length + ' results. Filters: ' + describeState(state) + '. ' + (data.hasEvidence ? 'Evidence sentences are not covered by the data licence. ' : '') + 'Data: CC BY 4.0.';
    C.download('marxbase-' + stamp() + '-results.csv', C.toCSV(rows, data.columns, line), 'text/csv');
    exportMsg.textContent = 'Downloaded ' + rows.length + ' results.';
  });
  refBtn.addEventListener('click', () => {
    let papers;
    if (scopeSel.value === 'picked') {
      const all = new Map(index.findings.map((f) => [f.id, f]));
      papers = viewPapers([...picked].map((id) => all.get(id)).filter(Boolean));
    } else papers = viewPapers(lastView.items);
    const k = fmtSel.value, fmt = C.FORMATS[k];
    if (richBox.checked && C.STYLES[k.toUpperCase()]) C.download('marxbase-' + stamp() + '-references-' + k + '.html', C.richHtml(papers, k.toUpperCase()), 'text/html');
    else C.download('marxbase-' + stamp() + '-references-' + k + '.' + fmt.ext, fmt.make(papers), fmt.mime);
    exportMsg.textContent = 'Downloaded ' + papers.length + ' references.';
  });

  function render() {
    const st = currentState();
    const res = S.run(index, st), fac = S.facets(index, st);
    for (const [key] of FACET_DEFS) {
      const g = groups[key];
      let any = false;
      for (const [v, o] of Object.entries(g.inputs)) {
        const n = fac[key][v] || 0, checked = state[key].includes(v);
        o.cb.checked = state[key].includes(v); o.n.textContent = '(' + n + ')';
        o.lab.hidden = !n && !checked; if (n || checked) any = true;
      }
      g.box.hidden = !any || (key === 'hosts' && !st.allHosts && !st.hosts.length);
    }
    lastView = res;
    const active = engaged;
    if (hero) hero.hidden = active;
    if (extras) extras.hidden = active;
    resultsArea.hidden = !active; sortLab.hidden = !active; root.classList.toggle('landing', !active);
    document.body.classList.toggle('engaged', active);
    const sel = (k, n) => { const b = accordions[k].badge; b.hidden = !n; b.textContent = n || ''; };
    for (const [key] of FACET_DEFS) sel(key, st[key].length);
    sel('_strain', st.strain ? 1 : 0); sel('_year', (st.ymin != null ? 1 : 0) + (st.ymax != null ? 1 : 0));
    clear.hidden = !hasFilters(st);
    if (resultsTitle) resultsTitle.hidden = !active;
    list.replaceChildren(...res.items.slice(0, shown).map(renderFinding));
    updateExport();
    const rest = res.nFindings - shown;
    more.hidden = rest <= 0; more.textContent = 'Show more (' + rest + ' remaining)';
    const allMode = st.allHosts || st.hosts.length;
    const head = res.nFindings + (res.nFindings === 1 ? ' finding' : ' findings');
    count.replaceChildren(el('strong', { class: 'bignum', text: head }), ...sp(' (' + res.nRows + (res.nRows === 1 ? ' result) ' : ' results) ') + (allMode ? 'in all host organisms.' : 'in K. marxianus host organisms only.') + (res.nFindings || allMode ? '' : ' Try removing a filter or including other hosts.')));
    const weak = st.types.some((t) => WEAK_TYPES.includes(t)) || st.cats.includes('protein_production');
    note.hidden = !weak;
    note.textContent = weak ? 'Heads-up: results for heterologous expression, promoters and protein production are the least complete part of this collection (abstract-only extraction).' : '';
    try { const p = S.toParams(state), qs = p || (browseAll ? 'browse=1' : ''); history.replaceState(null, '', qs ? '?' + qs : location.pathname); } catch (e) { /* file:// may refuse; harmless */ }
  }

  function readControls() {
    const hostChanged = state.allHosts !== allHosts.checked;
    state.q = q.value.trim(); state.allHosts = allHosts.checked; state.strain = strainSel.value; state.derived = derived.checked;
    state.ymin = ymin.value ? Number(ymin.value) : null; state.ymax = ymax.value ? Number(ymax.value) : null; state.sort = sortSel.value;
    for (const [key] of FACET_DEFS) state[key] = Object.entries(groups[key].inputs).filter(([, o]) => o.cb.checked).map(([v]) => v);
    if (hostChanged) fillStrains();
    shown = 50;
  }
  let timer;
  const refresh = () => { readControls(); render(); };
  const refreshIfEngaged = () => { if (engaged) refresh(); else readControls(); };   // on the landing page, just remember the settings
  // ---- suggestions while typing ----
  let items = [], active = -1;
  function closeSugg() { sugg.hidden = true; sugg.replaceChildren(); items = []; active = -1; q.setAttribute('aria-expanded', 'false'); q.removeAttribute('aria-activedescendant'); }
  function setActive(i) {
    active = i;
    [...sugg.children].forEach((li, k) => { li.setAttribute('aria-selected', k === i ? 'true' : 'false'); li.classList.toggle('active', k === i); });
    if (i >= 0) q.setAttribute('aria-activedescendant', 'sg-' + i); else q.removeAttribute('aria-activedescendant');
  }
  function choose(i) { if (i < 0 || !items[i]) return; q.value = items[i].label; closeSugg(); clearTimeout(timer); refreshIfEngaged(); }
  function showSugg() {
    const text = q.value.trim();
    if (!text) return closeSugg();
    items = S.suggest(index, text, { allHosts: allHosts.checked });
    if (!items.length) return closeSugg();
    sugg.replaceChildren(...items.map((it, i) => {
      const li = el('li', { id: 'sg-' + i, role: 'option', 'aria-selected': 'false' }, el('strong', { text: it.label }), el('span', { class: 'hint' }, sp(' ' + it.hint)));
      li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });
      return li;
    }));
    sugg.hidden = false; q.setAttribute('aria-expanded', 'true'); setActive(-1);
  }
  form.addEventListener('submit', (e) => { e.preventDefault(); closeSugg(); clearTimeout(timer); engaged = true; refresh(); });
  q.addEventListener('input', () => { showSugg(); clearTimeout(timer); timer = setTimeout(refreshIfEngaged, 150); });
  q.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); setActive((active + 1) % items.length); }
    else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(active); }
    else if (e.key === 'Escape') closeSugg();
  });
  q.addEventListener('blur', () => setTimeout(closeSugg, 120));
  q.addEventListener('focus', () => { if (q.value.trim()) showSugg(); });
  for (const e of [allHosts, sortSel, strainSel, derived, ymin, ymax]) e.addEventListener('change', refreshIfEngaged);
  filterBox.addEventListener('change', refreshIfEngaged);
  more.addEventListener('click', () => { shown += 50; render(); });
  clear.addEventListener('click', () => { state = S.defaultState(); q.value = ''; allHosts.checked = false; fillStrains(); strainSel.value = ''; derived.checked = true; ymin.value = ''; ymax.value = ''; sortSel.value = 'relevance'; shown = 50; render(); });
  window.MarxApp = { render, getState: () => state };
  fillStrains();
  render();
})();

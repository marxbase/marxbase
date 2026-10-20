/* MarxBase search page. Builds the interface with DOM calls and textContent only (no innerHTML), so no data can inject markup. */
(function () {
  'use strict';
  const S = window.MarxSearch, data = window.MARXBASE;
  const index = S.build(data);
  const root = document.getElementById('app');
  if (!root) return;
  let state = S.fromParams(location.search);
  let shown = 50;

  const KIND = { locus_tagged: 'Locus tag', scerevisiae_gene: 'S. cerevisiae gene', undetermined_paralog: 'Undetermined paralog', enzyme_or_protein_label: 'Enzyme or protein label, not a gene symbol', heterologous_gene: 'Heterologous gene', unmapped_name: 'Name without a genome identifier' };
  const KIND_HELP = { undetermined_paralog: 'K. marxianus has several copies of this gene and the papers do not say which one was used.', enzyme_or_protein_label: "The paper's own name for an enzyme or protein, not an established gene symbol.", unmapped_name: 'No reliable genome identifier could be assigned to this name.', heterologous_gene: 'A gene from another species.' };
  const CLASS = { positive: ['+', 'Positive'], negative: ['−', 'Negative'], 'context-dependent': ['∼', 'Context-dependent'] };
  const QUAL = { greater_than: '> ', less_than: '< ', approx: '≈ ' };
  const WEAK_TYPES = ['heterologous_expression', 'promoter_swap'];

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

  // ---- static controls ----
  const q = el('input', { id: 'q', type: 'search', value: state.q, placeholder: 'gene, locus tag, ortholog (SUC2, YIL162W), product, strain, phenotype…', autocomplete: 'off', role: 'combobox', 'aria-autocomplete': 'list', 'aria-expanded': 'false', 'aria-controls': 'suggest' });
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
  const clear = el('button', { type: 'button', text: 'Clear all filters' });
  const count = el('p', { id: 'count', role: 'status', 'aria-live': 'polite' });
  const hostBtn = el('button', { type: 'button', class: 'linklike' });
  const note = el('p', { class: 'weak', hidden: true });
  const list = el('ol', { class: 'findings' });
  const more = el('button', { type: 'button', class: 'more' });
  const groups = {};
  const C = window.MarxCite;
  const picked = new Set();       // finding ids ticked with "cite"
  let lastView = { items: [], nRows: 0 };

  const filterBox = el('aside', { id: 'filters', 'aria-label': 'Filters' });
  filterBox.append(el('div', { class: 'row' }, el('label', { for: 'strain', text: 'Strain' }), strainSel),
    el('label', { class: 'inline' }, derived, ' include derived strains'),
    el('fieldset', {}, el('legend', { text: 'Publication year' }), ymin, ' to ', ymax));
  for (const [key, title, labelFn] of FACET_DEFS) {
    const box = el('fieldset', { class: 'facet', 'data-facet': key }, el('legend', { text: title }));
    groups[key] = { box, inputs: {} };
    for (const v of allValues[key]) {
      const cb = el('input', { type: 'checkbox', value: v });
      const n = el('span', { class: 'n' });
      const lab = el('label', { class: 'opt' }, cb, ' ', labelFn(v), ' ', n);
      groups[key].inputs[v] = { cb, n, lab };
      box.append(lab);
    }
    filterBox.append(box);
  }
  filterBox.append(clear);
  const hostSwitch = el('div', { class: 'hostswitch' }, el('label', { for: 'allhosts' }, allHosts, el('strong', { text: ' Include results in other host organisms' }),
    el('span', { class: 'small', text: ' (S. cerevisiae, Pichia, E. coli and others; by default only results obtained in K. marxianus are shown)' })));
  const form = el('div', { class: 'searchbar', role: 'search' }, el('label', { for: 'q', text: 'Search' }), el('div', { class: 'combo' }, q, sugg), hostSwitch,
    el('div', { class: 'toggles' }, el('label', { class: 'inline', for: 'sort' }, 'Sort ', sortSel)));
  const fmtSel = el('select', { id: 'fmt' }, Object.entries(C.FORMATS).map(([k, v]) => el('option', { value: k, text: v.label })));
  const scopeSel = el('select', { id: 'scope' });
  const richBox = el('input', { id: 'rich', type: 'checkbox' });
  const csvBtn = el('button', { type: 'button', text: 'Download results as CSV' });
  const refBtn = el('button', { type: 'button', text: 'Download references' });
  const exportMsg = el('p', { class: 'small', role: 'status' });
  const exportBox = el('details', { class: 'exportbox' }, el('summary', { text: 'Download or cite these results' }),
    el('p', { class: 'small', text: 'The CSV holds every result column for the findings you are looking at, one row per result.' + (data.hasEvidence ? ' Evidence sentences quote abstracts and are not covered by the data licence.' : '') }),
    el('p', {}, csvBtn),
    el('div', { class: 'row' }, el('label', { for: 'fmt', text: 'References for' }), scopeSel, el('label', { for: 'fmt', text: 'Format' }), fmtSel,
      el('label', { class: 'inline' }, richBox, ' also keep italics (opens as a web page you can paste into Word; AMA, APA, MLA, NLM only)')),
    el('p', {}, refBtn), el('p', { class: 'small', text: 'Volume, issue and page numbers are not stored; each reference carries the DOI instead.' }), exportMsg);
  root.append(form, el('div', { class: 'countbar' }, count, hostBtn), exportBox, note, el('div', { class: 'layout' }, el('details', { class: 'filterwrap', open: true }, el('summary', { text: 'Filters' }), filterBox), el('section', { 'aria-label': 'Results' }, list, more)));

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
    return el('span', { class: 'badge badge-' + g.kind, title: KIND_HELP[g.kind] || '', text: (prefix ? prefix + ': ' : '') + label });
  };

  function renderFinding(f) {
    const r0 = f.rows[0];
    const members = [];
    f.rows.forEach((r, i) => {
      if (i) members.push(' + ');
      members.push(el('a', { href: 'gene/' + r.gene_id + '.html', text: r.gene_name }), ' ', el('span', { class: 'chg', text: S.pretty(r.intervention_type) }));
    });
    const seen = new Set(), badges = [];
    const nGenes = new Set(f.rows.map((r) => r.gene_id)).size;
    for (const r of f.rows) if (!seen.has(r.gene_id)) { seen.add(r.gene_id); badges.push(badge(data.genes[r.gene_id], nGenes > 1 ? r.gene_name : ''), ' '); }
    const [icon, label] = CLASS[r0.result_class] || ['', r0.result_class];
    const p = data.papers[r0.pmid] || {};
    const meta = ['host ' + r0.host_organism];
    const metaEl = el('div', { class: 'fl2' }, 'host ', r0.host_organism === S.HOME_HOST ? r0.host_organism : el('strong', { text: r0.host_organism }));
    if (r0.strain_id) { const rs = data.strains[r0.strain_id].root || r0.strain_id; metaEl.append(' · strain ', el('a', { href: 'strain/' + rs + '.html', text: data.strains[rs].name })); }
    metaEl.append(' · ', el('a', { href: 'paper/' + r0.pmid + '.html', text: (p.first_author || 'Paper') + ' ' + (r0.year || '') }));
    const vt = valueText(r0);
    if (vt) metaEl.append(' · ' + vt);
    metaEl.append(' · ', el('a', { href: 'result/' + r0.public_id + '.html', text: 'details' }));
    const cb = el('input', { type: 'checkbox', 'aria-label': 'Select for citation export' });
    cb.checked = picked.has(f.id);
    cb.addEventListener('change', () => { if (cb.checked) picked.add(f.id); else picked.delete(f.id); updateExport(); });
    return el('li', { class: 'finding' },
      el('label', { class: 'pick small' }, cb, ' cite'),
      el('div', { class: 'fl1' }, members, ' → ', el('strong', { text: r0.effect_direction }), ' ' + r0.phenotype + ' ',
        el('span', { class: 'chip chip-' + r0.result_class }, el('span', { 'aria-hidden': 'true', text: icon }), ' ' + label),
        f.rows.length > 1 ? el('span', { class: 'combo', text: ' combination of ' + f.rows.length }) : null),
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
    const line = 'MarxBase release ' + data.version + ' (' + data.date + '), DOI pending. ' + items.length + ' findings, ' + rows.length + ' results. Filters: ' + describeState(state) + '. ' + (data.hasEvidence ? 'Evidence sentences are not covered by the data licence. ' : '') + 'Data: CC BY 4.0.';
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
    list.replaceChildren(...res.items.slice(0, shown).map(renderFinding));
    updateExport();
    const rest = res.nFindings - shown;
    more.hidden = rest <= 0; more.textContent = 'Show more (' + rest + ' remaining)';
    const allMode = st.allHosts || st.hosts.length;
    count.textContent = res.nFindings + (res.nFindings === 1 ? ' finding (' : ' findings (') + res.nRows + (res.nRows === 1 ? ' result) ' : ' results) ') + (allMode ? 'in all host organisms.' : 'in K. marxianus host organisms only.') + (res.nFindings || allMode ? '' : ' Try removing a filter or including other hosts.');
    hostBtn.textContent = allMode ? 'Show K. marxianus hosts only' : 'Include other host organisms';
    hostBtn.hidden = !!st.hosts.length;
    const weak = st.types.some((t) => WEAK_TYPES.includes(t)) || st.cats.includes('protein_production');
    note.hidden = !weak;
    note.textContent = weak ? 'Heads-up: results for heterologous expression, promoters and protein production are the least complete part of this collection (abstract-only extraction).' : '';
    try { const p = S.toParams(state); history.replaceState(null, '', p ? '?' + p : location.pathname); } catch (e) { /* file:// may refuse; harmless */ }
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
  // ---- suggestions while typing ----
  let items = [], active = -1;
  function closeSugg() { sugg.hidden = true; sugg.replaceChildren(); items = []; active = -1; q.setAttribute('aria-expanded', 'false'); q.removeAttribute('aria-activedescendant'); }
  function setActive(i) {
    active = i;
    [...sugg.children].forEach((li, k) => { li.setAttribute('aria-selected', k === i ? 'true' : 'false'); li.classList.toggle('active', k === i); });
    if (i >= 0) q.setAttribute('aria-activedescendant', 'sg-' + i); else q.removeAttribute('aria-activedescendant');
  }
  function choose(i) { if (i < 0 || !items[i]) return; q.value = items[i].label; closeSugg(); clearTimeout(timer); refresh(); }
  function showSugg() {
    const text = q.value.trim();
    if (!text) return closeSugg();
    items = S.suggest(index, text, { allHosts: allHosts.checked });
    if (!items.length) return closeSugg();
    sugg.replaceChildren(...items.map((it, i) => {
      const li = el('li', { id: 'sg-' + i, role: 'option', 'aria-selected': 'false' }, el('strong', { text: it.label }), el('span', { class: 'hint', text: ' ' + it.hint }));
      li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });
      return li;
    }));
    sugg.hidden = false; q.setAttribute('aria-expanded', 'true'); setActive(-1);
  }
  q.addEventListener('input', () => { showSugg(); clearTimeout(timer); timer = setTimeout(refresh, 150); });
  q.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); setActive((active + 1) % items.length); }
    else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(active); }
    else if (e.key === 'Escape') closeSugg();
  });
  q.addEventListener('blur', () => setTimeout(closeSugg, 120));
  q.addEventListener('focus', () => { if (q.value.trim()) showSugg(); });
  for (const e of [allHosts, sortSel, strainSel, derived, ymin, ymax]) e.addEventListener('change', refresh);
  filterBox.addEventListener('change', refresh);
  hostBtn.addEventListener('click', () => { allHosts.checked = !allHosts.checked; refresh(); });
  more.addEventListener('click', () => { shown += 50; render(); });
  clear.addEventListener('click', () => { state = S.defaultState(); q.value = ''; allHosts.checked = false; fillStrains(); strainSel.value = ''; derived.checked = true; ymin.value = ''; ymax.value = ''; sortSel.value = 'relevance'; shown = 50; render(); });
  window.MarxApp = { render, getState: () => state };
  fillStrains();
  render();
})();

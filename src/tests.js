/* In-browser tests for the search core. Open tests.html (served or from a file) and read the summary. */
(function () {
  'use strict';
  const S = window.MarxSearch, D = window.MARXBASE, E = window.EXPECTED;
  const out = document.getElementById('out'), summary = document.getElementById('summary');
  let pass = 0, fail = 0;
  const t = (name, ok, detail) => {
    ok ? pass++ : fail++;
    const li = document.createElement('li'); li.className = ok ? 'ok' : 'bad';
    li.textContent = (ok ? 'PASS ' : 'FAIL ') + name + (ok || detail == null ? '' : '  -> ' + JSON.stringify(detail));
    out.append(li);
  };
  const eqSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
  const idx = S.build(D);
  const ids = (res) => res.items.map((f) => f.id);
  const genesOf = (res) => [...new Set(res.items.flatMap((f) => f.rows.map((r) => r.gene_name)))];

  t('index has every finding', idx.findings.length === E.total_findings, [idx.findings.length, E.total_findings]);
  t('index has every result', D.results.length === E.total_results, [D.results.length, E.total_results]);
  const home = S.run(idx, {});
  t('default view shows K. marxianus-host findings only', home.nFindings === E.home_findings, [home.nFindings, E.home_findings]);
  const all = S.run(idx, { allHosts: true });
  t('switching on other hosts shows every finding', all.nFindings === E.total_findings && all.nRows === E.total_results, [all.nFindings, all.nRows]);
  t('empty-result query', S.run(idx, { q: 'zzzzqq', allHosts: true }).nFindings === 0);

  // Q1 KU70
  const ku = S.run(idx, { q: 'KU70', allHosts: true });
  t('Q1 KU70 search contains every KU70 finding', E.q1.findings.every((f) => ids(ku).includes(f)), E.q1.findings.filter((f) => !ids(ku).includes(f)));
  t('Q1 KU70 top results are KU70 findings', ku.items.slice(0, E.q1.n).every((f) => f.rows.some((r) => r.gene_name === 'KU70')));
  const kuNeg = S.run(idx, { q: 'KU70', allHosts: true, classes: ['negative', 'context-dependent'] }).items.filter((f) => E.q1.findings.includes(f.id));
  t('Q1 class split of KU70 findings', kuNeg.length === E.q1.classes.negative + E.q1.classes['context-dependent'], [kuNeg.length, E.q1.classes]);
  // Q2 xylitol
  const xy = S.run(idx, { products: ['Xylitol'], allHosts: true });
  t('Q2 xylitol findings', xy.nFindings === E.q2.n, [xy.nFindings, E.q2.n]);
  t('Q2 xylitol failed findings', eqSet(ids(S.run(idx, { products: ['Xylitol'], allHosts: true, classes: ['negative', 'context-dependent'] })), E.q2.not_positive));
  // Q3 strain
  if (E.q3) {
    t('Q3 NBRC 1777 with derived strains', S.run(idx, { strain: E.q3.strain, derived: true, allHosts: true }).nFindings === E.q3.with_derived, [S.run(idx, { strain: E.q3.strain, derived: true, allHosts: true }).nFindings, E.q3.with_derived]);
    t('Q3 NBRC 1777 without derived strains', S.run(idx, { strain: E.q3.strain, derived: false, allHosts: true }).nFindings === E.q3.without_derived);
  }
  // Q4/Q5 aliases and orthologs
  for (const key of ['q4', 'q4b', 'q5']) {
    const r = S.run(idx, { q: E[key].query, allHosts: true });
    t(`${key} search '${E[key].query}' finds the expected gene's findings`, E[key].findings.every((f) => ids(r).includes(f)), E[key].findings.filter((f) => !ids(r).includes(f)));
    t(`${key} top result is ${E[key].genes.join('/')}`, r.items.length > 0 && r.items[0].rows.some((x) => E[key].genes.includes(x.gene_name)), r.items[0] && r.items[0].rows.map((x) => x.gene_name));
  }
  // Q7
  t('Q7 S. cerevisiae host findings', (S.facets(idx, { allHosts: true }).hosts['Saccharomyces cerevisiae'] || 0) === E.q7, [S.facets(idx, { allHosts: true }).hosts['Saccharomyces cerevisiae'], E.q7]);
  // Q6/Q10 gene kinds as embedded
  t('Q6 undetermined paralogs', eqSet(Object.values(D.genes).filter((g) => g.kind === 'undetermined_paralog').map((g) => g.name), E.q6));
  if (E.q10) t('Q10 GDA kind', Object.values(D.genes).some((g) => g.name === 'GDA' && g.kind === E.q10.kind));
  // search behaviour
  const sName = (q, name, o) => S.run(idx, Object.assign({ q, allHosts: true }, o)).items.some((f) => f.rows.some((r) => r.gene_name === name));
  t('typing a space inside a strain name still works (DMKU 3-1042)', S.run(idx, { q: 'dmku 3-1042', allHosts: true }).nFindings > 0);
  t('squashed form works (dmku31042)', S.run(idx, { q: 'dmku31042', allHosts: true }).nFindings > 0);
  t('prefix of a product word works (xylit)', S.run(idx, { q: 'xylit', allHosts: true }).nFindings > 0);
  t('case does not matter', S.run(idx, { q: 'ku70', allHosts: true }).nFindings === ku.nFindings);
  t('every word must match (AND)', S.run(idx, { q: 'ku70 xylitol', allHosts: true }).nFindings <= ku.nFindings);
  t('locus tag search finds KU70', sName('KLMA_10274', 'KU70'));
  t('year filter', S.run(idx, { allHosts: true, ymin: 2025 }).items.every((f) => f.year >= 2025));
  t('class filter', S.run(idx, { allHosts: true, classes: ['negative'] }).items.every((f) => f.cls === 'negative'));
  t('combination counted once', S.run(idx, { allHosts: true }).nFindings < S.run(idx, { allHosts: true }).nRows);
  t('sort puts negatives first', (() => { const r = S.run(idx, { allHosts: true, sort: 'class' }).items; const first = r.findIndex((f) => f.cls === 'positive'); return first < 0 || r.slice(first).every((f) => f.cls === 'positive'); })());
  const st = Object.assign(S.defaultState(), { q: 'a b', classes: ['negative'], allHosts: true, strain: 'x', derived: false, ymin: 2000 });
  const back = S.fromParams('?' + S.toParams(st));
  t('URL parameters round-trip', back.q === 'a b' && back.classes[0] === 'negative' && back.allHosts && back.strain === 'x' && back.derived === false && back.ymin === 2000, back);
  t('facet counts for classes add up to the findings', Object.values(S.facets(idx, { allHosts: true }).classes).reduce((a, b) => a + b, 0) === E.total_findings);
  // suggestions
  const sg = (text, o) => S.suggest(idx, text, o);
  const labels = (r) => r.map((x) => x.label);
  t('suggestions: one letter gives up to 10 items', sg('k').length > 0 && sg('k').length <= 10, sg('k').length);
  t('suggestions: genes come first and start with the letter', sg('k').every((x) => x.label.toLowerCase().startsWith('k') || x.hint) && sg('k')[0].kind === 'gene', sg('k').slice(0, 3));
  t('suggestions: an ortholog name leads to its gene', sg('suc2').some((x) => x.label === 'SUC2' && x.hint.includes('ortholog of INU1')), sg('suc2'));
  t('suggestions: an ortholog ID leads to its gene', sg('yil1').some((x) => x.label === 'YIL162W' && x.hint.includes('INU1')), sg('yil1'));
  t('suggestions: an alias leads to its gene', sg('lig').some((x) => x.label === 'LIG4' && x.hint.includes('DNL4')), sg('lig'));
  t('suggestions: products are offered', sg('xylit').some((x) => x.label === 'Xylitol' && x.kind === 'product'), sg('xylit'));
  t('suggestions: strain names and collection aliases are offered', sg('dmku').some((x) => x.kind === 'strain' && x.label.startsWith('DMKU')), sg('dmku'));
  t('suggestions: derived strain names are not offered', !sg('yzb453', { allHosts: true }).length && !sg('nbrc1777-d', { allHosts: true }).length, [sg('yzb453', { allHosts: true }), sg('nbrc1777-d', { allHosts: true })]);
  t('suggestions: enzyme/protein labels are not offered', !sg('gda', { allHosts: true }).length && !sg('xyn-c', { allHosts: true }).length);
  const genes = Object.entries(D.genes);
  const otherOnly = genes.filter(([id, g]) => g.organism !== 'K. marxianus' && !D.results.some((r) => r.gene_id === id && r.host_organism === 'K. marxianus') && !genes.some(([, h]) => h.organism === 'K. marxianus' && h.name === g.name)).map(([, g]) => g.name);
  t('suggestions: genes only studied in other hosts are not offered as genes', otherOnly.length >= 5 && otherOnly.every((n) => !sg(n.toLowerCase(), { allHosts: true }).some((x) => x.kind === 'gene' && x.label === n)), otherOnly.filter((n) => sg(n.toLowerCase(), { allHosts: true }).some((x) => x.kind === 'gene' && x.label === n)));
  t('suggestions: a K. marxianus gene that shares a name with an S. cerevisiae gene is offered once as a gene', sg('gal80', { allHosts: true }).filter((x) => x.kind === 'gene').length === 1);
  t('suggestions: other-host strains only appear when other hosts are on', !sg('bl21').length && sg('bl21', { allHosts: true }).length > 0, [sg('bl21'), sg('bl21', { allHosts: true })]);
  t('suggestions: locus tags work', sg('klma_1027').some((x) => x.label === 'KLMA_10274' && x.hint.includes('KU70')), sg('klma_1027'));
  t('suggestions: nothing for gibberish or an empty box', !sg('zzzz').length && !sg('').length);
  t('suggestions: no duplicates', (() => { const r = sg('a'); return new Set(r.map((x) => x.label + x.hint)).size === r.length; })());
  // ---- citations and CSV ----
  const C = window.MarxCite;
  const ps = Object.values(D.papers);
  t('cite: every paper has a PMID, title, journal and year', ps.every((p) => p.pmid && p.title && p.journal && p.year));
  t('cite: author parsing matches the number of authors in the string', ps.every((p) => C.parseAuthors(p.authors).length === p.authors.split('; ').filter(Boolean).length));
  const sample = { pmid: '1', title: 'Gene A_b & 50% of {x}.', authors: 'de la Cruz AB; Smith J', journal: 'J Test', year: 2020, doi: '10.1/x', pmcid: 'PMC1' };
  t('cite: BibTeX escapes LaTeX characters and keeps compound surnames together', (() => { const b = C.toBibTeX([sample]); return b.includes('\\_b \\& 50\\% of \\{x\\}') && b.includes('{de la Cruz}, AB and Smith, J'); })(), C.toBibTeX([sample]));
  t('cite: BibTeX writes Greek letters and degrees as LaTeX commands', (() => { const b = C.toBibTeX([{ ...sample, title: 'Δ-ura at 42 °C with β-gal' }]); return b.includes('$\\Delta$-ura at 42 \\textdegree{}C with $\\beta$-gal'); })(), C.toBibTeX([{ ...sample, title: 'Δ-ura at 42 °C' }]));
  t('cite: RIS has one record per paper with TY and ER lines and CRLF', (() => { const r = C.toRIS([sample, sample]); return r.split('TY  - JOUR').length === 3 && r.split('ER  - ').length === 3 && r.includes('\r\n') && r.includes('DO  - 10.1/x'); })());
  t('cite: CSL-JSON parses and keeps authors, year and DOI', (() => { const j = JSON.parse(C.toCSL([sample])); return j[0].author[0].family === 'de la Cruz' && j[0].issued['date-parts'][0][0] === 2020 && j[0].DOI === '10.1/x'; })());
  t('cite: CSL-JSON authors match the release file rule for every paper', ps.every((p) => JSON.parse(C.toCSL([p]))[0].author.length === C.parseAuthors(p.authors).length));
  t('cite: AMA lists 6 authors in full and 3 plus et al beyond', (() => { const a = (n) => C.asText(C.formatted({ ...sample, authors: Array.from({ length: n }, (_, i) => 'Fam' + i + ' A').join('; ') }, 'AMA')); return !a(6).includes('et al') && a(7).includes('Fam2 A, et al') && !a(7).includes('Fam3'); })());
  t('cite: APA, MLA and NLM follow their author rules', (() => { const x = (s) => C.asText(C.formatted(sample, s)); return x('APA').startsWith('de la Cruz, A. B., & Smith, J. (2020).') && x('MLA').startsWith('de la Cruz, A. B., and J. Smith.') && x('NLM').startsWith('de la Cruz AB, Smith J.') && x('NLM').includes('PMID: 1.'); })(), [C.asText(C.formatted(sample, 'APA')), C.asText(C.formatted(sample, 'MLA')), C.asText(C.formatted(sample, 'NLM'))]);
  t('cite: journal names are italic in the HTML version and text is escaped', (() => { const h = C.asHtml(C.formatted({ ...sample, title: 'A <b> test' }, 'AMA')); return h.includes('<i>J Test</i>') && h.includes('&lt;b&gt;') && !h.includes('<b>'); })());
  t('cite: all four styles work for every paper without "undefined" or "NaN"', ps.every((p) => ['AMA', 'APA', 'MLA', 'NLM'].every((s) => !/undefined|NaN|null/.test(C.asText(C.formatted(p, s))))));
  t('csv: quotes, commas, newlines and empties are handled', C.csvCell('a,b') === '"a,b"' && C.csvCell('say "hi"') === '"say ""hi"""' && C.csvCell('x\ny') === '"x\ny"' && C.csvCell(null) === '' && C.csvCell(0) === '0');
  t('csv: comment line first (after BOM), header second, one row per result', (() => { const rows = D.results.slice(0, 5), out = C.toCSV(rows, D.columns, 'note'); const lines = out.split('\n'); return lines[0] === '\ufeff# note' && lines[1] === D.columns.join(',') && lines.length === 5 + 3; })());
  t('csv: a view downloads exactly its results', (() => { const v = S.run(idx, {}); return v.items.flatMap((f) => f.rows).length === v.nRows; })());
  t('csv: columns follow the evidence switch and never include the html copy', D.columns.includes('evidence_sentence') === !!D.hasEvidence && D.columns.includes('evidence_source') === !!D.hasEvidence && !D.columns.includes('evidence_sentence_html'));
  // ---- report form logic ----
  const SG = window.MarxSuggest;
  const okForm = { kind: 'error_report', comment: 'The effect looks reversed' };
  t('suggest: a valid report passes', SG.validate(okForm).length === 0);
  t('suggest: an empty or tiny comment is refused', SG.validate({ kind: 'error_report', comment: '  ' }).length > 0 && SG.validate({ kind: 'error_report', comment: 'ab' }).length > 0);
  t('suggest: an unknown kind is refused', SG.validate({ kind: 'delete_everything', comment: 'hello there' }).length > 0);
  t('suggest: edits, missing results and gene mappings each need their value', ['field_edit', 'missing_result', 'gene_mapping'].every((k) => SG.validate({ kind: k, comment: 'a reason' }).length > 0 && SG.validate({ kind: k, comment: 'a reason', proposed_value: 'x' }).length === 0));
  t('suggest: too-long text is refused', SG.validate({ ...okForm, comment: 'x'.repeat(2001) }).length > 0 && SG.validate({ ...okForm, contact: 'x'.repeat(201) }).length > 0);
  t('suggest: the payload has only the allowed columns and trims text', (() => { const p = SG.payload({ ...okForm, comment: '  hi there  ', contact: '', evidence: ' e ' }, { pageType: 'result', targetId: 'MARXBASE-R000001', release: '1.0-draft' }); return Object.keys(p).sort().join() === 'comment,contact,evidence,field_name,kind,page_type,proposed_value,release_version,target_id' && p.comment === 'hi there' && p.contact === null && p.evidence === 'e' && p.field_name === null; })());
  t('suggest: the field name is sent only for field edits', SG.payload({ kind: 'field_edit', field_name: 'product', proposed_value: 'x', comment: 'abc' }, { pageType: 'result', targetId: 'a', release: 'r' }).field_name === 'product' && SG.payload({ kind: 'error_report', field_name: 'product', comment: 'abc' }, { pageType: 'result', targetId: 'a', release: 'r' }).field_name === null);
  t('suggest: a publishable key goes in apikey only; a JWT key also in Authorization', (() => { const a = SG.headers('sb_publishable_abc'), b = SG.headers('eyJhbGciOi.x.y'); return a.apikey === 'sb_publishable_abc' && !a.Authorization && b.Authorization === 'Bearer eyJhbGciOi.x.y' && a.Prefer === 'return=minimal'; })());
  t('suggest: cooldown blocks a second send within 30 seconds', SG.cooldownLeft(1000, 11000) === 20000 && SG.cooldownLeft(1000, 40000) === 0 && SG.cooldownLeft(0, Date.now()) === 0);
  summary.textContent = `${pass} passed, ${fail} failed`;
  summary.className = fail ? 'bad' : 'ok';
  document.title = fail ? 'TESTS FAILED' : 'TESTS PASSED';
})();

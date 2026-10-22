/* MarxBase citation and CSV export: pure functions (no DOM), used by the search page, the paper pages and the tests.
   Formatted references are built from the fields MarxBase stores (authors, title, journal, year, DOI, PMID). Volume, issue and
   page numbers are NOT stored, so journal references carry the DOI and PMID instead. */
(function (root) {
  'use strict';

  // "Smith AB; de la Cruz C" -> [{family:'Smith', given:'AB'}, {family:'de la Cruz', given:'C'}]  (same rule as the release's CSL-JSON)
  function parseAuthors(s) {
    return String(s || '').split('; ').map((a) => a.trim()).filter(Boolean).map((a) => {
      const parts = a.split(/\s+/);
      return { family: parts.slice(0, -1).join(' ') || parts[0], given: parts.length > 1 ? parts[parts.length - 1] : '' };
    });
  }
  const letters = (g) => [...String(g || '').replace(/[^\p{L}]/gu, '')];
  const initialsPlain = (g) => letters(g).join('');
  const initialsDotted = (g) => letters(g).map((c) => c + '.').join(' ');
  const stripDot = (s) => String(s || '').trim().replace(/\.+$/, '');
  const doiUrl = (p) => (p.doi ? 'https://doi.org/' + p.doi : '');

  // ----- formatted references as segments [text, italic] -----
  const seg = (text, italic) => [text, !!italic];
  const join = (...parts) => parts.filter((s) => s && s[0]);

  function ama(p) {
    const a = parseAuthors(p.authors), names = a.map((x) => x.family + (x.given ? ' ' + initialsPlain(x.given) : ''));
    const list = names.length > 6 ? names.slice(0, 3).join(', ') + ', et al' : names.join(', ');
    return join(list ? seg(list + '. ') : null, seg(stripDot(p.title) + '. '), seg(stripDot(p.journal), true), seg('. ' + p.year + '.'),
      p.doi ? seg(' doi:' + p.doi) : null);
  }
  function apa(p) {
    const a = parseAuthors(p.authors).map((x) => x.family + (x.given ? ', ' + initialsDotted(x.given) : ''));
    let list;
    if (a.length === 0) list = '';
    else if (a.length === 1) list = a[0];
    else if (a.length <= 20) list = a.slice(0, -1).join(', ') + ', & ' + a[a.length - 1];
    else list = a.slice(0, 19).join(', ') + ', … ' + a[a.length - 1];
    return join(list ? seg(list + ' ') : null, seg('(' + p.year + '). '), seg(stripDot(p.title) + '. '), seg(stripDot(p.journal), true),
      seg('.'), p.doi ? seg(' ' + doiUrl(p)) : null);
  }
  function mla(p) {
    const a = parseAuthors(p.authors);
    const first = (x) => x.family + (x.given ? ', ' + initialsDotted(x.given) : '');
    const rest = (x) => (x.given ? initialsDotted(x.given) + ' ' : '') + x.family;
    let list = '';
    if (a.length === 1) list = first(a[0]);
    else if (a.length === 2) list = first(a[0]) + ', and ' + rest(a[1]);
    else if (a.length > 2) list = first(a[0]) + ', et al';
    return join(list ? seg(list + '. ') : null, seg('“' + stripDot(p.title) + '.” '), seg(stripDot(p.journal), true), seg(', ' + p.year),
      p.doi ? seg(', ' + doiUrl(p)) : null, seg('.'));
  }
  function nlm(p) {
    const a = parseAuthors(p.authors).map((x) => x.family + (x.given ? ' ' + initialsPlain(x.given) : ''));
    const list = a.length > 25 ? a.slice(0, 24).join(', ') + ', et al' : a.join(', ');
    return join(list ? seg(list + '. ') : null, seg(stripDot(p.title) + '. '), seg(stripDot(p.journal) + '. ' + p.year + '.'),
      p.doi ? seg(' doi: ' + p.doi + '.') : null, p.pmid ? seg(' PMID: ' + p.pmid + '.') : null);
  }
  const STYLES = { AMA: ama, APA: apa, MLA: mla, NLM: nlm };
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const asText = (segs) => segs.map((s) => s[0]).join('');
  const asHtml = (segs) => segs.map((s) => (s[1] ? '<i>' + esc(s[0]) + '</i>' : esc(s[0]))).join('');
  const formatted = (p, style) => STYLES[style](p);

  // ----- BibTeX -----
  const LATEX = { '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#', '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\textasciicircum{}' };
  // Greek letters and the degree sign are not defined by pdflatex's utf8 input, so they are written as LaTeX commands
  const GREEK = { 'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu', 'σ': 'sigma', 'τ': 'tau', 'ω': 'omega', 'Δ': 'Delta', 'Σ': 'Sigma', 'Ω': 'Omega' };
  const tex = (s) => String(s == null ? '' : s).replace(/[\\&%$#_{}~^]/g, (c) => LATEX[c]).replace(/[α-ωΔΣΩ]/g, (c) => (GREEK[c] ? '$\\' + GREEK[c] + '$' : c)).replace(/°/g, '\\textdegree{}');
  function bibtexEntry(p) {
    const authors = parseAuthors(p.authors).map((a) => (/\s/.test(a.family) ? '{' + tex(a.family) + '}' : tex(a.family)) + (a.given ? ', ' + tex(a.given) : '')).join(' and ');
    const f = [['author', authors], ['title', '{' + tex(p.title) + '}'], ['journal', tex(p.journal)], ['year', String(p.year || '')], ['doi', tex(p.doi || '')], ['pmid', String(p.pmid || '')]];
    if (p.pmcid) f.push(['pmcid', String(p.pmcid)]);
    return '@article{pmid' + p.pmid + ',\n' + f.filter(([, v]) => v).map(([k, v]) => '  ' + k + ' = {' + v + '}').join(',\n') + '\n}\n';
  }
  const toBibTeX = (papers) => '% MarxBase citations (UTF-8). Volume, issue and pages are not stored; the DOI and PMID identify each paper.\n' + papers.map(bibtexEntry).join('\n');

  // ----- RIS -----
  function risEntry(p) {
    const lines = ['TY  - JOUR', 'ID  - pmid' + p.pmid];
    for (const a of parseAuthors(p.authors)) lines.push('AU  - ' + a.family + (a.given ? ', ' + a.given : ''));
    lines.push('TI  - ' + String(p.title || '').replace(/\s+/g, ' '), 'JO  - ' + (p.journal || ''), 'PY  - ' + (p.year || ''));
    if (p.doi) lines.push('DO  - ' + p.doi);
    lines.push('AN  - ' + p.pmid, 'UR  - https://pubmed.ncbi.nlm.nih.gov/' + p.pmid + '/');
    if (p.pmcid) lines.push('N1  - PMCID: ' + p.pmcid);
    lines.push('ER  - ', '');
    return lines.join('\r\n');
  }
  const toRIS = (papers) => papers.map(risEntry).join('\r\n');

  // ----- CSL-JSON (same shape as the release's citations.csl.json) -----
  function toCSL(papers) {
    return JSON.stringify(papers.map((p) => {
      const item = { id: 'pmid:' + p.pmid, type: 'article-journal', title: p.title, 'container-title': p.journal, author: parseAuthors(p.authors), PMID: p.pmid };
      if (p.year) item.issued = { 'date-parts': [[p.year]] };
      if (p.doi) item.DOI = p.doi;
      if (p.pmcid) item.PMCID = p.pmcid;
      return item;
    }), null, 1) + '\n';
  }

  const FORMATS = {
    bibtex: { label: 'BibTeX (.bib)', ext: 'bib', mime: 'application/x-bibtex', make: toBibTeX },
    ris: { label: 'RIS (.ris)', ext: 'ris', mime: 'application/x-research-info-systems', make: toRIS },
    csl: { label: 'CSL-JSON (.json)', ext: 'json', mime: 'application/json', make: toCSL },
    ama: { label: 'AMA, formatted text (.txt)', ext: 'txt', mime: 'text/plain', make: (ps) => ps.map((p) => asText(ama(p))).join('\n\n') + '\n' },
    apa: { label: 'APA, formatted text (.txt)', ext: 'txt', mime: 'text/plain', make: (ps) => ps.map((p) => asText(apa(p))).join('\n\n') + '\n' },
    mla: { label: 'MLA, formatted text (.txt)', ext: 'txt', mime: 'text/plain', make: (ps) => ps.map((p) => asText(mla(p))).join('\n\n') + '\n' },
    nlm: { label: 'NLM, formatted text (.txt)', ext: 'txt', mime: 'text/plain', make: (ps) => ps.map((p) => asText(nlm(p))).join('\n\n') + '\n' }
  };
  // a rich-text (HTML) version keeps the italics for the four styles; open the file in Word or paste it into a document
  function richHtml(papers, style) {
    return '<!doctype html><meta charset="utf-8"><title>MarxBase references (' + style + ')</title><body>' +
      papers.map((p) => '<p>' + asHtml(formatted(p, style)) + '</p>').join('\n') + '</body>';
  }
  const sortPapers = (papers) => papers.slice().sort((a, b) => (a.pmid < b.pmid ? -1 : 1));

  // ----- CSV of results -----
  function csvCell(v) {
    if (v == null) return '';
    const s = String(v);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function toCSV(rows, columns, commentLine) {
    const out = ['﻿# ' + commentLine, columns.join(',')];
    for (const r of rows) out.push(columns.map((c) => csvCell(r[c])).join(','));
    return out.join('\n') + '\n';
  }

  function download(filename, text, mime) {
    const url = URL.createObjectURL(new Blob([text], { type: (mime || 'text/plain') + ';charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  root.MarxCite = { parseAuthors, formatted, asText, asHtml, richHtml, toBibTeX, toRIS, toCSL, toCSV, tex, csvCell, FORMATS, STYLES, sortPapers, download, initialsDotted, initialsPlain };
})(typeof window !== 'undefined' ? window : globalThis);

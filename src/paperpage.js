/* Paper page: the "Cite" button opens a pop-up (a native <dialog>, like PubMed's) with the formatted citation, a choice of style,
   a Copy button and a download choice (BibTeX, RIS, CSL-JSON). DOM calls and textContent only. */
(function () {
  'use strict';
  const C = window.MarxCite, btn = document.getElementById('cite-open'), src = document.getElementById('paper-data');
  if (!C || !btn || !src) return;
  const p = JSON.parse(src.textContent);
  const STYLES = Object.keys(C.STYLES), DOWNLOADS = ['bibtex', 'ris', 'csl'];

  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'text') e.textContent = v; else if (k in e && k !== 'class' && k !== 'for') e[k] = v; else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return e;
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* not a secure page (for example a local file): fall back */ }
    const ta = el('textarea', { class: 'offscreen', 'aria-hidden': 'true' }); ta.value = text; (document.querySelector('dialog[open]') || document.body).append(ta); ta.select();   // inside the open dialog: the rest of the page is inert while it is modal
    let ok = false; try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove(); return ok;
  }

  const styleSel = el('select', { id: 'cite-style' }, STYLES.map((s) => el('option', { value: s, text: s })));
  try { const last = sessionStorage.getItem('marxbase-cite-style'); if (last && STYLES.includes(last)) styleSel.value = last; } catch (e) { /* private mode */ }
  const text = el('div', { class: 'citetext', id: 'cite-text', tabindex: '0' });
  const status = el('span', { class: 'small', role: 'status', 'aria-live': 'polite' });
  const copyBtn = el('button', { type: 'button', class: 'iconbtn copybtn', 'aria-label': 'Copy the citation', title: 'Copy' });
  const dlSel = el('select', { id: 'cite-download', 'aria-label': 'Download format' }, DOWNLOADS.map((k) => el('option', { value: k, text: C.FORMATS[k].label })));
  const dlBtn = el('button', { type: 'button', class: 'iconbtn', 'aria-label': 'Download the citation', title: 'Download' });
  function icon(paths) {
    const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
    for (const [k, v] of [['viewBox', '0 0 20 20'], ['width', '18'], ['height', '18'], ['aria-hidden', 'true'], ['focusable', 'false']]) svg.setAttribute(k, v);
    for (const d of paths) {
      const path = document.createElementNS(NS, 'path');
      for (const [k, v] of [['d', d], ['fill', 'none'], ['stroke', 'currentColor'], ['stroke-width', '1.8'], ['stroke-linecap', 'round'], ['stroke-linejoin', 'round']]) path.setAttribute(k, v);
      svg.append(path);
    }
    return svg;
  }
  dlBtn.append(icon(['M10 3v9m0 0-3.5-3.5M10 12l3.5-3.5M4 16h12']));
  copyBtn.append(icon(['M7 7h9v9H7z', 'M13 7V4H4v9h3']));   // two overlapping squares
  const closeBtn = el('button', { type: 'button', class: 'close', 'aria-label': 'Close', text: '\u00d7' });
  const dlg = el('dialog', { class: 'citedialog', 'aria-labelledby': 'cite-title' },
    el('div', { class: 'cd-head' }, el('h2', { id: 'cite-title', text: 'Cite this paper' }), closeBtn),
    el('div', { class: 'cd-body' }, el('div', { class: 'citebox' }, text, status, copyBtn),
      el('div', { class: 'cd-actions' }, el('label', { for: 'cite-style', text: 'Format:' }), styleSel, el('label', { for: 'cite-download', text: 'Download:' }), dlSel, dlBtn)));
  document.body.append(dlg);

  function show() {
    const segs = C.formatted(p, styleSel.value);
    text.replaceChildren(...segs.map(([t, italic]) => (italic ? el('i', { text: t }) : document.createTextNode(t))));
    status.textContent = '';
  }
  show();
  styleSel.addEventListener('change', () => { show(); try { sessionStorage.setItem('marxbase-cite-style', styleSel.value); } catch (e) { /* private mode */ } });
  copyBtn.addEventListener('click', async () => { status.textContent = (await copyText(C.asText(C.formatted(p, styleSel.value)))) ? 'Copied to the clipboard.' : 'Could not copy; select the text and copy it.'; });
  dlBtn.addEventListener('click', () => { const f = C.FORMATS[dlSel.value]; C.download('pmid' + p.pmid + '.' + f.ext, f.make([p]), f.mime); });
  closeBtn.addEventListener('click', () => dlg.close());
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });            // a click on the dimmed background closes it
  btn.addEventListener('click', () => { show(); if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); });
  btn.hidden = false;
})();

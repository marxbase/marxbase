/* MarxBase "Report or suggest" form. Builds the form with DOM calls and textContent only (no innerHTML).
   It sends one anonymous row to the suggestion table and nothing else; it never reads anything back.
   It stays invisible when no site configuration is present (the offline copy and a local build without keys). */
(function (root) {
  'use strict';
  const KINDS = {
    error_report: 'Something looks wrong',
    field_edit: 'Suggest a change to a field',
    missing_result: 'A result is missing',
    gene_mapping: 'Gene identifier or mapping'
  };
  const FIELDS = ['effect', 'phenotype', 'type of change', 'host organism', 'strain', 'product', 'value or unit', 'paper details', 'other'];
  const LIMITS = { target_id: 200, field_name: 80, proposed_value: 1000, comment: 2000, evidence: 2000, contact: 200 };
  const LABELS = {
    error_report: { value: null, comment: 'What looks wrong?', evidence: 'Sentence from the paper that shows it (optional)' },
    field_edit: { value: 'Proposed value', comment: 'Why? (a short reason)', evidence: 'Sentence from the paper that supports it (optional)' },
    missing_result: { value: 'Paper (PMID or DOI)', comment: 'Describe the result: gene, change, effect, phenotype', evidence: 'Sentence from the paper that states it' },
    gene_mapping: { value: 'Locus tag or gene identifier', comment: 'Paper (PMID or DOI) and any note', evidence: 'Sentence from the paper that states the locus tag' }
  };
  const COOLDOWN_MS = 30000;
  // old-style anon keys are JWTs and go in both headers; the newer publishable keys (sb_publishable_...) are not JWTs and go in apikey only
  function headers(key) {
    const h = { apikey: key, 'Content-Type': 'application/json', Prefer: 'return=minimal' };
    if (/^eyJ/.test(key)) h.Authorization = 'Bearer ' + key;
    return h;
  }

  // ---- pure logic (tested in tests.html) ----
  function validate(f) {
    const errors = [];
    if (!KINDS[f.kind]) errors.push('Choose what kind of message this is.');
    const need = (v, n) => String(v || '').trim().length >= n;
    if (!need(f.comment, 3)) errors.push('Please write a short description.');
    if (f.kind === 'field_edit' && !need(f.proposed_value, 1)) errors.push('Please give the proposed value.');
    if (f.kind === 'gene_mapping' && !need(f.proposed_value, 1)) errors.push('Please give the locus tag or identifier.');
    if (f.kind === 'missing_result' && !need(f.proposed_value, 1)) errors.push('Please give the PMID or DOI of the paper.');
    for (const [k, n] of Object.entries(LIMITS)) if (String(f[k] || '').length > n) errors.push('The ' + k.replace('_', ' ') + ' is too long (maximum ' + n + ' characters).');
    return errors;
  }
  function payload(f, ctx) {
    const clean = (v) => { const s = String(v == null ? '' : v).trim(); return s === '' ? null : s; };
    return {
      kind: f.kind, page_type: ctx.pageType, target_id: ctx.targetId, release_version: ctx.release,
      field_name: f.kind === 'field_edit' ? clean(f.field_name) : null, proposed_value: clean(f.proposed_value),
      comment: String(f.comment).trim(), evidence: clean(f.evidence), contact: clean(f.contact)
    };
  }
  function cooldownLeft(last, now) { return Math.max(0, COOLDOWN_MS - (now - (last || 0))); }

  const api = { KINDS, FIELDS, LIMITS, LABELS, validate, payload, cooldownLeft, COOLDOWN_MS, headers };
  root.MarxSuggest = api;

  // ---- interface ----
  const doc = root.document;
  if (!doc) return;
  const cfg = root.MARXBASE_CONFIG, box = doc.getElementById('suggest-box');
  if (!cfg || !cfg.supabaseUrl || !cfg.supabaseAnonKey || !box || root.location.protocol === 'file:') return;
  const ctx = { pageType: box.dataset.pageType, targetId: box.dataset.targetId, release: box.dataset.release };

  function el(tag, attrs, ...kids) {
    const e = doc.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'text') e.textContent = v; else if (k in e && k !== 'class' && k !== 'for' && k !== 'list') e[k] = v; else e.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : doc.createTextNode(String(kid)));
    return e;
  }
  const kindSel = el('select', { id: 'sg-kind' }, Object.entries(KINDS).map(([k, t]) => el('option', { value: k, text: t })));
  const fieldSel = el('select', { id: 'sg-field' }, FIELDS.map((t) => el('option', { value: t, text: t })));
  const valueIn = el('input', { id: 'sg-value', type: 'text', maxLength: LIMITS.proposed_value });
  const commentIn = el('textarea', { id: 'sg-comment', rows: 4, maxLength: LIMITS.comment });
  const evidenceIn = el('textarea', { id: 'sg-evidence', rows: 2, maxLength: LIMITS.evidence });
  const contactIn = el('input', { id: 'sg-contact', type: 'text', maxLength: LIMITS.contact, autocomplete: 'off' });
  const trap = el('input', { type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off', 'aria-hidden': 'true' });
  const trapWrap = el('div', { class: 'sg-trap', 'aria-hidden': 'true' }, trap);
  const msg = el('p', { role: 'status', 'aria-live': 'polite' });
  const send = el('button', { type: 'submit', text: 'Send' });
  const lbl = {};
  const row = (key, id, label, input) => { lbl[key] = el('label', { for: id, text: label }); return el('div', { class: 'row', 'data-row': key }, lbl[key], input); };
  const rows = {
    field: row('field', 'sg-field', 'Which field?', fieldSel), value: row('value', 'sg-value', '', valueIn), comment: row('comment', 'sg-comment', '', commentIn),
    evidence: row('evidence', 'sg-evidence', '', evidenceIn), contact: row('contact', 'sg-contact', 'Your name or email (optional, only used to reply)', contactIn)
  };
  function refresh() {
    const k = kindSel.value, L = LABELS[k];
    rows.field.hidden = k !== 'field_edit'; rows.value.hidden = !L.value;
    lbl.value.textContent = L.value || ''; lbl.comment.textContent = L.comment; lbl.evidence.textContent = L.evidence;
  }
  const form = el('form', { class: 'sg-form', novalidate: true },
    el('p', { class: 'small', text: 'About: ' + (ctx.pageType || '') + ' ' + (ctx.targetId || '') + ', release ' + ctx.release + '. Messages are read only by the MarxBase maintainers and are never shown on the site.' }),
    el('div', { class: 'row' }, el('label', { for: 'sg-kind', text: 'What is this about?' }), kindSel), rows.field, rows.value, rows.comment, rows.evidence, rows.contact, trapWrap, el('p', {}, send), msg);
  const wrap = el('details', { class: 'sg-wrap' }, el('summary', { text: 'Report or suggest' }), form);
  box.replaceChildren(wrap);
  kindSel.addEventListener('change', refresh); refresh();

  function lastSent() { try { return Number(root.sessionStorage.getItem('marxbase-sg') || 0); } catch (e) { return 0; } }
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = { kind: kindSel.value, field_name: fieldSel.value, proposed_value: valueIn.value, comment: commentIn.value, evidence: evidenceIn.value, contact: contactIn.value };
    const errors = validate(f);
    if (errors.length) { msg.textContent = errors.join(' '); return; }
    const wait = cooldownLeft(lastSent(), Date.now());
    if (wait) { msg.textContent = 'Please wait ' + Math.ceil(wait / 1000) + ' seconds before sending another message.'; return; }
    send.disabled = true; msg.textContent = 'Sending…';
    const done = () => { try { root.sessionStorage.setItem('marxbase-sg', String(Date.now())); } catch (e) { /* private mode */ } form.reset(); refresh(); msg.textContent = 'Thank you. Your message was sent to the MarxBase maintainers.'; };
    if (trap.value) { done(); send.disabled = false; return; }       // a bot filled the hidden field: pretend it worked, send nothing
    try {
      const res = await fetch(cfg.supabaseUrl.replace(/\/$/, '') + '/rest/v1/suggestion', {
        method: 'POST', headers: headers(cfg.supabaseAnonKey),
        body: JSON.stringify(payload(f, ctx))
      });
      if (res.ok) done(); else msg.textContent = 'Sorry, the message could not be sent (error ' + res.status + '). Please try again later.';
    } catch (e) { msg.textContent = 'Sorry, the message could not be sent. Check your connection and try again.'; }
    send.disabled = false;
  });
})(typeof window !== 'undefined' ? window : globalThis);

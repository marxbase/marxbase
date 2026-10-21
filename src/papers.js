/* Papers page: the "Only papers with findings" box. The page lists every text-mined paper; papers without a finding carry class "nofind".
   With the box ticked (the default) those are hidden, empty years are hidden, and the counts follow. DOM calls only. */
(function () {
  'use strict';
  const box = document.getElementById('only-findings'), wrap = document.getElementById('papers-toggle');
  if (!box || !wrap) return;
  const years = [...document.querySelectorAll('section.year')];
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  function apply() {
    const only = box.checked;
    for (const y of years) {
      let n = 0;
      for (const li of y.querySelectorAll('li')) { const hide = only && li.classList.contains('nofind'); li.hidden = hide; if (!hide) n++; }
      y.hidden = n === 0;
      const c = y.querySelector('.count'); if (c) c.textContent = '(' + plural(n, 'paper') + ')';
    }
    try { const u = new URL(location.href); if (only) u.searchParams.delete('all'); else u.searchParams.set('all', '1'); history.replaceState(null, '', u.pathname + u.search); } catch (e) { /* file:// may refuse */ }
  }
  box.checked = new URLSearchParams(location.search).get('all') !== '1';
  wrap.hidden = false;
  box.addEventListener('change', apply);
  apply();
})();

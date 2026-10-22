/* Site-wide behaviour: the Menu button for the navigation on narrow screens. DOM calls only. */
(function () {
  'use strict';
  document.documentElement.classList.add('js');
  function init() {
    const btn = document.getElementById('menu-toggle'), nav = document.getElementById('site-nav');
    if (!btn || !nav) return;
    btn.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && nav.classList.contains('open')) { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); btn.focus(); } });
  }
  // a link such as products.html#sugar-alcohols-and-polyols opens that dropdown
  function openTarget() {
    const d = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (d && d.tagName === 'DETAILS') { d.open = true; d.scrollIntoView(); }
  }
  window.addEventListener('hashchange', openTarget);
  document.addEventListener('DOMContentLoaded', openTarget);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

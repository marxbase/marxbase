/* Citation block on a paper page: reads the paper's fields from the embedded JSON and shows the four reference styles
   plus buttons for BibTeX, RIS and CSL-JSON. DOM calls and textContent only. */
(function () {
  'use strict';
  const C = window.MarxCite, box = document.getElementById('paper-cite'), src = document.getElementById('paper-data');
  if (!C || !box || !src) return;
  const p = JSON.parse(src.textContent);
  box.replaceChildren();
  for (const style of Object.keys(C.STYLES)) {
    const line = document.createElement('p');
    const tag = document.createElement('strong'); tag.textContent = style + ' ';
    line.append(tag);
    for (const [text, italic] of C.formatted(p, style)) {
      if (italic) { const i = document.createElement('i'); i.textContent = text; line.append(i); } else line.append(document.createTextNode(text));
    }
    box.append(line);
  }
  const row = document.createElement('p');
  for (const k of ['bibtex', 'ris', 'csl']) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = C.FORMATS[k].label.split(' (')[0] + ' file';
    b.addEventListener('click', () => C.download('pmid' + p.pmid + '.' + C.FORMATS[k].ext, C.FORMATS[k].make([p]), C.FORMATS[k].mime));
    row.append(b, ' ');
  }
  box.append(row);
  const note = document.createElement('p'); note.className = 'small'; note.textContent = 'Volume, issue and page numbers are not stored; the DOI identifies the paper.';
  box.append(note);
})();

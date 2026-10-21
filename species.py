"""Species names in italics, everywhere they appear in page text.

`names_from(...)` builds the list of names to look for (the organisms that occur in the data, their abbreviated forms, and a few well-known yeasts);
`italicize(html, names)` wraps each one in <i> inside the TEXT of an HTML fragment only: never inside tags or attribute values, and never inside
<i>, <em>, <script>, <style>, <code>, <title>, <option>, <textarea>, <select> or <svg>. The same list goes to the browser (data.js) so the search
page italicises its own text the same way (src/search-core.js, speciesParts).
"""
import re

EXTRA = ["Kluyveromyces marxianus", "K. marxianus", "Saccharomyces cerevisiae", "S. cerevisiae", "Escherichia coli", "E. coli", "Pichia pastoris", "P. pastoris",
         "Komagataella phaffii", "K. phaffii", "Kluyveromyces lactis", "K. lactis", "Yarrowia lipolytica", "Y. lipolytica", "Homo sapiens", "Arabidopsis thaliana",
         "Pichia", "Kluyveromyces", "Saccharomyces"]
BINOMIAL = re.compile(r"[A-Z][a-z]+ [a-z]+|[A-Z]\. [a-z]+")
SKIP = {"i", "em", "script", "style", "code", "title", "option", "textarea", "select", "svg", "head"}
TOKEN = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)


def names_from(organisms) -> list:
    names = set(EXTRA)
    for o in organisms:
        o = (o or "").strip()
        if BINOMIAL.fullmatch(o):
            names.add(o)
            m = re.fullmatch(r"([A-Z])[a-z]+ ([a-z]+)", o)
            if m:
                names.add(f"{m.group(1)}. {m.group(2)}")
    return sorted(names, key=lambda s: (-len(s), s))


def _pattern(names):
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w])")


def italicize(html_text: str, names: list) -> str:
    pat = _pattern(names)
    out, stack = [], []
    for piece in TOKEN.split(html_text):
        if piece.startswith("<!--"):
            out.append(piece)
        elif piece.startswith("<"):
            m = re.match(r"</?\s*([a-zA-Z0-9]+)", piece)
            if m:
                tag = m.group(1).lower()
                if piece.startswith("</"):
                    if tag in stack:
                        while stack and stack.pop() != tag:
                            pass
                elif tag in SKIP and not piece.rstrip().endswith("/>"):
                    stack.append(tag)
            out.append(piece)
        else:
            out.append(piece if stack else pat.sub(lambda mm: f"<i>{mm.group(0)}</i>", piece))
    return "".join(out)

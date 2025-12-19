import re
from typing import Optional, Dict

import requests
from bs4 import BeautifulSoup


ATTR_TRANSLATIONS = {
    "Latein": "latin",
    "Typ": "type",
    "Flexionsart": "flexion_type",
    "Form": "form",
    "Deutsch": "german",
    "Geschlecht": "gender",
}


def _fetch_html(word: str) -> str:
    """Fetch the HTML page for a given Latin word, following the first-result redirect logic."""
    base_url = f"https://www.frag-caesar.de/lateinwoerterbuch/{word}-uebersetzung.html"
    resp = requests.get(base_url, timeout=10)
    resp.raise_for_status()
    text = resp.text

    # If there are multiple results, follow the "-1.html" link (like the Node version)
    marker = f'Ihr Suchwort <strong><span class="textmarker">{word}</span></strong> entspricht'
    if marker in text:
        redirect_url = f"https://www.frag-caesar.de/lateinwoerterbuch/{word}-uebersetzung-1.html"
        resp = requests.get(redirect_url, timeout=10)
        resp.raise_for_status()
        text = resp.text

    return text


def get_word_information(word: str) -> Optional[Dict[str, str]]:
    """
    Python port of FragCaesar's getWordInformation (Node version).
    Returns a dict like:
    {
      "latin": "appellantur",
      "type": "Verb",
      "flexion_type": "A-Konjugation",
      "form": "3. Person Plural Präsens Indikativ Passiv",
      "german": "sie werden genannt|sie werden angeredet|...",
      "gender": "...",
      ...
    }
    or None if nothing found.
    """
    html = _fetch_html(word)
    soup = BeautifulSoup(html, "html.parser")

    # Select all table rows in the responsive table (mirrors $('.table-responsive table tr'))
    table = soup.select_one(".table-responsive table")
    if not table:
        return None

    rows = table.find_all("tr")
    if not rows:
        return None

    # Build content dict like in JS:
    # content[i] = [ "cell1text|", "cell2text|", ... ]
    content = {}
    for i, tr in enumerate(rows, start=1):
        cells_texts = []
        for td in tr.find_all("td"):
            # Collect all text nodes in this cell and join them with '|'
            texts = []
            for child in td.descendants:
                if child.string and not isinstance(child, type(td)):
                    # strip but keep empty '|' separators
                    txt = child.string.strip()
                    if txt:
                        texts.append(txt)
            # Join with '|' and add trailing '|' to match original JS
            cell_content = "|".join(texts) + ("|" if texts else "")
            cells_texts.append(cell_content)
        content[i] = cells_texts

    if 1 not in content or not content[1]:
        return None

    result: Dict[str, str] = {}

    # This mirrors the JS logic:
    # - header row is content[1]
    # - data row is either content[3] (if exists) or content[2]
    for y, header_cell in enumerate(content[1]):
        # normalize header to map via ATTR_TRANSLATIONS
        header_key_raw = header_cell.replace("|", "")
        key_return_form = ATTR_TRANSLATIONS.get(header_key_raw, header_key_raw)

        # choose which row contains the actual values
        key_content = 3 if (3 in content and len(content[3]) > y) else 2
        if key_content not in content or len(content[key_content]) <= y:
            continue

        value_cell = content[key_content][y]
        # strip trailing '|'
        if value_cell.endswith("|"):
            value_cell = value_cell[:-1]

        result[key_return_form] = value_cell

    # add latin word
    result["latin"] = word

    # remove empty-key entry if present
    result.pop("", None)

    return result

# frag_caesar_bs4.py
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

ATTR_TRANSLATIONS = {
    "Latein": "latin",
    "Typ": "type",
    "Flexionsart": "flexion_type",
    "Form": "form",
    "Deutsch": "german",
}

def get_kurzuebersicht(word: str) -> List[Dict[str, str]]:
    url = f"https://www.frag-caesar.de/lateinwoerterbuch/{word}-uebersetzung.html"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # find the Kurzübersicht table
    headline = soup.find("h2", string=lambda s: s and "Kurz" in s)
    table = headline.find_next("table") if headline else None
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # header
    header_cells = rows[0].find_all(["th", "td"])
    header = [c.get_text(strip=True) for c in header_cells]

    result: List[Dict[str, str]] = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) != len(header):
            continue
        data: Dict[str, str] = {}
        for h, td in zip(header, cells):
            key = ATTR_TRANSLATIONS.get(h, h)
            # join <br> texts for Deutsch
            text = " ".join(t.strip() for t in td.stripped_strings)
            data[key] = text
        data["latin"] = word
        result.append(data)

    return result



"""
if __name__ == "__main__":
    rows = get_kurzuebersicht("currebas")
    for r in rows:
        print(r)

    rows = get_kurzuebersicht("audis")
    for r in rows:
        print(r)

"""
"""
Scrapes Latin word data from frag-caesar.de, focusing on the 'Kurzübersicht' summary table.
Provides lemma information like German meanings, word type, and flexion type.
"""

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
    """
    Fetches the 'Kurzübersicht' table data for a given Latin lemma from frag-caesar.de.

    Args:
        word (str): Latin lemma (e.g., 'petere', 'nox').

    Returns:
        List[Dict[str, str]]: Rows of table data with translated keys and 'latin' added.
        Empty list if no table found or insufficient rows.
    """
    url = f"https://www.frag-caesar.de/lateinwoerterbuch/{word}-uebersetzung.html"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Locate Kurzübersicht section
    headline = soup.find("h2", string=lambda s: s and "Kurz" in s)
    table = headline.find_next("table") if headline else None
    if not table:
        return []

    rows = table.find_all("tr")
    print(f"Found {len(rows)} rows for {word}")  # Debug: remove in production

    if len(rows) < 2:
        return []

    # Extract header from first row
    header_row = rows[0]
    header_cells = header_row.find_all(["th", "td"])
    header = [c.get_text(strip=True) for c in header_cells]
    expected_cols = len(header)
    print(f"Header: {header}")  # Debug

    result: List[Dict[str, str]] = []
    # Process data rows starting from index 1, skipping invalid rows
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) != expected_cols:
            continue  # Skip header-like, separator, or mismatched rows
        data: Dict[str, str] = {}
        for h, td in zip(header, cells):
            key = ATTR_TRANSLATIONS.get(h, h.lower().replace(" ", "_"))
            # Concatenate multi-line text (e.g., <br> separated)
            text = " ".join(t.strip() for t in td.stripped_strings)
            data[key] = text
        result.append(data)
        print(f"Extracted row: {data}")  # Debug

    print(f"Returned {len(result)} data rows")  # Debug
    return result


def get_german_meanings(word: str) -> list[str]:
    """
    Retrieves German translations for the lemma from the first Kurzübersicht row.

    Args:
        word (str): Latin lemma.

    Returns:
        list[str]: List with the primary German meaning (whole string).
        Empty list if unavailable.
    """
    rows = get_kurzuebersicht(word)
    if not rows:
        return []

    german = rows[0].get("german", "").strip()
    return [german] if german else []


def get_word_type(word: str) -> str:
    """
    Gets the word type (e.g., 'Nomen', 'Verbum') from the first Kurzübersicht row.

    Args:
        word (str): Latin lemma.

    Returns:
        str: Type value or empty string if unavailable.
    """
    rows = get_kurzuebersicht(word)
    return rows[0]["type"] if rows else ""


def get_flexion_type(word: str) -> str:
    """
    Gets the flexion type (e.g., 'A-Deklination') from the first Kurzübersicht row.

    Args:
        word (str): Latin lemma.

    Returns:
        str: Flexion type or empty string if unavailable.
    """
    rows = get_kurzuebersicht(word)
    return rows[0]["flexion_type"] if rows else ""


if __name__ == "__main__":
    print(get_german_meanings("petere"))
    print(get_flexion_type("petere"))
    print(get_word_type("petere"))
    print(get_flexion_type("templum"))
    print(get_kurzuebersicht("noctis"))

"""Kerää säädösasiakirjojen (HE = hallituksen esitys) otsikko ja pääasiallinen
sisältö VaskiData-taulusta, äänestysten aiheluokittelun rikastamiseksi.

HE-dokumentin XML (varmistettu):
  - SisaltoKuvaus / OtsikkoTeksti : otsikko
  - ensimmäiset KappaleKooste     : "Esityksessä ehdotetaan ..." = pääas. sisältö
Haemme vain alkukappaleet (ei koko säädöstekstiä) — riittää aiheen tunnistukseen.
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

from .. import config, db
from .eduskunta_client import EduskuntaClient
from .util import localname

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
MAX_SUMMARY_CHARS = 4000
SUMMARY_PARAGRAPHS = 8


def parse_legislation(xml: str) -> Tuple[Optional[str], str]:
    """Palauta (otsikko, tiivistelmä) HE-dokumentin XML:stä."""
    if not xml:
        return None, ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None, ""
    title = None
    for name in ("SisaltoKuvaus", "OtsikkoTeksti", "NimekeKooste", "AsiakirjaNimi"):
        for e in root.iter():
            if localname(e.tag) == name and e.text and e.text.strip():
                title = e.text.strip()
                break
        if title:
            break
    paras: List[str] = []
    for e in root.iter():
        if localname(e.tag) == "KappaleKooste" and e.text and e.text.strip():
            paras.append(e.text.strip())
            if len(paras) >= SUMMARY_PARAGRAPHS:
                break
    summary = " ".join(paras)[:MAX_SUMMARY_CHARS]
    return title, summary


def _doc_type(item: str) -> str:
    return item.split(None, 1)[0] if item else ""


def collect_legislation(conn, client: Optional[EduskuntaClient] = None,
                        item_types=("HE",), only_missing: bool = True) -> dict:
    """Kerää kaikkien äänestyksiin liittyvien säädöskohteiden tekstit."""
    client = client or EduskuntaClient()
    items = [r["legislative_item"] for r in conn.execute(
        "SELECT DISTINCT legislative_item FROM vote"
        " WHERE legislative_item IS NOT NULL AND legislative_item != ''")]
    have = set()
    if only_missing:
        have = {r["eduskunta_tunnus"] for r in conn.execute(
            "SELECT eduskunta_tunnus FROM legislation")}
    n = 0
    n_text = 0
    for item in items:
        if not any(item.startswith(t + " ") for t in item_types):
            continue
        if item in have:
            continue
        rows = client.filter_rows("VaskiData", "Eduskuntatunnus", item, per_page=20)
        best = None
        for r in rows:
            xd = r.get("XmlData")
            if xd and (best is None or len(xd) > len(best)):
                best = xd
        title, summary = parse_legislation(best or "")
        url = (f"https://www.eduskunta.fi/FI/vaski/HallituksenEsitys/Sivut/"
               f"{item.replace(' ', '_').replace('/', '+')}.aspx")
        conn.execute(
            "INSERT OR REPLACE INTO legislation(eduskunta_tunnus,doc_type,title,summary,url,fetched_at)"
            " VALUES(?,?,?,?,?,?)",
            (item, _doc_type(item), title, summary, url, NOW()))
        n += 1
        if title or summary:
            n_text += 1
        if n % 20 == 0:
            conn.commit()
    conn.commit()
    return {"items": n, "with_text": n_text}

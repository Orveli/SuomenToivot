"""Apufunktiot keruulle: XML-namespacen riisuminen, päivämäärät, puoluenormalisointi."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional


def localname(tag: str) -> str:
    return tag.split("}")[-1]


def strip_attrs(elem: ET.Element) -> dict:
    """Palauta elementin attribuutit ilman namespace-prefiksiä."""
    return {k.split("}")[-1]: v for k, v in elem.attrib.items()}


def findtext_local(elem: ET.Element, name: str) -> Optional[str]:
    """Etsi ensimmäinen lapsielementti paikallisnimellä (ohittaen namespacen)."""
    for c in elem.iter():
        if localname(c.tag) == name:
            return (c.text or "").strip() or None
    return None


_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def fi_date_to_iso(value: Optional[str]) -> Optional[str]:
    """'24.03.1995' -> '1995-03-24'. Palauttaa None jos ei täysi pp.kk.vvvv."""
    if not value:
        return None
    value = value.strip()
    m = _DATE_RE.match(value)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # ISO jo valmiina?
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    return None


_DIGITS_TAIL = re.compile(r"\d+$")


def normalize_party(code: Optional[str]) -> Optional[str]:
    """'sd01' -> 'sd', 'kok       ' -> 'kok'. Yhtenäistää ryhmätunnukset."""
    if not code:
        return None
    c = code.strip().lower()
    c = _DIGITS_TAIL.sub("", c)
    return c or None


def word_count(text: Optional[str]) -> int:
    if not text:
        return 0
    return len(re.findall(r"\S+", text))

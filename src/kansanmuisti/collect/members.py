"""Kerää kansanedustajat (MemberOfParliament) ja jäsentää biografia-XML:n.

Poimitut tiedot: nimi, nykyinen ryhmä, ministeriys, syntymävuosi, sukupuoli,
vaalipiiri, ammatti, edustajatoimien kaudet, ryhmäjäsenyydet (alku/loppu),
ministerikaudet. Kaikki MemberOfParliament-taulusta (HetekaData on tyhjä).
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from typing import List, Optional

from .. import config
from .eduskunta_client import EduskuntaClient
from .util import fi_date_to_iso, localname, normalize_party

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


def _first_child_text(elem: ET.Element, name: str) -> Optional[str]:
    for c in elem:
        if localname(c.tag) == name:
            return (c.text or "").strip() or None
    return None


def _find_first(elem: ET.Element, name: str) -> Optional[ET.Element]:
    for c in elem.iter():
        if localname(c.tag) == name:
            return c
    return None


def parse_member_xml(person_id: int, xml: str) -> dict:
    """Jäsennä Henkilo-XML rakenteiseksi dictiksi."""
    out: dict = {
        "person_id": person_id,
        "birth_year": None, "gender": None, "profession": None,
        "electoral_district": None, "party_current": None, "party_current_name": None,
        "terms": [], "parties": [], "minister_roles": [],
    }
    if not xml:
        return out
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out

    out["birth_year"] = _find_first_text(root, "SyntymaPvm")
    out["gender"] = _find_first_text(root, "SukuPuoliKoodi")
    out["profession"] = _find_first_text(root, "Ammatti")

    # Vaalipiiri: nykyinen, muuten viimeisin edellinen
    cur_vp = _find_first(root, "NykyinenVaalipiiri")
    if cur_vp is not None and _first_child_text(cur_vp, "Nimi"):
        out["electoral_district"] = _first_child_text(cur_vp, "Nimi")
    else:
        prev = root.iter()
        last_name = None
        for vp in root.iter():
            if localname(vp.tag) == "VaaliPiiri":
                nm = _first_child_text(vp, "Nimi")
                if nm:
                    last_name = nm
        out["electoral_district"] = last_name

    # Edustajatoimet (kaudet)
    for tag in root.iter():
        if localname(tag.tag) == "Edustajatoimi":
            a = fi_date_to_iso(_first_child_text(tag, "AlkuPvm"))
            l = fi_date_to_iso(_first_child_text(tag, "LoppuPvm"))
            if a or l:
                out["terms"].append({"start": a, "end": l})

    # Ryhmäjäsenyydet
    nyk = _find_first(root, "NykyinenEduskuntaryhma")
    if nyk is not None:
        code = _first_child_text(nyk, "Tunnus")
        name = _first_child_text(nyk, "Nimi")
        start = fi_date_to_iso(_first_child_text(nyk, "AlkuPvm"))
        if code or name:
            out["parties"].append({"code": normalize_party(code), "name": name,
                                    "start": start, "end": None})
            out["party_current"] = normalize_party(code)
            out["party_current_name"] = name
    # Edelliset ryhmät: kukin Eduskuntaryhma voi sisältää useita Jasenyys-jaksoja
    for er in root.iter():
        if localname(er.tag) != "Eduskuntaryhma":
            continue
        code = _first_child_text(er, "Tunnus")
        name = _first_child_text(er, "Nimi")
        if not (code or name):
            continue
        had_jasenyys = False
        for j in er:
            if localname(j.tag) == "Jasenyys":
                had_jasenyys = True
                out["parties"].append({
                    "code": normalize_party(code), "name": name,
                    "start": fi_date_to_iso(_first_child_text(j, "AlkuPvm")),
                    "end": fi_date_to_iso(_first_child_text(j, "LoppuPvm")),
                })
        if not had_jasenyys:
            out["parties"].append({"code": normalize_party(code), "name": name,
                                   "start": None, "end": None})

    # jos nykyinen ryhmä puuttui, päättele viimeisimmästä jäsenyydestä
    if not out["party_current"] and out["parties"]:
        ranked = sorted(out["parties"], key=lambda p: (p["end"] or "9999", p["start"] or ""))
        out["party_current"] = ranked[-1]["code"]
        out["party_current_name"] = ranked[-1]["name"]

    # Ministerikaudet
    for jm in root.iter():
        if localname(jm.tag) == "Jasenyys" and jm.find("./") is not None:
            pass
    vnj = _find_first(root, "ValtioneuvostonJasenyydet")
    if vnj is not None:
        for j in vnj:
            if localname(j.tag) != "Jasenyys":
                continue
            title = _first_child_text(j, "Nimi") or _first_child_text(j, "Ministeriys")
            gov = _first_child_text(j, "Hallitus")
            a = fi_date_to_iso(_first_child_text(j, "AlkuPvm"))
            l = fi_date_to_iso(_first_child_text(j, "LoppuPvm"))
            if title or gov:
                out["minister_roles"].append({"title": title, "government": gov,
                                              "start": a, "end": l})
    return out


def _find_first_text(root: ET.Element, name: str) -> Optional[str]:
    el = _find_first(root, name)
    return (el.text or "").strip() if el is not None and el.text else None


def _person_active_in_range(member: dict, start_year: int, end_year: int) -> bool:
    """Onko edustajalla kausi, joka osuu [start_year, end_year]?"""
    if not member["terms"]:
        return True  # epävarmoissa tapauksissa pidetään mukana, merkitään myöhemmin
    for t in member["terms"]:
        s = int(t["start"][:4]) if t["start"] else 1900
        e = int(t["end"][:4]) if t["end"] else 2999
        if e >= start_year and s <= end_year:
            return True
    return False


def collect_members(conn, client: Optional[EduskuntaClient] = None,
                    start_year: int = config.DEFAULT_START_YEAR,
                    end_year: int = config.DEFAULT_END_YEAR,
                    only_active_in_range: bool = True) -> int:
    """Kerää kaikki edustajat ja tallenna ne, jotka olivat aktiivisia annetulla välillä."""
    client = client or EduskuntaClient()
    n = 0
    base_url = f"{config.API_BASE}/tables/MemberOfParliament/rows"
    for row in client.iter_table("MemberOfParliament", per_page=100):
        pid = int(row["personId"])
        xml = row.get("XmlDataFi") or row.get("XmlData") or ""
        member = parse_member_xml(pid, xml)
        if only_active_in_range and not _person_active_in_range(member, start_year, end_year):
            continue
        first = (row.get("firstname") or "").strip()
        last = (row.get("lastname") or "").strip()
        terms = member["terms"]
        active_from = min((t["start"] for t in terms if t["start"]), default=None)
        active_to_vals = [t["end"] for t in terms]
        active_to = None if any(v is None for v in active_to_vals) else (
            max((v for v in active_to_vals if v), default=None))
        is_minister = 1 if (str(row.get("minister", "")).lower() in ("t", "true", "1")
                            or member["minister_roles"]) else 0
        conn.execute(
            "INSERT OR REPLACE INTO person(person_id,last_name,first_name,full_name,"
            "party_current,party_current_name,is_minister,birth_year,gender,"
            "electoral_district,profession,active_from,active_to,source_url,fetched_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, last, first, f"{first} {last}".strip(),
             member["party_current"], member["party_current_name"], is_minister,
             member["birth_year"], member["gender"], member["electoral_district"],
             member["profession"], active_from, active_to,
             f"{base_url}?columnName=personId&columnValue={pid}", NOW()),
        )
        conn.execute("DELETE FROM person_party WHERE person_id=?", (pid,))
        conn.execute("DELETE FROM person_term WHERE person_id=?", (pid,))
        conn.execute("DELETE FROM person_minister_role WHERE person_id=?", (pid,))
        for p in member["parties"]:
            conn.execute(
                "INSERT INTO person_party(person_id,group_code,group_name,start_date,end_date)"
                " VALUES(?,?,?,?,?)", (pid, p["code"], p["name"], p["start"], p["end"]))
        for t in terms:
            conn.execute(
                "INSERT INTO person_term(person_id,start_date,end_date) VALUES(?,?,?)",
                (pid, t["start"], t["end"]))
        for r in member["minister_roles"]:
            conn.execute(
                "INSERT INTO person_minister_role(person_id,title,government,start_date,end_date)"
                " VALUES(?,?,?,?,?)", (pid, r["title"], r["government"], r["start"], r["end"]))
        n += 1
        if n % 50 == 0:
            conn.commit()
    conn.commit()
    return n

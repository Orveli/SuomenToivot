"""Kerää täysistuntopuheet PTK-dokumenteista (VaskiData).

Tärkeä havainto: SaliDBPuheenvuoro.XmlData on tyhjä — se on vain metahakemisto.
Varsinainen puheteksti on VaskiData-taulun PTK-pöytäkirjojen XML:ssä.

PTK-rakenne (varmistettu):
  Poytakirja(eduskuntaTunnus='PTK 50/2024 vp')
    -> Asiakohta(eduskuntaTunnus='HE .../SKT ...')
       -> ... -> PuheenvuoroToimenpide(puheenvuoroLuokitusKoodi, puheenvuoroAloitusHetki)
            -> Toimija -> Henkilo(@muuTunnus = personId)       (puhuja)
            -> PuheenvuoroOsa(@muuTunnus = puheen tunniste)
                 -> KohtaSisalto -> KappaleKooste (tekstikappaleet)
       Puhemiehen välihuudot ovat PuheenjohtajaRepliikki-elementeissä -> rajataan pois.
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from .. import config, db
from .eduskunta_client import EduskuntaClient
from .util import localname, strip_attrs, word_count

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731

META_NS = "{http://www.vn.fi/skeemat/metatietoelementit/2010/04/27}"
VASKI_NS = "{http://www.eduskunta.fi/skeemat/vaskielementit/2011/01/04}"


def _attr_local(elem: ET.Element, name: str) -> Optional[str]:
    for k, v in elem.attrib.items():
        if k.split("}")[-1] == name:
            return v
    return None


def parse_ptk(xml: str, ptk_id: str, session_key: str) -> List[Dict]:
    """Jäsennä yhden PTK-dokumentin puheet listaksi dictejä."""
    speeches: List[Dict] = []
    if not xml:
        return speeches
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return speeches
    parents = {c: p for p in root.iter() for c in p}

    def ancestor(elem, tag):
        cur = parents.get(elem)
        while cur is not None:
            if localname(cur.tag) == tag:
                return cur
            cur = parents.get(cur)
        return None

    def speech_text(pvosa: ET.Element) -> str:
        parts = []
        for kk in pvosa.iter():
            if localname(kk.tag) != "KappaleKooste":
                continue
            # ohita puhemiehen repliikkien sisällä olevat kappaleet
            skip = False
            anc = parents.get(kk)
            while anc is not None and anc is not pvosa:
                if localname(anc.tag) == "PuheenjohtajaRepliikki":
                    skip = True
                    break
                anc = parents.get(anc)
            if not skip and (kk.text and kk.text.strip()):
                parts.append(kk.text.strip())
        return "\n\n".join(parts)

    for tp in root.iter():
        if localname(tp.tag) != "PuheenvuoroToimenpide":
            continue
        # puhuja
        toimija = next((c for c in tp if localname(c.tag) == "Toimija"), None)
        person_id = None
        if toimija is not None:
            for h in toimija.iter():
                if localname(h.tag) == "Henkilo":
                    person_id = _attr_local(h, "muuTunnus")
                    break
        pvosa = next((c for c in tp if localname(c.tag) == "PuheenvuoroOsa"), None)
        if pvosa is None:
            continue
        text = speech_text(pvosa)
        if not text:
            continue
        asia = ancestor(tp, "Asiakohta")
        item = strip_attrs(asia).get("eduskuntaTunnus") if asia is not None else None
        ext_key = _attr_local(pvosa, "muuTunnus") or f"{ptk_id}#{tp.attrib.get(VASKI_NS+'puheenvuoroJNro')}"
        speeches.append({
            "external_key": ext_key,
            "person_id": int(person_id) if person_id and person_id.isdigit() else None,
            "speech_type": _attr_local(tp, "puheenvuoroLuokitusKoodi"),
            "started_at": _attr_local(tp, "puheenvuoroAloitusHetki"),
            "legislative_item": item,
            "session_key": session_key,
            "ptk_id": ptk_id,
            "text": text,
            "word_count": word_count(text),
        })
    return speeches


def _fetch_ptk_xml(client: EduskuntaClient, ptk_id: str) -> Optional[str]:
    """Hae PTK-dokumentin laajin (täysi) XML VaskiDatasta."""
    rows = client.filter_rows("VaskiData", "Eduskuntatunnus", ptk_id, per_page=20)
    best = None
    for r in rows:
        xd = r.get("XmlData")
        if xd and (best is None or len(xd) > len(best)):
            best = xd
    return best


def _person_lookup(conn) -> Dict[int, Dict]:
    out = {}
    for r in conn.execute("SELECT person_id,first_name,last_name,party_current FROM person"):
        out[r["person_id"]] = dict(r)
    return out


def store_speeches(conn, speeches: List[Dict], persons: Dict[int, Dict]) -> int:
    n = 0
    for s in speeches:
        p = persons.get(s["person_id"]) if s["person_id"] else None
        ptk_num = s["ptk_id"].split()[1].split("/")[0] if "/" in s["ptk_id"] else ""
        url = (f"https://www.eduskunta.fi/FI/vaski/Poytakirja/Sivut/"
               f"{s['ptk_id'].replace(' ', '_').replace('/', '+')}.aspx")
        cur = conn.execute(
            "INSERT OR IGNORE INTO speech(external_key,person_id,first_name,last_name,party,"
            "session_key,ptk_id,speech_type,started_at,legislative_item,text,word_count,url,fetched_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s["external_key"], s["person_id"],
             p["first_name"] if p else None, p["last_name"] if p else None,
             p["party_current"] if p else None,
             s["session_key"], s["ptk_id"], s["speech_type"], s["started_at"],
             s["legislative_item"], s["text"], s["word_count"], url, NOW()),
        )
        if cur.rowcount:
            sid = cur.lastrowid
            conn.execute("INSERT INTO speech_fts(rowid,text) VALUES(?,?)", (sid, s["text"]))
            n += 1
    return n


def collect_speeches_for_year(conn, year: int, client: Optional[EduskuntaClient] = None,
                              max_session: int = 200, miss_stop: int = 20,
                              limit_sessions: Optional[int] = None) -> dict:
    """Kerää vuoden täysistuntopuheet iteroimalla PTK 1..N / year.

    Lopettaa kun peräkkäisiä löytymättömiä istuntoja on miss_stop kpl.
    """
    client = client or EduskuntaClient()
    persons = _person_lookup(conn)
    job = f"speeches:{year}"
    db.set_ingest_state(conn, job, status="running")
    n_speeches = 0
    n_sessions = 0
    consecutive_miss = 0
    for num in range(1, max_session + 1):
        ptk_id = f"PTK {num}/{year} vp"
        xml = _fetch_ptk_xml(client, ptk_id)
        if not xml:
            consecutive_miss += 1
            if consecutive_miss >= miss_stop:
                break
            continue
        consecutive_miss = 0
        speeches = parse_ptk(xml, ptk_id, f"{year}/{num}")
        n_speeches += store_speeches(conn, speeches, persons)
        n_sessions += 1
        conn.commit()
        db.set_ingest_state(conn, job, last_pk=str(num), n_items=n_speeches)
        if limit_sessions and n_sessions >= limit_sessions:
            break
    db.set_ingest_state(conn, job, status="done", n_items=n_speeches,
                        note=f"{n_sessions} istuntoa")
    return {"speeches": n_speeches, "sessions": n_sessions, "year": year}

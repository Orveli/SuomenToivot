"""Kerää täysistuntoäänestykset ja edustajakohtaiset äänet.

SaliDBAanestys on kahdennettu kielittäin (KieliId 1=fi, 2=sv) -> pidetään fi.
Mitätöidyt äänestykset (AanestysMitatoity != 0) ohitetaan.
Edustajakohtaiset äänet: SaliDBAanestysEdustaja, suodatus AanestysId:llä.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from .. import config, db
from .eduskunta_client import EduskuntaClient

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731

# Menettelyäänestysten heuristiikka (METHODOLOGY.md, PROCEDURAL_SUSPECT)
_PROCEDURAL_HINTS = (
    "päiväjärjestykseen siirtyminen", "työjärjestys", "asian palauttaminen",
    "pöydällepano", "pöydälle panemisesta", "lähetekeskustelu",
)


def _is_procedural(*titles: Optional[str]) -> int:
    blob = " ".join(t.lower() for t in titles if t)
    return 1 if any(h in blob for h in _PROCEDURAL_HINTS) else 0


def _normalize_vote_value(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = raw.strip()
    mapping = {"Jaa": "Jaa", "Ei": "Ei", "Tyhjää": "Tyhjää",
               "Tyhjiä": "Tyhjää", "Poissa": "Poissa"}
    return mapping.get(v, v)


def _to_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def collect_vote_records(conn, client: EduskuntaClient, vote_id: int) -> int:
    """Hae yhden äänestyksen edustajakohtaiset äänet."""
    conn.execute("DELETE FROM vote_record WHERE vote_id=?", (vote_id,))
    n = 0
    for row in client.iter_table("SaliDBAanestysEdustaja", per_page=100,
                                 column="AanestysId", value=str(vote_id)):
        pid = _to_int(row.get("EdustajaHenkiloNumero"))
        conn.execute(
            "INSERT OR IGNORE INTO vote_record(vote_id,person_id,first_name,last_name,party,vote_value)"
            " VALUES(?,?,?,?,?,?)",
            (vote_id, pid,
             (row.get("EdustajaEtunimi") or "").strip(),
             (row.get("EdustajaSukunimi") or "").strip(),
             (row.get("EdustajaRyhmaLyhenne") or "").strip().lower() or None,
             _normalize_vote_value(row.get("EdustajaAanestys"))),
        )
        n += 1
    return n


def collect_votes_for_year(conn, year: int, client: Optional[EduskuntaClient] = None,
                           with_records: bool = True, limit: Optional[int] = None) -> dict:
    """Kerää yhden valtiopäivävuoden äänestykset (+ edustajaäänet)."""
    client = client or EduskuntaClient()
    job = f"votes:{year}"
    db.set_ingest_state(conn, job, status="running")
    n_votes = 0
    n_records = 0
    seen_ids = set()
    for row in client.iter_table("SaliDBAanestys", per_page=100,
                                 column="IstuntoVPVuosi", value=str(year)):
        if str(row.get("KieliId")) != "1":
            continue
        if str(row.get("AanestysMitatoity", "0")) not in ("0", "", "None", None):
            continue
        vote_id = _to_int(row.get("AanestysId"))
        if vote_id is None or vote_id in seen_ids:
            continue
        seen_ids.add(vote_id)
        proc = _is_procedural(row.get("AanestysOtsikko"), row.get("KohtaOtsikko"),
                              row.get("PJOtsikko"), row.get("KohtaKasittelyOtsikko"))
        conn.execute(
            "INSERT OR REPLACE INTO vote(vote_id,vp_year,session_number,session_date,"
            "title,extra_title,main_item_title,item_title,treatment_title,treatment_stage,"
            "legislative_item,legislative_item_url,result_yes,result_no,result_empty,"
            "result_absent,result_total,minutes_url,url,is_procedural,fetched_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vote_id, _to_int(row.get("IstuntoVPVuosi")), _to_int(row.get("IstuntoNumero")),
             row.get("IstuntoPvm"), row.get("AanestysOtsikko"), row.get("AanestysLisaOtsikko"),
             row.get("PaaKohtaOtsikko"), row.get("KohtaOtsikko"),
             row.get("KohtaKasittelyOtsikko"), row.get("KohtaKasittelyVaihe"),
             row.get("AanestysValtiopaivaasia"), row.get("AanestysValtiopaivaasiaUrl"),
             _to_int(row.get("AanestysTulosJaa")), _to_int(row.get("AanestysTulosEi")),
             _to_int(row.get("AanestysTulosTyhjia")), _to_int(row.get("AanestysTulosPoissa")),
             _to_int(row.get("AanestysTulosYhteensa")),
             row.get("AanestysPoytakirjaUrl"), row.get("Url"), proc, NOW()),
        )
        n_votes += 1
        if with_records:
            n_records += collect_vote_records(conn, client, vote_id)
        if n_votes % 25 == 0:
            conn.commit()
            db.set_ingest_state(conn, job, last_pk=str(vote_id), n_items=n_votes)
        if limit and n_votes >= limit:
            break
    conn.commit()
    db.set_ingest_state(conn, job, status="done", n_items=n_votes,
                        note=f"{n_records} edustajaääntä")
    return {"votes": n_votes, "records": n_records, "year": year}

"""Pytest-fixturet: deterministinen testitietokanta ilman verkkoa.

Asetetaan KANSANMUISTI_DB ennen kansanmuisti-importteja, jotta sekä keruu,
analyysi että web käyttävät samaa eristettyä tiedostoa.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="kansanmuisti-test-")
os.environ["KANSANMUISTI_DATA"] = _TMP
os.environ["KANSANMUISTI_DB"] = os.path.join(_TMP, "test.sqlite3")

import datetime as dt  # noqa: E402

import pytest  # noqa: E402

from kansanmuisti import db  # noqa: E402
from kansanmuisti.analyze.pipeline import run_all  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def _seed(conn):
    # --- henkilöt ---
    persons = [
        # (id, last, first, party)
        (1, "Aalto", "Anna", "kok"),
        (2, "Berg", "Bo", "kok"),
        (3, "Citron", "Cecilia", "kok"),
        (4, "Dahl", "Dan", "sd"),
        (5, "Eskola", "Eero", "sd"),
    ]
    for pid, last, first, party in persons:
        conn.execute(
            "INSERT INTO person(person_id,last_name,first_name,full_name,party_current,"
            "party_current_name,is_minister,source_url,fetched_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, last, first, f"{first} {last}", party, party.upper(), 0,
             "http://example/source", NOW))

    # --- äänestykset (saman säädöskohteen kannanmuutos henkilölle 3) ---
    votes = [
        # (id, year, date, title, item)
        (100, 2024, "2024-03-01 12:00:00", "Terveydenhuollon rahoitus, hoitotakuu", "HE 1/2024 vp"),
        (101, 2024, "2024-04-01 12:00:00", "Verotuksen muutos, tulovero", "HE 2/2024 vp"),
        (102, 2024, "2024-05-01 12:00:00", "Terveydenhuollon rahoitus, hoitotakuu jatko", "HE 1/2024 vp"),
    ]
    for vid, yr, d, title, item in votes:
        conn.execute(
            "INSERT INTO vote(vote_id,vp_year,session_date,title,legislative_item,"
            "result_yes,result_no,result_empty,result_absent,result_total,url,fetched_at,is_procedural)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (vid, yr, d, title, item, 3, 2, 0, 0, 5, "http://example/vote", NOW))

    # --- edustajakohtaiset äänet ---
    # vote 100: kok enemmistö Jaa (1,2 Jaa, 3 Ei => 3 poikkeaa); sd Ei (4,5 Ei)
    # vote 101: kok kaikki Jaa; sd kaikki Ei
    # vote 102: kok 1,2 Jaa, 3 Jaa (3 muutti Ei->Jaa samalla säädöksellä); sd Ei
    records = [
        (100, 1, "kok", "Jaa"), (100, 2, "kok", "Jaa"), (100, 3, "kok", "Ei"),
        (100, 4, "sd", "Ei"), (100, 5, "sd", "Ei"),
        (101, 1, "kok", "Jaa"), (101, 2, "kok", "Jaa"), (101, 3, "kok", "Jaa"),
        (101, 4, "sd", "Ei"), (101, 5, "sd", "Poissa"),
        (102, 1, "kok", "Jaa"), (102, 2, "kok", "Jaa"), (102, 3, "kok", "Jaa"),
        (102, 4, "sd", "Ei"), (102, 5, "sd", "Ei"),
    ]
    for vid, pid, party, val in records:
        p = next(x for x in persons if x[0] == pid)
        conn.execute(
            "INSERT INTO vote_record(vote_id,person_id,first_name,last_name,party,vote_value)"
            " VALUES(?,?,?,?,?,?)", (vid, pid, p[2], p[1], party, val))

    # --- puheet (henkilö 1 puhuu terveydenhuollosta lähellä äänestystä 100) ---
    speeches = [
        # (ext, pid, party, session, ptk, type, started, item, text)
        ("s1", 1, "kok", "2024/10", "PTK 10/2024 vp", "T", "2024-02-25T10:00:00", "HE 1/2024 vp",
         "Arvoisa puhemies! Terveydenhuollon rahoitus ja hoitotakuu ovat tärkeitä. "
         "Sairaalat ja terveysasemat tarvitsevat lääkäreitä ja hoitajia."),
        ("s2", 1, "kok", "2024/12", "PTK 12/2024 vp", "V", "2024-03-28T10:00:00", "HE 2/2024 vp",
         "Verotus ja tulovero ovat keskiössä. Veroaste ja yhteisövero vaikuttavat talouteen."),
        ("s3", 4, "sd", "2024/10", "PTK 10/2024 vp", "T", "2024-02-26T10:00:00", "HE 1/2024 vp",
         "Puhemies! Terveydenhuolto ja hoitotakuu on turvattava. Potilaat tarvitsevat hoitoa."),
    ]
    for ext, pid, party, sk, ptk, typ, st, item, text in speeches:
        p = next(x for x in persons if x[0] == pid)
        wc = len(text.split())
        cur = conn.execute(
            "INSERT INTO speech(external_key,person_id,first_name,last_name,party,session_key,"
            "ptk_id,speech_type,started_at,legislative_item,text,word_count,url,fetched_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ext, pid, p[2], p[1], party, sk, ptk, typ, st, item, text, wc,
             "http://example/ptk", NOW))
        conn.execute("INSERT INTO speech_fts(rowid,text) VALUES(?,?)", (cur.lastrowid, text))

    # --- lupaus + kytkentä ---
    conn.execute(
        "INSERT INTO promise(id,scope,party_code,topic_slug,text,source_title,source_url,"
        "source_year,curated_by,curated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (1, "party", "kok", "terveydenhuolto", "Turvaamme hoitotakuun rahoituksen.",
         "Testiohjelma", "http://example/ohjelma", 2023, "test", NOW))
    conn.execute(
        "INSERT INTO promise_vote_map(id,promise_id,vote_id,expected_value,rationale,curated_by,"
        "mapping_version) VALUES(?,?,?,?,?,?,?)",
        (1, 1, 100, "Jaa", "Äänestys koskee hoitotakuun rahoitusta.", "test", "1"))
    conn.commit()


@pytest.fixture(scope="session")
def seeded_db():
    with db.session() as conn:
        # tyhjennä mahdollinen aiempi tila
        for t in ["person", "vote", "vote_record", "speech", "promise", "promise_vote_map",
                  "speech_fts"]:
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        conn.commit()
        _seed(conn)
        run_all(conn, period="testi")
    return os.environ["KANSANMUISTI_DB"]


@pytest.fixture
def conn(seeded_db):
    c = db.connect()
    yield c
    c.close()


@pytest.fixture
def client(seeded_db):
    from fastapi.testclient import TestClient
    from kansanmuisti.web.app import app
    return TestClient(app)

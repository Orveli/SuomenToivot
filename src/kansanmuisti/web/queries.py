"""Tietokantakyselyt verkkokäyttöliittymälle. Vain luku (paitsi korjauskanava)."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from .. import db
from ..analyze.taxonomy import TOPIC_IDS


def _rows(conn, q, *p):
    return [dict(r) for r in conn.execute(q, p).fetchall()]


def _one(conn, q, *p):
    r = conn.execute(q, p).fetchone()
    return dict(r) if r else None


# --- yleiskatsaus -----------------------------------------------------------
def overview(conn) -> dict:
    s = lambda q: conn.execute(q).fetchone()[0]  # noqa: E731
    return {
        "persons": s("SELECT COUNT(*) FROM person"),
        "votes": s("SELECT COUNT(*) FROM vote"),
        "vote_records": s("SELECT COUNT(*) FROM vote_record"),
        "speeches": s("SELECT COUNT(*) FROM speech"),
        "promises": s("SELECT COUNT(*) FROM promise"),
        "years_votes": _rows(conn, "SELECT vp_year, COUNT(*) c FROM vote GROUP BY vp_year ORDER BY vp_year"),
    }


# --- haku -------------------------------------------------------------------
def search(conn, q: str) -> dict:
    q = (q or "").strip()
    if not q:
        return {"persons": [], "speeches": [], "votes": []}
    like = f"%{q}%"
    persons = _rows(conn,
        "SELECT person_id, full_name, party_current, electoral_district FROM person"
        " WHERE full_name LIKE ? ORDER BY full_name LIMIT 30", like)
    votes = _rows(conn,
        "SELECT vote_id, session_date, title, legislative_item FROM vote"
        " WHERE title LIKE ? OR legislative_item LIKE ? OR item_title LIKE ?"
        " ORDER BY session_date DESC LIMIT 30", like, like, like)
    # FTS puheille
    speeches = []
    try:
        speeches = _rows(conn,
            "SELECT s.id, s.full_name AS who, s.last_name, s.first_name, s.party, s.ptk_id,"
            " s.started_at, snippet(speech_fts,0,'<mark>','</mark>','…',12) AS snip"
            " FROM speech_fts JOIN speech s ON s.id=speech_fts.rowid"
            " WHERE speech_fts MATCH ? ORDER BY rank LIMIT 30", _fts_query(q))
    except Exception:
        speeches = _rows(conn,
            "SELECT id, first_name, last_name, party, ptk_id, started_at,"
            " substr(text,1,160) AS snip FROM speech WHERE text LIKE ? LIMIT 30", like)
    return {"persons": persons, "speeches": speeches, "votes": votes, "q": q}


def _fts_query(q: str) -> str:
    # turvallinen FTS5-kysely: lainausmerkitään tokenit
    tokens = [t for t in q.replace('"', " ").split() if t]
    return " ".join(f'"{t}"' for t in tokens) if tokens else '""'


# --- edustaja ---------------------------------------------------------------
def person(conn, pid: int) -> Optional[dict]:
    return _one(conn, "SELECT * FROM person WHERE person_id=?", pid)


def person_party_history(conn, pid: int) -> List[dict]:
    return _rows(conn, "SELECT group_code, group_name, start_date, end_date FROM person_party"
                 " WHERE person_id=? ORDER BY COALESCE(start_date,'')", pid)


def person_terms(conn, pid: int) -> List[dict]:
    return _rows(conn, "SELECT start_date, end_date FROM person_term WHERE person_id=?"
                 " ORDER BY COALESCE(start_date,'')", pid)


def person_minister_roles(conn, pid: int) -> List[dict]:
    return _rows(conn, "SELECT title, government, start_date, end_date FROM person_minister_role"
                 " WHERE person_id=? ORDER BY COALESCE(start_date,'')", pid)


def person_summary(conn, pid: int) -> Optional[dict]:
    return _one(conn, "SELECT * FROM analysis_member_summary WHERE person_id=?", pid)


def person_topic_activity(conn, pid: int) -> List[dict]:
    return _rows(conn,
        "SELECT t.slug, t.label, amt.n_speeches, amt.n_votes FROM analysis_member_topic amt"
        " JOIN topic t ON t.id=amt.topic_id WHERE amt.person_id=?"
        " AND (amt.n_speeches>0 OR amt.n_votes>0) ORDER BY (amt.n_speeches+amt.n_votes) DESC", pid)


def person_vote_behavior(conn, pid: int) -> dict:
    dist = _rows(conn, "SELECT vote_value, COUNT(*) c FROM vote_record WHERE person_id=?"
                 " GROUP BY vote_value", pid)
    return {"distribution": {r["vote_value"]: r["c"] for r in dist}}


def person_deviations(conn, pid: int, limit: int = 25) -> List[dict]:
    return _rows(conn,
        "SELECT d.vote_id, d.party, d.member_value, d.party_line, v.session_date, v.title,"
        " v.legislative_item FROM analysis_party_deviation d JOIN vote v ON v.vote_id=d.vote_id"
        " WHERE d.person_id=? AND d.classification='deviates'"
        " ORDER BY v.session_date DESC LIMIT ?", pid, limit)


def person_speeches(conn, pid: int, limit: int = 20) -> List[dict]:
    return _rows(conn,
        "SELECT id, ptk_id, speech_type, started_at, legislative_item, word_count,"
        " substr(text,1,200) AS preview FROM speech WHERE person_id=?"
        " ORDER BY started_at DESC LIMIT ?", pid, limit)


def person_position_changes(conn, pid: int) -> List[dict]:
    return _rows(conn,
        "SELECT pc.item_base, pc.from_value, pc.from_date, pc.to_value, pc.to_date,"
        " pc.gap_days, t.label AS topic FROM analysis_position_change pc"
        " LEFT JOIN topic t ON t.id=pc.topic_id WHERE pc.person_id=?"
        " ORDER BY pc.to_date DESC", pid)


def person_recent_votes(conn, pid: int, limit: int = 20) -> List[dict]:
    return _rows(conn,
        "SELECT vr.vote_id, vr.vote_value, v.session_date, v.title, v.legislative_item,"
        " d.party_line, d.classification FROM vote_record vr JOIN vote v ON v.vote_id=vr.vote_id"
        " LEFT JOIN analysis_party_deviation d ON d.vote_id=vr.vote_id AND d.person_id=vr.person_id"
        " WHERE vr.person_id=? ORDER BY v.session_date DESC LIMIT ?", pid, limit)


# --- lupaukset --------------------------------------------------------------
def all_promises(conn) -> List[dict]:
    return _rows(conn, "SELECT * FROM promise ORDER BY party_code, id")


def promise_mappings(conn, promise_id: int) -> List[dict]:
    return _rows(conn,
        "SELECT m.*, v.title, v.session_date, v.legislative_item FROM promise_vote_map m"
        " JOIN vote v ON v.vote_id=m.vote_id WHERE m.promise_id=?", promise_id)


def person_promise_alignment(conn, pid: int) -> List[dict]:
    """Laske kuratoitujen lupausten linjaus edustajalle lennossa (METHODOLOGY §3.3)."""
    person_row = person(conn, pid)
    party = person_row["party_current"] if person_row else None
    out = []
    for pr in _rows(conn, "SELECT * FROM promise"):
        # vain puolueen lupaukset tälle edustajalle (tai henkilökohtaiset)
        if pr["scope"] == "party" and pr["party_code"] and party and pr["party_code"] != party:
            continue
        if pr["scope"] == "person" and pr["person_id"] and pr["person_id"] != pid:
            continue
        maps = _rows(conn,
            "SELECT m.vote_id, m.expected_value, m.rationale, v.title, v.session_date,"
            " v.legislative_item FROM promise_vote_map m JOIN vote v ON v.vote_id=m.vote_id"
            " WHERE m.promise_id=?", pr["id"])
        details = []
        s = c = u = 0
        for m in maps:
            vr = _one(conn, "SELECT vote_value FROM vote_record WHERE vote_id=? AND person_id=?",
                      m["vote_id"], pid)
            val = vr["vote_value"] if vr else None
            if val in (None, "Poissa", "Tyhjää"):
                per = "epäselvä"; u += 1
            elif val == m["expected_value"]:
                per = "tukee"; s += 1
            else:
                per = "ristiriidassa"; c += 1
            details.append({**m, "member_value": val, "per_vote": per})
        if not maps:
            alignment = "ei kartoitettu"
        elif s + c == 0:
            alignment = "epäselvä"
        elif c == 0:
            alignment = "tukee"
        elif s == 0:
            alignment = "ristiriidassa"
        else:
            alignment = "epäselvä (ristiriitainen)"
        out.append({"promise": pr, "details": details, "alignment": alignment,
                    "n_support": s, "n_conflict": c, "n_unclear": u,
                    "unmapped": not maps})
    return out


# --- puolue -----------------------------------------------------------------
def party_members(conn, code: str) -> List[dict]:
    return _rows(conn,
        "SELECT p.person_id, p.full_name, p.electoral_district, s.consistency_index,"
        " s.deviation_rate, s.confidence_level FROM person p"
        " LEFT JOIN analysis_member_summary s ON s.person_id=p.person_id"
        " WHERE p.party_current=? ORDER BY p.full_name", code)


def party_overview(conn, code: str) -> dict:
    agg = _one(conn,
        "SELECT COUNT(*) n, AVG(s.consistency_index) avg_idx, AVG(s.deviation_rate) avg_dev"
        " FROM person p LEFT JOIN analysis_member_summary s ON s.person_id=p.person_id"
        " WHERE p.party_current=?", code)
    name = _one(conn, "SELECT party_current_name FROM person WHERE party_current=?"
                " AND party_current_name IS NOT NULL LIMIT 1", code)
    return {"code": code, "name": name["party_current_name"] if name else code, **(agg or {})}


def parties(conn) -> List[dict]:
    return _rows(conn,
        "SELECT party_current code, COALESCE(MAX(party_current_name),party_current) name,"
        " COUNT(*) n FROM person WHERE party_current IS NOT NULL"
        " GROUP BY party_current ORDER BY n DESC")


# --- aihe -------------------------------------------------------------------
def topics(conn) -> List[dict]:
    return _rows(conn,
        "SELECT t.id, t.slug, t.label,"
        " (SELECT COUNT(*) FROM speech_topic st WHERE st.topic_id=t.id) n_speeches,"
        " (SELECT COUNT(*) FROM vote_topic vt WHERE vt.topic_id=t.id) n_votes"
        " FROM topic t WHERE t.slug!='muu' ORDER BY t.id")


def topic_detail(conn, slug: str, limit: int = 30) -> dict:
    tid = TOPIC_IDS.get(slug)
    if not tid:
        return {}
    t = _one(conn, "SELECT * FROM topic WHERE id=?", tid)
    speeches = _rows(conn,
        "SELECT s.id, s.first_name, s.last_name, s.party, s.started_at, st.score,"
        " substr(s.text,1,160) preview FROM speech_topic st JOIN speech s ON s.id=st.speech_id"
        " WHERE st.topic_id=? ORDER BY st.score DESC LIMIT ?", tid, limit)
    votes = _rows(conn,
        "SELECT v.vote_id, v.session_date, v.title, v.legislative_item, vt.score"
        " FROM vote_topic vt JOIN vote v ON v.vote_id=vt.vote_id"
        " WHERE vt.topic_id=? ORDER BY v.session_date DESC LIMIT ?", tid, limit)
    top_speakers = _rows(conn,
        "SELECT s.person_id, s.first_name, s.last_name, s.party, COUNT(*) n"
        " FROM speech_topic st JOIN speech s ON s.id=st.speech_id"
        " WHERE st.topic_id=? AND s.person_id IS NOT NULL GROUP BY s.person_id"
        " ORDER BY n DESC LIMIT 10", tid)
    return {"topic": t, "speeches": speeches, "votes": votes, "top_speakers": top_speakers}


# --- äänestys ---------------------------------------------------------------
def vote_detail(conn, vote_id: int) -> dict:
    v = _one(conn, "SELECT * FROM vote WHERE vote_id=?", vote_id)
    if not v:
        return {}
    records = _rows(conn,
        "SELECT person_id, first_name, last_name, party, vote_value FROM vote_record"
        " WHERE vote_id=? ORDER BY party, last_name", vote_id)
    # puoluelinjat
    party_lines = _rows(conn,
        "SELECT party, party_line, COUNT(*) n, classification FROM analysis_party_deviation"
        " WHERE vote_id=? GROUP BY party, classification", vote_id)
    topics_v = _rows(conn,
        "SELECT t.slug, t.label, vt.score, vt.is_primary FROM vote_topic vt"
        " JOIN topic t ON t.id=vt.topic_id WHERE vt.vote_id=? ORDER BY vt.score DESC", vote_id)
    by_party = {}
    for r in records:
        by_party.setdefault(r["party"] or "(tuntematon)", {"Jaa": 0, "Ei": 0, "Tyhjää": 0, "Poissa": 0})
        by_party[r["party"] or "(tuntematon)"][r["vote_value"]] = \
            by_party[r["party"] or "(tuntematon)"].get(r["vote_value"], 0) + 1
    return {"vote": v, "records": records, "by_party": by_party, "topics": topics_v}


# --- puhe -------------------------------------------------------------------
def speech_detail(conn, sid: int) -> dict:
    s = _one(conn, "SELECT * FROM speech WHERE id=?", sid)
    if not s:
        return {}
    topics_s = _rows(conn,
        "SELECT t.slug, t.label, st.score, st.is_primary FROM speech_topic st"
        " JOIN topic t ON t.id=st.topic_id WHERE st.speech_id=? ORDER BY st.score DESC", sid)
    related_votes = []
    if s["legislative_item"]:
        related_votes = _rows(conn,
            "SELECT vote_id, session_date, title FROM vote WHERE legislative_item=?"
            " ORDER BY session_date LIMIT 10", s["legislative_item"])
    return {"speech": s, "topics": topics_s, "related_votes": related_votes}


# --- vertailu ---------------------------------------------------------------
def compare(conn, a: int, b: int) -> dict:
    return {
        "a": {"person": person(conn, a), "summary": person_summary(conn, a),
              "topics": person_topic_activity(conn, a), "behavior": person_vote_behavior(conn, a)},
        "b": {"person": person(conn, b), "summary": person_summary(conn, b),
              "topics": person_topic_activity(conn, b), "behavior": person_vote_behavior(conn, b)},
    }


def list_persons(conn, limit: int = 500) -> List[dict]:
    return _rows(conn,
        "SELECT person_id, full_name, party_current FROM person ORDER BY full_name LIMIT ?", limit)


# --- lajiteltava edustajalista ---------------------------------------------
# Sallitut lajitteluavaimet -> SQL-lauseke (estää injektion)
MEMBER_SORT = {
    "nimi": "p.full_name",
    "puolue": "p.party_current",
    "puheet": "s.n_speeches",
    "aanet": "s.n_votes_cast",
    "poissa": "s.n_absent",
    "poissa_pct": "(CASE WHEN s.n_votes_total>0 THEN 1.0*s.n_absent/s.n_votes_total END)",
    "poikkeama": "s.deviation_rate",
    "indeksi": "s.consistency_index",
}
MEMBER_SORT_LABELS = {
    "nimi": "Nimi", "puolue": "Ryhmä", "puheet": "Puheita", "aanet": "Ääniä annettu",
    "poissa": "Poissa", "poissa_pct": "Poissa-%", "poikkeama": "Poikkeama ryhmästä",
    "indeksi": "Johdonm.indeksi",
}


def member_directory(conn, sort: str = "nimi", direction: str = "asc",
                     party: Optional[str] = None, min_eligible: int = 0) -> List[dict]:
    col = MEMBER_SORT.get(sort, "p.full_name")
    direction_sql = "DESC" if str(direction).lower() == "desc" else "ASC"
    where = ["s.person_id IS NOT NULL"]
    params: list = []
    if party:
        where.append("p.party_current=?")
        params.append(party)
    if min_eligible:
        where.append("s.n_votes_eligible>=?")
        params.append(min_eligible)
    where_sql = " AND ".join(where)
    sql = (
        "SELECT p.person_id, p.full_name, p.party_current, s.n_speeches, s.n_votes_cast,"
        " s.n_votes_total, s.n_absent, s.n_votes_eligible, s.deviation_rate,"
        " s.consistency_index, s.confidence_level,"
        " CASE WHEN s.n_votes_total>0 THEN 100.0*s.n_absent/s.n_votes_total END AS absent_pct"
        " FROM person p JOIN analysis_member_summary s ON s.person_id=p.person_id"
        f" WHERE {where_sql}"
        # NULLit aina loppuun kummassakin suunnassa, tasapeli nimellä
        f" ORDER BY ({col}) IS NULL, ({col}) {direction_sql}, p.full_name ASC")
    return _rows(conn, sql, *params)


# --- puoluevertailu ---------------------------------------------------------
def party_comparison(conn, min_members: int = 3) -> List[dict]:
    """Puoluetason koonti nykyisen ryhmän mukaan (jäsenten tunnuslukujen keskiarvot)."""
    return _rows(conn,
        "SELECT p.party_current AS code,"
        " COALESCE(MAX(p.party_current_name), p.party_current) AS name,"
        " COUNT(*) AS n_members,"
        " SUM(s.n_speeches) AS speeches,"
        " ROUND(AVG(s.n_speeches),0) AS avg_speeches,"
        " ROUND(AVG(s.consistency_index),1) AS avg_idx,"
        " ROUND(AVG(s.deviation_rate)*100,2) AS avg_dev,"
        " ROUND(AVG(CASE WHEN s.n_votes_total>0 THEN 100.0*s.n_absent/s.n_votes_total END),1) AS avg_absent"
        " FROM person p JOIN analysis_member_summary s ON s.person_id=p.person_id"
        " WHERE p.party_current IS NOT NULL"
        " GROUP BY p.party_current HAVING n_members>=? ORDER BY avg_idx DESC", min_members)


def party_cohesion(conn, min_eligible: int = 1000) -> List[dict]:
    """Ryhmäkuri: poikkeama-% ryhmän äänestyshetken mukaan (autoritatiivisin)."""
    return _rows(conn,
        "SELECT party, COUNT(*) eligible, SUM(classification='deviates') deviations,"
        " ROUND(100.0*SUM(classification='deviates')/COUNT(*),2) pct"
        " FROM analysis_party_deviation WHERE classification IN ('follows','deviates')"
        " AND party IS NOT NULL GROUP BY party HAVING eligible>=? ORDER BY pct ASC", min_eligible)


# --- tilastot ---------------------------------------------------------------
def topic_trends(conn) -> dict:
    """Per vuosi per aihe: primääriaiheen puheenvuorojen määrä (2015–2024)."""
    years = list(range(2015, 2025))
    topics = _rows(conn, "SELECT id, slug, label FROM topic WHERE slug!='muu' ORDER BY id")
    counts = {t["slug"]: {y: 0 for y in years} for t in topics}
    for r in conn.execute(
            "SELECT CAST(substr(s.started_at,1,4) AS INT) y, t.slug, COUNT(*) n"
            " FROM speech s JOIN speech_topic st ON st.speech_id=s.id AND st.is_primary=1"
            " JOIN topic t ON t.id=st.topic_id WHERE t.slug!='muu' AND s.started_at IS NOT NULL"
            " GROUP BY y, t.slug"):
        if r["y"] in counts.get(r["slug"], {}):
            counts[r["slug"]][r["y"]] = r["n"]
    return {"years": years, "topics": topics, "counts": counts}


def closest_votes(conn, limit: int = 12) -> List[dict]:
    return _rows(conn,
        "SELECT vote_id, vp_year, title, legislative_item, result_yes, result_no,"
        " ABS(result_yes-result_no) AS era FROM vote"
        " WHERE is_procedural=0 AND result_yes>40 AND result_no>40"
        " ORDER BY era ASC, session_date DESC LIMIT ?", limit)


def top_speakers(conn, limit: int = 12) -> List[dict]:
    return _rows(conn,
        "SELECT person_id, first_name, last_name, party, COUNT(*) n FROM speech"
        " WHERE person_id IS NOT NULL GROUP BY person_id ORDER BY n DESC LIMIT ?", limit)


def stats_overview(conn) -> dict:
    return {
        "trends": topic_trends(conn),
        "cohesion": party_cohesion(conn),
        "party_comparison": party_comparison(conn),
        "closest": closest_votes(conn),
        "speakers": top_speakers(conn),
    }


# --- kattavuus --------------------------------------------------------------
def coverage(conn) -> List[dict]:
    return _rows(conn, "SELECT metric, dimension, value FROM coverage_stat ORDER BY metric, dimension")


# --- korjauskanava ----------------------------------------------------------
def add_correction(conn, page_ref: str, person_id, contact: str, message: str) -> int:
    import sqlite3
    import time
    params = (dt.datetime.now(dt.timezone.utc).isoformat(), page_ref,
              int(person_id) if person_id else None, contact, message)
    sql = ("INSERT INTO correction_request(created_at,page_ref,person_id,contact,message,status)"
           " VALUES(?,?,?,?,?,'open')")
    for attempt in range(5):
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def list_corrections(conn, status: Optional[str] = None) -> List[dict]:
    if status:
        return _rows(conn, "SELECT * FROM correction_request WHERE status=?"
                     " ORDER BY created_at DESC", status)
    return _rows(conn, "SELECT * FROM correction_request ORDER BY"
                 " CASE status WHEN 'open' THEN 0 ELSE 1 END, created_at DESC")


def set_correction_status(conn, correction_id: int, status: str) -> None:
    if status not in ("open", "resolved", "rejected"):
        raise ValueError("virheellinen tila")
    conn.execute("UPDATE correction_request SET status=? WHERE id=?", (status, correction_id))
    conn.commit()

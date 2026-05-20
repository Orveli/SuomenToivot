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
# Korttien attribuuttiarvot (1–99) — kuvaileva sijoittuminen muihin edustajiin nähden.
ATTR_LABELS = {"puhe": "Puheliaisuus", "las": "Äänestysaktiivisuus",
               "aihe": "Aihelaajuus", "kok": "Kokemus", "its": "Itsenäisyys"}
ATTR_ABBR = {"puhe": "PUH", "las": "LÄS", "aihe": "AIH", "kok": "KOK", "its": "ITS"}
# Lyhyet selkokieliset akselilabelit tutkagraafiin
RADAR_LABELS = {"puhe": "Puheliaisuus", "las": "Läsnäolo", "aihe": "Aiheet",
                "kok": "Kokemus", "its": "Itsenäisyys"}
# Yhden lauseen selitys kullekin (näytetään kortissa)
ATTR_HELP = {
    "puhe": "Kuinka paljon pitää puheenvuoroja",
    "las": "Kuinka usein osallistuu äänestyksiin (läsnä)",
    "aihe": "Kuinka monesta eri aiheesta puhuu",
    "kok": "Kuinka pitkä ura edustajana",
    "its": "Kuinka usein äänestää eri tavalla kuin oma ryhmä",
}
ATTR_ORDER = ["puhe", "las", "aihe", "kok", "its"]


def _percentile_ratings(values: dict) -> dict:
    """Muunna {pid: arvo} -> {pid: 1..99} persentiilisijan mukaan (suurempi arvo = suurempi luku)."""
    items = sorted((v, pid) for pid, v in values.items() if v is not None)
    n = len(items)
    out = {}
    for i, (_v, pid) in enumerate(items):
        out[pid] = round(1 + 98 * i / (n - 1)) if n > 1 else 50
    return out


def member_attributes(conn) -> dict:
    """Laske jokaiselle edustajalle 1–99 attribuuttiarvot (persentiili). Pelimäinen,
    kuvaileva: kertoo missä edustaja sijoittuu muihin nähden, ei arvota."""
    rows = _rows(conn,
        "SELECT s.person_id, s.n_speeches, s.n_votes_cast, s.n_votes_total, s.deviation_rate"
        " FROM analysis_member_summary s")
    active_from = {r["person_id"]: r["active_from"] for r in
                   _rows(conn, "SELECT person_id, active_from FROM person")}
    breadth = {}
    for r in conn.execute("SELECT person_id, COUNT(*) c FROM analysis_member_topic"
                          " WHERE n_speeches>0 GROUP BY person_id"):
        breadth[r["person_id"]] = r["c"]
    raw = {"puhe": {}, "las": {}, "aihe": {}, "kok": {}, "its": {}}
    this_year = 2025
    for r in rows:
        pid = r["person_id"]
        raw["puhe"][pid] = r["n_speeches"] or 0
        raw["las"][pid] = (100.0 * r["n_votes_cast"] / r["n_votes_total"]) if r["n_votes_total"] else None
        raw["aihe"][pid] = breadth.get(pid, 0)
        af = active_from.get(pid)
        raw["kok"][pid] = (this_year - int(str(af)[:4])) if af else None
        raw["its"][pid] = r["deviation_rate"]
    ratings = {k: _percentile_ratings(v) for k, v in raw.items()}
    out = {}
    for r in rows:
        pid = r["person_id"]
        out[pid] = {k: ratings[k].get(pid) for k in ATTR_ORDER}
    return out


def card_flair(m: dict) -> dict:
    """Lisää korttiin harvinaisuustaso, ominaisuusmerkit ja korttinumero (pelillisyys).
    Kaikki kuvailevia, faktapohjaisia — eivät arvosanoja."""
    badges = m.get("badges") or []
    yr = None
    if m.get("active_from"):
        try:
            yr = int(str(m["active_from"])[:4])
        except ValueError:
            yr = None
    if badges or m.get("is_minister"):
        m["rarity"] = "legendaarinen"
    elif (m.get("n_speeches") or 0) >= 400 or (yr and yr <= 2011):
        m["rarity"] = "harvinainen"
    else:
        m["rarity"] = "perus"
    traits = []
    if m.get("is_minister"):
        traits.append("Ministeri")
    if yr and yr <= 2011:
        traits.append("Konkari")
    if m.get("absent_pct") is not None and m["absent_pct"] < 8:
        traits.append("Ahkera äänestäjä")
    m["traits"] = traits
    m["cardno"] = m.get("person_id")
    return m


def _top_topic(conn, pid):
    r = _one(conn,
        "SELECT t.label FROM analysis_member_topic amt JOIN topic t ON t.id=amt.topic_id"
        " WHERE amt.person_id=? AND t.slug!='muu' AND amt.n_speeches>0"
        " ORDER BY amt.n_speeches DESC LIMIT 1", pid)
    return r["label"] if r else None


def awards(conn) -> List[dict]:
    """Leaderboardien voittajat 'palkintokortteina' (kuvailevia, ei arvosanoja)."""
    out = []

    def add(key, emoji, label, caption, row, value_text):
        if row:
            out.append({"key": key, "emoji": emoji, "label": label, "caption": caption,
                        "value_text": value_text, **dict(row)})

    add("speeches", "🗣️", "Puhelias", "Eniten puheenvuoroja", _one(conn,
        "SELECT p.person_id,p.full_name,p.party_current,p.photo_url,s.n_speeches v"
        " FROM analysis_member_summary s JOIN person p ON p.person_id=s.person_id"
        " ORDER BY s.n_speeches DESC LIMIT 1"), None)
    if out and out[-1]["key"] == "speeches":
        out[-1]["value_text"] = f"{out[-1]['v']} puhetta"

    add("absent", "🏃", "Useimmin poissa", "Suurin poissaolo-% (ei ministerit)", _one(conn,
        "SELECT p.person_id,p.full_name,p.party_current,p.photo_url,"
        " 100.0*s.n_absent/s.n_votes_total v FROM analysis_member_summary s"
        " JOIN person p ON p.person_id=s.person_id WHERE s.n_votes_total>=500 AND p.is_minister=0"
        " ORDER BY v DESC LIMIT 1"), None)
    if out and out[-1]["key"] == "absent":
        out[-1]["value_text"] = f"{out[-1]['v']:.0f} % poissa"

    add("rebel", "🐴", "Itsenäisin", "Suurin poikkeama omasta ryhmästä", _one(conn,
        "SELECT p.person_id,p.full_name,p.party_current,p.photo_url,100.0*s.deviation_rate v"
        " FROM analysis_member_summary s JOIN person p ON p.person_id=s.person_id"
        " WHERE s.n_votes_eligible>=200 AND s.deviation_rate IS NOT NULL ORDER BY v DESC LIMIT 1"), None)
    if out and out[-1]["key"] == "rebel":
        out[-1]["value_text"] = f"{out[-1]['v']:.1f} % poikkeama"

    add("loyal", "🎯", "Ryhmäuskollisin", "Pienin poikkeama (väh. 1000 ääntä)", _one(conn,
        "SELECT p.person_id,p.full_name,p.party_current,p.photo_url,100.0*s.deviation_rate v"
        " FROM analysis_member_summary s JOIN person p ON p.person_id=s.person_id"
        " WHERE s.n_votes_eligible>=1000 AND s.deviation_rate IS NOT NULL ORDER BY v ASC LIMIT 1"), None)
    if out and out[-1]["key"] == "loyal":
        out[-1]["value_text"] = f"{out[-1]['v']:.1f} % poikkeama"

    for key, emoji, label, cat, cap in [
            ("filler", "💬", "Täytesanakuningas", "filler", "Eniten täytesanoja / 1000 sanaa"),
            ("swear", "🌶️", "Värikkäin kieli", "swear", "Eniten voimasanoja / 1000 sanaa")]:
        add(key, emoji, label, cap, _one(conn,
            "SELECT p.person_id,p.full_name,p.party_current,p.photo_url,u.per_1000 v"
            " FROM analysis_word_usage u JOIN person p ON p.person_id=u.person_id"
            " WHERE u.category=? AND u.n_words>=5000 ORDER BY u.per_1000 DESC LIMIT 1", cat), None)
        if out and out[-1]["key"] == key:
            out[-1]["value_text"] = f"{out[-1]['v']:.2f} / 1000 sanaa"

    br = promise_breakers_persons(conn, limit=1)
    if br:
        b = br[0]
        out.append({"key": "flip", "emoji": "🔄", "label": "Takinkääntäjä",
                    "caption": "Useimmin oman ryhmän lupausta vastaan",
                    "person_id": b["person_id"], "full_name": b["full_name"],
                    "party_current": b.get("party_current"),
                    "photo_url": _one(conn, "SELECT photo_url FROM person WHERE person_id=?", b["person_id"])["photo_url"],
                    "value_text": f"{b['against']}/{b['eval']} lupausta vastaan"})
    return out


def front_feed(conn) -> dict:
    from collections import defaultdict
    aw = awards(conn)
    holders = defaultdict(list)
    for a in aw:
        holders[a["person_id"]].append({"emoji": a["emoji"], "label": a["label"]})
    mps = _rows(conn,
        "SELECT p.person_id,p.full_name,p.party_current,p.electoral_district,p.photo_url,p.is_minister,"
        " p.active_from,s.consistency_index,s.n_speeches,s.n_votes_cast,s.n_votes_total,s.n_absent,"
        " s.deviation_rate FROM analysis_member_summary s JOIN person p ON p.person_id=s.person_id"
        " WHERE s.n_votes_eligible>=100 ORDER BY RANDOM() LIMIT 8")
    attrs = member_attributes(conn)
    for m in mps:
        m["absent_pct"] = (100.0 * m["n_absent"] / m["n_votes_total"]) if m["n_votes_total"] else None
        m["top_topic"] = _top_topic(conn, m["person_id"])
        m["badges"] = holders.get(m["person_id"], [])
        m["attrs"] = attrs.get(m["person_id"])
        card_flair(m)
    parties = sorted(party_comparison(conn), key=lambda x: -(x["n_members"] or 0))
    return {"awards": aw, "mps": mps, "parties": parties,
            "highlights": index_highlights(conn)}


def award_holders(conn) -> dict:
    from collections import defaultdict
    holders = defaultdict(list)
    for a in awards(conn):
        holders[a["person_id"]].append({"emoji": a["emoji"], "label": a["label"]})
    return holders


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


def speeches_by_ids(conn, ids, scores=None) -> List[dict]:
    """Hae puheet annetussa järjestyksessä (merkityshaun tuloksille)."""
    if not ids:
        return []
    order = {sid: i for i, sid in enumerate(ids)}
    qmarks = ",".join("?" * len(ids))
    rows = _rows(conn,
        f"SELECT id, person_id, first_name, last_name, party, ptk_id, started_at,"
        f" legislative_item, substr(text,1,220) AS snip FROM speech WHERE id IN ({qmarks})", *ids)
    rows.sort(key=lambda r: order.get(r["id"], 1e9))
    if scores:
        for r in rows:
            r["score"] = round(scores.get(r["id"], 0), 3)
    return rows


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


def party_words(conn, code: str, limit: int = 25) -> List[dict]:
    """Ryhmää erottavat sanat (fightin' words), z-arvon mukaan."""
    return _rows(conn,
        "SELECT word, zscore, n_party, n_total FROM analysis_party_words"
        " WHERE party=? ORDER BY rank LIMIT ?", code, limit)


def all_party_top_words(conn, per_party: int = 6) -> List[dict]:
    """Kunkin ryhmän kärkisanat (tilastosivun koontia varten)."""
    rows = _rows(conn,
        "SELECT party, word, rank FROM analysis_party_words WHERE rank<=? ORDER BY party, rank",
        per_party)
    out = {}
    for r in rows:
        out.setdefault(r["party"], []).append(r["word"])
    return [{"party": p, "words": w} for p, w in out.items()]


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
        "SELECT p.person_id, p.full_name, p.party_current, p.electoral_district, p.active_from,"
        " p.is_minister, p.photo_url, s.n_speeches, s.n_votes_cast,"
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


def party_covote_matrix(conn, min_votes: int = 200) -> dict:
    """Puolueiden samanmielisyys: osuus äänestyksistä, joissa kahdella ryhmällä
    oli sama enemmistölinja (Jaa/Ei). Paljastaa blokit."""
    from collections import defaultdict
    lines = defaultdict(dict)
    for r in conn.execute(
            "SELECT DISTINCT vote_id, party, party_line FROM analysis_party_deviation"
            " WHERE party_line IN ('Jaa','Ei')"):
        lines[r["vote_id"]][r["party"]] = r["party_line"]
    # vain ryhmät, joilla riittävästi linjoja
    counts = defaultdict(int)
    for pl in lines.values():
        for p in pl:
            counts[p] += 1
    order = ["kok", "ps", "kesk", "sd", "vihr", "vas", "r", "kd", "liik", "sin"]
    parties = [p for p in order if counts.get(p, 0) >= min_votes]
    agree = defaultdict(lambda: [0, 0])
    for pl in lines.values():
        present = [p for p in parties if p in pl]
        for i, a in enumerate(present):
            for b in present[i + 1:]:
                key = (a, b)
                agree[key][1] += 1
                if pl[a] == pl[b]:
                    agree[key][0] += 1
    matrix = {}
    for a in parties:
        for b in parties:
            if a == b:
                matrix[(a, b)] = None
            else:
                k = (a, b) if (a, b) in agree else (b, a)
                s, t = agree[k]
                matrix[(a, b)] = round(100 * s / t) if t else None
    return {"parties": parties, "matrix": matrix}


# Kortti-tutkan kiinteät akselit (luettavuus + vertailtavuus)
RADAR_TOPICS = [
    ("talous", "Talous"), ("terveydenhuolto", "Terv."), ("koulutus", "Koul."),
    ("ilmasto", "Ilm."), ("maahanmuutto", "Maah."), ("turvallisuus", "Turv."),
    ("sosiaaliturva", "Sos."), ("tyo", "Työ"),
]


def member_cards(conn, party: Optional[str] = None, sort: str = "puheet",
                 direction: str = "desc", limit: int = 60, min_eligible: int = 0) -> List[dict]:
    rows = member_directory(conn, sort=sort, direction=direction, party=party,
                            min_eligible=min_eligible)[:limit]
    if not rows:
        return []
    ids = [r["person_id"] for r in rows]
    qmarks = ",".join("?" * len(ids))
    # aihevektorit (puheet per aihe) valituille
    tv = {pid: {} for pid in ids}
    for r in conn.execute(
            f"SELECT amt.person_id, t.slug, amt.n_speeches FROM analysis_member_topic amt"
            f" JOIN topic t ON t.id=amt.topic_id WHERE amt.person_id IN ({qmarks})", ids):
        tv[r["person_id"]][r["slug"]] = r["n_speeches"]
    # kärkiaihe (eniten puheita, ei 'muu')
    top_topic = {pid: None for pid in ids}
    for r in conn.execute(
            f"SELECT amt.person_id, t.label, amt.n_speeches FROM analysis_member_topic amt"
            f" JOIN topic t ON t.id=amt.topic_id WHERE amt.person_id IN ({qmarks})"
            f" AND t.slug!='muu' AND amt.n_speeches>0 ORDER BY amt.n_speeches DESC", ids):
        if top_topic.get(r["person_id"]) is None:
            top_topic[r["person_id"]] = r["label"]
    cards = []
    for r in rows:
        pid = r["person_id"]
        vec = tv.get(pid, {})
        mx = max((vec.get(slug, 0) for slug, _ in RADAR_TOPICS), default=0) or 1
        radar = [(short, (vec.get(slug, 0) / mx)) for slug, short in RADAR_TOPICS]
        d = dict(r)
        d["radar"] = radar
        d["top_topic"] = top_topic.get(pid)
        cards.append(d)
    return cards


def member_party_agreement(conn, pid: int, min_total: int = 50) -> List[dict]:
    """Edustajan 'äänestyssormenjälki': kuinka usein hän äänesti samoin kuin
    kunkin puolueen enemmistölinja (vain substantiiviset Jaa/Ei molemmin puolin)."""
    return _rows(conn,
        "SELECT apl.party, SUM(vr.vote_value=apl.line) agree, COUNT(*) total,"
        " ROUND(100.0*SUM(vr.vote_value=apl.line)/COUNT(*)) pct"
        " FROM vote_record vr JOIN analysis_party_line apl ON apl.vote_id=vr.vote_id"
        " WHERE vr.person_id=? AND vr.vote_value IN ('Jaa','Ei') AND apl.line IN ('Jaa','Ei')"
        " GROUP BY apl.party HAVING total>=? ORDER BY pct DESC", pid, min_total)


def pair_agreement(conn, a: int, b: int) -> Optional[dict]:
    """Kahden edustajan samanmielisyys: osuus yhteisistä substantiiviäänistä, joissa sama ääni."""
    r = _one(conn,
        "SELECT SUM(va.vote_value=vb.vote_value) agree, COUNT(*) total"
        " FROM vote_record va JOIN vote_record vb ON va.vote_id=vb.vote_id"
        " WHERE va.person_id=? AND vb.person_id=? AND va.vote_value IN ('Jaa','Ei')"
        " AND vb.vote_value IN ('Jaa','Ei')", a, b)
    if not r or not r["total"]:
        return None
    return {"agree": r["agree"], "total": r["total"], "pct": round(100 * r["agree"] / r["total"])}


def activity_scatter(conn, limit: int = 500) -> List[dict]:
    return _rows(conn,
        "SELECT p.person_id, p.full_name, p.party_current, s.n_speeches, s.n_votes_cast,"
        " CASE WHEN s.n_votes_total>0 THEN 100.0*s.n_absent/s.n_votes_total END absent_pct"
        " FROM analysis_member_summary s JOIN person p ON p.person_id=s.person_id"
        " WHERE s.n_votes_cast>0 ORDER BY s.n_votes_cast DESC LIMIT ?", limit)


def index_highlights(conn) -> dict:
    spotlight = _one(conn,
        "SELECT p.person_id, p.full_name, p.party_current, s.consistency_index,"
        " s.n_speeches, s.n_votes_cast FROM analysis_member_summary s"
        " JOIN person p ON p.person_id=s.person_id WHERE s.n_votes_eligible>=200"
        " ORDER BY RANDOM() LIMIT 1")
    if spotlight:
        tt = _one(conn,
            "SELECT t.label FROM analysis_member_topic amt JOIN topic t ON t.id=amt.topic_id"
            " WHERE amt.person_id=? AND t.slug!='muu' AND amt.n_speeches>0"
            " ORDER BY amt.n_speeches DESC LIMIT 1", spotlight["person_id"])
        spotlight = dict(spotlight)
        spotlight["top_topic"] = tt["label"] if tt else None
    tight = _one(conn,
        "SELECT vote_id, vp_year, title, legislative_item, result_yes, result_no,"
        " ABS(result_yes-result_no) era FROM vote WHERE is_procedural=0"
        " AND result_yes>40 AND result_no>40 ORDER BY vp_year DESC, era ASC LIMIT 1")
    trend = _one(conn,
        "SELECT t.label, t.slug, COUNT(*) n FROM speech s"
        " JOIN speech_topic st ON st.speech_id=s.id AND st.is_primary=1"
        " JOIN topic t ON t.id=st.topic_id WHERE t.slug!='muu'"
        " AND substr(s.started_at,1,4)=(SELECT MAX(substr(started_at,1,4)) FROM speech)"
        " GROUP BY t.slug ORDER BY n DESC LIMIT 1")
    return {"spotlight": spotlight, "tight": tight, "trend": trend}


def word_leaderboard(conn, category: str, direction: str = "desc",
                     limit: int = 15, min_words: int = 5000) -> List[dict]:
    """Leaderboard täyte-/kirosanoista per 1000 sanaa (reilu vertailu)."""
    order = "DESC" if direction == "desc" else "ASC"
    return _rows(conn,
        f"SELECT u.person_id, p.full_name, p.party_current, u.per_1000, u.n_hits, u.n_words"
        f" FROM analysis_word_usage u JOIN person p ON p.person_id=u.person_id"
        f" WHERE u.category=? AND u.n_words>=?"
        f" ORDER BY u.per_1000 {order}, u.n_words DESC LIMIT ?",
        category, min_words, limit)


def word_zero_count(conn, category: str, min_words: int = 5000) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM analysis_word_usage WHERE category=? AND n_words>=? AND n_hits=0",
        (category, min_words)).fetchone()[0]


def person_word_style(conn, pid: int) -> dict:
    out = {}
    for r in conn.execute(
            "SELECT category, n_hits, n_words, per_1000 FROM analysis_word_usage WHERE person_id=?",
            (pid,)):
        words = _rows(conn,
            "SELECT word, n FROM analysis_word_hits WHERE person_id=? AND category=?"
            " ORDER BY n DESC LIMIT 6", pid, r["category"])
        out[r["category"]] = {**dict(r), "top": words}
    return out


def vaalikone_statements(conn, election: str = "eduskuntavaalit2023") -> List[dict]:
    return _rows(conn, "SELECT id, text FROM vaalikone_statement WHERE election=? ORDER BY id", election)


def vaalikone_stance(conn, statement_id: int, election: str = "eduskuntavaalit2023") -> List[dict]:
    return _rows(conn,
        "SELECT party, party_code, mean, n, agree_pct FROM vaalikone_party_stance"
        " WHERE election=? AND statement_id=? AND party_code IS NOT NULL ORDER BY mean DESC",
        election, statement_id)


def _party_line_map(conn):
    m = {}
    for r in conn.execute("SELECT vote_id, party, line FROM analysis_party_line WHERE line IN ('Jaa','Ei')"):
        m[(r["vote_id"], r["party"])] = r["line"]
    return m


def promise_keeping_by_party(conn) -> dict:
    """#1 lupausvahti: piti vai rikkoi — PER LUPAUS (kukin kerran). Lupaus 'pidetty'
    jos ryhmän enemmistölinja vastasi odotusääntä sen kartoitettujen äänestysten
    enemmistössä. Säädöskohteen useat loppuäänestykset lasketaan yhdeksi lupaukseksi."""
    pl = _party_line_map(conn)
    from collections import defaultdict
    promises = {}
    pv = defaultdict(list)
    for r in _rows(conn,
            "SELECT m.promise_id, m.vote_id, m.expected_value, pr.party_code, pr.text,"
            " pr.source_url, v.legislative_item FROM promise_vote_map m"
            " JOIN promise pr ON pr.id=m.promise_id JOIN vote v ON v.vote_id=m.vote_id"
            " WHERE pr.scope='party' AND pr.party_code IS NOT NULL"):
        promises[r["promise_id"]] = r
        line = pl.get((r["vote_id"], r["party_code"]))
        if line is not None:
            pv[r["promise_id"]].append(line == r["expected_value"])
    agg = defaultdict(lambda: {"kept": 0, "broken": 0})
    broken = []
    for pid, results in pv.items():
        if not results:
            continue
        r = promises[pid]
        kept = sum(results) >= (len(results) / 2)
        agg[r["party_code"]]["kept" if kept else "broken"] += 1
        if not kept:
            broken.append({**r, "party_line": "Ei" if r["expected_value"] == "Jaa" else "Jaa"})
    parties = []
    for p, d in agg.items():
        tot = d["kept"] + d["broken"]
        parties.append({"party": p, "kept": d["kept"], "broken": d["broken"], "total": tot,
                        "keep_pct": round(100 * d["kept"] / tot) if tot else None})
    parties.sort(key=lambda x: (x["keep_pct"] if x["keep_pct"] is not None else 999, -x["total"]))
    return {"parties": parties, "broken": broken}


def promise_breakers_persons(conn, min_eval: int = 3, limit: int = 20) -> List[dict]:
    """Per-henkilö 'takinkääntäjät': kuinka usein edustaja äänesti oman puolueensa
    lupauksen ODOTUSäänen vastaisesti kartoitetuissa äänestyksissä."""
    from collections import defaultdict
    # per (person, promise): äänestikö enemmistössä kartoitetuista äänistä odotusta vastaan
    pp = defaultdict(lambda: defaultdict(list))  # person -> promise -> [against_bool]
    rows = conn.execute(
        "SELECT m.promise_id, m.expected_value, pr.party_code, vr.person_id, vr.vote_value"
        " FROM promise_vote_map m JOIN promise pr ON pr.id=m.promise_id"
        " JOIN vote_record vr ON vr.vote_id=m.vote_id AND vr.party=pr.party_code"
        " WHERE pr.scope='party' AND pr.party_code IS NOT NULL AND vr.vote_value IN ('Jaa','Ei')")
    for r in rows:
        pp[r["person_id"]][r["promise_id"]].append(r["vote_value"] != r["expected_value"])
    agg = defaultdict(lambda: {"against": 0, "eval": 0})
    for pid, proms in pp.items():
        for _prid, results in proms.items():
            agg[pid]["eval"] += 1
            if sum(results) > len(results) / 2:
                agg[pid]["against"] += 1
    out = []
    for pid, d in agg.items():
        if d["eval"] < min_eval or not pid:
            continue
        p = _one(conn, "SELECT full_name, party_current FROM person WHERE person_id=?", pid)
        if not p:
            continue
        out.append({"person_id": pid, **p, "against": d["against"], "eval": d["eval"],
                    "rate": round(100 * d["against"] / d["eval"])})
    out.sort(key=lambda x: (-x["rate"], -x["eval"]))
    return out[:limit]


def power_overview(conn) -> dict:
    """#1 vallan vaikutus + #6 hallituksen läpimeno."""
    eff = {}
    for r in conn.execute("SELECT party, status, win_pct, n_votes FROM analysis_power_effect"):
        eff.setdefault(r["party"], {})[r["status"]] = {"win_pct": r["win_pct"], "n": r["n_votes"]}
    # vain ryhmät joilla molemmat tai iso n
    parties = [{"party": p, **d} for p, d in eff.items()
               if (d.get("gov", {}).get("n", 0) + d.get("opp", {}).get("n", 0)) >= 2000]
    parties.sort(key=lambda x: -(x.get("gov", {}).get("n", 0)))
    winrate = _rows(conn, "SELECT vp_year, n_votes, gov_wins, pct FROM analysis_gov_winrate ORDER BY vp_year")
    lost = _rows(conn,
        "SELECT l.vote_id, l.margin, v.vp_year, v.title, v.legislative_item, v.result_yes, v.result_no"
        " FROM analysis_gov_lost l JOIN vote v ON v.vote_id=l.vote_id ORDER BY l.margin")
    return {"parties": parties, "winrate": winrate, "lost": lost}


def rhetoric_map_data(conn) -> dict:
    rows = _rows(conn,
        "SELECT r.person_id, r.dim1, r.dim2, r.party, r.nearest_party, p.full_name"
        " FROM analysis_rhetoric_map r JOIN person p ON p.person_id=r.person_id")
    from collections import defaultdict
    cg = defaultdict(list)
    for r in rows:
        cg[r["party"]].append((r["dim1"], r["dim2"]))
    centroids = {p: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
                 for p, v in cg.items() if len(v) >= 3}
    return {"points": rows, "centroids": centroids, "n": len(rows)}


def rhetoric_mismatch(conn, limit: int = 25) -> List[dict]:
    """Edustajat, joiden retoriikka on lähinnä eri ryhmää kuin oma (puhuu kuin X, kuuluu Y:hyn)."""
    return _rows(conn,
        "SELECT r.person_id, p.full_name, r.party, r.nearest_party FROM analysis_rhetoric_map r"
        " JOIN person p ON p.person_id=r.person_id WHERE r.nearest_party!=r.party"
        " ORDER BY p.full_name LIMIT ?", limit)


_OWN_PARTIES = ["kok", "ps", "kesk", "sd", "vihr", "vas", "r", "kd"]


def topic_ownership(conn, slug: str) -> dict:
    """#2 kuka 'omistaa' aiheen ajassa: puolueiden osuus aiheen puheista vuosittain."""
    from collections import defaultdict
    years = list(range(2015, 2025))
    raw = defaultdict(lambda: defaultdict(int))  # year -> party -> n
    for r in conn.execute(
            "SELECT CAST(substr(s.started_at,1,4) AS INT) y, s.party, COUNT(*) n"
            " FROM speech s JOIN speech_topic st ON st.speech_id=s.id AND st.is_primary=1"
            " JOIN topic t ON t.id=st.topic_id WHERE t.slug=? AND s.party IS NOT NULL"
            " AND s.started_at IS NOT NULL GROUP BY y, s.party", (slug,)):
        if r["y"] in years:
            party = r["party"] if r["party"] in _OWN_PARTIES else "muut"
            raw[r["y"]][party] += r["n"]
    parties = _OWN_PARTIES + ["muut"]
    series = {p: [] for p in parties}
    totals = []
    for y in years:
        tot = sum(raw[y].values()) or 1
        totals.append(sum(raw[y].values()))
        for p in parties:
            series[p].append(round(100 * raw[y].get(p, 0) / tot, 1))
    return {"years": years, "parties": parties, "series": series, "totals": totals}


def political_map(conn) -> dict:
    """Poliittisen kartan pisteet, ryhmäkeskipisteet ja meta (selitysosuudet)."""
    rows = _rows(conn,
        "SELECT m.person_id, m.dim1, m.dim2, m.party, m.dist_own, m.nearest_party, p.full_name"
        " FROM analysis_political_map m JOIN person p ON p.person_id=m.person_id")
    from collections import defaultdict
    cg = defaultdict(list)
    for r in rows:
        cg[r["party"]].append((r["dim1"], r["dim2"]))
    centroids = {p: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
                 for p, v in cg.items() if len(v) >= 3}
    meta = get = conn.execute("SELECT n_items, note FROM ingest_state WHERE job='political_map'").fetchone()
    var1 = var2 = period = None
    if meta and meta["note"] and "|" in meta["note"]:
        var1, var2, period = (meta["note"].split("|") + [None, None, None])[:3]
    return {"points": rows, "centroids": centroids,
            "n": len(rows), "var1": var1, "var2": var2, "period": period}


def mavericks(conn, limit: int = 15) -> List[dict]:
    """Edustajat kauimpana oman ryhmänsä keskipisteestä (kuvaileva itsenäisyysmittari)."""
    return _rows(conn,
        "SELECT m.person_id, p.full_name, m.party, m.dist_own, m.nearest_party, m.n_votes"
        " FROM analysis_political_map m JOIN person p ON p.person_id=m.person_id"
        " WHERE m.dist_own IS NOT NULL ORDER BY m.dist_own DESC LIMIT ?", limit)


def party_outsiders(conn) -> List[dict]:
    """Edustajat, joiden lähin ryhmäkeskipiste EI ole oma ryhmä — äänestävät
    käytännössä lähempänä toista ryhmää."""
    return _rows(conn,
        "SELECT m.person_id, p.full_name, m.party, m.nearest_party, m.dist_own, m.n_votes"
        " FROM analysis_political_map m JOIN person p ON p.person_id=m.person_id"
        " WHERE m.nearest_party IS NOT NULL AND m.nearest_party!=m.party"
        " ORDER BY m.dist_own DESC")


def stats_overview(conn) -> dict:
    return {
        "trends": topic_trends(conn),
        "cohesion": party_cohesion(conn),
        "party_comparison": party_comparison(conn),
        "covote": party_covote_matrix(conn),
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


# --- M2: Sanat vs. äänet -tilikirja ----------------------------------------
ALIGN_LABELS = {
    "linjassa": "Linjassa",
    "ristiriita": "Ristiriita",
    "vastentahtoinen": "Vastentahtoinen kuri",
    "konteksti": "Kontekstisidonnainen",
    "ei_riitä": "Data ei riitä",
}
ALIGN_HELP = {
    "linjassa": "Puheen kanta ja ääni samaan suuntaan (lain hyväksyntä/hylkäys).",
    "ristiriita": "Puheessa toinen kanta kuin annettu ääni — ilman avointa kompromissisignaalia.",
    "vastentahtoinen": "Ääni eri suuntaan kuin puheen kanta, mutta puhuja kertoo avoimesti äänestävänsä kantaansa vastaan (esim. hallituskuri).",
    "konteksti": "Ääni ei koske yksiselitteisesti lain hyväksymistä (esim. lausuma- tai muutosehdotus) — ristiriitaa ei voi päätellä.",
    "ei_riitä": "Ääni oli tyhjä/poissa tai puheen kanta ehdollinen — ei vertailtavissa.",
}
ALIGN_ORDER = ["ristiriita", "vastentahtoinen", "linjassa", "konteksti", "ei_riitä"]


def words_votes_overview(conn) -> dict:
    counts = {r["alignment"]: r["c"] for r in conn.execute(
        "SELECT alignment, COUNT(*) c FROM analysis_words_votes GROUP BY alignment")}
    agg = _one(conn,
        "SELECT COUNT(DISTINCT person_id) np, COUNT(DISTINCT legislative_item) ni, "
        "COUNT(*) n FROM analysis_words_votes")
    model = _one(conn, "SELECT model FROM analysis_speech_stance ORDER BY computed_at DESC LIMIT 1")
    examples = _rows(conn,
        "SELECT wv.alignment, wv.legislative_item, wv.speech_stance, wv.speech_quote, "
        "wv.speech_id, wv.vote_id, wv.vote_value, wv.context_note, wv.confidence, "
        "p.person_id, p.full_name, p.party_current, p.photo_url, v.title vote_title, v.session_date "
        "FROM analysis_words_votes wv JOIN person p ON p.person_id=wv.person_id "
        "JOIN vote v ON v.vote_id=wv.vote_id "
        "ORDER BY CASE wv.alignment WHEN 'ristiriita' THEN 0 WHEN 'vastentahtoinen' THEN 1 "
        "WHEN 'linjassa' THEN 2 WHEN 'konteksti' THEN 3 ELSE 4 END, wv.confidence DESC")
    # dedupe per (henkilö, säädös): yksi edustava rivi + liittyvien äänten määrä
    seen: dict = {}
    deduped = []
    for e in examples:
        k = (e["person_id"], e["legislative_item"])
        if k in seen:
            seen[k]["n_related"] += 1
            continue
        e["n_related"] = 1
        seen[k] = e
        deduped.append(e)
    return {"counts": counts, "n_pairs": (agg or {}).get("n", 0),
            "n_persons": (agg or {}).get("np", 0), "n_items": (agg or {}).get("ni", 0),
            "examples": deduped[:24], "model": (model or {}).get("model")}


def person_words_votes(conn, pid: int) -> List[dict]:
    """Edustajan tilikirja säädöksittäin: puheen kanta + lainaus + liittyvät äänet."""
    rows = _rows(conn,
        "SELECT wv.legislative_item, wv.speech_stance, wv.speech_quote, wv.speech_id, "
        "wv.speech_date, wv.vote_id, wv.vote_value, wv.alignment, wv.context_note, "
        "v.title vote_title, v.session_date "
        "FROM analysis_words_votes wv JOIN vote v ON v.vote_id=wv.vote_id "
        "WHERE wv.person_id=? ORDER BY wv.legislative_item, wv.vote_date", pid)
    items: dict = {}
    for r in rows:
        it = items.setdefault(r["legislative_item"], {
            "legislative_item": r["legislative_item"], "stance": r["speech_stance"],
            "quote": r["speech_quote"], "speech_id": r["speech_id"],
            "speech_date": r["speech_date"], "votes": []})
        it["votes"].append({"vote_id": r["vote_id"], "vote_value": r["vote_value"],
                            "alignment": r["alignment"], "context_note": r["context_note"],
                            "vote_title": r["vote_title"], "session_date": r["session_date"]})
    return list(items.values())


# --- M24: Lakiselittäjä + aihe-aikajana ------------------------------------
def bill_explainer(conn, item: str) -> Optional[dict]:
    import json
    r = _one(conn,
        "SELECT e.*, l.title AS leg_title, l.summary AS leg_summary, l.url AS leg_url "
        "FROM analysis_bill_explainer e "
        "LEFT JOIN legislation l ON l.eduskunta_tunnus=e.legislative_item "
        "WHERE e.legislative_item=?", item)
    if r:
        try:
            r["sources"] = json.loads(r.get("sources_json") or "[]")
        except Exception:
            r["sources"] = []
    return r


def votes_for_item(conn, item: str) -> List[dict]:
    return _rows(conn,
        "SELECT vote_id, session_date, title, result_yes, result_no, is_procedural "
        "FROM vote WHERE legislative_item=? ORDER BY session_date", item)


def topic_timeline(conn, slug: str, limit: int = 40) -> List[dict]:
    """Deterministinen, tapahtumapohjainen aikajana aiheelle: aiheeseen luokitellut
    äänestykset aikajärjestyksessä. Ei kausaali- tai motiiviväitteitä."""
    return _rows(conn,
        "SELECT v.vote_id, v.session_date, v.legislative_item, v.title, "
        "v.result_yes, v.result_no, "
        "EXISTS(SELECT 1 FROM analysis_bill_explainer e WHERE e.legislative_item=v.legislative_item) has_explainer "
        "FROM vote v JOIN vote_topic vt ON vt.vote_id=v.vote_id "
        "JOIN topic t ON t.id=vt.topic_id "
        "WHERE t.slug=? AND v.is_procedural=0 AND v.session_date IS NOT NULL "
        "ORDER BY v.session_date LIMIT ?", slug, limit)


def glossary() -> List[dict]:
    import json
    from .. import config as _cfg
    p = _cfg.SEED_DIR / "glossary.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("terms", [])


# --- M23: Äänestyksen puolesta/vastaan -selitys ----------------------------
def vote_proscons(conn, vote_id: int) -> Optional[dict]:
    import json
    r = _one(conn, "SELECT * FROM analysis_vote_proscons WHERE vote_id=?", vote_id)
    if not r:
        return None
    for k in ("pro", "con"):
        try:
            r[k] = json.loads(r.get(k + "_json") or "[]")
        except Exception:
            r[k] = []
    return r


# --- Esitys-/synteesikyselyt (UX-kierros) ----------------------------------
def item_stances(conn, item: str) -> dict:
    """Säädöksen puhekannat ryhmiteltynä: kuka puhui puolesta/vastaan/ehdollisesti.
    Yksi edustava rivi per (edustaja, kanta), korkein luottamus."""
    rows = _rows(conn,
        "SELECT ss.person_id, ss.stance, ss.proposition, ss.conditional_note, "
        "ss.evidence_quote, ss.speech_id, ss.confidence, p.full_name, p.party_current "
        "FROM analysis_speech_stance ss JOIN person p ON p.person_id=ss.person_id "
        "WHERE ss.legislative_item=? ORDER BY ss.confidence DESC", item)
    groups = {"puolesta": [], "vastaan": [], "ehdollinen": [], "ei_kantaa": []}
    seen = set()
    for r in rows:
        key = (r["person_id"], r["stance"])
        if key in seen or r["stance"] not in groups:
            continue
        seen.add(key)
        groups[r["stance"]].append(r)
    return {"groups": groups,
            "counts": {k: len(v) for k, v in groups.items()}}


def item_conflicts(conn, item: str) -> List[dict]:
    """Säädöksen puhe–ääni-ristiriidat ja vastentahtoiset (yksi per edustaja)."""
    rows = _rows(conn,
        "SELECT DISTINCT wv.person_id, wv.speech_stance, wv.speech_quote, wv.speech_id, "
        "wv.vote_value, wv.alignment, wv.context_note, p.full_name, p.party_current "
        "FROM analysis_words_votes wv JOIN person p ON p.person_id=wv.person_id "
        "WHERE wv.legislative_item=? AND wv.alignment IN ('ristiriita','vastentahtoinen') "
        "ORDER BY wv.alignment, p.full_name", item)
    out, seen = [], set()
    for r in rows:
        if r["person_id"] in seen:
            continue
        seen.add(r["person_id"])
        out.append(r)
    return out


def person_highlights(conn, pid: int) -> List[dict]:
    """Neutraalit, lähteistetyt 'kohokohdat' edustajasta — vain laskettuja faktoja,
    ankkurilinkki todisteeseen. Ei adjektiiveja, ei arvottamista."""
    h = []
    s = _one(conn, "SELECT * FROM analysis_member_summary WHERE person_id=?", pid)
    if s:
        if s.get("n_deviations"):
            h.append({"text": f"Äänesti {s['n_deviations']} kertaa eri tavalla kuin oma "
                      f"ryhmänsä enemmistö", "anchor": "#aanet"})
        if s.get("consistency_index") is not None:
            h.append({"text": f"Johdonmukaisuusindeksi {s['consistency_index']}/100 "
                      f"({s.get('confidence_level') or '—'} luottamus)", "anchor": "#indeksi"})
    wv = _one(conn,
        "SELECT SUM(alignment='ristiriita') ris, SUM(alignment='vastentahtoinen') vas, "
        "COUNT(DISTINCT legislative_item) items FROM analysis_words_votes WHERE person_id=?", pid)
    if wv and (wv.get("ris") or wv.get("vas")):
        parts = []
        if wv.get("ris"):
            parts.append(f"{wv['ris']} puheen ja äänen ristiriita")
        if wv.get("vas"):
            parts.append(f"{wv['vas']} vastentahtoinen ääni")
        h.append({"text": " · ".join(parts) + " kirjattu", "anchor": "#sanat-aanet"})
    pc = _one(conn, "SELECT COUNT(*) c FROM analysis_position_change WHERE person_id=?", pid)
    if pc and pc["c"]:
        h.append({"text": f"{pc['c']} kannanmuutosta samasta säädöskohteesta", "anchor": "#muutokset"})
    return h

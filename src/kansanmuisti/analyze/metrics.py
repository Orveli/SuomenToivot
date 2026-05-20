"""Lasketut tunnusluvut (METHODOLOGY.md §2, §4, §5, §6).

Kaikki funktiot ovat deterministisiä ja kirjoittavat analysis_*-tauluihin.
Puolue äänestyshetkellä saadaan suoraan vote_record.party-kentästä (ryhmä,
jonka edustaja ilmoitti äänestyshetkellä) — tämä on autoritatiivinen tieto.
"""
from __future__ import annotations

import bisect
import datetime as dt
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from . import LEXICON_VERSION, MAPPING_VERSION

W_A = 0.5
W_B = 0.5
WINDOW_DAYS = 30
SUBSTANTIVE = {"Jaa", "Ei"}

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


def _date(s: Optional[str]) -> Optional[dt.date]:
    if not s:
        return None
    s = s.strip().replace("T", " ")[:10]
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# §5 Puoluelinja ja poikkeamat
# ---------------------------------------------------------------------------
def compute_party_deviation(conn) -> dict:
    """Puoluelinja ja poikkeamat (METHODOLOGY §5). Menettelyäänestykset
    (is_procedural=1) jätetään pois, koska ne eivät kuvaa substantiivista kantaa (§8)."""
    conn.execute("DELETE FROM analysis_party_deviation")
    # puoluelinja per (vote, party) — vain ei-menettelylliset äänestykset
    party_line: Dict[Tuple[int, str], str] = {}
    counts = defaultdict(lambda: {"Jaa": 0, "Ei": 0})
    for r in conn.execute(
            "SELECT vr.vote_id, vr.party, vr.vote_value FROM vote_record vr"
            " JOIN vote v ON v.vote_id=vr.vote_id"
            " WHERE vr.party IS NOT NULL AND v.is_procedural=0"):
        if r["vote_value"] in SUBSTANTIVE:
            counts[(r["vote_id"], r["party"])][r["vote_value"]] += 1
    for key, c in counts.items():
        if c["Jaa"] == c["Ei"]:
            party_line[key] = "TIE" if (c["Jaa"] + c["Ei"]) else "UNDEFINED"
        else:
            party_line[key] = "Jaa" if c["Jaa"] > c["Ei"] else "Ei"

    # persistoi puoluelinja per (vote, party) — sormenjälki & samanmielisyysmatriisi
    conn.execute("DELETE FROM analysis_party_line")
    conn.executemany(
        "INSERT OR REPLACE INTO analysis_party_line(vote_id,party,line) VALUES(?,?,?)",
        [(vid, p, line) for (vid, p), line in party_line.items()])

    n = 0
    rows = []
    for r in conn.execute(
            "SELECT vr.vote_id, vr.person_id, vr.party, vr.vote_value FROM vote_record vr"
            " JOIN vote v ON v.vote_id=vr.vote_id"
            " WHERE vr.person_id IS NOT NULL AND vr.party IS NOT NULL AND v.is_procedural=0"):
        line = party_line.get((r["vote_id"], r["party"]), "UNDEFINED")
        val = r["vote_value"]
        if val == "Poissa":
            cls = "absent"
        elif val == "Tyhjää":
            cls = "ineligible"
        elif line in ("UNDEFINED", "TIE"):
            cls = "ineligible"
        elif val == line:
            cls = "follows"
        else:
            cls = "deviates"
        rows.append((r["person_id"], r["vote_id"], r["party"], val, line, cls))
        n += 1
    conn.executemany(
        "INSERT OR REPLACE INTO analysis_party_deviation"
        "(person_id,vote_id,party,member_value,party_line,classification)"
        " VALUES(?,?,?,?,?,?)", rows)
    conn.commit()
    return {"records": n}


# ---------------------------------------------------------------------------
# §2 Puhe–ääni-topikaalinen linjaus (komponentti A)
# ---------------------------------------------------------------------------
def build_alignment_index(conn):
    """Esilaske kerran kaikki rakenteet puhe–ääni-linjausta varten (suorituskyky).

    Palauttaa:
      person_votes: pid -> [(date, frozenset(topics))]  (ei-Poissa-äänet)
      person_speech_topic_dates: pid -> {topic_id -> sorted([date])}
    Linjaus A = Σ_T ctx_count[T] / Σ_T vote_count[T], missä ctx = onko samasta
    aiheesta puhetta ±30 vrk (bisect-haku). Vastaa METHODOLOGY §2/§6.1(a).
    """
    vt: Dict[int, set] = defaultdict(set)
    for r in conn.execute("SELECT vote_id, topic_id FROM vote_topic"):
        vt[r["vote_id"]].add(r["topic_id"])
    st: Dict[int, set] = defaultdict(set)
    for r in conn.execute("SELECT speech_id, topic_id FROM speech_topic"):
        st[r["speech_id"]].add(r["topic_id"])

    person_votes: Dict[int, list] = defaultdict(list)
    for r in conn.execute(
            "SELECT vr.person_id, vr.vote_id, v.session_date FROM vote_record vr"
            " JOIN vote v ON v.vote_id=vr.vote_id"
            " WHERE vr.person_id IS NOT NULL AND vr.vote_value!='Poissa'"):
        person_votes[r["person_id"]].append((_date(r["session_date"]), vt.get(r["vote_id"], frozenset())))

    person_speech_dates: Dict[int, Dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute("SELECT person_id, id, started_at FROM speech WHERE person_id IS NOT NULL"):
        d = _date(r["started_at"])
        if d is None:
            continue
        for T in st.get(r["id"], ()):  # noqa: E741
            person_speech_dates[r["person_id"]][T].append(d)
    for pid in person_speech_dates:
        for T in person_speech_dates[pid]:
            person_speech_dates[pid][T].sort()
    return person_votes, person_speech_dates


def alignment_for(votes: list, speech_dates: Dict[int, list]) -> Optional[float]:
    """Laske komponentti A esilasketuista rakenteista (bisect ±30 vrk)."""
    window = dt.timedelta(days=WINDOW_DAYS)
    vote_count = 0
    ctx_count = 0
    for vd, vtopics in votes:
        for T in vtopics:  # noqa: E741
            vote_count += 1
            dates = speech_dates.get(T)
            if vd and dates:
                lo = bisect.bisect_left(dates, vd - window)
                if lo < len(dates) and dates[lo] <= vd + window:
                    ctx_count += 1
    if vote_count == 0:
        return None
    return ctx_count / vote_count


# ---------------------------------------------------------------------------
# §6 Johdonmukaisuusindeksi + edustajan yhteenveto
# ---------------------------------------------------------------------------
def compute_member_summaries(conn, period: str = "kerätty aineisto") -> dict:
    conn.execute("DELETE FROM analysis_member_summary")
    conn.execute("DELETE FROM analysis_member_topic")
    # Vain eduskunnan jäsenrekisterissä olevat henkilöt (ei orpoja ei-edustaja-puhujia)
    persons = [r["person_id"] for r in conn.execute(
        "SELECT DISTINCT person_id FROM vote_record WHERE person_id IS NOT NULL"
        " AND person_id IN (SELECT person_id FROM person)"
        " UNION SELECT DISTINCT person_id FROM speech WHERE person_id IS NOT NULL"
        " AND person_id IN (SELECT person_id FROM person)")]
    # Esilaske linjausindeksi kerran (suorituskyky koko 10v aineistolle)
    person_votes, person_speech_dates = build_alignment_index(conn)
    n = 0
    for pid in persons:
        # poikkeamat
        dev = conn.execute(
            "SELECT classification, COUNT(*) c FROM analysis_party_deviation"
            " WHERE person_id=? GROUP BY classification", (pid,)).fetchall()
        dmap = {r["classification"]: r["c"] for r in dev}
        follows = dmap.get("follows", 0)
        deviates = dmap.get("deviates", 0)
        eligible = follows + deviates
        deviation_rate = (deviates / eligible) if eligible else None
        B = (1 - deviation_rate) if deviation_rate is not None else None

        # raakaluvut yhdestä (dedupatusta) lähteestä — vote_record
        n_votes_total = conn.execute(
            "SELECT COUNT(*) c FROM vote_record WHERE person_id=?", (pid,)).fetchone()["c"]
        n_cast = conn.execute(
            "SELECT COUNT(*) c FROM vote_record WHERE person_id=? AND vote_value IN ('Jaa','Ei','Tyhjää')",
            (pid,)).fetchone()["c"]
        absent = conn.execute(
            "SELECT COUNT(*) c FROM vote_record WHERE person_id=? AND vote_value='Poissa'",
            (pid,)).fetchone()["c"]
        n_speeches = conn.execute(
            "SELECT COUNT(*) c FROM speech WHERE person_id=?", (pid,)).fetchone()["c"]

        A = alignment_for(person_votes.get(pid, []), person_speech_dates.get(pid, {}))

        available = []
        if A is not None:
            available.append((A, W_A))
        if B is not None:
            available.append((B, W_B))
        if available:
            num = sum(w * c for c, w in available)
            den = sum(w for _c, w in available)
            index = round(100 * num / den)
        else:
            index = None

        # luottamus
        conf_score = min(1.0, eligible / 50) * min(1.0, (n_speeches + 1) / 20)
        comps = len(available)
        if conf_score >= 0.66 and comps == 2:
            conf_level = "korkea"
        elif conf_score >= 0.33:
            conf_level = "kohtalainen"
        else:
            conf_level = "matala"

        flags = []
        if eligible < 10:
            flags.append("LOW_SAMPLE")
        if comps < 2:
            flags.append("SINGLE_COMPONENT")
            if conf_level == "korkea":
                conf_level = "kohtalainen"
        # puoluevaihdos jaksolla
        nparties = conn.execute(
            "SELECT COUNT(DISTINCT party) c FROM vote_record WHERE person_id=? AND party IS NOT NULL",
            (pid,)).fetchone()["c"]
        if nparties and nparties > 1:
            flags.append("PARTY_CHANGE")

        conn.execute(
            "INSERT OR REPLACE INTO analysis_member_summary("
            "person_id,period,n_votes_total,n_votes_eligible,n_deviations,deviation_rate,"
            "n_votes_cast,n_absent,n_speeches,speech_vote_alignment,party_line_score,"
            "consistency_index,confidence_score,confidence_level,flags,computed_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, period, n_votes_total, eligible, deviates, deviation_rate,
             n_cast, absent, n_speeches,
             round(A, 4) if A is not None else None,
             round(B, 4) if B is not None else None,
             index, round(conf_score, 4), conf_level, ",".join(flags), NOW()))

        # aihekohtaiset määrät
        topic_counts = defaultdict(lambda: [0, 0])  # topic_id -> [speeches, votes]
        for r in conn.execute(
                "SELECT st.topic_id, COUNT(*) c FROM speech s JOIN speech_topic st"
                " ON st.speech_id=s.id WHERE s.person_id=? GROUP BY st.topic_id", (pid,)):
            topic_counts[r["topic_id"]][0] = r["c"]
        for r in conn.execute(
                "SELECT vt.topic_id, COUNT(*) c FROM vote_record vr JOIN vote_topic vt"
                " ON vt.vote_id=vr.vote_id WHERE vr.person_id=? AND vr.vote_value!='Poissa'"
                " GROUP BY vt.topic_id", (pid,)):
            topic_counts[r["topic_id"]][1] = r["c"]
        for tid, (sc, vc) in topic_counts.items():
            conn.execute(
                "INSERT OR REPLACE INTO analysis_member_topic(person_id,topic_id,n_speeches,n_votes)"
                " VALUES(?,?,?,?)", (pid, tid, sc, vc))
        n += 1
        if n % 50 == 0:
            conn.commit()
    conn.commit()
    return {"members": n}


# ---------------------------------------------------------------------------
# §4 Kannanmuutokset (vahvat: sama säädöskohde, Jaa<->Ei)
# ---------------------------------------------------------------------------
def _item_base(item: Optional[str]) -> Optional[str]:
    if not item:
        return None
    return item.strip()


# Vähimmäisväli (vrk) eri tilaisuuksien erottamiseksi: saman istunnon/viikon
# muutosesitysäänestykset eivät ole "kannanmuutos" vaan saman käsittelyn osia.
POSITION_CHANGE_MIN_GAP_DAYS = 7


def compute_position_changes(conn) -> dict:
    """Havaitse kannanmuutokset (METHODOLOGY §4): sama säädöskohde, Jaa<->Ei,
    eri tilaisuuksissa. Vain ei-menettelylliset äänestykset; yhden päivän sisäiset
    (ristiriitaiset) äänet ohitetaan, koska ne koskevat usein muutosesityksiä."""
    conn.execute("DELETE FROM analysis_position_change")
    # Kerää edustajan substantiiviset, ei-menettelylliset äänet ryhmiteltynä
    # (säädöskohde + käsittelyvaihe), jotta verrataan samaa kysymystyyppiä eikä
    # esim. muutosesitystä loppuäänestykseen. Avain: (pid, base, treatment_stage).
    raw = defaultdict(lambda: defaultdict(set))  # key -> date -> {values}
    vote_of = {}  # (key, date, value) -> vote_id
    for r in conn.execute(
            "SELECT vr.person_id, vr.vote_value, v.legislative_item, v.session_date,"
            " v.vote_id, v.treatment_stage"
            " FROM vote_record vr JOIN vote v ON v.vote_id=vr.vote_id"
            " WHERE vr.person_id IS NOT NULL AND vr.vote_value IN ('Jaa','Ei')"
            " AND v.legislative_item IS NOT NULL AND v.legislative_item != ''"
            " AND v.is_procedural=0"):
        base = _item_base(r["legislative_item"])
        d = _date(r["session_date"])
        if base and d:
            key = (r["person_id"], base, r["treatment_stage"] or "")
            raw[key][d].add(r["vote_value"])
            vote_of[(key, d, r["vote_value"])] = r["vote_id"]
    n = 0
    for key, by_day in raw.items():
        pid, base, _stage = key
        # yksi edustava arvo per päivä; ristiriitaiset päivät ohitetaan
        seq = []
        for d in sorted(by_day):
            vals = by_day[d]
            if len(vals) == 1:
                seq.append((d, next(iter(vals))))
        if len(seq) < 2:
            continue
        for i in range(1, len(seq)):
            gap = (seq[i][0] - seq[i - 1][0]).days
            if seq[i][1] != seq[i - 1][1] and gap >= POSITION_CHANGE_MIN_GAP_DAYS:
                vid = vote_of.get((key, seq[i][0], seq[i][1]))
                tr = conn.execute(
                    "SELECT topic_id FROM vote_topic WHERE vote_id=? AND is_primary=1",
                    (vid,)).fetchone() if vid else None
                conn.execute(
                    "INSERT INTO analysis_position_change(person_id,topic_id,item_base,"
                    "from_value,from_date,to_value,to_date,gap_days,note) VALUES(?,?,?,?,?,?,?,?,?)",
                    (pid, tr["topic_id"] if tr else None, base,
                     seq[i - 1][1], seq[i - 1][0].isoformat(),
                     seq[i][1], seq[i][0].isoformat(), gap,
                     "sama säädöskohde, eri tilaisuus (vahva signaali) — tarkista molemmat äänestykset"))
                n += 1
    conn.commit()
    return {"changes": n}

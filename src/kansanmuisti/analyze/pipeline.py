"""Analyysiputken ajuri: aiheet -> poikkeamat -> yhteenvedot -> kannanmuutokset
-> kattavuus. Deterministinen ja uudelleenajettava."""
from __future__ import annotations

import datetime as dt

from .. import db
from . import classify, metrics
from .taxonomy import seed_topics

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


def compute_coverage(conn) -> None:
    """Laske kattavuusluvut coverage_stat-tauluun."""
    conn.execute("DELETE FROM coverage_stat")

    def add(metric, dim, val):
        db.add_coverage(conn, metric, dim, val)

    add("persons", "yhteensä", conn.execute("SELECT COUNT(*) c FROM person").fetchone()["c"])
    add("votes", "yhteensä", conn.execute("SELECT COUNT(*) c FROM vote").fetchone()["c"])
    add("vote_records", "yhteensä",
        conn.execute("SELECT COUNT(*) c FROM vote_record").fetchone()["c"])
    add("speeches", "yhteensä", conn.execute("SELECT COUNT(*) c FROM speech").fetchone()["c"])
    add("promises", "yhteensä", conn.execute("SELECT COUNT(*) c FROM promise").fetchone()["c"])

    for r in conn.execute("SELECT vp_year, COUNT(*) c FROM vote GROUP BY vp_year ORDER BY vp_year"):
        add("votes", f"vuosi {r['vp_year']}", r["c"])
    for r in conn.execute(
            "SELECT substr(started_at,1,4) y, COUNT(*) c FROM speech"
            " WHERE started_at IS NOT NULL GROUP BY y ORDER BY y"):
        add("speeches", f"vuosi {r['y']}", r["c"])

    # aihekattavuus (NO_MATCH-osuus)
    nv = conn.execute("SELECT COUNT(*) c FROM vote").fetchone()["c"]
    classified_v = conn.execute(
        "SELECT COUNT(DISTINCT vote_id) c FROM vote_topic vt JOIN topic t"
        " ON t.id=vt.topic_id WHERE t.slug!='muu'").fetchone()["c"]
    if nv:
        add("aiheluokiteltu", "äänestykset %", round(100 * classified_v / nv, 1))
    ns = conn.execute("SELECT COUNT(*) c FROM speech").fetchone()["c"]
    classified_s = conn.execute(
        "SELECT COUNT(DISTINCT speech_id) c FROM speech_topic st JOIN topic t"
        " ON t.id=st.topic_id WHERE t.slug!='muu'").fetchone()["c"]
    if ns:
        add("aiheluokiteltu", "puheet %", round(100 * classified_s / ns, 1))

    # puheiden henkilölinkitys
    linked = conn.execute("SELECT COUNT(*) c FROM speech WHERE person_id IS NOT NULL").fetchone()["c"]
    if ns:
        add("puheet_henkilölinkitetty", "%", round(100 * linked / ns, 1))
    conn.commit()


def run_all(conn, period: str = "kerätty aineisto") -> dict:
    """Aja koko analyysiputki."""
    results = {}
    # Varmista FTS-haun synkronointi speech-taulun kanssa (external content -taulu)
    try:
        conn.execute("INSERT INTO speech_fts(speech_fts) VALUES('rebuild')")
        conn.commit()
    except Exception:
        pass
    results["topics_seeded"] = seed_topics(conn)
    results["classify"] = classify.classify_all(conn)
    results["deviation"] = metrics.compute_party_deviation(conn)
    results["summaries"] = metrics.compute_member_summaries(conn, period=period)
    results["position_changes"] = metrics.compute_position_changes(conn)
    from .fightinwords import compute_party_words
    results["party_words"] = compute_party_words(conn)
    from .wordstyle import compute_word_style
    results["word_style"] = compute_word_style(conn)
    from .government import compute_power_analysis
    results["power"] = compute_power_analysis(conn)
    try:
        from .politmap import compute_political_map
        results["political_map"] = compute_political_map(conn)
        from .rhetoricmap import compute_rhetoric_map
        results["rhetoric_map"] = compute_rhetoric_map(conn)
    except ImportError:
        results["political_map"] = {"skipped": "numpy puuttuu"}
    compute_coverage(conn)
    return results

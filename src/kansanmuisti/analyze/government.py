"""Hallitus↔oppositio-analyysi: vallan vaihtumisen vaikutus + hallituksen läpimeno.

Hallituskaudet 2015–2024 (julkinen tieto). Huom Sipilän hallituksen ps/sin-jako
13.6.2017: perussuomalaiset siirtyivät oppositioon, Sininen tulevaisuus (sin) jäi.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731

# (alku, loppu, hallituspuolueet) — loppu None = jatkuu
GOV_PERIODS = [
    ("2015-05-29", "2017-06-13", {"kesk", "kok", "ps"}),     # Sipilä I
    ("2017-06-13", "2019-06-06", {"kesk", "kok", "sin"}),    # Sipilä II (ps -> sin)
    ("2019-06-06", "2023-06-20", {"sd", "kesk", "vihr", "vas", "r"}),  # Rinne/Marin
    ("2023-06-20", None, {"kok", "ps", "r", "kd"}),          # Orpo
]


def gov_parties_at(date_str):
    if not date_str:
        return set()
    d = date_str[:10]
    for start, end, parties in GOV_PERIODS:
        if start <= d and (end is None or d < end):
            return parties
    return set()


def compute_power_analysis(conn) -> dict:
    # äänestysten perustiedot
    votes = {}
    for r in conn.execute(
            "SELECT vote_id, session_date, vp_year, result_yes, result_no, is_procedural FROM vote"):
        votes[r["vote_id"]] = r
    # puoluelinjat
    lines = defaultdict(dict)
    for r in conn.execute("SELECT vote_id, party, line FROM analysis_party_line WHERE line IN ('Jaa','Ei')"):
        lines[r["vote_id"]][r["party"]] = r["line"]

    # #1 vallan vaikutus: per (party, status) osuus, jossa puoluelinja == voittava puoli
    pe = defaultdict(lambda: [0, 0])           # (party,status)->[wins,total]
    # #6 hallituksen läpimeno per vuosi
    gov_year = defaultdict(lambda: [0, 0])     # year->[gov_wins,total]
    clashes = []                               # tiukat substantiiviset gov-äänestykset

    for vid, pl in lines.items():
        v = votes.get(vid)
        if not v or v["is_procedural"]:
            continue
        ry, rn = v["result_yes"], v["result_no"]
        if ry is None or rn is None or ry == rn:
            continue
        winning = "Jaa" if ry > rn else "Ei"
        govset = gov_parties_at(v["session_date"])
        # #1
        for party, line in pl.items():
            status = "gov" if party in govset else "opp"
            pe[(party, status)][1] += 1
            if line == winning:
                pe[(party, status)][0] += 1
        # #6 hallituksen enemmistölinja
        gj = sum(1 for p in govset if pl.get(p) == "Jaa")
        ge = sum(1 for p in govset if pl.get(p) == "Ei")
        if gj + ge:
            gov_line = "Jaa" if gj > ge else ("Ei" if ge > gj else None)
            if gov_line:
                gov_year[v["vp_year"]][1] += 1
                if gov_line == winning:
                    gov_year[v["vp_year"]][0] += 1
                else:
                    clashes.append((abs(ry - rn), vid, v["vp_year"], ry, rn))

    conn.execute("DELETE FROM analysis_power_effect")
    for (party, status), (w, t) in pe.items():
        if t >= 30:
            conn.execute(
                "INSERT OR REPLACE INTO analysis_power_effect(party,status,n_votes,win_pct) VALUES(?,?,?,?)",
                (party, status, t, round(100 * w / t, 1)))
    conn.execute("DELETE FROM analysis_gov_winrate")
    for y, (w, t) in gov_year.items():
        conn.execute(
            "INSERT OR REPLACE INTO analysis_gov_winrate(vp_year,n_votes,gov_wins,pct) VALUES(?,?,?,?)",
            (y, t, w, round(100 * w / t, 1) if t else None))
    conn.execute("DELETE FROM analysis_gov_lost")
    for margin, vid, _y, _ry, _rn in clashes:
        conn.execute("INSERT OR REPLACE INTO analysis_gov_lost(vote_id,margin) VALUES(?,?)", (vid, margin))
    conn.commit()
    n_lost = len(clashes)
    return {"power_rows": len(pe), "year_rows": len(gov_year),
            "gov_lost_votes": n_lost}

"""Vaalikonedata (Yle, avoin CC-BY) — puoluetason aggregaatti.

Yle julkaisi eduskuntavaalien 2023 vaalikonevastaukset avoimena datana CC-BY-
lisenssillä. AVOIMESTA datasta on poistettu nimet ja ehdokasnumerot (anonyymi),
joten tästä saadaan vain PUOLUETASON aggregaatti — ei per-henkilö.

Nimellinen data (per ehdokas → edustaja -kytkentä) edellyttää erillistä pyyntöä
Yleltä tieteelliseen/journalistiseen tarkoitukseen (ks. docs/VAALIKONE.md). Sama
parseri tukee nimellistä tiedostoa (col 'nimi'/'etunimi'+'sukunimi'), jolloin
voidaan tehdä per-henkilö-analyysi.

Lähde + lisenssi näytetään käyttöliittymässä.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from collections import defaultdict

YLE_2023_URL = ("https://old-vaalikone.yle.fi/vaalikone/eduskuntavaalit2023/"
                "Eduskuntavaalit%202023%20vastausdata%20-%20Kaikki%20vaalipiirit%20-%20anonyymi.csv")
ELECTION = "eduskuntavaalit2023"
SOURCE_NOTE = "Lähde: Yle vaalikone, eduskuntavaalit 2023, avoin data CC BY 4.0."

# Vaalikoneen puoluenimi -> meidän ryhmätunnus
PARTY_MAP = {
    "kansallinen kokoomus": "kok", "kokoomus": "kok",
    "perussuomalaiset": "ps",
    "suomen keskusta": "kesk", "keskusta": "kesk",
    "suomen sosialidemokraattinen puolue": "sd", "sdp": "sd",
    "vihreä liitto": "vihr", "vihreät": "vihr",
    "vasemmistoliitto": "vas",
    "suomen ruotsalainen kansanpuolue": "r", "ruotsalainen kansanpuolue": "r", "rkp": "r",
    "suomen kristillisdemokraatit": "kd", "kristillisdemokraatit": "kd", "kd": "kd",
    "liike nyt": "liik",
}


def _party_code(name: str):
    return PARTY_MAP.get((name or "").strip().lower())


def _load_csv(path_or_url):
    if str(path_or_url).startswith("http"):
        req = urllib.request.Request(path_or_url, headers={"User-Agent": "SuomenToivot/0.1 civic"})
        raw = urllib.request.urlopen(req, timeout=180).read()
    else:
        raw = open(path_or_url, "rb").read()
    text = raw.decode("utf-8-sig", errors="replace")
    delim = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def collect_vaalikone(conn, source=YLE_2023_URL, election: str = ELECTION) -> dict:
    rows = _load_csv(source)
    if not rows:
        return {"error": "tyhjä"}
    header = rows[0]
    # paikanna puolue-sarake ja väittämäsarakkeet (väittämät = pitkät tekstisarakkeet)
    try:
        p_idx = next(i for i, h in enumerate(header) if h.strip().lower() == "puolue")
    except StopIteration:
        return {"error": "puolue-saraketta ei löydy"}
    # väittämät = sarakkeet, jotka eivät ole taustakenttiä
    bg = {"vaalipiiri", "puolue", "ikä", "sukupuoli", "nimi", "etunimi", "sukunimi",
          "ehdokasnumero", "valittu"}
    stmt_cols = [i for i, h in enumerate(header) if h.strip().lower() not in bg and len(h.strip()) > 15]

    # tallenna väittämät
    conn.execute("DELETE FROM vaalikone_statement WHERE election=?", (election,))
    sid_of = {}
    for n, i in enumerate(stmt_cols, 1):
        conn.execute("INSERT OR REPLACE INTO vaalikone_statement(id,election,text) VALUES(?,?,?)",
                     (n, election, header[i].strip()))
        sid_of[i] = n

    # aggregoi per (puolue, väittämä)
    agg = defaultdict(lambda: [0.0, 0, 0])   # (party, sid) -> [sum, n, agree_count]
    for r in rows[1:]:
        if len(r) <= p_idx:
            continue
        party = r[p_idx].strip()
        for i in stmt_cols:
            if i >= len(r):
                continue
            v = r[i].strip()
            if not v.isdigit():
                continue
            val = int(v)
            if not (1 <= val <= 5):
                continue
            a = agg[(party, sid_of[i])]
            a[0] += val
            a[1] += 1
            if val >= 4:
                a[2] += 1

    conn.execute("DELETE FROM vaalikone_party_stance WHERE election=?", (election,))
    n_rows = 0
    parties = set()
    for (party, sid), (s, n, agree) in agg.items():
        if n < 3:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO vaalikone_party_stance"
            "(election,party,party_code,statement_id,mean,n,agree_pct) VALUES(?,?,?,?,?,?,?)",
            (election, party, _party_code(party), sid, round(s / n, 2), n, round(100 * agree / n, 1)))
        n_rows += 1
        parties.add(party)
    conn.commit()
    return {"statements": len(stmt_cols), "parties": len(parties), "rows": n_rows,
            "candidates": len(rows) - 1}

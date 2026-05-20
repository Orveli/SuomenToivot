"""Poliittinen kartta: pelkistää äänestysmatriisin (edustaja × äänestys) kahteen
ulottuvuuteen SVD:llä (ideal-point / NOMINATE-tyyppinen analyysi).

Periaate ja rajaus:
- Akselit ovat **datasta johdettuja**, eivät käsin nimettyjä "vasen/oikea". Pääakseli
  (dim1) selittää eniten äänestysvaihtelusta; sen empiirinen tulkinta esitetään
  käyttäjälle (kuvaileva, ei arvottava).
- Käytetään yhden vaalikauden (oletus 2023–2024) substantiivisia ei-menettelyäänestyksiä,
  jotta kaikki edustajat jakavat saman äänestysjoukon (vertailukelpoisuus).
- Etäisyys oman ryhmän keskipisteeseen = kuinka "tyypillinen" tai poikkeava edustaja on
  ryhmässään (kuvaileva — ei kerro syytä).

Vaatii numpyn.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Tuple

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
MIN_VOTES = 100  # edustajalla oltava väh. näin monta substantiiviääntä jaksolla


def compute_political_map(conn, years: Tuple[int, ...] = (2023, 2024)) -> dict:
    import numpy as np

    period = "–".join(str(y) for y in (years[0], years[-1]))
    placeholders = ",".join("?" * len(years))
    votes = [r[0] for r in conn.execute(
        f"SELECT vote_id FROM vote WHERE vp_year IN ({placeholders}) AND is_procedural=0", years)]
    if len(votes) < 20:
        return {"members": 0, "note": "liian vähän äänestyksiä"}
    vindex = {v: i for i, v in enumerate(votes)}

    rows = defaultdict(lambda: np.zeros(len(votes)))
    nz = defaultdict(int)
    for r in conn.execute(
            f"SELECT person_id, vote_id, vote_value FROM vote_record"
            f" WHERE vote_id IN ({','.join('?'*len(votes))}) AND person_id IS NOT NULL", votes):
        j = vindex.get(r["vote_id"])
        if j is None:
            continue
        v = 1.0 if r["vote_value"] == "Jaa" else (-1.0 if r["vote_value"] == "Ei" else 0.0)
        if v != 0.0:
            rows[r["person_id"]][j] = v
            nz[r["person_id"]] += 1

    ids = [pid for pid in rows if nz[pid] >= MIN_VOTES]
    if len(ids) < 5:
        return {"members": 0, "note": "liian vähän edustajia"}
    X = np.array([rows[pid] for pid in ids])
    Xc = X - X.mean(axis=0)
    U, S, _Vt = np.linalg.svd(Xc, full_matrices=False)
    coords = U[:, :2] * S[:2]

    # nykyinen ryhmä jokaiselle
    party = {}
    for pid in ids:
        r = conn.execute("SELECT party_current FROM person WHERE person_id=?", (pid,)).fetchone()
        party[pid] = (r["party_current"] if r and r["party_current"] else "?")

    # determinismi: orientoi akselit kiinteästi ryhmäkeskiarvojen mukaan
    def party_mean(dim):
        m = defaultdict(list)
        for k, pid in enumerate(ids):
            m[party[pid]].append(coords[k, dim])
        return {p: float(np.mean(v)) for p, v in m.items()}

    pm1 = party_mean(0)
    # dim1: 'sd' vasemmalle (neg), 'kok' oikealle (pos)
    if pm1.get("sd", 0) > pm1.get("kok", 0):
        coords[:, 0] *= -1
    pm2 = party_mean(1)
    if pm2.get("vihr", 0) < 0:  # vakaa orientointi dim2:lle
        coords[:, 1] *= -1

    # skaalaa molemmat ulottuvuudet välille ~[-100,100] luettavuuden vuoksi
    for d in (0, 1):
        col = coords[:, d]
        lo, hi = col.min(), col.max()
        if hi > lo:
            coords[:, d] = 200 * (col - lo) / (hi - lo) - 100

    # ryhmäkeskipisteet (väh. 3 jäsentä)
    cgroups = defaultdict(list)
    for k, pid in enumerate(ids):
        cgroups[party[pid]].append(coords[k])
    centroids = {p: (float(np.mean([c[0] for c in v])), float(np.mean([c[1] for c in v])))
                 for p, v in cgroups.items() if len(v) >= 3}

    var = (S ** 2) / float(np.sum(S ** 2))

    conn.execute("DELETE FROM analysis_political_map")
    out = []
    for k, pid in enumerate(ids):
        d1, d2 = float(coords[k, 0]), float(coords[k, 1])
        own = party[pid]
        dist_own = None
        if own in centroids:
            cx, cy = centroids[own]
            dist_own = ((d1 - cx) ** 2 + (d2 - cy) ** 2) ** 0.5
        # lähin ryhmäkeskipiste
        nearest, best = None, 1e18
        for p, (cx, cy) in centroids.items():
            dd = (d1 - cx) ** 2 + (d2 - cy) ** 2
            if dd < best:
                best, nearest = dd, p
        out.append((pid, period, own, d1, d2, dist_own, nearest, nz[pid], NOW()))
    conn.executemany(
        "INSERT OR REPLACE INTO analysis_political_map"
        "(person_id,period,party,dim1,dim2,dist_own,nearest_party,n_votes,computed_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)", out)
    var1, var2 = round(100 * float(var[0])), round(100 * float(var[1]))
    from .. import db as _db
    _db.set_ingest_state(conn, "political_map", status="done", n_items=len(ids),
                         note=f"{var1}|{var2}|{period}")
    conn.commit()
    return {"members": len(ids), "votes": len(votes), "period": period,
            "var1": var1, "var2": var2}

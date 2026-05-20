"""Retoriikkakartta: sijoittaa edustajat sen mukaan MITÄ he puhuvat (puheiden
merkitys), erotuksena poliittisesta kartasta joka perustuu siihen MITEN he äänestävät.

Keskimääräinen puheupotus per edustaja → SVD 2D. Vertaamalla retoriikka- ja
äänestyskarttaa nähdään, kuka puhuu kuin yksi ryhmä mutta äänestää kuin toinen.

Vaatii upotukset (km embed) + numpy. Kuvaileva; akseleita ei nimetä käsin.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
MIN_SPEECHES = 20


def is_available() -> bool:
    from .embeddings import EMB_PATH, IDS_PATH
    try:
        import numpy  # noqa: F401
    except ImportError:
        return False
    return EMB_PATH.exists() and IDS_PATH.exists()


def compute_rhetoric_map(conn) -> dict:
    if not is_available():
        return {"skipped": "upotukset puuttuvat"}
    import numpy as np
    from .embeddings import EMB_PATH, IDS_PATH
    emb = np.load(EMB_PATH)
    sids = np.load(IDS_PATH)
    spid = {r["id"]: r["person_id"] for r in conn.execute(
        "SELECT id, person_id FROM speech WHERE person_id IS NOT NULL")}
    dim = emb.shape[1]
    sums = defaultdict(lambda: np.zeros(dim, dtype=np.float64))
    cnt = defaultdict(int)
    for i in range(len(sids)):
        pid = spid.get(int(sids[i]))
        if pid is None:
            continue
        sums[pid] += emb[i]
        cnt[pid] += 1

    party = {}
    for pid in list(sums):
        r = conn.execute("SELECT party_current FROM person WHERE person_id=?", (pid,)).fetchone()
        party[pid] = (r["party_current"] if r and r["party_current"] else None)

    ids = [p for p in sums if cnt[p] >= MIN_SPEECHES and party.get(p)]
    if len(ids) < 5:
        return {"members": 0}
    M = np.array([sums[p] / cnt[p] for p in ids])
    M = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    Mc = M - M.mean(axis=0)
    U, S, _ = np.linalg.svd(Mc, full_matrices=False)
    coords = U[:, :2] * S[:2]

    def pmean(dim_i):
        m = defaultdict(list)
        for k, pid in enumerate(ids):
            m[party[pid]].append(coords[k, dim_i])
        return {p: float(np.mean(v)) for p, v in m.items()}

    if pmean(0).get("sd", 0) > pmean(0).get("kok", 0):
        coords[:, 0] *= -1
    if pmean(1).get("vihr", 0) < 0:
        coords[:, 1] *= -1
    for d in (0, 1):
        col = coords[:, d]
        lo, hi = col.min(), col.max()
        if hi > lo:
            coords[:, d] = 200 * (col - lo) / (hi - lo) - 100

    cg = defaultdict(list)
    for k, pid in enumerate(ids):
        cg[party[pid]].append(coords[k])
    centroids = {p: (float(np.mean([c[0] for c in v])), float(np.mean([c[1] for c in v])))
                 for p, v in cg.items() if len(v) >= 3}

    conn.execute("DELETE FROM analysis_rhetoric_map")
    for k, pid in enumerate(ids):
        d1, d2 = float(coords[k, 0]), float(coords[k, 1])
        nearest, best = None, 1e18
        for p, (cx, cy) in centroids.items():
            dd = (d1 - cx) ** 2 + (d2 - cy) ** 2
            if dd < best:
                best, nearest = dd, p
        conn.execute(
            "INSERT OR REPLACE INTO analysis_rhetoric_map(person_id,party,dim1,dim2,nearest_party,computed_at)"
            " VALUES(?,?,?,?,?,?)", (pid, party[pid], d1, d2, nearest, NOW()))
    conn.commit()
    return {"members": len(ids)}

"""Kuratoitujen, lähteistettyjen vaalilupausten latain.

Lupaukset ovat ihmisen kuratoimia ja lähteistettyjä (puolueohjelma / julkinen
kannanotto). Lupaus↔äänestys-kytkentä on toimituksellinen tulkinta, ei
automaattinen totuus (METHODOLOGY.md §3). Kytkennät viittaavat säädöskohteeseen
(esim. "HE 74/2024 vp"), joka latauksessa resolvoidaan kerättyihin äänestyksiin.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


def load_promises(conn, path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    n_p = n_m = n_resolved = 0
    for p in data.get("promises", []):
        conn.execute(
            "INSERT OR REPLACE INTO promise(id,scope,party_code,person_id,topic_slug,text,"
            "source_title,source_url,source_year,curated_by,curated_at,note)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (p["id"], p.get("scope", "party"), p.get("party_code"), p.get("person_id"),
             p.get("topic_slug"), p["text"], p.get("source_title"), p.get("source_url"),
             p.get("source_year"), p.get("curated_by", "seed"), NOW(), p.get("note")))
        n_p += 1
    # tyhjennä vanhat kytkennät ladattaville lupauksille
    ids = [p["id"] for p in data.get("promises", [])]
    if ids:
        conn.execute(
            f"DELETE FROM promise_vote_map WHERE promise_id IN ({','.join('?' * len(ids))})",
            ids)
    for m in data.get("promise_vote_map", []):
        # resolvoi säädöskohde -> äänestys. Valitaan substantiivinen loppuäänestys
        # ("Hyväksyminen/hylkääminen", ei-menettelyllinen), ei kaikkia ali-/menettelyäänestyksiä.
        vote_ids = []
        if "vote_id" in m:
            vote_ids = [m["vote_id"]]
        elif "legislative_item" in m:
            item = m["legislative_item"]
            rows = conn.execute(
                "SELECT vote_id FROM vote WHERE legislative_item=? AND is_procedural=0"
                " AND (title LIKE '%Hyväksy%' OR title LIKE '%hylk%' OR title LIKE '%Hylk%')"
                " ORDER BY session_date", (item,)).fetchall()
            if not rows:  # varatie: ei-menettelylliset
                rows = conn.execute(
                    "SELECT vote_id FROM vote WHERE legislative_item=? AND is_procedural=0"
                    " ORDER BY session_date", (item,)).fetchall()
            vote_ids = [r["vote_id"] for r in rows]
        for vid in vote_ids:
            conn.execute(
                "INSERT INTO promise_vote_map(promise_id,vote_id,expected_value,rationale,"
                "source_note,curated_by,mapping_version) VALUES(?,?,?,?,?,?,?)",
                (m["promise_id"], vid, m["expected_value"], m.get("rationale"),
                 m.get("source_note"), m.get("curated_by", "seed"), m.get("mapping_version", "1")))
            n_resolved += 1
        n_m += 1
    conn.commit()
    return {"promises": n_p, "mappings": n_m, "resolved": n_resolved}

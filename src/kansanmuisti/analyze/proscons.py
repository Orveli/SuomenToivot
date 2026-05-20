"""M23 — Neutraali puolesta/vastaan-selitys äänestykselle. Kokoaa salikeskustelusta
kummankin puolen argumentit, kukin nimettyyn puhujaan ja sanatarkkaan lainaukseen
sidottuna. Tasapuolinen: molemmat puolet esitetään, ei johtopäätöstä, ei motiiveja.

Tuotetaan Claude Code -ajossa (ei API-avainta): vie äänestysten keskustelut,
analysoi, lataa tällä loaderilla (lainausvarmennus mukana)."""
from __future__ import annotations

import datetime as dt
import json

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


def export_vote_debates(conn, *, limit=10, out=None, max_speech=900, n_speeches=12):
    """Vie puhtaiden hyväksyntä/hylkäys-äänestysten keskustelut analysoitavaksi."""
    rows = conn.execute(
        "SELECT v.vote_id, v.legislative_item, v.title, l.title leg_title, l.summary "
        "FROM vote v LEFT JOIN legislation l ON l.eduskunta_tunnus=v.legislative_item "
        "WHERE v.is_procedural=0 AND lower(v.title) LIKE 'hyväksyminen / hylk%' "
        "AND v.legislative_item IN (SELECT DISTINCT legislative_item FROM analysis_speech_stance) "
        "AND v.vote_id NOT IN (SELECT vote_id FROM analysis_vote_proscons) "
        "ORDER BY v.vote_id LIMIT ?", (int(limit),)).fetchall()
    out_items = []
    for r in rows:
        sp = conn.execute(
            "SELECT first_name, last_name, party, text FROM speech WHERE legislative_item=? "
            "AND person_id IS NOT NULL AND length(text)>300 ORDER BY length(text) DESC LIMIT ?",
            (r["legislative_item"], n_speeches)).fetchall()
        debate = [{"speaker": f"{s['first_name']} {s['last_name']}", "party": s["party"],
                   "text": s["text"][:max_speech]} for s in sp]
        out_items.append({"vote_id": r["vote_id"], "legislative_item": r["legislative_item"],
                          "summary": (r["summary"] or "")[:1500], "debate": debate})
    if out:
        json.dump({"votes": out_items}, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return {"votes": len(out_items), "out": out}


def load_proscons(conn, path) -> dict:
    """Lataa puolesta/vastaan-selitykset. Integriteetti: jokaisen argumentin lainauksen
    on oltava sanatarkka osa kyseisen säädöksen jotakin puhetta."""
    data = json.loads(open(path, encoding="utf-8").read())
    model = data.get("model_label", "Claude Code -agentti")
    inserted = skipped = 0
    for pc in data.get("proscons", []):
        vid = pc.get("vote_id")
        item = conn.execute("SELECT legislative_item FROM vote WHERE vote_id=?", (vid,)).fetchone()
        if not item:
            skipped += 1
            continue
        corpus = " ".join(x["t"] for x in conn.execute(
            "SELECT text t FROM speech WHERE legislative_item=? AND text IS NOT NULL",
            (item["legislative_item"],)))
        bad = False
        for side in ("pro", "con"):
            for a in pc.get(side, []):
                q = a.get("quote")
                if q and q not in corpus:
                    bad = True
        if bad:
            skipped += 1
            continue
        conn.execute(
            "INSERT OR REPLACE INTO analysis_vote_proscons(vote_id,pro_json,con_json,note,"
            "model,computed_at) VALUES(?,?,?,?,?,?)",
            (vid, json.dumps(pc.get("pro", []), ensure_ascii=False),
             json.dumps(pc.get("con", []), ensure_ascii=False), pc.get("note"), model, NOW()))
        inserted += 1
    conn.commit()
    return {"inserted": inserted, "skipped_quote_mismatch": skipped}

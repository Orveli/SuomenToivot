"""M24 — Lakiselittäjä. Kääntää hallituksen esityksen (HE) arkikielelle:
mikä muuttuu, keitä koskee, mistä kiisteltiin. Lähteistetty esityksen
pääasialliseen sisältöön ja salikeskustelun lainauksiin; ei ennusteta
vaikutuksia eikä esitetä motiiveja.

Toimii ilman avainta pelkän välimuistin/demon varassa. Aja: km llm-explain --limit N
"""
from __future__ import annotations

import datetime as dt
import json

from .llm import LLMRunner

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
MAX_SUMMARY = 3000
MAX_SPEECH = 700
N_SPEECHES = 8

SYSTEM = (
    "Olet selkokielen toimittaja. Selitä suomalainen hallituksen esitys (HE) tavalliselle "
    "äänestäjälle. Säännöt:\n"
    "- Käytä VAIN annettua esityksen sisältöä ja salipuheiden lainauksia. Älä keksi vaikutuksia.\n"
    "- 'what_changes': mikä konkreettisesti muuttuu (selkokieli, lyhyt).\n"
    "- 'who_affected': keitä muutos koskee.\n"
    "- 'contested': mistä salissa kiisteltiin — esitä molemmat puolet jos ne löytyvät, "
    "nimeä puhuja ja liitä lainaus. Jos kiistaa ei näy aineistossa, kerro se.\n"
    "- 'sources': lista {type, ref, quote} jokaiselle väitteelle, joka nojaa puheeseen.\n"
    "- Älä ennusta tulevaa, älä arvioi onko laki hyvä, älä esitä motiiveja. Kuvaileva ja neutraali."
)

TOOL = {
    "name": "selita_laki",
    "description": "Selitä HE arkikielellä lähdelainauksin.",
    "input_schema": {
        "type": "object",
        "properties": {
            "what_changes": {"type": "string"},
            "who_affected": {"type": "string"},
            "contested": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "object", "properties": {
                "type": {"type": "string", "description": "esim. 'esitys' tai 'puhe'"},
                "ref": {"type": "string", "description": "esim. puhujan nimi tai 'HE'"},
                "quote": {"type": "string"}}, "required": ["type", "quote"]}},
        },
        "required": ["what_changes", "who_affected", "contested"],
    },
}


def _candidate_items(conn, limit):
    sql = ("SELECT l.eduskunta_tunnus item, l.title, l.summary FROM legislation l "
           "WHERE l.summary IS NOT NULL AND length(l.summary) > 120 "
           "AND l.eduskunta_tunnus IN (SELECT DISTINCT legislative_item FROM vote "
           "WHERE legislative_item IS NOT NULL) ORDER BY l.eduskunta_tunnus")
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def compute_explainers(conn, *, limit=None, model=None, max_calls=None) -> dict:
    runner = LLMRunner(conn, model=model, max_calls=max_calls)
    n = 0
    for it in _candidate_items(conn, limit):
        speeches = conn.execute(
            "SELECT first_name, last_name, party, text FROM speech WHERE legislative_item=? "
            "AND person_id IS NOT NULL AND length(text)>300 ORDER BY length(text) DESC LIMIT ?",
            (it["item"], N_SPEECHES)).fetchall()
        debate = "\n\n".join(
            f"{s['first_name']} {s['last_name']} ({s['party']}): {s['text'][:MAX_SPEECH]}"
            for s in speeches)
        user = (f"Säädös: {it['item']}\n\nEsityksen pääasiallinen sisältö:\n"
                f"{(it['summary'] or '')[:MAX_SUMMARY]}\n\nSalikeskustelua:\n{debate}")
        try:
            out = runner.extract(SYSTEM, user, TOOL)
        except Exception:
            break
        if out is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO analysis_bill_explainer(legislative_item,what_changes,"
            "who_affected,contested,sources_json,model,computed_at) VALUES(?,?,?,?,?,?,?)",
            (it["item"], out.get("what_changes"), out.get("who_affected"), out.get("contested"),
             json.dumps(out.get("sources", []), ensure_ascii=False), runner.model, NOW()))
        n += 1
        conn.commit()
    return {"explainers": n, **runner.stats()}


def load_explainer_demo(conn, path) -> dict:
    """Lataa käsin varmennettu lakiselittäjä-demo. Integriteetti: jokaisen lähde-
    lainauksen on oltava sanatarkka osa jotakin saman säädöksen puhetta tai esityksen
    sisältöä."""
    data = json.loads(open(path, encoding="utf-8").read())
    model = data.get("model_label", "käsin varmennettu demo-otos")
    inserted = skipped = 0
    for e in data.get("explainers", []):
        item = e["legislative_item"]
        corpus = " ".join(r["t"] for r in conn.execute(
            "SELECT text t FROM speech WHERE legislative_item=? AND text IS NOT NULL", (item,)))
        leg = conn.execute("SELECT summary FROM legislation WHERE eduskunta_tunnus=?",
                           (item,)).fetchone()
        if leg and leg["summary"]:
            corpus += " " + leg["summary"]
        bad = [s for s in e.get("sources", []) if s.get("quote") and s["quote"] not in corpus]
        if bad:
            skipped += 1
            continue
        conn.execute(
            "INSERT OR REPLACE INTO analysis_bill_explainer(legislative_item,what_changes,"
            "who_affected,contested,sources_json,model,computed_at) VALUES(?,?,?,?,?,?,?)",
            (item, e["what_changes"], e["who_affected"], e.get("contested"),
             json.dumps(e.get("sources", []), ensure_ascii=False), model, NOW()))
        inserted += 1
    conn.commit()
    return {"inserted": inserted, "skipped_quote_mismatch": skipped}

"""M1 — Kanta-resolveri. Poimii puheista konkreettiset väittämät ja kannan
(puolesta/vastaan/ehdollinen/ei_kantaa), jokainen suoralla lainauksella tuettuna.

Tämä on se mitä pelkkä sanahaku ei voi: sanahaku löytää MAININNAN, tämä erottaa
KANNAN (myös ehdollisen) ja vaatii todistuslainauksen.

Ilman API-avainta moduuli toimii pelkän välimuistin varassa (ei tuotantokutsuja):
jo lasketut tulokset luetaan, uusia ei muodosteta. Aja: km llm-stance --limit N
"""
from __future__ import annotations

import datetime as dt

from .llm import LLMRunner

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
MAX_SPEECH_CHARS = 6000  # pitkät puheet katkaistaan (kustannus + konteksti)

SYSTEM = (
    "Olet huolellinen politiikan analyytikko. Tehtäväsi on poimia suomalaisesta "
    "eduskuntapuheesta KONKREETTISET poliittiset väittämät, joihin puhuja ottaa kannan. "
    "Säännöt, joita on noudatettava ehdottomasti:\n"
    "- Palauta vain väittämät, joissa on selkeä kanta. Jos kantaa ei ole, palauta tyhjä lista.\n"
    "- 'stance' on tasan yksi: 'puolesta', 'vastaan', 'ehdollinen' tai 'ei_kantaa'.\n"
    "- 'ehdollinen' edellyttää, että kerrot ehdon 'conditional_note'-kenttään.\n"
    "- Jokaisessa väittämässä on oltava 'evidence_quote': SANATARKKA, suoraan tekstistä "
    "kopioitu lainaus (älä muuta sanoja). Jos et löydä lainausta, älä lisää väittämää.\n"
    "- ÄLÄ päättele motiiveja, vilpittömyyttä tai luonnetta. Kuvaile vain mitä sanotaan.\n"
    "- Älä keksi mitään tekstin ulkopuolelta. Epävarmuus → matala 'confidence'."
)

TOOL = {
    "name": "kirjaa_kannat",
    "description": "Kirjaa puheesta poimitut väittämät ja kannat lähdelainauksin.",
    "input_schema": {
        "type": "object",
        "properties": {
            "propositions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "proposition": {"type": "string",
                                        "description": "Konkreettinen asia, johon kanta otetaan (lyhyt)."},
                        "stance": {"type": "string",
                                   "enum": ["puolesta", "vastaan", "ehdollinen", "ei_kantaa"]},
                        "conditional_note": {"type": "string",
                                             "description": "Ehto, jos stance=ehdollinen, muuten tyhjä."},
                        "evidence_quote": {"type": "string",
                                           "description": "Sanatarkka lainaus puheesta."},
                        "confidence": {"type": "number", "description": "0..1"},
                    },
                    "required": ["proposition", "stance", "evidence_quote", "confidence"],
                },
            }
        },
        "required": ["propositions"],
    },
}


def _candidate_speeches(conn, limit, only_with_votes=True):
    """Puheet, joilla on säädöskohde. only_with_votes=True rajaa niihin, joihin
    liittyy äänestys (M2:n hyödynnettävä joukko)."""
    sql = (
        "SELECT s.id, s.person_id, s.legislative_item, s.text, s.started_at "
        "FROM speech s WHERE s.person_id IS NOT NULL AND s.text IS NOT NULL "
        "AND length(s.text) > 200 AND s.legislative_item IS NOT NULL AND s.legislative_item<>'' ")
    if only_with_votes:
        sql += ("AND s.legislative_item IN (SELECT DISTINCT legislative_item FROM vote "
                "WHERE legislative_item IS NOT NULL AND legislative_item<>'') ")
    sql += "ORDER BY s.id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def export_candidates(conn, *, limit=40, out=None, clean_votes_only=True,
                      max_chars=2600) -> dict:
    """Vie analysoitavat puheet JSON-tiedostoon Claude Code -analyysiä varten
    (ei API-avainta — analyysin tuottaa kielimalli ajon aikana). clean_votes_only
    priorisoi puheet, joiden säädöksellä on yksiselitteinen hyväksyntä/hylkäys-
    äänestys (M2:n hyödyllisin joukko). Ohittaa jo analysoidut puheet."""
    import json
    where_clean = ""
    if clean_votes_only:
        where_clean = (
            " AND s.legislative_item IN (SELECT DISTINCT legislative_item FROM vote "
            "WHERE is_procedural=0 AND (lower(title) LIKE 'hyväksyminen / hylk%' "
            "OR (lower(title) LIKE 'mietintö /%' AND lower(title) LIKE '%hylk%')))")
    rows = conn.execute(
        "SELECT s.id, s.first_name, s.last_name, s.party, s.legislative_item, s.text "
        "FROM speech s WHERE s.person_id IS NOT NULL AND s.text IS NOT NULL "
        "AND length(s.text) > 300 AND s.legislative_item IS NOT NULL AND s.legislative_item<>'' "
        "AND s.id NOT IN (SELECT speech_id FROM analysis_speech_stance)" + where_clean +
        " ORDER BY s.legislative_item, s.id LIMIT ?", (int(limit),)).fetchall()
    batch = [{"speech_id": r["id"], "legislative_item": r["legislative_item"],
              "speaker": f"{r['first_name']} {r['last_name']} ({r['party']})",
              "text": r["text"][:max_chars]} for r in rows]
    payload = {"_instructions": SYSTEM, "_schema": "ks. analysis_speech_stance; "
               "tuota tiedosto jossa model_label + stances:[{speech_id, legislative_item, "
               "proposition, stance(puolesta/vastaan/ehdollinen/ei_kantaa), conditional_note, "
               "evidence_quote (SANATARKKA), confidence}]", "candidates": batch}
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if out:
        open(out, "w", encoding="utf-8").write(text)
    return {"candidates": len(batch), "out": out}


def load_stance_demo(conn, path) -> dict:
    """Lataa käsin varmennetut kannat (demo-otos) analysis_speech_stance-tauluun.
    Integriteetti: rivi hylätään, jos evidence_quote ei ole SANATARKKA osa puheen
    tekstiä. Idempotentti per speech_id."""
    import json
    data = json.loads(open(path, encoding="utf-8").read())
    model = data.get("model_label", "käsin varmennettu demo-otos")
    inserted = skipped = 0
    for s in data.get("stances", []):
        sp = conn.execute("SELECT id, person_id, text FROM speech WHERE id=?",
                          (s["speech_id"],)).fetchone()
        if sp is None or not sp["text"] or s["evidence_quote"] not in sp["text"]:
            skipped += 1
            continue
        conn.execute("DELETE FROM analysis_speech_stance WHERE speech_id=? AND proposition=?",
                     (sp["id"], s.get("proposition")))
        conn.execute(
            "INSERT INTO analysis_speech_stance(speech_id,person_id,legislative_item,"
            "proposition,stance,conditional_note,evidence_quote,confidence,model,computed_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (sp["id"], sp["person_id"], s["legislative_item"], s.get("proposition"),
             s["stance"], s.get("conditional_note"), s["evidence_quote"],
             float(s.get("confidence") or 0.0), model, NOW()))
        inserted += 1
    conn.commit()
    return {"inserted": inserted, "skipped_quote_mismatch": skipped}


def compute_stance(conn, *, limit=None, model=None, max_calls=None, only_with_votes=True) -> dict:
    runner = LLMRunner(conn, model=model, max_calls=max_calls)
    rows = _candidate_speeches(conn, limit, only_with_votes)
    n_speeches = 0
    n_props = 0
    for r in rows:
        user = (f"Säädöskohde: {r['legislative_item']}\n\n"
                f"Puheenvuoro:\n{r['text'][:MAX_SPEECH_CHARS]}")
        try:
            out = runner.extract(SYSTEM, user, TOOL)
        except Exception:
            break  # budjetti täynnä tms. → lopeta siististi, säilytä tehty työ
        if out is None:
            continue  # ei avainta eikä välimuistia → ohita
        # idempotentti: poista puheen aiemmat rivit ennen uusien kirjausta
        conn.execute("DELETE FROM analysis_speech_stance WHERE speech_id=?", (r["id"],))
        for p in out.get("propositions", []):
            if not p.get("evidence_quote") or p.get("stance") not in (
                    "puolesta", "vastaan", "ehdollinen", "ei_kantaa"):
                continue
            conn.execute(
                "INSERT INTO analysis_speech_stance(speech_id,person_id,legislative_item,"
                "proposition,stance,conditional_note,evidence_quote,confidence,model,computed_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (r["id"], r["person_id"], r["legislative_item"], p.get("proposition"),
                 p["stance"], p.get("conditional_note"), p["evidence_quote"],
                 float(p.get("confidence") or 0.0), runner.model, NOW()))
            n_props += 1
        n_speeches += 1
        conn.commit()
    return {"speeches_processed": n_speeches, "propositions": n_props, **runner.stats()}

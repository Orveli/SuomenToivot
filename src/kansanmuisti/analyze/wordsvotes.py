"""M2 + M3 — Sanat vs. äänet -tilikirja.

Yhdistää M1:n poimiman puhekannan saman säädöksen äänestykseen. Sovitus on
DETERMINISTINEN ja läpinäkyvä (eksplisiittinen sääntö, ei LLM-arvausta) — kun
kannat on kerran poimittu, tämä ajetaan ilman API-avainta.

Reilu kohtelu (M3):
- Menettelyäänestykset ja muutosesitykset eivät kartu suoraan lakikannaksi →
  'konteksti' (Jaa/Ei voi tarkoittaa eri asiaa kuin lain kannatus).
- Tyhjä/Poissa → 'ei_riitä'.
- Jos kanta ja ääni ovat ristiriidassa MUTTA puheessa on avoin hallituskuri-/
  kompromissisignaali ("hallitusvastuun vuoksi", "vastentahtoisesti äänestän") →
  'vastentahtoinen', ei 'ristiriita'. Näin avointa kompromissia ei leimata.

Tämä on se mitä sanahaku ei voi: se ei tiedä koskeeko ääni samaa asiaa kuin puhe,
eikä erota vastentahtoista kuria aidosta ristiriidasta.
"""
from __future__ import annotations

import datetime as dt

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731

# Läpinäkyvä leksikko: VAIN yksiselitteiset, oman äänestyspäätöksen vastentahtoi-
# suutta ilmaisevat MONISANAFRAASIT. Yksittäissanat (esim. "vastentahtoisesti",
# "kompromissi", "ryhmäkuri") tuottavat vääriä osumia, koska ne kuvaavat usein
# jotain muuta asiaa kuin puhujan omaa ääntä → niitä ei käytetä. Aito vastentahtoi-
# suuden tunnistus jää LLM-ajolle; tämä deterministinen heuristiikka on tarkoituk-
# sella varovainen (mieluummin "ristiriita" kuin väärä "vastentahtoinen").
RELUCTANCE_MARKERS = [
    "hallitusvastuun vuoksi", "hallitusvastuun nimissä", "vastoin omaa kantaani",
    "vastoin omaa näkemystäni", "en pidä tästä mutta", "en kannata mutta äänestän",
    "äänestän puolesta vaikka", "äänestän vastentahtoisesti", "joudun äänestämään puolesta",
    "hampaat irvessä", "kokonaisuuden vuoksi äänestän", "ryhmäkurin vuoksi",
]


def _reluctant(text: str | None) -> str | None:
    if not text:
        return None
    low = text.lower()
    for m in RELUCTANCE_MARKERS:
        if m in low:
            return m
    return None


def _dominant_stance(rows):
    """Yhdistä henkilön kannat samasta säädöksestä yhdeksi edustavaksi kannaksi.
    Palauta (stance, edustava rivi) tai (None, None)."""
    score = {"puolesta": 0.0, "vastaan": 0.0}
    best = {}
    for r in rows:
        st = r["stance"]
        if st in score:
            score[st] += float(r["confidence"] or 0.0) + 0.01
        if st not in best or (r["confidence"] or 0) > (best[st]["confidence"] or 0):
            best[st] = r
    if score["puolesta"] == 0 and score["vastaan"] == 0:
        # vain ehdollinen / ei_kantaa
        for st in ("ehdollinen", "ei_kantaa"):
            if st in best:
                return st, best[st]
        return None, None
    if score["puolesta"] > 0 and score["vastaan"] > 0:
        ratio = min(score.values()) / max(score.values())
        if ratio > 0.5:  # molempia suunnilleen yhtä paljon → ehdollinen/sekava
            return "ehdollinen", best.get("puolesta") or best.get("vastaan")
    dom = "puolesta" if score["puolesta"] >= score["vastaan"] else "vastaan"
    return dom, best[dom]


def _is_bill_passage(title):
    """Yksiselitteinen lain sisältöäänestys: JAA = lain hyväksyntä, EI = hylkäys.
    Vain nämä mapataan suoraan. Lausuma-/muutosehdotusäänestyksissä Ei EI tarkoita
    lain vastustamista (esim. opposition ponsi) → ne jätetään 'konteksti'-luokkaan,
    jottei reilua kantaa leimata virheellisesti ristiriidaksi."""
    if not title:
        return False
    parts = title.split("/")
    jaa = parts[0].strip().lower()
    ei = parts[1].strip().lower() if len(parts) > 1 else ""
    return (jaa.startswith("hyväksy") or jaa.startswith("mietintö")) and \
           ("hylk" in ei or "hyljät" in ei)


def _classify(stance, vote_value, is_procedural, stage, reluctance, title):
    """Eksplisiittinen sovitussääntö → (alignment, context_note)."""
    if vote_value in ("Tyhjää", "Poissa") or not vote_value:
        return "ei_riitä", f"ääni oli {vote_value or 'tuntematon'}"
    if is_procedural:
        return "konteksti", "menettelyäänestys — ei suoraan lain kannatus"
    if not _is_bill_passage(title):
        return "konteksti", "ei yksiselitteinen lain sisältöäänestys (esim. lausuma/muutosehdotus)"
    if stance in ("ehdollinen", "ei_kantaa", None):
        return "konteksti", "puheen kanta ehdollinen/avoin"
    # Kanoninen: Jaa = mietinnön (lain) mukainen, Ei = vaihtoehtoinen ehdotus.
    supports_bill = (vote_value == "Jaa")
    aligned = (stance == "puolesta" and supports_bill) or (stance == "vastaan" and not supports_bill)
    if aligned:
        return "linjassa", "Jaa = lain hyväksyntä, Ei = hylkäys"
    # ristiriita — mutta avoin kompromissi?
    if reluctance:
        return "vastentahtoinen", f"puheessa avoin kompromissisignaali: \"{reluctance}\""
    return "ristiriita", "puheen kanta ja ääni eri suuntiin (hyväksyntä/hylkäys)"


def compute_words_votes(conn) -> dict:
    """Rakenna tilikirja uudelleen M1:n kannoista ja äänestysdatasta."""
    conn.execute("DELETE FROM analysis_words_votes")
    # ryhmittele kannat (henkilö, säädöskohde)
    pairs = conn.execute(
        "SELECT DISTINCT person_id, legislative_item FROM analysis_speech_stance "
        "WHERE person_id IS NOT NULL AND legislative_item IS NOT NULL AND legislative_item<>''"
    ).fetchall()
    n = 0
    for pr in pairs:
        pid, item = pr["person_id"], pr["legislative_item"]
        srows = conn.execute(
            "SELECT ss.*, sp.text AS speech_text, sp.started_at AS sdate "
            "FROM analysis_speech_stance ss JOIN speech sp ON sp.id=ss.speech_id "
            "WHERE ss.person_id=? AND ss.legislative_item=?", (pid, item)).fetchall()
        stance, rep = _dominant_stance(srows)
        if rep is None:
            continue
        reluctance = _reluctant(rep["speech_text"])
        votes = conn.execute(
            "SELECT vote_id, title, session_date, treatment_stage, is_procedural FROM vote "
            "WHERE legislative_item=?", (item,)).fetchall()
        for v in votes:
            vr = conn.execute(
                "SELECT vote_value FROM vote_record WHERE vote_id=? AND person_id=?",
                (v["vote_id"], pid)).fetchone()
            vote_value = vr["vote_value"] if vr else None
            align, note = _classify(stance, vote_value, v["is_procedural"],
                                    v["treatment_stage"], reluctance, v["title"])
            conn.execute(
                "INSERT INTO analysis_words_votes(person_id,vote_id,speech_id,legislative_item,"
                "speech_stance,speech_quote,speech_date,vote_value,vote_date,vote_stage,"
                "alignment,context_note,confidence,model,computed_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, v["vote_id"], rep["speech_id"], item, stance, rep["evidence_quote"],
                 rep["sdate"], vote_value, v["session_date"], v["treatment_stage"],
                 align, note, rep["confidence"], rep["model"], NOW()))
            n += 1
    conn.commit()
    counts = {r["alignment"]: r["c"] for r in conn.execute(
        "SELECT alignment, COUNT(*) c FROM analysis_words_votes GROUP BY alignment")}
    return {"rows": n, "by_alignment": counts}

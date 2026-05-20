"""M23 — "Kysy edustajasta" -haku (RAG). Kansalainen kysyy luonnollisella kielellä;
vastaus muodostetaan VAIN haetuista, lähteistetyistä puheista, viitteet mukana.

Kaksivaiheinen, jotta ydin toimii ilman API-avainta:
  1. Haku (retrieve): kokotekstihaku (FTS5) puheista — toimii aina, näyttää
     lähteistetyt katkelmat. Tämä on jo arvokasta ilman kielimallia.
  2. Vastaus (answer): kielimalli tiivistää vastauksen VAIN haetuista katkelmista,
     viittaa numeroin [n], kieltäytyy jos tieto ei löydy. Vaatii avaimen.

Periaatteet: ei hallusinaatiota (vain konteksti), ei motiiveja, ei äänestysohjeita,
jokainen väite jäljitettävissä puheeseen. Vastaus merkitään tekoälyn tuottamaksi.
"""
from __future__ import annotations

from .llm import LLMRunner

MAX_PASSAGE = 700

SYSTEM = (
    "Olet neutraali avustaja, joka vastaa kansalaisen kysymykseen suomalaisesta "
    "kansanedustajasta VAIN annettujen puhekatkelmien perusteella. Tiukat säännöt:\n"
    "- Käytä ainoastaan numeroituja katkelmia. Älä käytä mitään muuta tietoa.\n"
    "- Viittaa jokaiseen väitteeseen katkelman numerolla, esim. [2].\n"
    "- Jos vastaus ei löydy katkelmista, aseta answerable=false ja sano selkeästi, "
    "ettei aineistossa ole tietoa asiasta. ÄLÄ arvaa.\n"
    "- Älä esitä motiiveja, ennusteita äläkä äänestysohjeita. Kuvaileva ja neutraali.\n"
    "- Vastaa selkeällä, ymmärrettävällä suomella."
)

TOOL = {
    "name": "vastaa",
    "description": "Vastaa kysymykseen vain annetuista katkelmista, viitteet mukana.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answerable": {"type": "boolean", "description": "Löytyykö vastaus katkelmista."},
            "answer": {"type": "string", "description": "Vastaus selkokielellä, viitteet [n]."},
            "used_passages": {"type": "array", "items": {"type": "integer"},
                              "description": "Käytettyjen katkelmien numerot."},
        },
        "required": ["answerable", "answer"],
    },
}


def _fts(q: str) -> str:
    tokens = [t for t in (q or "").replace('"', " ").split() if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'


def retrieve(conn, q: str, pid: int | None = None, k: int = 8) -> list[dict]:
    """Kokotekstihaku puheista. Toimii ilman API-avainta."""
    params: list = [_fts(q)]
    extra = ""
    if pid:
        extra = " AND s.person_id=?"
        params.append(pid)
    params.append(k)
    try:
        rows = conn.execute(
            "SELECT s.id, (s.first_name||' '||s.last_name) AS who, s.party, s.started_at, "
            "s.legislative_item, substr(s.text,1,?) AS text, s.person_id "
            "FROM speech_fts JOIN speech s ON s.id=speech_fts.rowid "
            "WHERE speech_fts MATCH ?" + (extra) + " ORDER BY rank LIMIT ?",
            [MAX_PASSAGE] + params).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def answer(conn, q: str, passages: list[dict], *, model=None, max_calls=None) -> dict | None:
    """Tiivistä vastaus haetuista katkelmista. None jos avainta/välimuistia ei ole."""
    if not passages:
        return None
    runner = LLMRunner(conn, model=model, max_calls=max_calls)
    ctx = "\n\n".join(
        f"[{i+1}] {p['who']} ({p.get('party') or '?'}, {(p.get('started_at') or '')[:10]}"
        f"{', ' + p['legislative_item'] if p.get('legislative_item') else ''}): {p['text']}"
        for i, p in enumerate(passages))
    user = f"Kysymys: {q}\n\nKatkelmat:\n{ctx}"
    try:
        out = runner.extract(SYSTEM, user, TOOL)
    except Exception:
        return None
    return out

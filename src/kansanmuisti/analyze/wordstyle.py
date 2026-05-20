"""Puhetyyli: täytesanojen ja kirosanojen laskenta per edustaja.

Kuvaileva, läpinäkyvä laskenta (leksikot näkyvissä alla). Normalisointi per 1000
sanaa, jotta vertailu on reilu eri pituisten urien välillä.

REHELLISET RAJAUKSET:
- Täysistuntopöytäkirjat (PTK) ovat TOIMITETTUJA: osa puhutuista täytesanoista
  (öö, niinku, tota) on jo poistettu puhtaaksikirjoituksessa → todelliset puhetavat
  ovat "siistimpiä" tekstissä kuin salissa. Mittaamme mitä tekstiin jäi.
- Tarkka sananmuototäsmäys (ei prefiksi) väärien osumien välttämiseksi, mutta
  konteksti voi silti tuottaa kohinaa (esim. lainaus, paikannimi, sävyttävä käyttö).
- EI arvottava: "kirosana"-luku ei kerro pätevyydestä tai luonteesta — se on
  kuvaileva sanalaskenta julkisesta pöytäkirjasta.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from .classify import normalize

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
LEXICON_VERSION = "1"
MIN_WORDS_LEADERBOARD = 5000  # vertailuun vaaditaan väh. näin monta sanaa

# --- Täytesanat / täytefraasit (puhekielen täytteet, jotka selviävät toimituksesta) ---
FILLER_WORDS = {
    "niinku", "niinkun", "niinkö", "tota", "tuota", "tuotanoin", "siis", "tavallaan",
    "tietysti", "tietenkin", "oikeastaan", "periaatteessa", "käytännössä", "öö", "ää",
    "tuolla", "tämmöinen", "tämmönen", "semmonen", "semmoinen", "kaiketi",
}
FILLER_PHRASES = [
    ("itse", "asiassa"), ("totta", "kai"), ("ikään", "kuin"), ("niin", "sanotusti"),
    ("niin", "sanottu"), ("tota", "noin"), ("tuota", "noin"), ("niin", "kuin"),
    ("sillä", "tavalla"), ("sillä", "lailla"), ("tuolla", "tavalla"), ("no", "niin"),
]

# --- Kirosanat / voimasanat (suomalaiset, lievät -> vahvat; yleisiä taivutusmuotoja) ---
SWEAR_WORDS = {
    "perkele", "perkeleen", "perkelettä", "perkeleet", "perskele",
    "helvetti", "helvetin", "helvettiä", "helvettiin", "helvetissä",
    "vittu", "vitun", "vittua", "vituttaa", "vitutus",
    "saatana", "saatanan", "saatanaa",
    "jumalauta", "jumankauta", "jumaliste",
    "paska", "paskaa", "paskat", "paskan", "paskamainen", "paskaks",
    "hitto", "hiton", "hittoa", "hittolainen",
    "piru", "pirun", "pirua", "pirut", "pirullinen",
    "perhana", "perhanan", "perhanaa",
    "saamari", "saamarin", "hemmetti", "hemmetin", "helkkari", "helkkarin",
    "jukra", "jukolauta", "hitsi", "kirottu", "riivattu",
}
SWEAR_PHRASES = [("voi", "perkele"), ("voi", "helvetti")]


def _count(tokens, words, phrases):
    """Palauta (yhteismäärä, Counter osumista) annetulle leksikolle."""
    hits = Counter()
    for t in tokens:
        if t in words:
            hits[t] += 1
    n = len(tokens)
    for parts in phrases:
        k = len(parts)
        for i in range(n - k + 1):
            if all(tokens[i + j] == parts[j] for j in range(k)):
                hits[" ".join(parts)] += 1
    return sum(hits.values()), hits


def compute_word_style(conn) -> dict:
    per_person_words = defaultdict(int)
    cat_total = defaultdict(lambda: defaultdict(int))      # (pid)->{cat:count}
    cat_breakdown = defaultdict(lambda: defaultdict(Counter))  # pid->cat->Counter
    for r in conn.execute(
            "SELECT person_id, text FROM speech WHERE person_id IS NOT NULL AND text IS NOT NULL"):
        pid = r["person_id"]
        toks = normalize(r["text"])
        per_person_words[pid] += len(toks)
        for cat, (words, phrases) in (("filler", (FILLER_WORDS, FILLER_PHRASES)),
                                      ("swear", (SWEAR_WORDS, SWEAR_PHRASES))):
            total, hits = _count(toks, words, phrases)
            if total:
                cat_total[pid][cat] += total
                cat_breakdown[pid][cat].update(hits)

    conn.execute("DELETE FROM analysis_word_usage")
    conn.execute("DELETE FROM analysis_word_hits")
    n = 0
    for pid, nwords in per_person_words.items():
        # vain rekisterissä olevat henkilöt
        if not conn.execute("SELECT 1 FROM person WHERE person_id=?", (pid,)).fetchone():
            continue
        for cat in ("filler", "swear"):
            cnt = cat_total[pid].get(cat, 0)
            per1000 = (1000.0 * cnt / nwords) if nwords else 0.0
            conn.execute(
                "INSERT OR REPLACE INTO analysis_word_usage"
                "(person_id,category,n_hits,n_words,per_1000,lexicon_version,computed_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (pid, cat, cnt, nwords, round(per1000, 3), LEXICON_VERSION, NOW()))
            for word, c in cat_breakdown[pid][cat].most_common(20):
                conn.execute(
                    "INSERT OR REPLACE INTO analysis_word_hits(person_id,category,word,n) VALUES(?,?,?,?)",
                    (pid, cat, word, c))
            n += 1
    conn.commit()
    return {"rows": n, "lexicon_version": LEXICON_VERSION,
            "filler_terms": len(FILLER_WORDS) + len(FILLER_PHRASES),
            "swear_terms": len(SWEAR_WORDS) + len(SWEAR_PHRASES)}

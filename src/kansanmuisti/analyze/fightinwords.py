"""Puolueita erottava kieli ("fightin' words").

Menetelmä: log-odds-suhde informatiivisella Dirichlet-priorilla (Monroe, Colaresi
& Quinn 2008). Jokaiselle sanalle lasketaan z-arvo, joka kertoo kuinka vahvasti
sana on yli- tai aliedustettu ryhmän puheissa muihin verrattuna. Priori vakauttaa
harvinaiset sanat, joten tulokset eivät ole pelkkiä satunnaisia harvinaisuuksia.

Läpinäkyvä ja kuvaileva: jokainen "erottava sana" on aito ryhmän puheissa
yliedustettu sana. EI tulkitse sävyä eikä motiivia.

Rajaus: tokenit ovat taivutusmuotoja (suomen taivutus hajauttaa laskentaa);
esitämme todelliset käytetyt sanat. Stopword-lista poistaa yleissanat ja
istuntorutiinin ("arvoisa puhemies" jne.).
"""
from __future__ import annotations

import datetime as dt
import math
from collections import Counter, defaultdict

from .classify import normalize

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731

MIN_GLOBAL_COUNT = 30   # sana huomioidaan vain jos esiintyy väh. näin usein koko aineistossa
TOP_N = 30              # talletettavien erottavien sanojen määrä per ryhmä
MIN_WORD_LEN = 3

# Suomen yleissanat + eduskuntarutiini (poistetaan)
STOPWORDS = set("""
ja on ei että se tämä joka mutta kun niin myös vaan jos hän me te he ne sen tämän
olen oli ollut ovat oli olla olleet onko emme ette eivät en et emmekö
kyllä no siis vielä jo nyt sitten tässä tämä tuo nämä noita näitä tätä tuota
arvoisa puhemies rouva herra ledamot talman edustaja edustajat ministeri valtioneuvosto
kysymys vastaus asia asian asiaa asiat tässä salissa kiitos kiitoksia
minä sinä hänen meidän teidän heidän minun sinun itse oma omat
mikä mitä mikäli koska jotta vai tai sekä eikä jotka joiden joita jonka mihin missä
ihan oikein todella aivan juuri vain vähän paljon enemmän kaikki kaikkien moni monet
tulee pitää voi voidaan saada tehdä ottaa antaa mennä tulla olisi pitäisi täytyy
hyvä hyvin parempi paras suuri pieni uusi vanha sama eri muu muut muiden
tämän tällä tällaisia tällainen sellaisia sellainen sellaista tällaista
kun jolloin koska siksi siis siten näin niin kuten esimerkiksi muun muassa muassa
puhuja puheenvuoro puheenvuoron edellä mainittu kohta pykälä momentti
suomen suomi suomessa maan maassa täällä siellä tänään eilen huomenna
puolue puolueen hallitus hallituksen oppositio eduskunta eduskunnan
prosenttia miljoonaa miljardia euroa vuoden vuonna vuotta aikana osalta suhteen
""".split())

# Puolueiden omat nimet — triviaalisti erottavia, poistetaan paremman signaalin vuoksi
STOPWORDS |= set("""
perussuomalaiset perussuomalaisten perussuomalainen perussuomalaisia
vihreät vihreiden vihreä vihreille
kokoomus kokoomuksen kokoomuksessa kokoomuksesta kokoomuslaiset
sdp sosiaalidemokraatit sosiaalidemokraattien sosialidemokraatit demarit
vasemmistoliitto vasemmistoliiton vasemmistoliitossa vasemmisto vasemmiston
keskusta keskustan keskustassa keskustalaiset
kristillisdemokraatit kristillisdemokraattien rkp kokoomuksenkin
""".split())


def _party_token_counts(conn):
    """Palauta (per_party Counter, per_party total, global Counter)."""
    per_party = defaultdict(Counter)
    totals = defaultdict(int)
    global_counts = Counter()
    for r in conn.execute("SELECT party, text FROM speech WHERE party IS NOT NULL AND text IS NOT NULL"):
        party = r["party"]
        for tok in normalize(r["text"]):
            if len(tok) < MIN_WORD_LEN or tok in STOPWORDS or tok.isdigit():
                continue
            per_party[party][tok] += 1
            totals[party] += 1
            global_counts[tok] += 1
    return per_party, totals, global_counts


def compute_party_words(conn, min_party_total: int = 20000) -> dict:
    """Laske erottavat sanat per ryhmä ja talleta analysis_party_words-tauluun."""
    per_party, totals, global_counts = _party_token_counts(conn)
    # vain ryhmät, joilla riittävästi tekstiä
    parties = [p for p in totals if totals[p] >= min_party_total]
    vocab = {w: c for w, c in global_counts.items() if c >= MIN_GLOBAL_COUNT}
    total_all = sum(global_counts.values())
    # informatiivinen priori: alpha_w suhteessa sanan globaaliin yleisyyteen
    a0 = 1000.0  # priorin kokonaisvahvuus
    alpha = {w: a0 * global_counts[w] / total_all for w in vocab}

    conn.execute("DELETE FROM analysis_party_words")
    n = 0
    for party in parties:
        ci = per_party[party]
        ni = totals[party]
        # "muut" = kaikki paitsi tämä ryhmä
        nj = total_all - ni
        scored = []
        for w in vocab:
            yi = ci.get(w, 0)
            yj = global_counts[w] - yi
            aw = alpha[w]
            # log-odds erotus priorilla
            num_i = yi + aw
            den_i = ni + a0 - yi - aw
            num_j = yj + aw
            den_j = nj + a0 - yj - aw
            if den_i <= 0 or den_j <= 0 or num_i <= 0 or num_j <= 0:
                continue
            delta = math.log(num_i / den_i) - math.log(num_j / den_j)
            var = 1.0 / num_i + 1.0 / num_j
            z = delta / math.sqrt(var)
            scored.append((z, w, yi))
        scored.sort(reverse=True)
        for rank, (z, w, yi) in enumerate(scored[:TOP_N], 1):
            conn.execute(
                "INSERT OR REPLACE INTO analysis_party_words(party,word,zscore,n_party,n_total,rank)"
                " VALUES(?,?,?,?,?,?)", (party, w, round(z, 2), yi, global_counts[w], rank))
            n += 1
    conn.commit()
    return {"parties": len(parties), "words": n, "vocab": len(vocab)}

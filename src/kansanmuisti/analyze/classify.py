"""Läpinäkyvä avainsanapohjainen aiheluokitin (METHODOLOGY.md §1).

Determinismi: sama teksti + sama leksikko → sama tulos.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Dict, List, Tuple

from . import LEXICON_VERSION
from .taxonomy import TAXONOMY, TOPIC_IDS

HARD_THRESHOLD = 0.15
DOMINANCE_RATIO = 0.40
MAX_TOPICS_PER_ITEM = 3
MIN_LEN = 25

_TAG_RE = re.compile(r"<[^>]+>")
_NONWORD_RE = re.compile(r"[^\wäöåÄÖÅ\s-]", re.UNICODE)


def normalize(text: str) -> List[str]:
    if not text:
        return []
    t = unicodedata.normalize("NFC", text).lower()
    t = _TAG_RE.sub(" ", t)
    t = _NONWORD_RE.sub(" ", t)
    return [tok for tok in t.split() if tok]


def _count_positions(tokens: List[str], keyword: str) -> int:
    """Erillisten osumapaikkojen määrä. Monisanainen = peräkkäiset prefiksit."""
    parts = keyword.split()
    if len(parts) == 1:
        kw = parts[0]
        return sum(1 for tok in tokens if tok.startswith(kw))
    n = len(parts)
    hits = 0
    for i in range(len(tokens) - n + 1):
        if all(tokens[i + j].startswith(parts[j]) for j in range(n)):
            hits += 1
    return hits


def score_text(tokens: List[str]) -> Dict[str, float]:
    """Aihepistemäärät kaikille aiheille."""
    denom = math.sqrt(max(len(tokens), MIN_LEN))
    scores: Dict[str, float] = {}
    for slug, (_label, keywords) in TAXONOMY.items():
        if not keywords:
            scores[slug] = 0.0
            continue
        raw = 0.0
        for kw, w in keywords:
            raw += w * _count_positions(tokens, kw)
        scores[slug] = raw / denom
    return scores


def assign_topics(text: str) -> dict:
    """Palauta {topics:[(slug,score,is_primary)], primary, status, scores}."""
    tokens = normalize(text)
    scores = score_text(tokens)
    # ei oteta 'muu'-aihetta mukaan kilpailuun
    ranked = {s: v for s, v in scores.items() if s != "muu"}
    top = max(ranked.values()) if ranked else 0.0
    if top < HARD_THRESHOLD:
        return {"topics": [("muu", 0.0, True)], "primary": "muu",
                "status": "NO_MATCH", "scores": scores}
    cands = [(s, v) for s, v in ranked.items()
             if v >= DOMINANCE_RATIO * top and v >= HARD_THRESHOLD]
    # determinismi: score desc, sitten topicId asc
    cands.sort(key=lambda sv: (-sv[1], TOPIC_IDS[sv[0]]))
    cands = cands[:MAX_TOPICS_PER_ITEM]
    out = [(s, v, i == 0) for i, (s, v) in enumerate(cands)]
    status = "MULTI" if len(cands) > 1 else "SINGLE"
    return {"topics": out, "primary": cands[0][0], "status": status, "scores": scores}


def _vote_text(row, leg_title=None, leg_summary=None) -> str:
    parts = [row["title"], row["item_title"], row["main_item_title"],
             row["treatment_title"], row["legislative_item"], row["extra_title"],
             leg_title, leg_summary]
    return " ".join(p for p in parts if p)


def classify_all(conn) -> dict:
    """Luokittele kaikki puheet ja äänestykset; täytä speech_topic, vote_topic."""
    conn.execute("DELETE FROM speech_topic")
    conn.execute("DELETE FROM vote_topic")
    n_speech = 0
    no_match_speech = 0
    for row in conn.execute("SELECT id, text FROM speech"):
        res = assign_topics(row["text"] or "")
        if res["status"] == "NO_MATCH":
            no_match_speech += 1
        for slug, sc, primary in res["topics"]:
            conn.execute(
                "INSERT OR REPLACE INTO speech_topic(speech_id,topic_id,score,is_primary)"
                " VALUES(?,?,?,?)", (row["id"], TOPIC_IDS[slug], round(sc, 4), int(primary)))
        n_speech += 1
    n_vote = 0
    no_match_vote = 0
    for row in conn.execute(
            "SELECT v.vote_id,v.title,v.item_title,v.main_item_title,v.treatment_title,"
            "v.legislative_item,v.extra_title, l.title AS leg_title, l.summary AS leg_summary"
            " FROM vote v LEFT JOIN legislation l ON l.eduskunta_tunnus=v.legislative_item"):
        res = assign_topics(_vote_text(row, row["leg_title"], row["leg_summary"]))
        if res["status"] == "NO_MATCH":
            no_match_vote += 1
        for slug, sc, primary in res["topics"]:
            conn.execute(
                "INSERT OR REPLACE INTO vote_topic(vote_id,topic_id,score,is_primary)"
                " VALUES(?,?,?,?)", (row["vote_id"], TOPIC_IDS[slug], round(sc, 4), int(primary)))
        n_vote += 1
    conn.commit()
    return {"speeches": n_speech, "votes": n_vote,
            "no_match_speech": no_match_speech, "no_match_vote": no_match_vote,
            "lexicon_version": LEXICON_VERSION}

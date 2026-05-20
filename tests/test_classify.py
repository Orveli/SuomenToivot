"""Aiheluokittimen yksikkötestit (METHODOLOGY.md §1)."""
from kansanmuisti.analyze import classify


def test_normalize_strips_and_tokenizes():
    toks = classify.normalize("Arvoisa puhemies! Terveydenhuolto, hoitotakuu.")
    assert "terveydenhuolto" in toks
    assert "hoitotakuu" in toks
    assert all(t == t.lower() for t in toks)


def test_health_text_classified_as_terveydenhuolto():
    res = classify.assign_topics(
        "Terveydenhuollon rahoitus ja hoitotakuu. Sairaalat ja lääkärit ja hoitajat.")
    assert res["primary"] == "terveydenhuolto"
    assert res["status"] in ("SINGLE", "MULTI")


def test_no_match_returns_muu():
    res = classify.assign_topics("Kissa istui maton päällä ja katseli ulos ikkunasta hiljaa.")
    assert res["primary"] == "muu"
    assert res["status"] == "NO_MATCH"


def test_determinism_same_input_same_output():
    text = "Verotus, tulovero ja veroaste sekä yhteisövero ovat tärkeitä talouskysymyksiä."
    a = classify.assign_topics(text)
    b = classify.assign_topics(text)
    assert a["primary"] == b["primary"]
    assert a["scores"] == b["scores"]


def test_threshold_short_offtopic_text():
    # lyhyt teksti ilman avainsanoja
    res = classify.assign_topics("Hei vaan kaikille.")
    assert res["primary"] == "muu"


def test_multiword_keyword_matches():
    # "tulovero" on yksi sana; testaa monisanainen "julkis talou"
    res = classify.assign_topics(
        "Julkinen talous ja julkis taloutemme alijäämä sekä valtiontalous huolettavat.")
    assert "talous" in [t[0] for t in res["topics"]]

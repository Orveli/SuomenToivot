"""Testit LLM-kerrokselle (M1/M2): luokittelusäännöt, välimuisti, demo-loaderin
lainausvarmennus ja tilikirjan rakennus + web-sivu."""
import json
import os

from kansanmuisti import config
from kansanmuisti.analyze import llm
from kansanmuisti.analyze.stance import load_stance_demo
from kansanmuisti.analyze.wordsvotes import _classify, _is_bill_passage, compute_words_votes

CLEAN = "Hyväksyminen / Hylkääminen"
LAUSUMA = "Mietintö / Lauri Ihalainen, lausumaehdotus"


def test_is_bill_passage():
    assert _is_bill_passage(CLEAN)
    assert _is_bill_passage("Mietintö / X hylkäysehdotus")
    assert not _is_bill_passage(LAUSUMA)
    assert not _is_bill_passage("edustaja A:n ehdotus / edustaja B:n ehdotus")
    assert not _is_bill_passage(None)


def test_classify_rules():
    # puhdas hyväksyntä/hylkäys
    assert _classify("puolesta", "Jaa", 0, "x", None, CLEAN)[0] == "linjassa"
    assert _classify("vastaan", "Ei", 0, "x", None, CLEAN)[0] == "linjassa"
    assert _classify("puolesta", "Ei", 0, "x", None, CLEAN)[0] == "ristiriita"
    # avoin kompromissi → vastentahtoinen, EI ristiriita
    assert _classify("puolesta", "Ei", 0, "x", "hallitusvastuun vuoksi", CLEAN)[0] == "vastentahtoinen"
    # lausumaäänestys → konteksti (Ei ei tarkoita lain vastustusta)
    assert _classify("puolesta", "Ei", 0, "x", None, LAUSUMA)[0] == "konteksti"
    # menettely / tyhjä-poissa / ehdollinen
    assert _classify("puolesta", "Jaa", 1, "x", None, CLEAN)[0] == "konteksti"
    assert _classify("puolesta", "Poissa", 0, "x", None, CLEAN)[0] == "ei_riitä"
    assert _classify("ehdollinen", "Jaa", 0, "x", None, CLEAN)[0] == "konteksti"


def test_llm_cache_and_budget(conn, monkeypatch):
    llm.ensure_cache(conn)
    calls = {"n": 0}

    def fake(system, user, tool, model):
        calls["n"] += 1
        return {"propositions": []}

    monkeypatch.setattr(llm, "_http_call", fake)
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    tool = {"name": "t", "input_schema": {"type": "object", "properties": {}}}
    r = llm.LLMRunner(conn, use_cache_only=False, max_calls=5)
    assert r.extract("sys-uniq", "usr-uniq", tool) == {"propositions": []}
    r.extract("sys-uniq", "usr-uniq", tool)            # sama → välimuistista
    assert calls["n"] == 1 and r.cache_hits == 1
    # ilman avainta välimuistin ohi → None
    r2 = llm.LLMRunner(conn, use_cache_only=True)
    assert r2.extract("toinen", "kysely", tool) is None


def test_demo_loader_verifies_quotes(conn, tmp_path):
    sp = conn.execute("SELECT id, text FROM speech WHERE person_id IS NOT NULL "
                      "AND text IS NOT NULL LIMIT 1").fetchone()
    good = sp["text"][:30]
    payload = {"model_label": "testi-demo", "stances": [
        {"speech_id": sp["id"], "legislative_item": "HE 1/2024 vp",
         "proposition": "ok", "stance": "puolesta", "confidence": 0.9, "evidence_quote": good},
        {"speech_id": sp["id"], "legislative_item": "HE 1/2024 vp",
         "proposition": "bad", "stance": "vastaan", "confidence": 0.5,
         "evidence_quote": "tätä lausetta ei esiinny puheessa lainkaan xyzzy"},
    ]}
    f = tmp_path / "demo.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    res = load_stance_demo(conn, str(f))
    assert res["inserted"] == 1 and res["skipped_quote_mismatch"] == 1


def test_words_votes_ledger(conn):
    sp = conn.execute("SELECT id FROM speech WHERE person_id=1 LIMIT 1").fetchone()
    conn.execute("DELETE FROM analysis_speech_stance")
    conn.execute(
        "INSERT INTO analysis_speech_stance(speech_id,person_id,legislative_item,proposition,"
        "stance,evidence_quote,confidence,model,computed_at) VALUES(?,1,'HE 9/2099 vp','t',"
        "'puolesta','q',0.9,'test','now')", (sp["id"],))
    conn.execute(
        "INSERT INTO vote(vote_id,vp_year,session_date,title,legislative_item,is_procedural,"
        "result_yes,result_no,result_empty,result_absent,result_total,url,fetched_at)"
        " VALUES(900,2099,'2099-01-01',?, 'HE 9/2099 vp',0,1,0,0,0,1,'u','now')", (CLEAN,))
    conn.execute("INSERT INTO vote_record(vote_id,person_id,party,vote_value) "
                 "VALUES(900,1,'kok','Jaa')")
    conn.commit()
    compute_words_votes(conn)
    row = conn.execute("SELECT alignment FROM analysis_words_votes "
                       "WHERE person_id=1 AND vote_id=900").fetchone()
    assert row["alignment"] == "linjassa"


def test_wordsvotes_page(client):
    r = client.get("/sanat-vs-aanet")
    assert r.status_code == 200
    assert "Sanat vs. äänet" in r.text


def test_explainer_demo_quote_check(conn, tmp_path):
    from kansanmuisti.analyze.explain import load_explainer_demo
    sp = conn.execute("SELECT legislative_item, text FROM speech WHERE legislative_item "
                      "IS NOT NULL AND text IS NOT NULL LIMIT 1").fetchone()
    payload = {"model_label": "testi-demo", "explainers": [
        {"legislative_item": sp["legislative_item"], "what_changes": "x", "who_affected": "y",
         "contested": "z", "sources": [{"type": "puhe", "quote": sp["text"][:25]}]},
        {"legislative_item": sp["legislative_item"], "what_changes": "x", "who_affected": "y",
         "contested": "z", "sources": [{"type": "puhe", "quote": "ei esiinny missään qqzz"}]},
    ]}
    f = tmp_path / "ex.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    res = load_explainer_demo(conn, str(f))
    assert res["inserted"] == 1 and res["skipped_quote_mismatch"] == 1


def test_glossary_and_pages(client):
    assert client.get("/sanasto").status_code == 200
    assert client.get("/laki?item=HE 1/2024 vp").status_code == 200  # ei selitystä → notice


def test_rag_retrieve(conn):
    from kansanmuisti.analyze import rag
    hits = rag.retrieve(conn, "terveydenhuolto hoitotakuu")
    assert hits and all("text" in h and h.get("who") for h in hits)
    # answer ilman avainta → None (ei tuotantokutsua)
    assert rag.answer(conn, "kysymys", hits, max_calls=0) is None


def test_ask_page(client):
    r = client.get("/kysy?q=hoitotakuu")
    assert r.status_code == 200
    r2 = client.get("/kysy")  # tyhjä lomake
    assert r2.status_code == 200 and "Kysy edustajasta" in r2.text

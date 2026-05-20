"""Web-integraatiotestit fixture-tietokantaa vasten."""


def test_index_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Kansanmuisti" in r.text


def test_person_page_shows_index_and_sources(client):
    r = client.get("/edustaja/1")
    assert r.status_code == 200
    assert "Anna Aalto" in r.text
    # lasketut luvut merkitään indikaattoriksi
    assert "laskennallinen indikaattori" in r.text
    # lähde näkyvissä
    assert "Lähde" in r.text or "lähde" in r.text


def test_person_promise_alignment_visible(client):
    r = client.get("/edustaja/1")
    # kok-edustajan hoitotakuu-lupaus (henkilö 1 äänesti Jaa äänestyksessä 100 -> tukee)
    assert "hoitotakuu" in r.text.lower() or "Lupaukset vs. teot" in r.text


def test_vote_page_lists_records(client):
    r = client.get("/aanestys/100")
    assert r.status_code == 200
    assert "Edustajakohtaiset äänet" in r.text
    assert "Anna" in r.text


def test_speech_page_full_text(client):
    r = client.get("/puhe/1")
    assert r.status_code == 200
    assert "Terveydenhuolto" in r.text or "terveydenhuol" in r.text.lower()


def test_search_finds_person(client):
    r = client.get("/haku?q=Aalto")
    assert r.status_code == 200
    assert "Anna Aalto" in r.text


def test_search_fts_speech(client):
    r = client.get("/haku?q=hoitotakuu")
    assert r.status_code == 200
    # FTS:n pitäisi löytää puhe
    assert "puhe" in r.text.lower()


def test_topic_page(client):
    r = client.get("/aihe/terveydenhuolto")
    assert r.status_code == 200


def test_coverage_and_methods_pages(client):
    assert client.get("/kattavuus").status_code == 200
    assert client.get("/menetelmat").status_code == 200
    assert client.get("/etiikka").status_code == 200


def test_compare(client):
    r = client.get("/vertailu?a=1&b=4")
    assert r.status_code == 200
    assert "Anna Aalto" in r.text and "Dan Dahl" in r.text


def test_correction_post(client):
    r = client.post("/korjaus", data={"message": "Testi korjaus", "page_ref": "/edustaja/1",
                                       "person_id": "1"})
    assert r.status_code == 200
    assert "tallennettu" in r.text


def test_unknown_person_404page(client):
    r = client.get("/edustaja/999999")
    assert r.status_code == 200
    assert "ei löytynyt" in r.text.lower()


def test_admin_corrections_requires_token(client):
    # ilman tokenia pääsy estetty
    r = client.get("/yllapito/korjaukset")
    assert r.status_code == 403


def test_admin_corrections_with_token(client):
    from kansanmuisti import config
    config.ADMIN_TOKEN = "testitoken"
    try:
        # luo korjauspyyntö
        client.post("/korjaus", data={"message": "Audit-testi", "page_ref": "/edustaja/1"})
        r = client.get("/yllapito/korjaukset?token=testitoken")
        assert r.status_code == 200
        assert "Audit-testi" in r.text
        # väärä token estetty
        assert client.get("/yllapito/korjaukset?token=vaara").status_code == 403
    finally:
        config.ADMIN_TOKEN = ""

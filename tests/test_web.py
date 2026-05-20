"""Web-integraatiotestit fixture-tietokantaa vasten."""


def test_index_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "SuomenToivot" in r.text


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
    # MP↔MP-samanmielisyys näkyy (jakavat fixture-äänestykset 100/101/102)
    assert "samanmielisyys" in r.text


def test_party_line_persisted(conn):
    # analysis_party_line täyttyy ja sisältää substantiiviset linjat
    n = conn.execute("SELECT COUNT(*) FROM analysis_party_line").fetchone()[0]
    assert n > 0
    line = conn.execute("SELECT line FROM analysis_party_line WHERE vote_id=100 AND party='kok'").fetchone()
    assert line["line"] == "Jaa"  # kok-enemmistö äänesti Jaa äänestyksessä 100


def test_member_fingerprint_query(conn):
    from kansanmuisti.web import queries
    # pienellä otoksella (min_total=1) edustaja 1 on samaa mieltä kok-linjan kanssa
    fp = queries.member_party_agreement(conn, 1, min_total=1)
    assert any(f["party"] == "kok" and f["pct"] == 100 for f in fp)


def test_index_and_scatter_render(client):
    assert client.get("/").status_code == 200
    r = client.get("/tilastot")
    assert "Aktiivisuus" in r.text


def test_search_mode_toggle(client):
    # merkityshaku ei ole käytössä testiympäristössä (ei upotuksia) -> näytetään fallback
    r = client.get("/haku?q=koulutus&mode=merkitys")
    assert r.status_code == 200
    assert "Sanahaku" in r.text and "Merkityshaku" in r.text


def test_commons_file_url():
    from kansanmuisti.collect.photos import _commons_file_url
    u = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Jouni_Backman.jpg/330px-x.jpg"
    assert _commons_file_url(u) == "https://commons.wikimedia.org/wiki/File:Jouni_Backman.jpg"


def test_power_page_renders(client):
    r = client.get("/valta")
    assert r.status_code == 200
    assert "Hallitus" in r.text and "läpimeno" in r.text.lower()


def test_rhetoric_page_renders(client):
    r = client.get("/retoriikka")
    assert r.status_code == 200
    assert "Retoriikkakartta" in r.text


def test_gov_periods():
    from kansanmuisti.analyze.government import gov_parties_at
    assert "kok" in gov_parties_at("2024-01-15")   # Orpo
    assert "sd" in gov_parties_at("2021-03-01")    # Marin
    assert "ps" in gov_parties_at("2016-05-01")    # Sipilä I
    assert "sin" in gov_parties_at("2018-05-01")   # Sipilä II
    assert "kok" not in gov_parties_at("2021-03-01")  # oppositiossa


def test_topic_ownership_chart(client):
    r = client.get("/aihe/terveydenhuolto")
    assert r.status_code == 200


def test_words_page_renders(client):
    r = client.get("/sanat")
    assert r.status_code == 200
    assert "Täytesanat" in r.text and "Voimasanat" in r.text


def test_word_usage_computed(conn):
    n = conn.execute("SELECT COUNT(*) FROM analysis_word_usage").fetchone()[0]
    assert n > 0  # täyte/kiro lasketut fixture-datalle
    cats = {r[0] for r in conn.execute("SELECT DISTINCT category FROM analysis_word_usage")}
    assert "filler" in cats and "swear" in cats


def test_map_page_renders(client):
    r = client.get("/kartta")
    assert r.status_code == 200
    assert "Poliittinen kartta" in r.text


def test_category_scatter_svg():
    from kansanmuisti.web import viz
    pts = [(-50, 10, "A (sd)", "sd"), (60, -20, "B (kok)", "kok"), (5, 5, "C (kesk)", "kesk")]
    svg = viz.category_scatter_svg(pts, "x", "y", centroids={"sd": (-50, 10)})
    assert svg.startswith("<svg") and "circle" in svg
    assert viz.category_scatter_svg([], "x", "y") == ""


def test_correction_post(client):
    r = client.post("/korjaus", data={"message": "Testi korjaus", "page_ref": "/edustaja/1",
                                       "person_id": "1"})
    assert r.status_code == 200
    assert "tallennettu" in r.text


def test_unknown_person_404page(client):
    r = client.get("/edustaja/999999")
    assert r.status_code == 200
    assert "ei löytynyt" in r.text.lower()


def test_representatives_directory_and_sort(client):
    r = client.get("/edustajat")
    assert r.status_code == 200
    assert "Anna Aalto" in r.text and "Poikkeama" in r.text
    # lajittelu poikkeaman mukaan (henkilö 3 poikkesi → mukana)
    r2 = client.get("/edustajat?sort=poikkeama&dir=desc")
    assert r2.status_code == 200
    # puoluesuodatus
    r3 = client.get("/edustajat?party=kok")
    assert r3.status_code == 200
    assert "Anna Aalto" in r3.text and "Dan Dahl" not in r3.text


def test_stats_page(client):
    r = client.get("/tilastot")
    assert r.status_code == 200
    assert "Puoluevertailu" in r.text and "Puoluekuri" in r.text and "Aihetrendit" in r.text
    assert "samanmielisyys" in r.text  # heatmap-osio
    assert "<svg" in r.text  # trendikäyrä


def test_cards_page(client):
    r = client.get("/kortit")
    assert r.status_code == 200
    assert "Anna Aalto" in r.text
    assert "mp-card" in r.text and "<svg" in r.text  # kortit + tutka
    # puoluesuodatus
    r2 = client.get("/kortit?party=kok&sort=indeksi")
    assert r2.status_code == 200
    assert "Dan Dahl" not in r2.text  # sd ei näy kok-suodatuksessa


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

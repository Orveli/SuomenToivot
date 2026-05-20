# SuomenToivot

**Verkkopalvelu, joka kartoittaa, analysoi ja esittää suomalaisten poliittisten päättäjien
julkista ja todennettavaa toimintaa**: täysistuntopuheet, äänestykset ja vaalilupaukset.

> Sisäinen Python-paketti on edelleen nimeltään `kansanmuisti` (importit, `km`-komento ja
> `KANSANMUISTI_*`-ympäristömuuttujat). Julkinen nimi on **SuomenToivot**.

> **Periaate:** emme väitä tietävämme päättäjien motiiveja. Näytämme mitä on *sanottu*, miten on
> *äänestetty*, mitä on *luvattu*, missä sanat ja teot ovat linjassa, missä on ristiriitoja, missä
> kanta on muuttunut ja missä **data puuttuu**. Jokaisella väitteellä on lähde. Lasketut tunnusluvut
> ovat läpinäkyviä indikaattoreita, eivät arvosanoja.

Lähde: **Eduskunnan avoin data** (avoindata.eduskunta.fi), CC BY 4.0.

---

## Mitä tämä on

- **Datankeruu** Eduskunnan avoimesta data-API:sta: edustajat, äänestykset (edustajakohtaiset
  äänet), täysistuntopuheet (teksti PTK-pöytäkirjoista).
- **SQLite-tietokanta** täydellä provenienssilla (jokaisella faktalla lähde-URL + nouto­aika) ja
  FTS5-kokotekstihaulla.
- **Läpinäkyvä analyysiputki**: avainsanapohjainen aiheluokittelu, puhe–ääni-linjaus, puoluelinjasta
  poikkeaminen, kannanmuutosten havaitseminen, johdonmukaisuusindeksi eksplisiittisellä kaavalla.
- **FastAPI-verkkopalvelu**: haku, päättäjäprofiilit, puolueprofiilit, aihenäkymät, äänestys- ja
  puhenäkymät, "lupaukset vs. teot", vertailu, kattavuusnäkymä, menetelmäkuvaus ja korjauskanava.
- **Testit** (pytest), jotka kattavat luokittimen, tunnusluvut, jäsentimet ja web-reitit.

Dokumentit: [`docs/PLAN.md`](docs/PLAN.md) · [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) ·
[`docs/LEGAL_ETHICS.md`](docs/LEGAL_ETHICS.md) · [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) ·
[`docs/UX.md`](docs/UX.md) · [`docs/COVERAGE.md`](docs/COVERAGE.md) (generoitu) ·
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
[`docs/AUDIT.md`](docs/AUDIT.md)

---

## Asennus

Vaatii Python 3.10+ (kehitetty 3.14).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .            # asentaa myös `km`-komennon
# kehitys + testit:
pip install -e ".[dev]"
```

## Ajo (datankeruu → analyysi → palvelin)

```bash
km initdb                                   # luo tietokanta (data/kansanmuisti.sqlite3)
km collect-members --start-year 2015 --end-year 2025
km collect-votes   --year 2024              # yksi valtiopäivävuosi (äänet mukana)
km collect-speeches --year 2024             # puheet PTK-pöytäkirjoista
km collect-legislation                      # HE-tekstit (rikastaa äänestysten aiheluokittelua)
km load-promises   seed/promises.json       # kuratoidut, lähteistetyt lupaukset
km analyze                                  # läpinäkyvä analyysiputki
km coverage-report                          # päivittää docs/COVERAGE.md
km serve                                    # http://127.0.0.1:8000
```

Koko 10 vuoden aineisto kerralla (kestää tunteja, ks. `docs/DATA_SOURCES.md`):

```bash
km collect-all --start-year 2015 --end-year 2025 && km analyze && km coverage-report
```

Keruu on **uudelleenajettava** (`ingest_state`-taulu seuraa tilaa; `INSERT OR REPLACE/IGNORE`).
Voit ajaa minkä tahansa vuoden uudelleen ilman duplikaatteja.

## Testit

```bash
pytest -q                  # ei vaadi verkkoa; käyttää eristettyä fixture-tietokantaa
```

---

## Arkkitehtuuri

```
src/kansanmuisti/
  config.py              keskitetty konfiguraatio (ympäristömuuttujat ohittavat)
  db.py                  SQLite-yhteys, skeeman alustus, ingest-tila, kattavuus
  schema.sql             koko tietokantaskeema (idempotentti)
  cli.py                 `km`-komentorivi
  report.py              kattavuusraportin generointi
  collect/
    eduskunta_client.py  sivutettu, throttlattu, uudelleenyrittävä HTTP-klientti (urllib)
    util.py              XML/päivämäärä/puolue-apurit
    members.py           edustajat + biografia-XML:n jäsennys
    votes.py             äänestykset + edustajakohtaiset äänet (kielikahdennus pois)
    speeches.py          puheet PTK-pöytäkirjoista (VaskiData) — puhuja + teksti
    promises.py          kuratoitujen lupausten latain
  analyze/
    taxonomy.py          aihetaksonomia (avainsanat = vartaloprefiksit)
    classify.py          läpinäkyvä avainsanaluokitin
    metrics.py           poikkeamat, puhe–ääni-linjaus, indeksi, kannanmuutokset
    pipeline.py          putken ajuri + kattavuuslaskenta
  web/
    app.py               FastAPI-reitit
    queries.py           tietokantakyselyt (vain luku, paitsi korjauskanava)
    templates/           Jinja2-templatet (neutraali ulkoasu)
    static/style.css     neutraali, saavutettava tyyli
tests/                   pytest (luokitin, tunnusluvut, jäsentimet, web)
seed/promises.json       kuratoidut, lähteistetyt esimerkkilupaukset
```

### Tietovirta

```
Eduskunnan API ─▶ collect/* ─▶ SQLite (faktat + provenienssi)
                                   │
                       analyze/* ─▶ analysis_*-taulut (lasketut indikaattorit, EROTETTU faktoista)
                                   │
                            web/* ─▶ HTML (jokaisella sivulla lähteet + indikaattorimerkinnät)
```

### Keskeiset datalöydökset (ks. `docs/DATA_SOURCES.md`)
- Puheen teksti **ei** ole `SaliDBPuheenvuoro`-taulussa (se on tyhjä metahakemisto), vaan
  `VaskiData`-taulun PTK-pöytäkirjojen XML:ssä. Puhuja: `PuheenvuoroToimenpide → Toimija →
  Henkilo/@muuTunnus` (= personId). Teksti: `PuheenvuoroOsa → KohtaSisalto → KappaleKooste`.
- Puoluehistoria on `MemberOfParliament.XmlDataFi`-kentässä (`HetekaData` on tyhjä).
- HE↔äänestys-liitos: `SaliDBAanestys.AanestysValtiopaivaasia` (esim. "HE 174/2024 vp").

---

## Miten toinen agentti tai kehittäjä jatkaa tästä

1. **Laajenna aikaikkunaa:** aja `km collect-votes/collect-speeches` halutuille vuosille 2015–2025.
   Koodi on jo parametrisoitu; ei muutoksia tarvita.
2. **Lisää lähteitä:** `VaskiData` (HE-tekstit, valiokunta-asiakirjat) — runko on olemassa
   (`collect/speeches.py` näyttää VaskiData-jäsentämisen mallin). Linkitys äänestyksiin
   `legislative_item`-kentän kautta on jo tietokannassa.
3. **Kuratoi lupauksia:** lisää rivejä `seed/promises.json`-tiedostoon (lähde-URL pakollinen) ja
   aja `km load-promises`.
4. **Paranna taksonomiaa:** muokkaa `analyze/taxonomy.py`, kasvata `LEXICON_VERSION`, aja `km analyze`.
5. **Jatkokehityslista:** `docs/ROADMAP.md` ja `docs/KNOWN_ISSUES.md`.

## Lisenssi ja vastuut
Ohjelmakoodi: MIT. Aineisto: Eduskunnan avoin data, CC BY 4.0 — attribuutio näkyy joka sivulla.
Tietosuoja, tekijänoikeus ja journalistinen käyttö: ks. `docs/LEGAL_ETHICS.md`.

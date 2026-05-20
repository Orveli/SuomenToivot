# Jatkoviimeistelyn työlista

Priorisoitu, konkreettinen lista. Jokainen kohta on tehtävissä ilman arkkitehtuurimuutoksia, ellei
toisin mainita.

## P1 — Kattavuuden täydennys (suora laajennus, ei koodimuutosta)
- [~] Aja `km collect-votes`/`collect-speeches` vuosille 2015–2022 (2023–2024 valmiit).
      **Käynnissä/ajettu** taustakeruuna; resumable. Arvio: ks. `docs/DATA_SOURCES.md`.
- [x] Aja `km analyze`/`coverage-report` uudelleen koko kerätylle aineistolle.

## P2 — Äänestysten aiheluokittelun parannus
- [x] **Toteutettu:** `legislation`-taulu + `collect/legislation.py` kerää HE:n otsikon ja
      pääasiallisen sisällön VaskiDatasta; `classify.py` luokittelee nyt myös HE-tekstin
      perusteella (LEFT JOIN legislation). Komento `km collect-legislation`.
- [ ] Jatko: myös valiokuntamietinnöt (ValiokuntaMietintö) luokittelun rikastukseen.

## P3 — Kannanmuutosten tarkennus
- [x] **Toteutettu:** vertailu rajattu samaan käsittelyvaiheeseen (`treatment_stage`) +
      eri tilaisuus (≥7 vrk) → näennäismuutokset poistuvat (42 519 → ~satoja).
- [ ] Jatko: alikohtatunniste (`AliKohtaTunniste`) tarkempaan erotteluun; "heikko" muutos
      (sama aihe, eri asia) omana luokkana UI:hin.

## P4 — Lupausaineiston laajennus
- [ ] Kuratoi puolueohjelmalupauksia POHTIVA-lähteistä (fsd.tuni.fi/pohtiva), lähde-URL pakollinen.
- [ ] Lisää henkilökohtaisia (scope=person) lupauksia julkisista, siteerattavista lähteistä.
- [ ] Toimituksellinen prosessi `promise_vote_map`-kytkentöjen vertaisarviointiin.

## P5 — Hallinta ja luotettavuus
- [x] **Toteutettu:** korjauspyyntöjen käsittelynäkymä `/yllapito/korjaukset` (tokenilla,
      `KANSANMUISTI_ADMIN_TOKEN`); tila open/resolved/rejected.
- [ ] Aja keruu ja web eri prosesseina; lisää ajastettu inkrementaalipäivitys (uusin valtiopäivävuosi).
- [ ] Lisää `lexicon_version`/`mapping_version` näkyviin käyttöliittymän indeksilaatikkoon.

## P6 — Laajennukset (arkkitehtuuria koskeva)
- [ ] Valiokunta-asiakirjat (`VaskiData`) ja niiden linkitys edustajiin/valiokuntiin.
- [ ] Kunnallinen ja EU-tason aineisto (erilliset rajapinnat, oma keruumoduuli).
- [ ] Kaksikielisyys (sv): lähteessä on `XmlDataSv`/`SaliDBAanestysKieli` — UI-lokalisointi.

## Laatuvelka / siivous
- [x] **Johdonmukaisuusindeksin laskenta optimoitu** O(äänestykset×puheet) → esilaskettu
      aiheindeksi + bisect ±30 vrk (`metrics.build_alignment_index`/`alignment_for`).
- [ ] Lisää integraatiotesti, joka ajaa pienen oikean keruun (verkkomerkitty, ohitettavissa CI:ssä).
- [ ] Tyyppivihjeiden täydennys ja `ruff`/`mypy`-konfiguraatio.
- [ ] Välimuisti raskaille profiilikyselyille suuremmilla aineistoilla.
- [ ] Ruotsinkielinen lokalisointi (sv-data on lähteessä; UI lokalisoimatta).

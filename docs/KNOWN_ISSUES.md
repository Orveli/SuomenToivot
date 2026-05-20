# Tunnetut puutteet ja rajoitteet

Tämä lista on tarkoituksella rehellinen. Osa kohdista on aidosti ulkoisesti estyneitä, osa on
jatkokehitystä (ks. `docs/ROADMAP.md`).

## Datan kattavuus
- **Aikaikkuna tässä toteutuksessa.** Keruukoodi kykenee koko 10 vuoden aineistoon (2015–2025) ja
  on parametrisoitu, mutta tässä ympäristössä on ajettu rajattu mutta täysi siivu (valtiopäivävuosi
  2024 kokonaan + kaikki 2015–2025 aktiiviset edustajat; 2023 ajossa/laajennettavissa). Syy:
  edustajakohtaisia ääniä on ~1,9 milj. riviä kymmeneltä vuodelta ja täysi veto kestää tunteja
  (`docs/DATA_SOURCES.md`). Laajennus on yksi komento per vuosi, ei koodimuutosta.
- **Puhedata alkaa 2014.** Sitä aiemmille äänestyksille ei ole puhekontekstia (lippu
  `PRE_2014_SPEECHGAP`). Ei korjattavissa — lähde alkaa 2014.

## Analyysi
- **Äänestysten aiheluokittelun no-match-osuus on korkea** otsikkopohjaisille menettely- ja
  luottamusäänestyksille (esim. "Luottamuslause", "Pöydällepano"), koska äänestyksen otsikko on
  lyhyt. Parannettavissa linkittämällä `legislative_item` HE-tekstiin (VaskiData) ja luokittelemalla
  sen sisällöstä — ks. roadmap.
- **Kannanmuutosten "vahva" tunnistus** ryhmittelee `legislative_item`-perustunnisteella. Sama
  tunnus voi sisältää useita erillisiä äänestyksiä (esim. luottamusäänestyssarja), jolloin
  Jaa↔Ei-vaihtelu ei aina ole aito kannanmuutos. Käyttöliittymä kehottaa lukemaan molemmat
  äänestykset; jatkossa tarkennus alikohtatunnisteella.
- **Menettelyäänestysten heuristiikka** (`PROCEDURAL_SUSPECT`) on otsikkopohjainen ja karkea.
- **Puhe–ääni-linjaus (A)** mittaa vain, *puhuuko* edustaja aiheesta lähellä äänestystä — ei puheen
  kantaa. Tämä on tietoinen rajaus (emme tulkitse sävyä).

## Lupaukset
- **Lupausaineisto on kuratoitu siemenaineisto**, ei kattava. Vaalikonevastauksia (Yle/HS) **ei**
  ole mukana lisenssi-/tietokantaoikeussyistä (`docs/LEGAL_ETHICS.md`). POHTIVA-puolueohjelmista ei
  ole bulk-API:a; lupaukset lisätään kuratoiden lähde-URL:lla.
- Lupaus↔äänestys-kytkentä on toimituksellinen ja edellyttää ihmistyötä; se ei skaalaudu
  automaattisesti.

## Edustajakuvat
- **Kuvat haetaan Wikimedia Commonsista** (`km photos`, Wikipedian pageimages-API), ~75 % edustajista
  (329/438). Eduskunnan avoimessa datassa ei ole kuvia (XML:ssä ei kuvaa, Attachment = vain PDF:t,
  eduskunta.fi-sivut 404). Ne joille ei löydy kuvaa, näytetään nimikirjain-monogrammilla.
- **Lisenssi/attribuutio:** Commons-kuvilla on kullakin oma lisenssinsä (pääosin CC/PD). Näytämme
  kuvalähde­linkin (Commons-tiedostosivu), mutta **kuvakohtaiset lisenssi- ja tekijätiedot tulisi
  varmistaa ennen laajaa tuotantokäyttöä** — k. LEGAL_ETHICS.md. Kuvat ovat ulkoinen rikaste, eivät
  Eduskunnan avointa dataa.

## Merkityshaku (semanttinen)
- Valinnainen embedding-pohjainen haku (`km embed` + sentence-transformers). Käyttää neuroverkkomallia
  ("musta laatikko") — siksi sitä käytetään **vain haun apuna**, ei väitteiden tai pisteytysten
  perustana; tulokset linkittyvät aina alkuperäiseen puheeseen. Ydin (FTS-sanahaku) toimii ilman tätä.
  Upotukset (~175 MB) eivät ole versionhallinnassa; ne lasketaan komennolla `km embed`.

## Tekninen
- **Yhtäaikainen massakeruu + web-kirjoitus** voi aiheuttaa hetkellisen SQLite-lukon
  (korjauskanava). Lieventävä uudelleenyritys + `busy_timeout` on toteutettu; tuotannossa keruu ja
  web kannattaa ajaa eri prosesseina (lukijat eivät estä WAL-tilassa).
- **Ministerikausien jäsennys** poimii nimen/hallituksen biografia-XML:stä; kenttien laatu vaihtelee
  lähteessä.
- **Vaalipiiri** otetaan nykyisestä, muuten viimeisimmästä — historiallinen vaalipiirimuutos ei näy
  täydellisenä aikasarjana.

## Ei toteutettu tässä vaiheessa (roadmap)
- Kunnat ja EU-taso (eri rajapinnat).
- VaskiData-pohjainen HE-/valiokunta-asiakirjojen täysi keruu ja luokittelu.
- Käyttäjätunnistettu korjausten käsittelytyökalu (nyt tallennus `correction_request`-tauluun).

# Tietolähteet (DATA_SOURCES)

Tämä dokumentti kuvaa Kansanmuisti-palvelun datalähteet. Päälähde on Eduskunnan
avoimen datan rajapinta (Eduskunta open data API), jota täydennetään kuratoiduilla
puolueohjelma- ja vaalilupauslähteillä.

Kaikki alla olevat luvut, sarakenimet ja päivämäärävälit on tarkistettu suoraan
elävästä rajapinnasta (probattu 2026-05-20).

---

## 1. Eduskunnan avoimen datan rajapinta (API)

- Perus-URL: `https://avoindata.eduskunta.fi/api/v1/`
- Taulujen listaus: `GET /api/v1/tables/` (huom. **loppukauttaviiva pakollinen** —
  `GET /api/v1/tables` palauttaa 404).
- Lisenssi: Eduskunnan avoin data (CC BY 4.0 -tyyppinen vapaa uudelleenkäyttö).

### Taulut

Rajapinnasta löytyy seuraavat taulut (`GET /api/v1/tables/`):

```
Attachment, AttachmentGroup, HetekaData, MemberOfParliament, PrimaryKeys,
SaliDBAanestys, SaliDBAanestysAsiakirja, SaliDBAanestysEdustaja,
SaliDBAanestysJakauma, SaliDBAanestysKieli, SaliDBIstunto, SaliDBKohta,
SaliDBKohtaAanestys, SaliDBKohtaAsiakirja, SaliDBMessageLog, SaliDBPuheenvuoro,
SaliDBTiedote, SeatingOfParliament, VaskiData
```

Pääavaimet (`GET /api/v1/tables/PrimaryKeys/rows`):

| Taulu | Pääavain (PK) |
|---|---|
| SaliDBAanestys | `AanestysId` |
| SaliDBAanestysEdustaja | `EdustajaId` |
| SaliDBPuheenvuoro | `Id` |
| VaskiData | `Id` |
| MemberOfParliament | `personId` |
| HetekaData | `Id` |

### Kaksi tapaa hakea rivit

1. **Sivutus (page/perPage)** — `GET /tables/{Taulu}/rows?perPage=100&page=N`.
   Vastaus sisältää avaimet: `page, perPage, hasMore, tableName, columnNames,
   rowData, columnCount, rowCount, pkName, pkStartValue, pkLastValue`.
   - Rivit järjestetään pääavaimen (PK) mukaan nousevasti.
   - `hasMore: false` ja tyhjä `rowData` merkitsevät sivutuksen loppua.
   - HUOM: `rowCount` on **vain kyseisen sivun rivimäärä**, EI taulun
     kokonaisrivimäärää. Kokonaismäärää ei saa suoraan — se on pääteltävä
     etsimällä viimeinen sivu (binäärihaku `page`-arvolla).

2. **Batch (resumoituva)** — `GET /tables/{Taulu}/batch?pkName={PK}&pkStartValue=V`.
   Palauttaa enintään 100 riviä, joiden PK > V, sekä `pkLastValue`-arvon.
   Tämä on **suositeltu** tapa massa-ajoon: tallenna `pkLastValue` ja jatka siitä.
   Esim. `GET /tables/SaliDBAanestys/batch?pkName=AanestysId&pkStartValue=0`
   palauttaa 100 riviä ja `pkLastValue: 13358`.

> Huom. yksittäisriviä ei voi hakea polulla `/tables/{Taulu}/{id}` (palauttaa 404).

### Rate-limit ja suorituskyky (mitattu)

- 10 peräkkäistä `perPage=100`-pyyntöä suoriutui **1,1 sekunnissa** ilman
  throttlausta tai 429-vastauksia. Rajapinta on nopea eikä havaittavaa
  pyyntörajoitusta esiintynyt kohtuukäytöllä.
- Suositus silti: pidä rinnakkaisuus maltillisena (1–4 yhtäaikaista pyyntöä) ja
  lisää uudelleenyrityslogiikka (retry + exponential backoff) verkkovirheiden varalle.

---

## 2. Äänestykset — SaliDBAanestys

Yksi rivi = yksi täysistuntoäänestys yhdellä kielellä.

### Sarakkeet (35 kpl)

```
AanestysId, KieliId, IstuntoVPVuosi, IstuntoNumero, IstuntoPvm,
IstuntoIlmoitettuAlkuaika, IstuntoAlkuaika, PJOtsikko, AanestysNumero,
AanestysAlkuaika, AanestysLoppuaika, AanestysMitatoity, AanestysOtsikko,
AanestysLisaOtsikko, PaaKohtaTunniste, PaaKohtaOtsikko, PaaKohtaHuomautus,
KohtaKasittelyOtsikko, KohtaKasittelyVaihe, KohtaJarjestys, KohtaTunniste,
KohtaOtsikko, KohtaHuomautus, AanestysTulosJaa, AanestysTulosEi,
AanestysTulosTyhjia, AanestysTulosPoissa, AanestysTulosYhteensa, Url,
AanestysPoytakirja, AanestysPoytakirjaUrl, AanestysValtiopaivaasia,
AanestysValtiopaivaasiaUrl, AliKohtaTunniste, Imported
```

### Päivämääräväli ja määrät (tarkistettu)

- **Aikajänne:** ensimmäinen äänestys vuodelta **1996** (`IstuntoVPVuosi`),
  uusin probattu päivämäärä **2026-05-12** (`IstuntoPvm`).
- **Kokonaisrivimäärä koko taulussa:** ~**43 109** riviä (viimeinen sivu
  `perPage=100` on sivu **432**, jolla 9 riviä; sivut 0–431 täysiä).
- **Kaksi kieliriviä per äänestys:** otanta useilta sivuilta antoi tasan 50/50
  jakauman `KieliId=1` (suomi) ja `KieliId=2` (ruotsi). Siis **uniikkeja
  äänestyksiä ≈ 43 109 / 2 ≈ 21 500** koko historiassa.

### Rajaaminen vuosittain

- `AanestysId` on **suunnilleen kronologinen** (sivu 0 = 1996, sivu 250 ≈ 2016,
  sivu 350 ≈ 2021). HUOM: aivan tauluun lopun sivuilla (n. 419→) on uusinta dataa
  (2024–2026), ja viimeiset sivut (430–432) sisältävät myöhemmin täydennettyjä
  vanhoja rivejä (2009–2014) — eli järjestys ei ole täysin tiukka.
- Vuosirajaus kannattaa tehdä **`IstuntoVPVuosi`-kentällä** (valtiopäivävuosi)
  tai `IstuntoPvm`-kentällä, EI pelkän PK-välin perusteella. Käytännössä:
  hae batch-ajolla läpi ja suodata `IstuntoVPVuosi`-arvolla 2015–2025.
- **2015–2025-haarukka** sijoittuu noin sivuille **235–429** (`perPage=100`),
  eli ~195 sivua ≈ **19 500 kielikohtaista riviä ≈ 9 750 uniikkia äänestystä**
  kymmeneltä vuodelta.

### Linkki säädöksiin

- `AanestysValtiopaivaasia` sisältää tunnisteen muodossa **`"HE 174/2024 vp"`**
  (ruotsiksi `"RP 174/2024 rd"`), ja `AanestysValtiopaivaasiaUrl` on esim.
  `/valtiopaivaasiat/HE+174/2024`.
- Tämä tunniste on **suora liitosavain** VaskiData-taulun `Eduskuntatunnus`-kenttään
  (ks. luku 4): "HE 174/2024 vp" SaliDBAanestys-puolella vastaa täsmälleen
  "HE 174/2024 vp" VaskiData-puolella.

---

## 3. Edustajakohtaiset äänet — SaliDBAanestysEdustaja

Yksi rivi = yhden kansanedustajan ääni yhdessä äänestyksessä.

### Sarakkeet

```
EdustajaId, AanestysId, EdustajaEtunimi, EdustajaSukunimi,
EdustajaHenkiloNumero, EdustajaRyhmaLyhenne, EdustajaAanestys, Imported
```

- `AanestysId` viittaa SaliDBAanestys-tauluun. Liitos osuu **suomenkieliseen
  riviin** (`KieliId=1`): esim. `AanestysId=38385` on suomenkielinen äänestysrivi.
- `EdustajaRyhmaLyhenne` = eduskuntaryhmän lyhenne äänestyshetkellä (esim. `sd`,
  `kok`, `kesk`) — tämä on **historiallinen ryhmätieto** kyseiseltä hetkeltä.
- `EdustajaAanestys` = yksi arvoista `Jaa` / `Ei` / `Tyhjää` / `Poissa`.
- `EdustajaHenkiloNumero` = sama henkilönumero kuin muissa tauluissa
  (`MemberOfParliament` ei käytä sitä PK:na, mutta puheissa kenttä on
  `henkilonumero`).

### Määrät (tarkistettu)

- **Kokonaisrivimäärä koko taulussa:** ~**8,55 miljoonaa** riviä (viimeinen
  `perPage=100`-sivu on noin **85 500**; sivut 86 000+ palauttavat tyhjää).
- Yhtä äänestystä kohden on **~199 riviä** (yksi per istunnossa läsnä/poissa
  ollut edustaja), vain yhdellä kielellä — ei kielikahdennusta tässä taulussa.
  (Varmistettu: `AanestysId=38385` jakautui ~199 riville peräkkäisillä sivuilla.)
- **Arvio 2015–2025:** ~9 750 uniikkia äänestystä × ~199 edustajaa
  ≈ **1,9 miljoonaa riviä** kymmeneltä vuodelta.

---

## 4. Asiakirjat — VaskiData (HE, valiokunnat, PTK)

VaskiData on Eduskunnan **asiakirjavarasto**: hallituksen esitykset, valiokuntien
mietinnöt/lausunnot, pöytäkirjat ym. täydellisinä XML-dokumentteina.

### Sarakkeet

```
Id, XmlData, Status, Created, Eduskuntatunnus, AttachmentGroupId, Imported
```

- `XmlData` sisältää **koko dokumentin XML:n** (tyypillisesti 10–80 kt).
  Skeema on Eduskunnan VASKI-"Siirto"-rakenne
  (`http://www.eduskunta.fi/skeemat/siirto/...`), namespacet vsk/sis/met/jme jne.
- `Eduskuntatunnus` = ihmisluettava tunnus, esim. `"HE 131/2020 vp"`,
  `"PTK 27/2023 vp"`, `"TaVL ... vp"`, `"AjUB 1/2015 rd"` (ruotsi).

### Määrät (tarkistettu)

- **Kokonaisrivimäärä:** ~**390 000** riviä (viimeinen `perPage=100`-sivu noin
  **3 900**; sivut 4 000+ tyhjiä). Rivit on järjestetty `Eduskuntatunnus`-kentän
  mukaan aakkosjärjestykseen.
- Esimerkkidokumentteja: `HE 131/2020 vp` (XmlData 80 568 merkkiä),
  `PTK 27/2023 vp` (43 454 merkkiä).

### Asiakirjatyypit (Eduskuntatunnuksen etuliite)

Otoksissa esiintyi mm.: `HE` (hallituksen esitys), `PTK` (täysistunnon
pöytäkirja, **sisältää puheiden tekstit**, ks. luku 5), `KK` (kirjallinen
kysymys), `EDK`, `EUN`, `EK`, `TaVL`/muut valiokuntalyhenteet (valiokunnan
lausunnot ja mietinnöt), `SS`, `PR`. Ruotsinkieliset tunnistaa `rd`-päätteestä
(esim. `RP`, `AjUB`).

### Linkitys äänestyksiin

- **Hallituksen esitys (HE):** suodata VaskiData `Eduskuntatunnus LIKE 'HE %vp'`.
  Liitä äänestyksiin SaliDBAanestys-kentän `AanestysValtiopaivaasia` kautta —
  arvot ovat identtisiä (`"HE 174/2024 vp"`). Tämä mahdollistaa myöhemmin
  äänestyksen kytkemisen sen taustalla olevaan lakiesitykseen ja sitä kautta
  valiokuntakäsittelyyn.
- **Valiokunta-asiakirjat:** löytyvät samasta taulusta valiokuntalyhenteillä;
  ne viittaavat samaan valtiopäiväasiaan (HE-numero esiintyy dokumentin XML:ssä),
  joten yhteys HE → valiokunta → äänestys on rakennettavissa HE-tunnuksen kautta.

---

## 5. Puheenvuorot — SaliDBPuheenvuoro + puheteksti VaskiDatasta

### SaliDBPuheenvuoro: sarakkeet

```
Id, IstuntoTekninenAvain, KohtaTekninenAvain, TekninenAvain, Jarjestys,
PVTyyppi, henkilonumero, Etunimi, Sukunimi, Sukupuoli, PyyntoTapa, PyyntoAika,
XmlData, Created, Modified, RyhmaLyhenneFI, RyhmaLyhenneSV, Puhunut, JarjestysNro,
ADtunnus, MinisteriysFI, MinisteriysSV, Imported
```

### Tärkeä havainto: `XmlData` on tyhjä

> **SaliDBPuheenvuoro.XmlData on käytännössä aina tyhjä merkkijono (`""`).**
> Tämä varmistettiin lukuisilta sivuilta ja batch-erästä eri vuosilta (2014–2026):
> kaikki tarkastetut rivit antoivat `XmlData`-pituudeksi 0. SaliDBPuheenvuoro on
> siis vain **puheenvuorojen metadata-/pyyntöhakemisto** (kuka pyysi/piti
> puheenvuoron, milloin, mikä ryhmä, mikä istunto/kohta), EI puheen tekstisisältö.

### Määrät ja aikajänne (tarkistettu)

- **Aikajänne:** ensimmäiset rivit vuodelta **2014** (`PyyntoAika`), uusimmat
  probatut 2026 (esim. 2026-03-12).
- **Kokonaisrivimäärä:** ~**143 500** riviä (viimeinen `perPage=100`-sivu noin
  **1 435**; sivut 1 440+ tyhjiä).
- `PVTyyppi`-jakauma vaihtelee (esiintyy mm. `T`, `V`, `E`, `N`); osa riveistä on
  puheenvuoropyyntöjä, joita ei pidetty.

### Mistä puheen teksti löytyy

Puheen **varsinainen sisältö löytyy täysistunnon pöytäkirjasta** (PTK-dokumentti
VaskiData-taulussa, `Eduskuntatunnus = "PTK n/vvvv vp"`). PTK-XML:ssä yksittäinen
puheenvuoro on elementissä `vsk:PuheenvuoroOsa`, ja **puhuttu teksti on poluilla:**

```
vsk:PuheenvuoroOsa  (attribuutit: puheenvuoroAloitusHetki, puheenvuoroLopetusHetki,
                     puheenvuoroJNro, met1:muuTunnus, met1:kieliKoodi)
  └─ vsk:KohtaSisalto
       └─ sis:KappaleKooste   ← yksi <sis:KappaleKooste> per puhuttu kappale
```

Eli kaikki yhden puheenvuoron kappaleet ovat peräkkäisinä
`sis:KappaleKooste`-elementteinä `vsk:KohtaSisalto`-elementin sisällä, joka taas
on `vsk:PuheenvuoroOsa`-elementin sisällä. `met1:muuTunnus`-attribuutti
`vsk:PuheenvuoroOsa`-elementissä on puheenvuoron tekninen tunnus, jolla puhe
voidaan periaatteessa kytkeä SaliDBPuheenvuoro-metadataan (puhuja, ryhmä, aika).

**Suositus:** käytä SaliDBPuheenvuoro-taulua puhujien/ajankohtien indeksinä, mutta
hae puheiden tekstit PTK-dokumenteista VaskiDatasta ja jäsennä yllä oleva XML-polku.

---

## 6. Kansanedustajat ja puoluehistoria — MemberOfParliament

### Sarakkeet

```
personId, lastname, firstname, party, minister, XmlData, XmlDataSv, XmlDataFi,
XmlDataEn
```

- `personId` = henkilönumero (sama kuin SaliDBAanestysEdustaja-taulun
  `EdustajaHenkiloNumero` / puheiden `henkilonumero`).
- `XmlDataFi` = **koko biografia-XML suomeksi** (esim. ~9,8 kt). Vastaavat
  `XmlDataSv`/`XmlDataEn` ovat lyhyemmät käännösversiot; `XmlData` on tyhjä/lyhyt.
- `party` ja `minister` ovat lippukenttiä; varsinainen ryhmähistoria on XML:ssä.

### Määrät (tarkistettu)

- **Kokonaisrivimäärä:** ~**2 900** edustajaa (viimeinen `perPage=100`-sivu noin
  **29**; sivut 30+ tyhjiä). Tämä kattaa **koko historian**, ei vain nykyisiä.
- Aktiivisten 2015–2025-edustajien rajaaminen: tee se ryhmäjäsenyyksien
  päivämäärien perusteella (ks. alla) tai ristiin SaliDBAanestysEdustaja-taulun
  `EdustajaHenkiloNumero`-arvojen kanssa kyseiseltä ajanjaksolta.

### Puoluejäsenyyshistoria biografia-XML:stä

Ryhmähistoria poimitaan `XmlDataFi`-kentän XML:stä. Rakenne:

```
Eduskuntaryhmat
  ├─ NykyinenEduskuntaryhma
  │     ├─ Tunnus           ← ryhmäkoodi (esim. "sd01")
  │     └─ AlkuPvm          ← muodossa pp.kk.vvvv
  └─ EdellisetEduskuntaryhmat
        └─ Eduskuntaryhma   (voi olla useita)
              ├─ Nimi       ← esim. "Sosialidemokraattinen eduskuntaryhmä"
              ├─ Tunnus     ← ryhmäkoodi (esim. "sd01")
              └─ Jasenyys   (voi olla useita per ryhmä)
                    ├─ AlkuPvm   ← pp.kk.vvvv (esim. 27.09.1975)
                    └─ LoppuPvm  ← pp.kk.vvvv (esim. 21.03.1991)
```

Lisäksi on `TehtavatEduskuntaryhmassa`-osio (roolit ryhmässä). Päivämäärät ovat
suomalaisessa muodossa `pp.kk.vvvv`. Yhdistämällä `NykyinenEduskuntaryhma` ja
kaikki `EdellisetEduskuntaryhmat/Eduskuntaryhma/Jasenyys`-jaksot saadaan
edustajan **täydellinen puoluejäsenyyden aikajana** päivämäärineen — tämä on
keskeinen "loikkareiden"/ryhmävaihdosten seurantaan.

### HetekaData — tyhjä, älä käytä

> **HetekaData-taulu palautti kaikissa probauksissa 0 riviä** (sivutus ja
> batch eri pkStartValue-arvoilla). Sarakkeet ovat `Id, XmlData, Status, Created,
> AttachmentGroupId, Imported`, mutta dataa ei ole rajapinnan kautta saatavilla.
> **Kaikki tarvittava biografia- ja ryhmähistoriadata on MemberOfParliament-taulun
> `XmlDataFi`-kentässä.** (Myös `Statistics`-taulu oli tyhjä.)

---

## 7. Vaalilupaukset ja puolueohjelmat

Eduskunnan rajapinnassa ei ole vaalilupauksia eikä puolueohjelmia. Realistiset,
viitattavat lähteet:

### POHTIVA (FSD / Tampereen yliopisto) — suositeltu päälähde

- URL: `https://www.fsd.tuni.fi/pohtiva/`
- "Poliittisten ohjelmien tietovaranto", ylläpitäjä Yhteiskuntatieteellinen
  tietoarkisto (FSD), Tampere.
- Kattavuus: **~1 586 ohjelmaa, vuodet 1880–2025, ~96 puoluetta** (yleisohjelmat,
  vaaliohjelmat, erityisohjelmat). Sisältää ohjelmien **tekstisisällön** sana-
  hakua varten.
- **Bulkkilataus / API:ta ei ole** julkisesti tarjolla — käyttö tapahtuu
  web-käyttöliittymän kautta. URL-rakenne on kuitenkin vakaa ja siteerattava:
  - Ohjelmalistat: `https://www.fsd.tuni.fi/pohtiva/ohjelmalistat`
  - Puolueittain: `https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/{PUOLUE}`
    (esim. `/SDP`, `/KOK`, `/VIHR`)
  - Yksittäinen ohjelma: `https://www.fsd.tuni.fi/pohtiva/ohjelmalistat/{PUOLUE}/{ID}`
- Lisenssiehdot tulee tarkistaa POHTIVAn "Lisätietoja"-sivulta
  (`/pohtiva/lisatietoja`) ennen sisällön talletusta; siteeraus ja linkitys ovat
  joka tapauksessa turvallisia.

### Puolueiden omat verkkosivut

- Ajankohtaiset vaaliohjelmat ja tavoiteohjelmat julkaistaan puolueiden sivuilla
  (usein PDF/HTML). Ei yhtenäistä rajapintaa; jokainen puolue erikseen.

### Suositus: kuratoitu siemenaineisto (curated seed)

Koska bulkki-/API-pääsyä ei ole, suositellaan **kuratoitua siemenlistaa**:
ylläpidetään käsin koottua taulukkoa (puolue, ohjelman tyyppi, vuosi, lähde-URL,
poimitut lupaukset) ja viitataan POHTIVA-/puolue-URL:eihin. Lupaustekstit
poimitaan ja talletetaan valikoiden, ei automaattisella massakeruulla, jotta
pysytään lähteiden käyttöehdoissa.

---

## 8. Käytännön sisäänluku­suunnitelma (ingestion)

### Suositellut parametrit

- **`perPage=100`** (suurin havaittu toimiva ja API:n oletussivukoko massahaussa).
- **Käytä `batch`-endpointtia**, ei `page`-sivutusta, suurissa tauluissa:
  tallenna kunkin taulun viimeksi tuotu PK (`pkLastValue`) ja jatka siitä.

### Resumoituva strategia

Tallenna pysyvästi per taulu joko:
- suurin tuotu pääavain (`max imported PK`), jolla seuraava ajo jatkaa
  `batch?pkName=...&pkStartValue={maxPK}`, TAI
- suurin tuotu sivunumero (`max page`) jos käytetään `page`-sivutusta.

`batch`-tapa on robustimpi, koska se on idempotentti ja kestää uusien rivien
lisäyksen häntään. Inkrementaalisissa päivitysajoissa voi lisäksi suodattaa
`Imported`-kentällä (kaikissa tauluissa) jo tuotujen ohittamiseksi.

### Karkea kokonaisaika 10 vuoden datalle

Mittauksen pohjalta (~100 riviä / ~0,11 s, eli ~900 riviä/s yksisäikeisenä):

| Taulu | ~rivejä 10 v | Pyyntöjä (`perPage=100`) | Karkea aika (1 säie) |
|---|---|---|---|
| SaliDBAanestys | ~19 500 (fi+sv) | ~195 | ~25–60 s |
| SaliDBAanestysEdustaja | ~1,9 milj. | ~19 000 | ~25–60 min |
| SaliDBPuheenvuoro (metadata) | ~143 500 (koko taulu, 2014→) | ~1 435 | ~3–5 min |
| VaskiData (HE/PTK/valiok., XML raskas) | kymmeniätuhansia rel. dokkareita | tuhansia | ~10–40 min |
| MemberOfParliament | ~2 900 (koko historia) | ~29 | ~10–20 s |

Kokonaisuudessaan **luokkaa 1–2 tuntia** yksisäikeisenä; maltillisella
rinnakkaisuudella (2–4 säiettä) selvästi alle tunnin. VaskiData on hitain rivi
kohden, koska `XmlData` on suuri — kannattaa hakea vain relevantit
asiakirjatyypit (HE, PTK, valiokunta-lyhenteet) suodattamalla
`Eduskuntatunnus`-etuliitteen perusteella sen sijaan, että ladattaisiin koko
~390 000 dokumentin taulu.

---

## Yhteenveto (vahvistetut luvut)

| Taulu | Aikajänne | Koko (koko taulu) | Avain / liitos |
|---|---|---|---|
| SaliDBAanestys | 1996 → 2026-05-12 | ~43 109 riviä (~21 500 uniikkia äänestystä, fi+sv 50/50) | `AanestysId`; HE-linkki `AanestysValtiopaivaasia` |
| SaliDBAanestysEdustaja | (seuraa äänestyksiä) | ~8,55 milj. riviä (~199 / äänestys) | `EdustajaId`, `AanestysId`, `EdustajaHenkiloNumero` |
| SaliDBPuheenvuoro | 2014 → 2026 | ~143 500 riviä (**XmlData tyhjä**) | `Id`, `henkilonumero`; teksti PTK:sta |
| VaskiData | (laaja) | ~390 000 dokumenttia | `Id`, `Eduskuntatunnus` |
| MemberOfParliament | koko historia | ~2 900 edustajaa | `personId`; ryhmähistoria `XmlDataFi`:ssä |
| HetekaData | — | **tyhjä, ei dataa** | — |

**Puheen tekstin XML-polku (PTK-dokumentti VaskiDatassa):**
`vsk:PuheenvuoroOsa / vsk:KohtaSisalto / sis:KappaleKooste`

**Suositeltu sivutus:** `batch?pkName={PK}&pkStartValue={maxImportedPK}`,
`perPage=100`, resumoituva tallentamalla `pkLastValue` per taulu.

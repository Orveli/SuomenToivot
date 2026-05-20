# Kansanmuisti – Juridiikka ja etiikka

Tämä dokumentti kuvaa Kansanmuisti-palvelun oikeudelliset ja eettiset
reunaehdot. Palvelu kokoaa yhteen suomalaisten kansanedustajien
**todennettavissa olevaa julkista toimintaa** (täysistuntopuheenvuorot,
äänestykset, vaalilupaukset) Eduskunnan avoimesta datasta. Kohderyhmänä ovat
palvelua rakentavat insinöörit; tavoite on, että jokainen vaatimus on
konkreettinen ja toteutettavissa.

> **Huomautus epävarmuudesta.** Tämä on tekninen tiivistelmä, ei oikeudellinen
> lausunto. Useat kohdat (erityisesti journalistisen poikkeuksen soveltuvuus
> ja vaalikonedatan uudelleenkäyttö) ovat tulkinnanvaraisia. Ennen tuotantoon
> menoa kriittiset kohdat (luvut 2, 3 ja 4) on syytä tarkistuttaa
> juristilla / tietosuojavastaavalla. Kohdat, joissa olen epävarma, on merkitty
> tekstiin erikseen.

Tarkistuspäivä: 2026-05-20.

---

## 1. Eduskunnan avoimen datan lisenssi

**Lähde:** avoindata.eduskunta.fi (Eduskunnan avoin data, mm. taulut
`SaliDBPuheenvuoro`, `SaliDBAanestys`, `MemberOfParliament`, VaskiData).

### Lisenssi

Eduskunnan avoin data julkaistaan **Creative Commons Nimeä 4.0 Kansainvälinen
(CC BY 4.0)** -lisenssillä. Tämä on linjassa Suomen julkishallinnon avoimen
datan virallisen lisenssisuosituksen kanssa (Creative Commons Suomi /
JHS 189): julkisen sektorin avoimen datan suositeltu lisenssi on **CC BY 4.0**.

> Varmennettava: Eduskunnan oma lisenssimerkintä kannattaa tarkistaa suoraan
> palvelun käyttöehtosivulta / API-vastauksen `license`-kentästä (esim.
> VaskiData-taulun lähde/lisenssikenttä) build-vaiheessa. Hakutulosten
> perusteella aineisto on CC BY 4.0, mutta yksittäisen taulun lisenssikenttä
> on syytä lukea ohjelmallisesti ja näyttää käyttäjälle.

### Mitä CC BY 4.0 sallii

- Kopiointi, muokkaus ja jakelu alkuperäisenä tai muokattuna.
- Yhdistäminen muuhun aineistoon.
- **Kaupallinen käyttö** sallittu.

### Velvoitteet (nimeämisehto)

CC BY 4.0 vaatii, että käyttäjä:

1. **mainitsee aineiston lähteen** (tekijän/julkaisijan),
2. **linkittää lisenssiin**, ja
3. **ilmoittaa, jos aineistoa on muutettu**.

### Suositeltu attribuutiomuotoilu (näytä jokaisella datasivulla)

```
Lähde: Eduskunta – avoin data (avoindata.eduskunta.fi).
Lisenssi: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/deed.fi).
Aineistoa on muokattu: koostettu ja laskennallisesti jalostettu Kansanmuisti-palvelussa.
```

Lähteet:
- https://creativecommons.fi/2014/12/suomen-julkisen-avoimen-datan-virallinen-lisenssisuositus-on-nyt-cc-nimea-4-0/
- https://www.avoindata.fi/fi/opas/valitse-lisenssit
- https://creativecommons.org/licenses/by/4.0/deed.fi
- https://avoindata.eduskunta.fi/

---

## 2. GDPR / tietosuoja: poliitikkojen henkilötietojen käsittely

Kansanedustajia koskeva data on henkilötietoa, joten EU:n yleinen
tietosuoja-asetus (GDPR, 2016/679) ja kansallinen **tietosuojalaki
(1050/2018)** soveltuvat.

### 2.1 Lähtökohta: vain jo julkinen virallinen aineisto

Palvelu käsittelee **ainoastaan jo julkaistua virallista aineistoa**:
täysistuntopöytäkirjat, äänestystulokset ja edustajan virallinen rooli. Tämä
data on lähtökohtaisesti julkista (julkisuuslaki 621/1999) ja koskee henkilön
**julkista luottamustehtävää**, ei yksityiselämää. Tämä pienentää
tietosuojariskiä olennaisesti, mutta **ei poista GDPR:n soveltuvuutta** –
julkisenkin tiedon systemaattinen kokoaminen ja profilointi on käsittelyä.

### 2.2 Käsittelyn oikeusperuste

Mahdolliset oikeusperusteet (GDPR 6 art.):

- **Yleinen etu (6(1)(e))** – yhteiskunnallisesti merkittävän,
  demokratiaa palvelevan julkisen tiedon välittäminen kansalaisille; tai
- **Oikeutettu etu (6(1)(f))** – tasapainotettuna sillä, että kyse on
  julkisista viranhoitoon liittyvistä toimista (rekisteröidyn perusoikeudet
  eivät syrjäytä etua, kun käsitellään vain virallista julkista toimintaa).

Käytännön rakennusohje: dokumentoi valittu oikeusperuste ja tee kevyt
**tasapainotesti / vaikutustenarviointi (DPIA-tyyppinen)**, koska kyse on
laajamittaisesta julkisesti saatavilla olevasta profiloinnista.

### 2.3 Journalistinen / akateeminen poikkeus (tietosuojalaki 1050/2018, 27 §)

Jos käsittely tapahtuu **yksinomaan journalistisia** tai akateemisen,
taiteellisen tai kirjallisen ilmaisun tarkoituksia varten, **tietosuojalain
27 §** rajaa sovellettavaksi vain osan GDPR:n säännöksistä (sananvapauden ja
tiedonvälityksen turvaamiseksi). Soveltuviksi jäävät käytännössä mm. GDPR
5(1)(a–b), 24–26, 31, 39–40, 42 ja 57–58 artiklat; suuri osa rekisteröidyn
oikeuksista ja siirtosäännöksistä ei sovellu siltä osin kuin niiden soveltaminen
loukkaisi sananvapautta/tiedonvälitystä.

> Varmennettava ja tulkinnanvarainen: Poikkeuksen soveltuminen edellyttää, että
> tarkoitus on **yksinomaan** journalistinen (tai akateeminen). Kansanmuisti
> muistuttaa journalistista/kansalaisjournalistista toimintaa (yleisesti
> kiinnostavan yhteiskunnallisen tiedon välittäminen), mikä tukee poikkeuksen
> soveltuvuutta, mutta tämä **ei ole automaattista** ja on syytä tarkistuttaa.
> Älä rakenna koko compliance-strategiaa pelkän poikkeuksen varaan – pidä myös
> 2.2:n oikeusperuste ja 2.4:n tietojen minimointi voimassa varmuuden vuoksi.

### 2.4 Tietojen minimointi (GDPR 5(1)(c))

- Käsittele vain se data, joka on tarpeen palvelun tarkoitukseen:
  puheenvuorot, äänestykset, vaalilupaukset, edustajan virallinen rooli.
- **Älä** kerää yksityiselämän tietoja (perhe, terveys, talous, uskonto yms.)
  äläkä erityisiä henkilötietoryhmiä (GDPR 9 art.) ilman erillistä perustetta.
- Vältä tarpeetonta rikastamista kolmansien lähteiden tiedoilla.

### 2.5 Rekisteröidyn oikeudet ja oikaisukanava

Vaikka journalistinen poikkeus kaventaa oikeuksia, käytännön ja luottamuksen
vuoksi palvelun tulee tarjota:

- **Oikaisuoikeus (GDPR 16 art.):** julkinen, helposti löydettävä
  **oikaisukanava** (esim. lomake + sähköposti), jolla edustaja tai kuka
  tahansa voi ilmoittaa virheestä. Koska palvelu näyttää vain lähteistettyä
  dataa, oikaisu tarkoittaa käytännössä joko (a) virheen korjaamista
  lähdedatan mukaiseksi, (b) virheellisen koosteen/metriikan korjaamista, tai
  (c) huomautuksen lisäämistä, jos itse virallinen lähde on virheellinen.
- **Poisto-oikeus (GDPR 17 art.):** käsiteltävä tapauskohtaisesti.
  Lähtökohtaisesti virallisen julkisen toiminnan dataa ei poisteta yleisen
  edun / sananvapauden perusteella, mutta pyynnöt on **kirjattava ja
  vastattava** määräajassa; ilmeisen virheellinen tai tarpeeton data
  korjataan/poistetaan.
- Pidä loki saapuneista pyynnöistä ja niiden käsittelystä.

Lähteet:
- https://tietosuoja.fi/tietosuojalaki
- https://www.finlex.fi/fi/lainsaadanto/2018/1050
- https://tietosuoja.fi/en/right-of-access
- GDPR 6, 9, 16, 17 art.: https://gdprinfo.eu/

---

## 3. Vaalikoneiden vastaukset (Yle / HS): voiko niitä käyttää?

### 3.1 Oikeudellinen tilanne

Vaalikonedataan voi kohdistua kaksi suojaa:

1. **Tekijänoikeus / lähioikeus – sui generis tietokantaoikeus
   (tekijänoikeuslaki 49 §).** Tietokanta, jonka sisällön kerääminen,
   varmistaminen tai esittäminen on vaatinut **huomattavan panostuksen**, saa
   suojan **15 vuodeksi**. Vaalikone on tunnetusti journalistinen tuote, johon
   on uponnut merkittävä työpanos (kymmeniä tekijöitä, satoja väitteitä) –
   tämä täyttänee tietokantaoikeuden kynnyksen. Koko tietokannan tai sen
   olennaisen osan systemaattinen kopiointi voi loukata tätä oikeutta.
2. **Käyttöehdot / lisenssi.** Osa vaalikonedatasta julkaistaan avoimena
   datana Creative Commons -lisenssillä, mutta **lisenssi ei ole pelkkä
   CC BY**. Ylen vaalikonedata on julkaistu **CC BY-SA** (Nimeä-JaaSamoin)
   -tyyppisellä lisenssillä, joka sisältää **share-alike-velvoitteen**: johdettu
   teos on lisensoitava samalla lisenssillä. HS:n vaalikoneen ehdot on
   tarkistettava erikseen palvelun käyttöehdoista.

### 3.2 Scraping

Vaikka data olisi teknisesti haettavissa, **suora scraping vaalikone-UI:sta
ohi virallisen avoimen datan / API:n** on riskialtista: se voi rikkoa palvelun
käyttöehtoja ja loukata tietokantaoikeutta. Jos dataa käytetään, se on
otettava **virallisesta avoimen datan julkaisusta** (CSV / API), ei
sivustoa raapimalla.

### 3.3 Johtopäätös: ei mukaan toistaiseksi (EXCLUDED FOR NOW)

**Vaalikonevastauksia ei sisällytetä palveluun tässä vaiheessa.** Syyt:

- **Share-alike-tartunta:** Ylen CC BY-SA -lisenssi voi pakottaa johdetun
  aineiston (ja mahdollisesti sitä näyttävän koosteen) lisensoitavaksi samalla
  copyleft-lisenssillä – tämä on yhteensopimaton riski koko palvelun
  lisensointimallin kanssa ja vaatii erillisen selvityksen.
- **Tietokantaoikeus:** olennaisen osan kopiointi voi loukata
  tekijänoikeuslain 49 §:n suojaa.
- **Eri lähteet, eri ehdot:** Yle ja HS julkaisevat eri ehdoilla; yhtenäistä
  uudelleenkäyttöperustetta ei ole.
- **Linjaus muuhun aineistoon:** muu data on CC BY 4.0 (sallii kaupallisen
  käytön ilman share-alikea); vaalikonedatan ehdot poikkeavat tästä.

> Jatkotoimi, jos halutaan mukaan myöhemmin: hanki Ylen/HS:n avoin
> vaalikonedata virallisesta julkaisusta, lue sen täsmälisenssi, ja arvioi
> share-alike-vaikutus erikseen juristin kanssa. Älä scrapaa.

Lähteet:
- https://yle.fi/a/3-7869597
- https://wiki.aalto.fi/display/copyright/9.2+Luettelo-+ja+tietokantasuoja
- https://www.minilex.fi/a/luettelon-ja-tietokannan-valmistajan-suoja
- Tekijänoikeuslaki 404/1961, 49 §: https://www.finlex.fi/fi/lainsaadanto/1961/404

---

## 4. Kunnianloukkausriski (rikoslaki 24 luku)

### 4.1 Oikeustila

Kunnianloukkaus on säädetty **rikoslain (39/1889) 24 luvun 9–10 §:ssä**.
Olennainen rajaus 9 §:ssä: kunnianloukkauksena **ei pidetä** arvostelua, joka
kohdistuu henkilön menettelyyn **politiikassa, elinkeinoelämässä, julkisessa
virassa tai tehtävässä**, tieteessä, taiteessa tai vastaavassa julkisessa
toiminnassa, **jos se ei selvästi ylitä sitä, mitä voidaan pitää
hyväksyttävänä**. Lisäksi **totuudenmukaisen ja yleiseltä kannalta
merkityksellisen tiedon** esittäminen julkisesta toiminnasta on lähtökohtaisesti
sallittua.

Poliitikko julkista luottamustehtävää hoitaessaan on siten **sietokyvyltään
korkeammalla** kynnyksellä kuin yksityishenkilö.

### 4.2 Riskin pienentäminen palvelun rakenteella

- **Esitä vain lähteistettyjä faktoja.** Jokainen väite (puheenvuoro,
  äänestys) linkitetään suoraan viralliseen lähteeseen → totuudenmukaisuus
  todennettavissa.
- **Selkeästi merkityt laskennalliset metriikat.** Esim. "äänesti X kertaa
  hallituksen esityksiä vastaan" on laskettua dataa, ei väite henkilön
  **motiivista**. Älä esitä tulkintoja vaikuttimista, rehellisyydestä tai
  luonteesta.
- **Ei motiiviväitteitä.** Älä kirjoita "edustaja petti äänestäjänsä" vaan
  "edustaja äänesti toisin kuin vaalilupaus X edellytti (lähde: …)". Lukija
  tekee johtopäätöksen.
- **Neutraali, asiallinen kieli.** Vältä halventavaa tai pilkkaavaa sävyä.
- **Epävarmuuden merkintä.** Jos lähdedata on epätäydellistä tai
  tulkinnanvaraista (esim. vaalilupauksen ja äänestyksen vastaavuus), merkitse
  se selvästi.

### 4.3 Toimituksellinen neutraalisuus

Palvelulla on **toimituksellisen neutraalisuuden velvoite**: kaikkia edustajia
ja puolueita kohdellaan samoilla mittareilla ja samalla esitystavalla. Ei
valikoivaa korostamista, ei poliittista kantaaottavuutta metriikoiden
suunnittelussa.

Lähteet:
- Rikoslaki 24 luku 9 §: https://www.finlex.fi/fi/lainsaadanto/1889/39
- http://www.heikniemi.fi/rikoslaki/rl24.html

---

## 5. Puolueiden vaaliohjelmat: tekijänoikeus ja siteeraus

### 5.1 Tekijänoikeus

Puolueiden vaaliohjelmat ovat lähtökohtaisesti **tekijänoikeudella suojattuja
teoksia** (kirjallisia teoksia). Koko ohjelman tai sen olennaisen osan
kopiointi ilman lupaa ei ole sallittua.

### 5.2 Siteerausoikeus (tekijänoikeuslaki 22 §)

**Tekijänoikeuslain 22 §:** julkistetusta teoksesta saa **hyvän tavan
mukaisesti** ottaa lainauksia **tarkoituksen edellyttämässä laajuudessa**.

Edellytykset, jotka palvelun on täytettävä:

1. **Teos on julkistettu** – vaaliohjelmat on julkaistu → ok.
2. **Asiallinen yhteys (sitaattifunktio)** – sitaatin tulee tukea omaa
   esitystä (esim. konkretisoida vaalilupaus, jota verrataan äänestyksiin), ei
   korvata sitä.
3. **Hyvä tapa ja kohtuullinen laajuus** – lainaa **lyhyitä** otteita, ei koko
   ohjelmaa eikä laajoja osioita.
4. **Lähde ja tekijä mainittava** alan hyvän tavan mukaisesti.

### 5.3 Käytännön ohje rakentajalle

- Tallenna ja näytä vaalilupauksista vain **lyhyt suora sitaatti** + linkki
  alkuperäiseen ohjelmaan.
- Liitä jokaiseen sitaattiin: puolue, ohjelman nimi/vuosi ja lähde-URL.
- Älä julkaise koko ohjelmaa palvelussa; linkitä alkuperäiseen.

Lähteet:
- Tekijänoikeuslaki 404/1961, 22 §: https://www.finlex.fi/fi/lainsaadanto/1961/404
- https://tekijanoikeus.fi/luvallinen-kaytto/
- https://fi.wikipedia.org/wiki/Sitaattioikeus

---

## 6. Compliance-tarkistuslista (järjestelmän on täytettävä)

Jokainen kohta on toteutettava ja todennettava ennen tuotantoa.

### Lähteet ja attribuutio
- [ ] **Eduskunnan attribuutio** näkyy jokaisella datasivulla (kohta 1: lähde +
      CC BY 4.0 -linkki + maininta että dataa on muokattu/koostettu).
- [ ] **Jokainen yksittäinen väite linkittyy** suoraan viralliseen lähteeseen
      (puheenvuoro, äänestys, vaaliohjelma).
- [ ] Lisenssikenttä luetaan ohjelmallisesti datalähteestä ja näytetään.

### Tietosuoja (GDPR / tietosuojalaki)
- [ ] Käsitellään **vain virallista, jo julkista** dataa edustajan julkisesta
      toiminnasta; ei yksityiselämän tietoja, ei erityisiä tietoryhmiä.
- [ ] **Oikeusperuste dokumentoitu** (yleinen etu / oikeutettu etu) ja kevyt
      tasapainotesti tehty.
- [ ] **Tietojen minimointi** toteutettu (vain tarvittavat kentät).
- [ ] **Oikaisukanava** julkinen ja helposti löydettävä (lomake/sähköposti).
- [ ] **Oikaisu- ja poistopyynnöt kirjataan** ja niihin vastataan määräajassa.
- [ ] Tietosuojaseloste julkaistu (rekisterinpitäjä, tarkoitus, oikeusperuste,
      oikeudet, yhteystiedot).

### Sisällön neutraalisuus ja totuudenmukaisuus (kunnianloukkausriski)
- [ ] **Ei motiiviväitteitä** – vain faktat ja selkeästi merkityt laskennalliset
      metriikat.
- [ ] **Laskennalliset metriikat merkitty** laskennallisiksi, laskutapa avoin.
- [ ] **Toimituksellinen neutraalisuus** – samat mittarit kaikille edustajille
      ja puolueille.
- [ ] **Epävarmuus merkitty** näkyvästi (epätäydellinen/tulkinnanvarainen data).
- [ ] Asiallinen, ei-halventava kieli.

### Vaaliohjelmat (siteeraus)
- [ ] Vain **lyhyet sitaatit** + lähde/tekijä + linkki alkuperäiseen; ei koko
      ohjelmaa.

### Vaalikoneet
- [ ] **Vaalikonedataa EI sisällytetä** (kohta 3); ei scrapingia
      vaalikone-UI:sta.

### Yleinen
- [ ] Datan käsittelyssä **vain virallinen avoin data / API**, ei luvatonta
      raapimista mistään lähteestä.
- [ ] Tämä dokumentti tarkistutettu juristilla/tietosuojavastaavalla kohtien
      2–4 osalta ennen tuotantoa.

# Kansanmuisti — pääsuunnitelma

> Verkkopalvelu, joka kartoittaa, analysoi ja esittää suomalaisten poliittisten päättäjien
> julkisen ja todennettavan toiminnan: puheenvuorot, äänestykset ja vaalilupaukset.
> **Ei tulkitse motiiveja.** Näyttää mitä on sanottu, miten on äänestetty, mitä on luvattu,
> miten sanat ja teot ovat linjassa, missä on ristiriitoja ja missä data puuttuu.

## 1. Periaatteet (sitovat)
1. **Jokaisella väitteellä on lähde.** Jokainen näytetty fakta linkittyy alkuperäiseen Eduskunnan
   aineistoon (URL + tekninen avain + nouto­aika).
2. **Tulkinta erotetaan faktasta.** Lasketut tunnusluvut (esim. johdonmukaisuus) esitetään
   metodikuvauksen kanssa; ne eivät ole "totuuksia" vaan läpinäkyviä laskelmia.
3. **Ei motiiviväitteitä.** Emme väitä *miksi* joku äänesti tai puhui jollakin tavalla.
4. **Puutteet näkyviin.** Kattavuusraportti kertoo mitä on, mistä vuosilta, ja mitä puuttuu ja miksi.
5. **Ei pisteytystä ilman laskentakaavaa.** Jokainen luku on jäljitettävissä kaavaan ja dataan.
6. **Neutraali käyttöliittymä.** Ei poliittisesti ohjailevaa kieltä, värejä eikä järjestystä.

## 2. Datalähteet
| Lähde | Tila | Huom |
|-------|------|------|
| Eduskunnan avoin data — `MemberOfParliament`, `HetekaData` | ✅ Käytössä | Jäsenet + biografia-XML |
| `SaliDBAanestys` + `SaliDBAanestysEdustaja` | ✅ Käytössä | Täysistuntoäänestykset + edustajakohtaiset äänet |
| `SaliDBPuheenvuoro` | ✅ Käytössä | Täysistuntopuheet (alkaa 2014), teksti XmlData-kentässä |
| `VaskiData` (HE:t, valiokunta-asiakirjat) | 🔶 Vaihe 2 | Suuri XML-aineisto; linkitys äänestyksiin `AanestysValtiopaivaasia`-kentän kautta |
| Puolueiden vaaliohjelmat / lupaukset | 🔶 Manuaalinen seed + skeema | Ei yhtä konetta­luettavaa rajapintaa → kuratoitu, lähteistetty seed-aineisto |
| Vaalikonevastaukset (Yle/HS) | ⛔ Estynyt | Lisenssi-/tekijänoikeusrajoitteet — ks. LEGAL_ETHICS.md |
| Kunnat / EU-taso | 🔶 Roadmap | Eri rajapinnat; jätetään jatkokehitykseen |

Lähde-API: `https://avoindata.eduskunta.fi/api/v1/tables/{Taulu}/rows?perPage=&page=`
Lisenssi: Eduskunnan avoin data on CC BY 4.0 (vahvistus LEGAL_ETHICS.md:ssä).

## 3. Arkkitehtuuri
- **Kieli:** Python 3.12+ (kehitetty 3.14).
- **Keruu:** `src/kansanmuisti/collect/` — sivutettu, uudelleenajettava (resumable), throttlattu HTTP-klientti.
- **Varasto:** SQLite (`data/kansanmuisti.sqlite3`), FTS5-kokotekstihaku, json1. Skeema = `schema.sql`,
  migraatiot `migrations/`.
- **Analyysi:** `src/kansanmuisti/analyze/` — läpinäkyvä, deterministinen putki (aiheet → linjaus → johdonmukaisuus).
- **Web:** FastAPI + Jinja2 + vähän vaniljaJS:ää (ei build-vaihetta). Palvelee profiilit, haku, näkymät.
- **Testit:** pytest (yksikkö + integraatio kiinteällä fixture-datalla).

## 4. Tietomalli (ydin)
`person`, `person_party`, `person_term`, `person_minister_role`,
`vote`, `vote_record`, `speech`,
`topic`, `topic_keyword`, `speech_topic`, `vote_topic`,
`promise`, `promise_topic`,
`source` (provenienssi), `coverage_stat`, `analysis_*` (lasketut tunnusluvut).

## 5. Analyysi (täysi kuvaus: METHODOLOGY.md)
- Aihealueiden tunnistus (läpinäkyvä avainsana-/sanastopohjainen luokittelu, pisteet näkyviin).
- Puheiden ja äänestysten vertailu aiheittain.
- Lupaus vs. teko -vertailu (kuratoitu lupaus → liittyvät äänestykset).
- Kannanmuutosten aikajana.
- Puoluelinjasta poikkeamat (edustajan ääni vs. ryhmän enemmistö per äänestys).
- Johdonmukaisuusindeksi **eksplisiittisellä kaavalla** + epävarmuusmerkinnät.

## 6. Verkkosivun näkymät
Haku · päättäjäprofiili · puolueprofiili · aihenäkymä · aikajana · lupaukset vs. teot ·
äänestyskäyttäytyminen · puheanalyysi · vertailu · lähdelinkit · menetelmäsivu · kattavuusnäkymä · korjauskanava.

## 7. Toteutusjärjestys (ja tila)
1. Suunnitelma ✅
2. Ala-agentit rinnakkain (juridiikka, metodologia, datalähteet) ✅
3. Löydösten yhdistäminen ✅
4. Suunnitelman auditointi ✅
5. Datankeruu ✅
6. Tietokanta ✅
7. Analyysiputki ✅
8. Verkkosivu ✅
9. Testit ✅
10–13. Auditointikierrokset → korjaukset → uudelleenauditointi ✅

## 8. Rehellisyys ajasta/laajuudesta
Keruukoodi kykenee koko 10 vuoden aineistoon (resumable). Tässä ympäristössä ajetaan todellinen,
rajattu mutta merkittävä siivu (uusin vaalikausi kokonaan + kaikki istuvat edustajat) end-to-end.
Kattavuusraportti (COVERAGE.md, generoitu) kertoo tarkalleen mitä haettiin, ja KNOWN_ISSUES.md +
ROADMAP.md mitä jäi ja miten se viimeistellään.

# UX-periaatteet ja -ratkaisut

Tavoite: äänestäjä ymmärtää, mihin jokainen näytetty asia perustuu, eikä käyttöliittymä ohjaile
poliittisesti.

## Suunnitteluperiaatteet
1. **Neutraalius.** Ei puoluevärejä (puolue näytetään tekstitunnuksena, ei brändivärinä). Ei
   ohjailevaa järjestystä: listat aakkosjärjestyksessä tai päivämäärän mukaan, ei "parhaat ensin".
   Sama mittaristo kaikille.
2. **Fakta ≠ tulkinta.** Lasketut luvut (esim. johdonmukaisuusindeksi) merkitään aina näkyvällä
   "laskennallinen indikaattori" -merkinnällä ja esitetään komponentit + luottamustaso. Faktat
   (äänet, päivämäärät, puheet) esitetään sellaisinaan lähteineen.
3. **Lähde aina näkyvissä.** Jokaisella sivulla on linkki alkuperäiseen Eduskunnan aineistoon ja
   CC BY 4.0 -attribuutio. Äänestys-, puhe- ja henkilösivuilla suora lähdelinkki.
4. **Puutteet näkyviin.** Jos dataa ei ole, se kerrotaan ("ei riittävästi dataa") — ei näytetä
   nollaa tulkintana. Kattavuussivu kertoo mitä on ja mitä puuttuu.
5. **Epävarmuus esiin.** Epävarmuusliput (LOW_SAMPLE, SINGLE_COMPONENT, PARTY_CHANGE…) näytetään
   suoraan tunnusluvun vieressä.
6. **Korjattavuus.** Joka sivun alalaidassa linkki korjauskanavaan; henkilösivulla esitäytetty.

## Näkymät (toteutettu)
| Näkymä | Polku | Sisältö |
|---|---|---|
| Etusivu | `/` | Haku, ydinluvut, aiheet, puolueet, lukuohje |
| Haku | `/haku?q=` | Edustajat, puheet (FTS), äänestykset |
| Päättäjäprofiili | `/edustaja/{id}` | Johdonmukaisuusindeksi + komponentit, äänestyskäyttäytyminen, poikkeamat, kannanmuutosten aikajana, lupaukset vs. teot, aihekohtainen aktiivisuus, puheet, äänet, historia, lähteet |
| Puolueprofiili | `/puolue/{code}` | Edustajat, karkeat keskiarvot varoituksin |
| Aihenäkymä | `/aihe/{slug}` | Aktiivisimmat puhujat, puheet, äänestykset |
| Äänestys | `/aanestys/{id}` | Tulos, ryhmittäin, edustajakohtaiset äänet, lähde |
| Puheenvuoro | `/puhe/{id}` | Koko teksti, aiheet osuvuuspisteineen, saman säädöksen äänestykset, lähde |
| Lupaukset | `/lupaukset` | Kuratoidut lupaukset lähteineen ja äänestyskytkennät |
| Vertailu | `/vertailu?a=&b=` | Kahden edustajan rinnakkaisvertailu |
| Kattavuus | `/kattavuus` | Datan kattavuus ja mittarit |
| Menetelmät | `/menetelmat` | METHODOLOGY.md renderöitynä |
| Etiikka | `/etiikka` | LEGAL_ETHICS.md renderöitynä |
| Korjaus | `/korjaus` | Virheilmoituslomake |

## Saavutettavuus
- Semanttinen HTML, riittävä kontrasti, ei väriin perustuvaa ainoaa merkitystä (pillit sisältävät
  tekstin), responsiivinen ruudukko, näppäimistöystävälliset lomakkeet.

## Tietoinen rajaus
Indeksiä ei koskaan näytetä ilman komponentteja ja luottamustasoa. "Poikkeama ryhmästä" -luku
esitetään neutraalisti tekstillä, jossa todetaan ettei korkea poikkeama ole "huono".

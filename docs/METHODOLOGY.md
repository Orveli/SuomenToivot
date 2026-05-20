# Kansanmuisti – Analyysimetodologia

Tämä dokumentti määrittelee, miten Kansanmuisti laskee ja esittää
kansanedustajien puheista, äänestyksistä ja vaalilupauksista johdetut
tunnusluvut. Tavoite on **läpinäkyvyys ja toistettavuus**: jokainen luku on
johdettavissa raakadatasta tässä kuvatuilla kaavoilla, ilman piilotettuja
parametreja.

Läpileikkaavat periaatteet:

- **Ei motiiviväitteitä.** Emme koskaan päättele, *miksi* edustaja äänesti tai
  puhui tietyllä tavalla. Esitämme vain havaitun käyttäytymisen.
- **Jokainen väite on lähteistetty.** Jokainen näytetty luku linkittyy
  taustadataan (äänestys-ID, puheenvuoro-ID, lupauksen lähde).
- **Tulkinta erotetaan faktasta.** Faktat (äänestysarvot, päivämäärät) ja
  niistä johdetut tulkinnalliset indikaattorit (esim. johdonmukaisuusindeksi)
  merkitään selvästi eri tasoiksi.
- **Ei pisteytystä ilman kaavaa.** Jokaisella tunnusluvulla on tässä esitetty
  eksplisiittinen kaava.
- **Epävarmuus näytetään aina.** Jokaiseen tunnuslukuun liitetään
  luottamustaso ja datan kattavuustieto.

> **Indikaattori, ei tuomio.** Kaikki johdetut luvut ovat *laskennallisia
> indikaattoreita*, eivät arvioita edustajan rehellisyydestä, pätevyydestä tai
> aikomuksista.

---

## 0. Datalähteet ja kentät

| Lähde | Taulu | Keskeiset kentät |
|---|---|---|
| Edustajat | `Member` | `personId`, `name`, `party`, `isMinister`, `biographyXml` |
| Edustajan historia | (biografia-XML) | puoluejäsenyydet päivämäärineen, valiokunnat, ministerinroolit, vaalipiirit |
| Äänestykset | `SaliDBAanestys` | `voteId`, `date`, `title`, `legislativeItem` (esim. "HE 95/2024 vp"), tuloslaskurit |
| Äänestys/edustaja | `SaliDBAanestysEdustaja` | `voteId`, `personId`, `voteValue` ∈ {Jaa, Ei, Tyhjää, Poissa}, `partyAbbr` |
| Puheenvuorot | `SaliDBPuheenvuoro` | `speechId`, `personId`, `party`, `datetime`, `xmlData` (vapaa teksti), 2014→ |
| Lupaukset | `Promise` | `promiseId`, `text`, `party`/`personId`, `topicId`, `sourceUrl`, `sourceDate`, kuratointitiedot |

Kaikki johdetut taulut alla on suunniteltu deterministisiksi: sama raakadata +
sama leksikkoversio → sama tulos.

**Versiointi.** Topic-leksikko ja lupauskartoitukset versioidaan
(`lexiconVersion`, `mappingVersion`). Jokainen tallennettu tunnusluku viittaa
käytettyyn versioon, jotta vanhat luvut ovat toistettavissa.

---

## 1. Aihetaksonomia ja tägäys (lexicon-luokitin)

### 1.1 Periaate

Käytämme **läpinäkyvää avainsanapohjaista (lexicon) luokitinta**. Ei
mustaa laatikkoa eikä koneoppimismallia – jokainen aihe-osuma on jäljitettävissä
yksittäiseen avainsanaan tekstissä. Tämä on tarkoituksella tarkkuus–kattavuus
-vaihtokaupassa kattavuuden puolella ja täysin auditoitava.

### 1.2 Tekstin normalisointi

Sekä puheenvuoron teksti että äänestyksen otsikko + säädöskohde
normalisoidaan ennen ottelua:

```
normalize(text):
    t = lowercase(text)
    t = strip XML/HTML-tagit
    t = poista välimerkit paitsi sananväli
    t = NFC-unicode-normalisointi
    tokens = split(t, whitespace)
    palauta tokens   # ei stemmausta; leksikko käyttää sananvartaloprefiksejä
```

Suomen taivutuksen vuoksi avainsanat tallennetaan **vartaloprefikseinä** ja
ottelu tehdään prefiksinä sanan alkuun:

```
matches(token, keyword):
    # keyword esim. "verot" osuu sanoihin verotus, verotuksen, veroja(EI), vero(EI)
    palauta token.startsWith(keyword)
```

Monisanaiset avainsanat (esim. `"perustulo"`, `"nato jäsenyys"`) otetaan
liukuvalla ikkunalla token-jonosta. Jokainen avainsana voi saada painon
`w ≥ 1` (oletus 1; väljät/yleiset termit voivat saada `0.5`, terävät termit
`2`).

### 1.3 Aihepistemäärä

Annetulle tekstille ja aiheelle `T` (jolla on avainsanajoukko `K_T`):

```
rawScore(text, T) = Σ_{k ∈ K_T}  weight(k) × count_distinct_positions(text, k)
```

`count_distinct_positions` laskee montako *erillistä* sanapaikkaa avainsana
osuu (ei sama positio kahdesti). Pitkät tekstit normalisoidaan pituudella, jotta
pitkä puhe ei automaattisesti voita:

```
score(text, T) = rawScore(text, T) / sqrt(max(tokenCount, MIN_LEN))
MIN_LEN = 25
```

`sqrt`-normalisointi vaimentaa pituusvaikutusta säilyttäen silti signaalin
useammasta osumasta.

### 1.4 Kynnys, valinta, tasapelit ja ei-osuma

```
HARD_THRESHOLD       = 0.15   # alle tämän: ei aihetta
DOMINANCE_RATIO      = 0.40   # aihe "pääaiheeksi" jos score ≥ 0.40 × topScore
MAX_TOPICS_PER_ITEM  = 3
```

Algoritmi:

```
assignTopics(text):
    scores = { T: score(text, T) for T in TAXONOMY }
    topScore = max(scores.values)
    if topScore < HARD_THRESHOLD:
        palauta { topics: [], primary: null, status: "NO_MATCH" }
    candidates = [T for T in TAXONOMY if scores[T] >= DOMINANCE_RATIO × topScore
                                       and scores[T] >= HARD_THRESHOLD]
    candidates = sort(candidates, by=scores desc, then by topicId asc)  # determinismi
    candidates = candidates[0 : MAX_TOPICS_PER_ITEM]
    primary = candidates[0]
    status = "MULTI" if len(candidates) > 1 else "SINGLE"
    palauta { topics: candidates, primary: primary, status: status, scores: scores }
```

- **Tasapeli** (kaksi aihetta yhtä suuri score) ratkaistaan deterministisesti
  pienemmän `topicId`:n hyväksi, ja molemmat säilyvät listalla (`MULTI`).
- **Ei-osuma** (`NO_MATCH`) tallennetaan eksplisiittisesti aiheeseen
  `muu/luokittelematon`. Tällaisia kohteita ei käytetä aihekohtaisissa
  vertailuissa, mutta niiden osuus raportoidaan kattavuuslukuna.

### 1.5 Talletettava taulu

`TopicAssignment(itemType ∈ {speech, vote}, itemId, topicId, score, isPrimary,
status, lexiconVersion)` — yksi rivi per (kohde, aihe).

### 1.6 Lähtötaksonomia (~15 aihetta)

| topicId | Aihe | Esimerkkiavainsanoja (vartaloprefiksit) |
|---|---|---|
| `talous` | Talous | talous, budjet, julkis talou, alijääm, velka, brutto kansan, suhdann, valtiontalou |
| `terveydenhuolto` | Terveydenhuolto | terveydenhuol, sairaal, soten, hoito takuu, lääk, hoitaj, terveys asem, potilas |
| `koulutus` | Koulutus | koulut, opetu, oppivelvol, yliopist, ammattikorkea, varhaiskasvat, opiskel, oppimi |
| `ilmasto` | Ilmasto ja ympäristö | ilmast, päästö, hiilineutr, luonnon suojel, monimuoto, ympäristö, kasvihuone, luontokato |
| `maahanmuutto` | Maahanmuutto | maahanmuut, turvapaik, pakolais, kotoutu, oleskelulu, työperäi maahan, rajamenet |
| `turvallisuus` | Turvallisuus ja puolustus | puolust, maanpuolus, nato, asevelvol, sotilas, kriisinhal, varuskun, sisäinen turval |
| `sosiaaliturva` | Sosiaaliturva | sosiaalitur, toimeentulotu, perustur, työttömyysturv, eläke, lapsilis, asumistu, perustulo |
| `verotus` | Verotus | verot, tulover, arvonlisäver, yhteisöver, veron koroitu, veroaste, pääomatulover |
| `eu` | EU | euroopan unio, eu komiss, eu rahast, eu jäsen, sisämarkkin, eu direkt, euroopan parlament |
| `maatalous` | Maatalous | maatalou, viljel, maatil, maaseut, ruoan tuotan, karja, maataloustu, elintarvike omavarai |
| `liikenne` | Liikenne | liikent, tie verkko, rata, joukkoliiken, raidelii, väylä, autoil, liikenne turval |
| `asuminen` | Asuminen | asumi, asunto, vuokra, kohtuuhintai, kaavoitu, ara asunto, asuntopolit, rakentami |
| `oikeus` | Oikeus ja sisäasiat | oikeus laitos, rikos, polii, tuomioistu, vankeu, syyttäj, perus oikeu, sisä asiat |
| `tyo` | Työ | työllis, työ markkin, työ ehto, lakko, palkka, työ sopimu, työttömy, paikallinen sopimi |
| `energia` | Energia | energi, sähkö, ydinvoim, tuulivoim, fossiili, energia oma varai, kantaverkk, polttoaine |
| `muu` | Muu / luokittelematon | (varataan NO_MATCH-tapauksille) |

> Leksikko on elävä taulukko. Jokainen muutos kasvattaa `lexiconVersion`-numeroa
> ja vanhat tunnusluvut säilyvät vanhalla versiolla, jotta historia on
> toistettavissa.

---

## 2. Puhe↔äänestys-vertailu aiheittain

Tavoite: kuvata, **puhuuko ja äänestääkö** edustaja samasta aiheesta — ei
arvottaa kantaa. Tämä on aktiivisuus- ja yhdenmukaisuusmittari, ei
"oikein/väärin"-mittari.

### 2.1 Aihekohtainen aktiivisuus

Edustajalle `p`, aiheelle `T`, aikaikkunalle `[t0, t1]`:

```
speechCount(p, T)  = niiden puheenvuorojen lkm, joiden TopicAssignment sisältää T
voteCount(p, T)    = niiden äänestysten lkm (joissa p ei Poissa),
                     joiden vote-TopicAssignment sisältää T
```

### 2.2 Topikaalinen linjaus (alignment) per äänestys

Jokaiselle aiheen `T` äänestykselle `v`, johon edustaja `p` on osallistunut,
etsitään ajallisesti läheiset *saman aiheen* puheenvuorot:

```
WINDOW_DAYS = 30
relatedSpeeches(p, v) = { s : p:n puheenvuoro,
                          T ∈ topics(s),
                          T ∈ topics(v),
                          |date(s) − date(v)| <= WINDOW_DAYS,
                          mieluiten sama legislativeItem jos saatavilla }
```

Jos `relatedSpeeches` ei ole tyhjä, äänestys saa lipun `hasContextSpeech = true`.
**Emme** päättele puheen sävystä, tukeeko se Jaa- vai Ei-ääntä — se olisi
tulkinta. Esitämme parin (puhe, ääni) käyttäjälle linkitettynä, ja käyttäjä voi
lukea molemmat.

### 2.3 Talletettava taulu

`SpeechVoteLink(personId, voteId, topicId, speechIds[], dayGap,
sameLegislativeItem)`.

### 2.4 Aihekohtainen "puhe–ääni-kattavuus"

```
speechVoteCoverage(p, T) = | äänestykset(T) joilla hasContextSpeech | / voteCount(p, T)
```

Tämä on **kuvaileva** luku: kuinka usein edustaja on puhunut aiheesta lähellä
äänestyshetkeä. Sitä ei tulkita oikeellisuudeksi.

---

## 3. Lupaus↔toiminta-vertailu

> **Tämä on kuratoitu, lähteistetty toimituksellinen kartoitus — ei
> automaattinen totuus.** Lupauksen ja äänestyksen yhteys edellyttää
> ihmisarviota siitä, mitä lupaus tarkoittaa ja mikä äänestys on sille
> relevantti. Kone ei voi tätä luotettavasti päätellä, joten emme teeskentele
> tekevämme sitä.

### 3.1 Lupauksen rakenne

Kuratoitu lupaus `Promise` sisältää:

- `text`, `topicId`, `sourceUrl`, `sourceDate` (esim. puolueohjelma, vaalikone),
- `direction` ∈ {edistää, vastustaa, säilyttää} suhteessa johonkin asiaan,
- kuratoijan nimimerkki + päiväys (`curatedBy`, `curatedAt`).

### 3.2 Lupauksen kartoitus äänestyksiin

Toimittaja/kuratoija liittää lupaukseen joukon **relevantteja äänestyksiä**
manuaalisesti. Jokaiselle linkille tallennetaan:

```
PromiseVoteMap(promiseId, voteId,
               expectedVoteValue ∈ {Jaa, Ei},   # mikä ääni TUKISI lupausta
               rationale,                        # vapaa teksti: miksi tämä äänestys on relevantti
               sourceNote,                       # lähde/perustelu
               curatedBy, curatedAt, mappingVersion)
```

`expectedVoteValue` on toimituksellinen tulkinta siitä, kumpi äänestyspuoli on
linjassa lupauksen kanssa kyseisessä äänestyksessä. Tämä tulkinta näytetään
käyttäjälle perusteluineen.

### 3.3 Linjauksen määritys edustajalle

Edustajalle `p` ja lupaukselle `q`, käyttäen sen kartoitettuja äänestyksiä:

```
foreach (q, v) in PromiseVoteMap:
    val = voteValue(p, v)
    if val == Poissa or val == Tyhjää or val puuttuu:
        per_vote = "epäselvä"          # ei riittävää signaalia
    elif val == expectedVoteValue:
        per_vote = "tukee"
    else:
        per_vote = "ristiriidassa"

aggregate over kartoitetut äänestykset:
    s = #tukee, c = #ristiriidassa, u = #epäselvä
    if s+c == 0:                       alignment = "epäselvä"   # ei substantiivisia ääniä
    elif c == 0:                       alignment = "tukee"
    elif s == 0:                       alignment = "ristiriidassa"
    else:                              alignment = "epäselvä (ristiriitainen)"
```

Esitettävät arvot: **tukee / ristiriidassa / epäselvä**. Jokainen yksittäinen
(lupaus, äänestys, edustajan ääni, expectedVoteValue, perustelu) näytetään
auki, jotta käyttäjä näkee laskennan.

### 3.4 Mitä emme väitä

Emme väitä, että edustaja "petti lupauksen" tai toimi vilpillisesti.
"Ristiriidassa" tarkoittaa täsmälleen: *tässä kuratoidussa äänestyksessä
edustaja äänesti toisin kuin lupausta tukeva ääni olisi ollut*. Konteksti
(esim. muutosesitykset, paketin osa) voi selittää tämän — siksi perustelu ja
linkit näytetään aina.

---

## 4. Kannanmuutoksen aikajana

Tavoite: havaita ja esittää, kun edustajan **äänestyskäyttäytyminen samasta
asiasta tai asiatyypistä muuttuu ajan myötä**. Emme väitä mielipiteen
muuttuneen — kuvaamme äänten muutoksen.

### 4.1 Vertailtavuusryhmät

Kaksi äänestystä ovat vertailukelpoisia, jos:

```
comparable(v1, v2):
    sameItem    = (legislativeItemBase(v1) == legislativeItemBase(v2))   # esim. "HE 95/2024 vp"
    sameTopic   = (primaryTopic(v1) == primaryTopic(v2))
    palauta sameItem OR sameTopic
```

`legislativeItemBase` poistaa kohdan/momentin tarkenteen ja säilyttää
perustunnisteen.

### 4.2 Muutoksen havaitseminen

Järjestetään edustajan substantiiviset äänet (`Jaa`/`Ei`, ei `Tyhjää`/`Poissa`)
vertailuryhmässä aikajärjestykseen:

```
sequence = [(date, voteValue) for v in group if voteValue in {Jaa, Ei}], sorted by date

changePoints = []
for i in 1..len(sequence)-1:
    if sequence[i].voteValue != sequence[i-1].voteValue:
        changePoints.append({
            from: sequence[i-1],
            to:   sequence[i],
            topicId, itemBase,
            gapDays: date diff
        })
```

- Vain `Jaa↔Ei`-vaihdokset lasketaan muutokseksi. `Tyhjää`/`Poissa` katkaisevat
  jatkumon mutta eivät itsessään ole "muutos".
- **Sama asia (`sameItem`)** -muutos on vahva signaali ja merkitään
  `strength = "vahva"`. Pelkkä **sama aihe** -muutos on `strength = "heikko"`,
  koska eri äänestykset voivat koskea eri asiakokonaisuuksia.

### 4.3 Esitys ja talletus

`PositionChange(personId, topicId, itemBase, fromValue, fromDate, toValue,
toDate, gapDays, strength)`. Aikajanalla näytetään molemmat äänestykset
linkkeineen; käyttäjä näkee otsikot ja voi arvioida, ovatko ne aidosti sama
kysymys.

---

## 5. Puoluelinjasta poikkeaminen

### 5.1 Puolueen enemmistökanta per äänestys

Kullekin äänestykselle `v` ja puolueelle `P` lasketaan **vain substantiiviset
äänet**:

```
yes(P,v) = #{ p in P : voteValue(p,v) == Jaa }
no(P,v)  = #{ p in P : voteValue(p,v) == Ei }
substantive(P,v) = yes(P,v) + no(P,v)

partyLine(P,v):
    if substantive(P,v) == 0:               palauta UNDEFINED   # ei kantaa
    if yes(P,v) > no(P,v):                   palauta Jaa
    if no(P,v) > yes(P,v):                   palauta Ei
    else:                                    palauta TIE          # tasan
```

`Tyhjää` ja `Poissa` eivät vaikuta enemmistön suuntaan.

### 5.2 Poikkeaman määritys edustajalle

```
deviation(p, v):
    val  = voteValue(p, v)
    line = partyLine(party(p), v)
    if val in {Poissa}:               palauta "EI_HUOMIOIDA"   # poissa: ei lasketa nimittäjään
    if val == Tyhjää:                 palauta "PIDÄTTYI"        # ei poikkeama eikä linja
    if line in {UNDEFINED, TIE}:      palauta "EI_LINJAA"      # puolueella ei selvää kantaa
    if val == line:                   palauta "LINJASSA"
    else:                             palauta "POIKKESI"
```

### 5.3 Poikkeamaprosentti per edustaja

```
eligible(p)  = #{ v : deviation(p,v) == "LINJASSA" tai "POIKKESI" }
              # eli substantiivinen ääni, jossa puolueella oli selvä linja
deviations(p) = #{ v : deviation(p,v) == "POIKKESI" }

deviationRate(p) = deviations(p) / eligible(p)        jos eligible(p) > 0
                 = UNDEFINED (ei tarpeeksi dataa)     jos eligible(p) == 0
```

Käsittely:

- **Poissa**: jätetään pois nimittäjästä (`eligible`) kokonaan — ei rankaise
  poissaolosta poikkeamana eikä linjana.
- **Tyhjää**: jätetään pois nimittäjästä (ei substantiivinen kanta).
- **TIE / UNDEFINED puoluelinja**: äänestys ei kelpaa poikkeaman arviointiin.
- **Puolueenvaihdos**: `party(p)` määräytyy biografia-XML:n puoluejäsenyyden
  voimassaolopäivien mukaan kunkin äänestyksen `date`-hetkellä, ei nykyisen
  puolueen mukaan.

Talletus: `PartyDeviation(personId, voteId, partyAtVote, memberValue,
partyLine, classification)`; aggregaatti `MemberDeviationRate(personId,
periodId, deviations, eligible, rate)`.

---

## 6. Johdonmukaisuusindeksi (0–100)

> **Laskennallinen indikaattori, ei tuomio.** Indeksi yhdistää kaksi
> kuvailevaa signaalia yhdeksi luvuksi vertailun helpottamiseksi. Se ei mittaa
> edustajan rehellisyyttä eikä pätevyyttä. Kaikki syötteet näytetään käyttäjälle
> auki.

### 6.1 Komponentit

**(a) Puhe–ääni-topikaalinen linjaus** — kuinka usein edustajan äänestyksiin
liittyy saman aiheen puheenvuoro lähellä äänestyshetkeä (kohta 2.4):

```
A(p) = keskiarvo aiheiden T yli speechVoteCoverage(p, T),
       painotettuna aiheen voteCount(p, T):lla
     = Σ_T voteCount(p,T) × speechVoteCoverage(p,T)  /  Σ_T voteCount(p,T)
A(p) ∈ [0, 1]
```

Tulkinta: korkea A = edustaja tyypillisesti puhuu niistä aiheista, joista myös
äänestää (avoimuus/aktiivisuus). **Ei** kannan oikeellisuus.

**(b) Puoluelinjakäyttäytyminen** — vakaus suhteessa omaan puolueeseen
(kohta 5.3):

```
B(p) = 1 − deviationRate(p)            jos deviationRate määritelty
     = ei käytettävissä                 muuten
B(p) ∈ [0, 1]
```

`B` mittaa puolueuskollisuutta. Korkea poikkeama ei ole "huono" — itsenäinen
äänestäjä saa matalan B:n. Tämä näytetään neutraalisti ja selitetään
käyttäjälle.

### 6.2 Indeksin kaava

```
W_A = 0.5     # paino: puhe–ääni-linjaus
W_B = 0.5     # paino: puoluelinjavakaus

# käytä vain niitä komponentteja, jotka ovat saatavilla:
available = []
if A(p) määritelty: available.append((A, W_A))
if B(p) määritelty: available.append((B, W_B))

if available tyhjä:
    consistencyIndex(p) = UNDEFINED
else:
    num = Σ_(comp, w) in available   w × comp
    den = Σ_(comp, w) in available   w
    consistencyIndex(p) = round( 100 × num / den )
```

Indeksi on aina välillä **0–100**. Painot `W_A`, `W_B` ovat eksplisiittiset ja
näytetään käyttöliittymässä; käyttäjä voi nähdä myös komponentit `A` ja `B`
erikseen.

### 6.3 Luottamustaso ja puuttuva data

Luottamus perustuu datan määrään, ei indeksin arvoon:

```
n_votes    = Σ_T voteCount(p, T)
n_speeches = Σ_T speechCount(p, T)
n_eligible = eligible(p)                  # kohta 5.3

confidenceScore(p) = min(1,  n_eligible / 50)
                   × min(1,  (n_speeches + 1) / 20 )   # +1: vältä nollaa
componentsAvailable = len(available)       # 0, 1 tai 2

confidenceLevel:
    "korkea"  jos confidenceScore >= 0.66 ja componentsAvailable == 2
    "kohtalainen" jos confidenceScore >= 0.33
    "matala"  muuten
```

Puuttuvan datan vaikutus:

- Jos vain yksi komponentti on saatavilla, indeksi lasketaan siitä mutta
  `confidenceLevel` lasketaan korkeintaan `"kohtalainen"`.
- Jos `n_eligible` tai puhemäärä on pieni, luottamus laskee suoraan kaavan
  kautta.
- Puuttuvat aiheet (NO_MATCH-osuus) raportoidaan erikseen `coverage`-lukuna.

### 6.4 Esitys

Käyttöliittymässä näytetään aina yhdessä:

```
Johdonmukaisuusindeksi: 72 / 100   [laskennallinen indikaattori]
  ├─ A puhe–ääni-linjaus:        0.81   (paino 0.5)
  ├─ B puoluelinjavakaus:        0.63   (paino 0.5, poikkeama 37 %)
  ├─ Luottamus: kohtalainen      (äänestyksiä 41, puheita 12)
  └─ Aihekattavuus: 88 % luokiteltu
```

Indeksiä **ei** koskaan näytetä ilman komponentteja ja luottamustasoa.

Talletus: `ConsistencyIndex(personId, periodId, indexValue, A, B, W_A, W_B,
confidenceScore, confidenceLevel, nVotes, nSpeeches, nEligible,
lexiconVersion, mappingVersion)`.

---

## 7. Epävarmuus- ja datapuutesäännöt

Jokaiselle näytetylle tunnusluvulle liitetään lippu seuraavista:

| Lippu | Ehto | Vaikutus |
|---|---|---|
| `LOW_SAMPLE` | nimittäjä < 10 (esim. eligible < 10) | luku näytetään, mutta merkitään "vähän dataa" |
| `NO_MATCH_HEAVY` | yli 25 % kohteista NO_MATCH-aiheessa | aihekattavuus näytetään varoituksella |
| `SINGLE_COMPONENT` | vain A tai vain B saatavilla indeksiin | luottamus ≤ kohtalainen |
| `PARTY_CHANGE` | edustaja vaihtoi puoluetta jaksolla | poikkeamaprosentti pilkotaan puoluejaksoittain |
| `PRE_2014_SPEECHGAP` | äänestys ennen 2014 → ei puhedataa | A jätetään pois, ei rangaista |
| `UNMAPPED_PROMISE` | lupauksella 0 kuratoitua äänestystä | linjaus = "epäselvä", merkitään "ei kartoitettu" |
| `PROCEDURAL_SUSPECT` | äänestyksen otsikko viittaa menettelyyn (esim. "pöydälle", "asian käsittely") | merkitään mahdollisesti menettelylliseksi (kohta 8) |

Sääntö: **mikään tunnusluku ei piiloudu epävarmuuden vuoksi** — se näytetään
lippuineen, jotta käyttäjä tietää rajoituksen. UNDEFINED-arvot näytetään
selvästi ("ei riittävästi dataa"), ei nollana.

---

## 8. Rajoitukset – mitä nämä menetelmät EIVÄT näytä

- **Eivät motiiveja.** Emme tiedä emmekä väitä, *miksi* edustaja äänesti tai
  puhui tietyllä tavalla. Kaikki luvut ovat havaitusta käyttäytymisestä.
- **Eivät äänestyksen kontekstia.** Yksittäinen ääni voi koskea muutosesitystä,
  budjettipaketin osaa, hallitus–oppositio-asetelmaa tai menettelytapaa.
  Numero ei kerro tätä; siksi linkitämme aina alkuperäiseen äänestykseen.
- **Eivät erota menettelyllisiä ja asiakysymyksiä luotettavasti.** Leksikko ja
  otsikkoheuristiikka (`PROCEDURAL_SUSPECT`) ovat karkeita. Menettelyäänestys
  (esim. asian pöydällepano) ei kerro substantiivisesta kannasta.
- **Lupauskartoitus on toimituksellinen tulkinta**, ei algoritminen totuus.
  "Ristiriidassa" ei tarkoita petosta; se tarkoittaa eroa kuratoidun
  odotusäänen ja edustajan äänen välillä yksittäisessä äänestyksessä.
- **Aiheluokitin on avainsanapohjainen** ja voi tehdä virheitä (ironia,
  sivulause, useita aiheita). Siksi jokainen aiheosuma on jäljitettävissä
  avainsanaan ja kattavuus raportoidaan.
- **Puhedata alkaa 2014.** Sitä ennen olevat äänestykset eivät saa
  puhekontekstia; tämä alentaa A-komponenttia vain datan puutteen vuoksi, ei
  käyttäytymisen vuoksi — siksi se jätetään laskennan ulkopuolelle.
- **Puoluelinjapoikkeama ei ole arvo.** Korkea poikkeama voi heijastaa
  itsenäistä harkintaa tai vaalipiirin etua; matala poikkeama ryhmäkuria.
  Esitämme luvun neutraalisti.
- **Johdonmukaisuusindeksi on yhdistelmäindikaattori**, joka pelkistää
  monimutkaisen toiminnan yhdeksi luvuksi. Se on tarkoitettu vertailun
  apuvälineeksi, ei edustajan arvosanaksi. Komponentit ja luottamustaso
  näytetään aina sen rinnalla.
- **Poissaolot eivät ole kannanottoja.** Poissaolo voi johtua sairaudesta,
  valiokuntatyöstä, parista (pairing) tai muusta syystä; sitä ei tulkita
  kannaksi eikä lasketa poikkeamaksi.

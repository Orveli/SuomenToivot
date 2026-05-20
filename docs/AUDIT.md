# Auditointiraportti

Kaksi riippumatonta ala-agenttia auditoi järjestelmän oikeaa kerättyä dataa vasten
(valtiopäivävuodet 2023–2024): **tekninen/validointiauditi** ja **toimituksellinen/etiikka-auditi**.
Kaikki sivut palauttivat HTTP 200 ilman template-kaatumisia; 28/28 testiä läpi.

## Tekninen & data-auditointi

**BLOCKER:** ei yhtään. Ei SQL-injektiota, ei orpoja äänestysrivejä, ei virheellisiä äänestysarvoja.

| # | Vakavuus | Löydös | Tila |
|---|----------|--------|------|
| M1 | MAJOR | `vote_record`-taulussa 2 310 duplikaattia `(vote_id, person_id)` (lähde palauttaa toisinaan saman edustajan kahdesti) → raakaluvut yliarvioituja | **Korjattu**: dedup-poisto, `UNIQUE INDEX ux_vote_record`, kerääjä `INSERT OR IGNORE`. Tarkistettu: 0 duplikaattia. |
| M2 | MAJOR | 9 puhetta viittasi henkilöihin (632, 903), joita ei ole jäsenrekisterissä → 2 orpoa, nimetöntä `analysis_member_summary`-riviä | **Korjattu**: yhteenvedot rajattu `person`-tauluun (0 orpoa); puhesivu näyttää "Puhuja (ei jäsenrekisterissä)". Nämä ovat ei-edustaja-puhujia (eivät ole MemberOfParliament-API:ssa). |
| m1 | MINOR | Menettelyäänestykset (is_procedural=1) mukana puoluelinjassa/indeksissä, mutta pois lupauskartoituksesta — epäsymmetristä | **Korjattu**: `compute_party_deviation` rajaa nyt `is_procedural=0`:aan (METHODOLOGY §8). |
| m2 | MINOR | "laskennallinen indikaattori" -koko­merkintä puuttui `/puolue`- ja `/vertailu`-sivuilta | **Korjattu**: koko­merkintä + menetelmälinkki lisätty molempiin. |
| m3 | MINOR | FTS-haku voi ajautua erilleen `speech`-taulusta (ei rebuild-polkua) | **Korjattu**: `INSERT INTO speech_fts(speech_fts) VALUES('rebuild')` analyysiputken alussa. |
| m4 | MINOR | `n_absent` laskettiin poikkeamataulusta, `n_votes_total` raakadatasta → epäjohdonmukaisuus | **Korjattu**: kaikki raakaluvut yhdestä (dedupatusta) `vote_record`-lähteestä. Tarkistettu: n_absent täsmää. |
| m5 | MINOR | `_member_topic_alignment` on O(äänestykset × puheet) per edustaja — hidas koko 10v aineistolle | **Kirjattu** ROADMAPiin (P-laatuvelka). Ei korrektiusongelma; nykyskaalalla 211 edustajaa ~36 s. |

**Vahvistetut invariantit (auditin toteamat):** kaikki äänestysarvot ∈ {Jaa,Ei,Tyhjää,Poissa};
puoluelinja täsmää substantiivisiin ääniin; `deviation_rate = deviations/eligible` tarkistettu;
indeksi 0–100; FTS-rivimäärä = puhemäärä; lupauskytkennät vain substantiivisiin (is_procedural=0)
äänestyksiin; kyselyt parametrisoituja (myös FTS ja dynaaminen `IN (...)`).

## Toimituksellinen & etiikka-auditointi

**Verdikti: vahvasti vaatimustenmukainen.** Ei BLOCKEReita, ei MAJOReita. Todennettu renderöidystä
HTML:stä (18 sivua, oikeat edustaja-/äänestys-/puhe-ID:t):

- **Ei motiiviväitteitä / ei ohjailevaa kieltä:** templatehaku termeille (petti, epärehel, paras,
  huonoin…) → 0 osumaa paitsi suojalauseke "Ei arvosana edustajan rehellisyydestä".
- **Indeksi aina komponentteineen + luottamustasoineen + menetelmälinkkeineen.**
- **Lupaus = toimituksellinen tulkinta**, lähde + peruste + odotusääni näkyvissä.
- **Lähteet joka sivulla**; footer CC BY 4.0 + korjauskanava kaikilla sivuilla.
- **Ei puoluevärejä**; "—" eikä "0" silloin kun dataa ei ole; epävarmuusliput näkyvät.
- **Päästä päähän -tarkistus läpäisi:** SDP-edustaja, joka äänesti Ei aikuiskoulutustuen
  lakkautuksesta (HE 8/2024) → "tukee" koulutuslupausta, perusteluineen, neutraalisti.

| # | Vakavuus | Löydös | Tila |
|---|----------|--------|------|
| E1 | MINOR | Ei julkaistua tietosuojaselostetta (LEGAL_ETHICS-checklistin ainoa täyttämätön kohta) | **Korjattu**: `docs/PRIVACY.md` + `/tietosuoja`-sivu + footer-linkki. Rekisterinpitäjäkentät merkitty `[TÄYDENNÄ]` ylläpitäjälle. |
| E2 | MINOR | Puoluesivun indeksisarake ilman menetelmälinkkiä | **Korjattu**: sarakeotsikkoon menetelmälinkki + sivulle koko­merkintä ja luottamushuomautus. |
| E3 | MINOR | Aggregaattipoikkeama pyöristyi "0 %":iin (aito data, ei peittelyä) | **Korjattu**: desimaalitarkkuus + "<1 %" -esitys. |

## Auditointikierrokset
1. Kierros 1 (yllä): 2 MAJOR + 6 MINOR löydöstä → kaikki korjattu.
2. Kierros 2 (uudelleenajo): analyysi + 28 testiä uudelleen; invariantit tarkistettu
   (0 duplikaattia, 0 orpoa, n_absent täsmää). Ei uusia korjattavia löydöksiä koodista/datasta.

Jäljellä olevat rajoitteet ovat **aidosti datan kattavuuteen tai lähteen luonteeseen liittyviä**
(ei koodivirheitä) ja kuvattu tiedostoissa `KNOWN_ISSUES.md` ja `ROADMAP.md`:
puhedata alkaa 2014, otsikkopohjaisen menettelyheuristiikan karkeus, lupausaineiston kuratoitu
laajuus, ja koko 10 vuoden veto on aikaa vievä mutta yhden komennon päässä per vuosi.

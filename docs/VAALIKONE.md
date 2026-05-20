# Vaalikonedata — lähteet, lisenssi ja per-henkilö-pyyntö

## Mitä on käytössä nyt (laillinen, automaattinen)
Yle julkaisi eduskuntavaalien 2023 vaalikonevastaukset **avoimena datana CC BY 4.0**:
- ~2 116 ehdokasta, 47 väittämää (vastaus 1–5).
- Lataus (suora CSV): `km vaalikone` hakee
  `https://old-vaalikone.yle.fi/vaalikone/eduskuntavaalit2023/Eduskuntavaalit 2023 vastausdata - Kaikki vaalipiirit - anonyymi.csv`
- **Avoimesta datasta on poistettu nimet ja ehdokasnumerot** → vain **puoluetason** aggregaatti
  (`vaalikone_party_stance`). Näkyy sivulla `/vaalikone`.

Lähteet:
- Yle: "Ylen eduskuntavaalien vaalikoneen aineisto julkaistu avoimena datana" https://yle.fi/a/3-10725384
- Ylen avoin data: https://yle.fi/aihe/a/20-10006887

## Miksi ei per-henkilö suoraan
Per-henkilö-vaalilupausten pito (kuka piti / kuka käänsi takkinsa) edellyttää, että vaalikonevastaus
kytketään nimettyyn ehdokkaaseen → edustajaan. **Avoin data on anonymisoitu**, joten tämä ei ole
mahdollista avoimesta aineistosta. Tämä on aidosti ulkoisesti estynyt ilman alla olevaa pyyntöä.

## Per-henkilö: Ylen nimellisen datan pyytäminen (ylläpitäjän tehtävä)
Yle luovuttaa nimellisen aineiston **tieteellisiin tai journalistisiin tarkoituksiin** pyynnöstä
(ks. Ylen artikkeli yllä — yhteydenotto sähköpostitse aineiston julkaisseelle toimitukselle).

Kun saat nimellisen CSV:n (sama muoto + nimi-/ehdokasnumerosarakkeet):
1. Aja `km vaalikone --file polku/nimelliseen.csv` (sama parseri tunnistaa nimisarakkeet).
2. (Toteutettava jatkossa) `collect/vaalikone.py`:n `collect_vaalikone_named`: täsmää ehdokas →
   `person` nimellä + vaalipiirillä, tallenna per-henkilö-vastaukset.
3. Kuratoi väittämä→äänestys-kartoitukset (mikä väittämä vastaa mitä lakiäänestystä), niin
   lupausvahti tuottaa **per-henkilö** lupaustenpidon ja takinkääntäjä-leaderboardin automaattisesti.

Käyttöehdot ja lisenssi: noudata Ylen luovutusehtoja; älä julkaise nimellistä raakadataa, vaan
johdetut, journalistisesti perustellut tulokset lähteistettyinä.

## Nyt käytössä per-henkilö ilman vaalikonetta
Lupausvahti (`/lupausvahti`) toimii jo **kuratoiduilla, lähteistetyillä lupauksilla**
(puolueohjelmat, julkiset kannanotot) ja niiden äänestyskartoituksilla — per-puolue ja per-henkilö.
Tämä laajenee kuratoimalla lisää lupauksia (`seed/promises.json`).

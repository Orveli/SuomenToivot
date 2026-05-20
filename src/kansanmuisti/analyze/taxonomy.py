"""Aihetaksonomia (METHODOLOGY.md §1.6). Avainsanat ovat vartaloprefiksejä.

Monisanainen avainsana (esim. "julkis talou") otellaan peräkkäisinä
token-prefikseinä liukuvalla ikkunalla.
"""
from __future__ import annotations

# topicId(slug) -> (label, [(keyword, weight), ...])
TAXONOMY = {
    "talous": ("Talous", [
        ("talous", 1), ("budjet", 1.5), ("julkis talou", 2), ("alijääm", 1.5),
        ("velka", 1), ("brutto kansan", 1.5), ("suhdann", 1), ("valtiontalou", 1.5)]),
    "terveydenhuolto": ("Terveydenhuolto", [
        ("terveydenhuol", 2), ("sairaal", 1.5), ("soten", 1.5), ("sote", 1.5),
        ("hoito takuu", 2), ("hoitotakuu", 2), ("lääk", 1), ("hoitaj", 1),
        ("terveys asem", 1.5), ("potilas", 1)]),
    "koulutus": ("Koulutus", [
        ("koulut", 1.5), ("opetu", 1.5), ("oppivelvol", 2), ("yliopist", 1.5),
        ("ammattikorkea", 1.5), ("varhaiskasvat", 2), ("opiskel", 1), ("oppimi", 1)]),
    "ilmasto": ("Ilmasto ja ympäristö", [
        ("ilmast", 1.5), ("päästö", 1.5), ("hiilineutr", 2), ("luonnon suojel", 2),
        ("luonnonsuojel", 2), ("monimuoto", 1.5), ("ympäristö", 1), ("kasvihuone", 1.5),
        ("luontokato", 2)]),
    "maahanmuutto": ("Maahanmuutto", [
        ("maahanmuut", 2), ("turvapaik", 2), ("pakolais", 1.5), ("kotoutu", 1.5),
        ("oleskelulu", 2), ("työperäi maahan", 2), ("rajamenet", 1.5)]),
    "turvallisuus": ("Turvallisuus ja puolustus", [
        ("puolust", 1.5), ("maanpuolus", 2), ("nato", 1.5), ("asevelvol", 2),
        ("sotilas", 1), ("kriisinhal", 1.5), ("varuskun", 1.5), ("sisäinen turval", 2)]),
    "sosiaaliturva": ("Sosiaaliturva", [
        ("sosiaalitur", 2), ("toimeentulotu", 2), ("perustur", 1.5), ("työttömyysturv", 2),
        ("eläke", 1.5), ("lapsilis", 2), ("asumistu", 1.5), ("perustulo", 2)]),
    "verotus": ("Verotus", [
        ("verot", 1.5), ("tulover", 2), ("arvonlisäver", 2), ("yhteisöver", 2),
        ("veron koroitu", 2), ("veroaste", 1.5), ("pääomatulover", 2)]),
    "eu": ("EU", [
        ("euroopan unio", 2), ("eu komiss", 2), ("eu rahast", 1.5), ("eu jäsen", 1.5),
        ("sisämarkkin", 1.5), ("eu direkt", 2), ("euroopan parlament", 2)]),
    "maatalous": ("Maatalous", [
        ("maatalou", 2), ("viljel", 1.5), ("maatil", 1.5), ("maaseut", 1),
        ("ruoan tuotan", 1.5), ("karja", 1), ("maataloustu", 2),
        ("elintarvike omavarai", 2)]),
    "liikenne": ("Liikenne", [
        ("liikent", 1.5), ("tie verkko", 1.5), ("rata", 1), ("joukkoliiken", 2),
        ("raidelii", 2), ("väylä", 1), ("autoil", 1.5), ("liikenne turval", 1.5)]),
    "asuminen": ("Asuminen", [
        ("asumi", 1.5), ("asunto", 1.5), ("vuokra", 1.5), ("kohtuuhintai", 2),
        ("kaavoitu", 1.5), ("ara asunto", 2), ("asuntopolit", 2), ("rakentami", 1)]),
    "oikeus": ("Oikeus ja sisäasiat", [
        ("oikeus laitos", 2), ("rikos", 1.5), ("polii", 1.5), ("tuomioistu", 2),
        ("vankeu", 1.5), ("syyttäj", 1.5), ("perus oikeu", 1.5), ("sisä asiat", 1.5)]),
    "tyo": ("Työ", [
        ("työllis", 2), ("työ markkin", 2), ("työ ehto", 1.5), ("lakko", 1.5),
        ("palkka", 1), ("työ sopimu", 1.5), ("työttömy", 1.5),
        ("paikallinen sopimi", 2)]),
    "energia": ("Energia", [
        ("energi", 1.5), ("sähkö", 1), ("ydinvoim", 2), ("tuulivoim", 2),
        ("fossiili", 1.5), ("energia oma varai", 2), ("kantaverkk", 1.5),
        ("polttoaine", 1.5)]),
    "muu": ("Muu / luokittelematon", []),
}

# Vakaa numerointi (topicId) determinismiä varten — aakkosjärjestyksen sijaan kiinteä.
TOPIC_IDS = {slug: i + 1 for i, slug in enumerate(TAXONOMY.keys())}


def seed_topics(conn) -> int:
    """Lataa taksonomia tietokantaan (idempotentti)."""
    n = 0
    for slug, (label, keywords) in TAXONOMY.items():
        tid = TOPIC_IDS[slug]
        conn.execute("INSERT OR REPLACE INTO topic(id,slug,label) VALUES(?,?,?)",
                     (tid, slug, label))
        conn.execute("DELETE FROM topic_keyword WHERE topic_id=?", (tid,))
        for kw, w in keywords:
            conn.execute(
                "INSERT INTO topic_keyword(topic_id,keyword,weight) VALUES(?,?,?)",
                (tid, kw, w))
            n += 1
    conn.commit()
    return n

"""PTK-puhejäsentimen ja jäsen-XML-jäsentimen testit (ei verkkoa)."""
from kansanmuisti.collect.speeches import parse_ptk
from kansanmuisti.collect.members import parse_member_xml
from kansanmuisti.collect.legislation import parse_legislation
from kansanmuisti.collect.util import fi_date_to_iso, normalize_party

META = "http://www.vn.fi/skeemat/metatietoelementit/2010/04/27"
VASKI = "http://www.eduskunta.fi/skeemat/vaskielementit/2011/01/04"
KOOSTE = "http://www.eduskunta.fi/skeemat/vaskikooste/2011/01/04"
SIS = "http://www.vn.fi/skeemat/sisaltokooste/2010/04/27"

PTK_XML = f"""<?xml version="1.0"?>
<Siirto xmlns:m="{META}" xmlns:v="{VASKI}" xmlns:k="{KOOSTE}" xmlns:s="{SIS}">
 <Poytakirja eduskuntaTunnus="PTK 5/2024 vp">
  <Asiakohta eduskuntaTunnus="HE 9/2024 vp">
   <k:PuheenvuoroToimenpide v:puheenvuoroLuokitusKoodi="T" v:puheenvuoroAloitusHetki="2024-03-10T10:00:00">
     <k:Toimija>
       <k:Henkilo m:muuTunnus="42"/>
     </k:Toimija>
     <k:PuheenvuoroOsa m:muuTunnus="900">
       <k:KohtaSisalto>
         <s:KappaleKooste>Arvoisa puhemies! Tämä on ensimmäinen kappale.</s:KappaleKooste>
         <s:KappaleKooste>Toinen kappale jatkaa asiaa.</s:KappaleKooste>
         <k:PuheenjohtajaRepliikki>
           <v:PuheenjohtajaTeksti>Puhemies keskeyttää.</v:PuheenjohtajaTeksti>
           <s:KappaleKooste>Tämä on puhemiehen repliikki, ei pidä tulla mukaan.</s:KappaleKooste>
         </k:PuheenjohtajaRepliikki>
       </k:KohtaSisalto>
     </k:PuheenvuoroOsa>
   </k:PuheenvuoroToimenpide>
  </Asiakohta>
 </Poytakirja>
</Siirto>"""


def test_parse_ptk_basic():
    speeches = parse_ptk(PTK_XML, "PTK 5/2024 vp", "2024/5")
    assert len(speeches) == 1
    s = speeches[0]
    assert s["person_id"] == 42
    assert s["speech_type"] == "T"
    assert s["legislative_item"] == "HE 9/2024 vp"
    assert s["external_key"] == "900"
    assert "ensimmäinen kappale" in s["text"]
    assert "Toinen kappale" in s["text"]
    # puhemiehen repliikki rajautuu pois
    assert "repliikki" not in s["text"].lower()
    assert s["word_count"] > 0


MEMBER_XML = """<?xml version="1.0"?>
<Henkilo><HenkiloNro>42</HenkiloNro><Ammatti>opettaja</Ammatti>
<SyntymaPvm>1970</SyntymaPvm><SukuPuoliKoodi>Nainen</SukuPuoliKoodi>
<Vaalipiirit><NykyinenVaalipiiri><Nimi>Helsingin vaalipiiri</Nimi></NykyinenVaalipiiri></Vaalipiirit>
<Edustajatoimet><Edustajatoimi><AlkuPvm>24.04.2019</AlkuPvm><LoppuPvm></LoppuPvm></Edustajatoimi></Edustajatoimet>
<Eduskuntaryhmat>
  <NykyinenEduskuntaryhma><Nimi>Kansallinen kokoomus</Nimi><Tunnus>kok01</Tunnus><AlkuPvm>24.04.2019</AlkuPvm></NykyinenEduskuntaryhma>
  <EdellisetEduskuntaryhmat>
    <Eduskuntaryhma><Nimi>Vihreä eduskuntaryhmä</Nimi><Tunnus>vihr01</Tunnus>
      <Jasenyys><AlkuPvm>22.04.2015</AlkuPvm><LoppuPvm>23.04.2019</LoppuPvm></Jasenyys>
    </Eduskuntaryhma>
  </EdellisetEduskuntaryhmat>
</Eduskuntaryhmat>
<ValtioneuvostonJasenyydet><Jasenyys><Nimi>opetusministeri</Nimi><Hallitus>Testihallitus</Hallitus>
  <AlkuPvm>10.06.2023</AlkuPvm><LoppuPvm></LoppuPvm></Jasenyys></ValtioneuvostonJasenyydet>
</Henkilo>"""


def test_parse_member_xml():
    m = parse_member_xml(42, MEMBER_XML)
    assert m["birth_year"] == "1970"
    assert m["gender"] == "Nainen"
    assert m["profession"] == "opettaja"
    assert m["electoral_district"] == "Helsingin vaalipiiri"
    assert m["party_current"] == "kok"
    assert m["party_current_name"] == "Kansallinen kokoomus"
    # historiassa myös vihreät
    codes = {p["code"] for p in m["parties"]}
    assert "vihr" in codes and "kok" in codes
    assert len(m["terms"]) == 1
    assert m["terms"][0]["start"] == "2019-04-24"
    assert m["minister_roles"] and m["minister_roles"][0]["title"] == "opetusministeri"


LEG_XML = """<?xml version="1.0"?>
<Asiakirja>
  <SisaltoKuvaus>Hallituksen esitys laiksi työttömyysturvalain muuttamisesta</SisaltoKuvaus>
  <KohtaSisalto>
    <KappaleKooste>Esityksessä ehdotetaan muutettavaksi työttömyysturvalakia ja sosiaaliturvaa.</KappaleKooste>
    <KappaleKooste>Toinen kappale lisätietoa verotuksesta.</KappaleKooste>
  </KohtaSisalto>
</Asiakirja>"""


def test_parse_legislation():
    title, summary = parse_legislation(LEG_XML)
    assert "työttömyysturvalain" in title
    assert "Esityksessä ehdotetaan" in summary
    assert "sosiaaliturvaa" in summary
    assert "verotuksesta" in summary  # toinen kappale mukana


def test_parse_legislation_empty():
    assert parse_legislation("") == (None, "")


def test_date_and_party_helpers():
    assert fi_date_to_iso("24.03.1995") == "1995-03-24"
    assert fi_date_to_iso("") is None
    assert fi_date_to_iso("epäkelpo") is None
    assert normalize_party("sd01") == "sd"
    assert normalize_party("kok       ") == "kok"
    assert normalize_party(None) is None

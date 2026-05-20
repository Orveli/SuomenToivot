"""Generoi kattavuusraportti (docs/COVERAGE.md) suoraan tietokannasta."""
from __future__ import annotations

import datetime as dt

from . import config, db


def generate_coverage_report(out_path=None) -> str:
    out_path = out_path or (config.ROOT / "docs" / "COVERAGE.md")
    with db.session() as conn:
        lines = []
        a = lines.append
        a("# Kattavuusraportti\n")
        a(f"> Generoitu automaattisesti {dt.date.today().isoformat()} "
          f"komennolla `km coverage-report`. Älä muokkaa käsin.\n")
        a("Tämä raportti kertoo, mitä aineistoa tietokannassa tällä hetkellä on. "
          "Se kuvaa **kerättyä** dataa, ei lähteen koko saatavuutta "
          "(ks. docs/DATA_SOURCES.md koko 10 vuoden potentiaalista).\n")

        # ydinluvut
        def scalar(q, *p):
            return conn.execute(q, p).fetchone()[0]

        a("## Ydinluvut\n")
        a("| Aineisto | Määrä |")
        a("|---|---|")
        a(f"| Edustajat | {scalar('SELECT COUNT(*) FROM person')} |")
        a(f"| Äänestykset | {scalar('SELECT COUNT(*) FROM vote')} |")
        a(f"| Edustajakohtaiset äänet | {scalar('SELECT COUNT(*) FROM vote_record')} |")
        a(f"| Puheenvuorot | {scalar('SELECT COUNT(*) FROM speech')} |")
        a(f"| — joista henkilöön linkitetty | {scalar('SELECT COUNT(*) FROM speech WHERE person_id IS NOT NULL')} |")
        a(f"| Kuratoidut lupaukset | {scalar('SELECT COUNT(*) FROM promise')} |")
        a(f"| Lupaus↔äänestys-kytkennät | {scalar('SELECT COUNT(*) FROM promise_vote_map')} |")
        a("")

        # vuosittain
        a("## Äänestykset vuosittain (valtiopäivävuosi)\n")
        a("| Vuosi | Äänestyksiä |")
        a("|---|---|")
        for r in conn.execute("SELECT vp_year, COUNT(*) c FROM vote GROUP BY vp_year ORDER BY vp_year"):
            a(f"| {r['vp_year']} | {r['c']} |")
        a("")
        a("## Puheet vuosittain\n")
        a("| Vuosi | Puheita |")
        a("|---|---|")
        for r in conn.execute("SELECT substr(started_at,1,4) y, COUNT(*) c FROM speech"
                              " WHERE started_at IS NOT NULL GROUP BY y ORDER BY y"):
            a(f"| {r['y']} | {r['c']} |")
        a("")

        # edustajat puolueittain
        a("## Edustajat puolueittain (nykyinen ryhmä)\n")
        a("| Ryhmä | Edustajia |")
        a("|---|---|")
        for r in conn.execute("SELECT COALESCE(party_current,'(tuntematon)') p, COUNT(*) c"
                              " FROM person GROUP BY p ORDER BY c DESC"):
            a(f"| {r['p']} | {r['c']} |")
        a("")

        # aihekattavuus
        a("## Aiheluokittelun kattavuus\n")
        a("| Mittari | Arvo |")
        a("|---|---|")
        for r in conn.execute("SELECT dimension, value FROM coverage_stat"
                              " WHERE metric='aiheluokiteltu' ORDER BY dimension"):
            a(f"| {r['dimension']} | {r['value']} % |")
        a("")

        # analyysin luottamusjakauma
        a("## Johdonmukaisuusindeksin luottamustaso (edustajat)\n")
        a("| Luottamus | Edustajia |")
        a("|---|---|")
        for r in conn.execute("SELECT COALESCE(confidence_level,'(ei laskettu)') l, COUNT(*) c"
                              " FROM analysis_member_summary GROUP BY l ORDER BY c DESC"):
            a(f"| {r['l']} | {r['c']} |")
        a("")

        # keruun tila
        a("## Keruun tila (ingest_state)\n")
        a("| Työ | Tila | Erät | Päivitetty |")
        a("|---|---|---|---|")
        for r in conn.execute("SELECT job,status,n_items,updated_at FROM ingest_state ORDER BY job"):
            a(f"| {r['job']} | {r['status']} | {r['n_items']} | {r['updated_at']} |")
        a("")
        a("## Tunnetut puutteet\n")
        a("Ks. erillinen `docs/KNOWN_ISSUES.md` ja jatkotyölista `docs/ROADMAP.md`.")
        a(f"\n---\n{config.DATA_ATTRIBUTION}\n")

        text = "\n".join(lines)
    out_path.write_text(text, encoding="utf-8")
    return str(out_path)

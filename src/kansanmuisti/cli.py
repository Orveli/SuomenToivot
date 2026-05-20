"""Komentorivikäyttöliittymä: keruu, analyysi, kattavuus, palvelin.

Esimerkit:
  km initdb
  km collect-members --start-year 2015 --end-year 2025
  km collect-votes --year 2024
  km collect-speeches --year 2024
  km collect-all --start-year 2023 --end-year 2024
  km analyze
  km coverage-report
  km load-promises seed/promises.json
  km serve
"""
from __future__ import annotations

import argparse
import sys

from . import config, db


def _log(msg: str) -> None:
    print(msg, flush=True)


def cmd_initdb(args):
    with db.session() as conn:
        db.init_db(conn)
    _log(f"Tietokanta alustettu: {config.DB_PATH}")


def cmd_collect_members(args):
    from .collect.members import collect_members
    with db.session() as conn:
        n = collect_members(conn, start_year=args.start_year, end_year=args.end_year,
                            only_active_in_range=not args.all)
    _log(f"Kerättiin {n} edustajaa.")


def cmd_collect_votes(args):
    from .collect.votes import collect_votes_for_year
    with db.session() as conn:
        for year in range(args.year if args.year else args.start_year,
                          (args.year if args.year else args.end_year) + 1):
            res = collect_votes_for_year(conn, year, with_records=not args.no_records,
                                        limit=args.limit)
            _log(f"  {year}: {res['votes']} äänestystä, {res['records']} edustajaääntä")


def cmd_collect_speeches(args):
    from .collect.speeches import collect_speeches_for_year
    with db.session() as conn:
        for year in range(args.year if args.year else args.start_year,
                          (args.year if args.year else args.end_year) + 1):
            res = collect_speeches_for_year(conn, year, limit_sessions=args.limit_sessions)
            _log(f"  {year}: {res['speeches']} puhetta, {res['sessions']} istuntoa")


def cmd_collect_all(args):
    from .collect.members import collect_members
    from .collect.votes import collect_votes_for_year
    from .collect.speeches import collect_speeches_for_year
    with db.session() as conn:
        _log("Kerätään edustajat...")
        n = collect_members(conn, start_year=args.start_year, end_year=args.end_year)
        _log(f"  {n} edustajaa")
        for year in range(args.start_year, args.end_year + 1):
            _log(f"Kerätään äänestykset {year}...")
            rv = collect_votes_for_year(conn, year)
            _log(f"  {rv['votes']} äänestystä, {rv['records']} edustajaääntä")
            _log(f"Kerätään puheet {year}...")
            rs = collect_speeches_for_year(conn, year)
            _log(f"  {rs['speeches']} puhetta, {rs['sessions']} istuntoa")
        from .collect.legislation import collect_legislation
        _log("Kerätään säädöstekstit (HE)...")
        rl = collect_legislation(conn)
        _log(f"  {rl['items']} säädöskohdetta")


def cmd_collect_legislation(args):
    from .collect.legislation import collect_legislation
    with db.session() as conn:
        res = collect_legislation(conn, only_missing=not args.refresh)
    _log(f"Kerättiin {res['items']} säädöskohdetta ({res['with_text']} sisälsi tekstin).")


def cmd_analyze(args):
    from .analyze.pipeline import run_all
    with db.session() as conn:
        res = run_all(conn)
    _log("Analyysi valmis:")
    for k, v in res.items():
        _log(f"  {k}: {v}")


def cmd_coverage_report(args):
    from .report import generate_coverage_report
    path = generate_coverage_report()
    _log(f"Kattavuusraportti kirjoitettu: {path}")


def cmd_load_promises(args):
    from .collect.promises import load_promises
    with db.session() as conn:
        res = load_promises(conn, args.path)
    _log(f"Ladattiin {res['promises']} lupausta, {res['mappings']} äänestyskytkentää "
         f"({res['resolved']} kohdistui kerättyihin äänestyksiin).")


def cmd_serve(args):
    import uvicorn
    uvicorn.run("kansanmuisti.web.app:app", host=args.host, port=args.port, reload=args.reload)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="km", description="Kansanmuisti CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("initdb", help="Alusta tietokanta")
    sp.set_defaults(func=cmd_initdb)

    sp = sub.add_parser("collect-members", help="Kerää edustajat")
    sp.add_argument("--start-year", type=int, default=config.DEFAULT_START_YEAR)
    sp.add_argument("--end-year", type=int, default=config.DEFAULT_END_YEAR)
    sp.add_argument("--all", action="store_true", help="Kaikki edustajat (ei aikarajausta)")
    sp.set_defaults(func=cmd_collect_members)

    sp = sub.add_parser("collect-votes", help="Kerää äänestykset")
    sp.add_argument("--year", type=int, help="Yksi valtiopäivävuosi")
    sp.add_argument("--start-year", type=int, default=config.DEFAULT_START_YEAR)
    sp.add_argument("--end-year", type=int, default=config.DEFAULT_END_YEAR)
    sp.add_argument("--no-records", action="store_true", help="Älä hae edustajakohtaisia ääniä")
    sp.add_argument("--limit", type=int, help="Rajoita äänestysten määrää (testaus)")
    sp.set_defaults(func=cmd_collect_votes)

    sp = sub.add_parser("collect-speeches", help="Kerää puheet PTK-dokumenteista")
    sp.add_argument("--year", type=int)
    sp.add_argument("--start-year", type=int, default=config.DEFAULT_START_YEAR)
    sp.add_argument("--end-year", type=int, default=config.DEFAULT_END_YEAR)
    sp.add_argument("--limit-sessions", type=int, help="Rajoita istuntoja (testaus)")
    sp.set_defaults(func=cmd_collect_speeches)

    sp = sub.add_parser("collect-all", help="Kerää kaikki annetulta väliltä")
    sp.add_argument("--start-year", type=int, default=config.DEFAULT_START_YEAR)
    sp.add_argument("--end-year", type=int, default=config.DEFAULT_END_YEAR)
    sp.set_defaults(func=cmd_collect_all)

    sp = sub.add_parser("collect-legislation", help="Kerää HE-tekstit aiheluokittelua varten")
    sp.add_argument("--refresh", action="store_true", help="Hae myös jo kerätyt uudelleen")
    sp.set_defaults(func=cmd_collect_legislation)

    sp = sub.add_parser("analyze", help="Aja analyysiputki")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("coverage-report", help="Generoi kattavuusraportti (COVERAGE.md)")
    sp.set_defaults(func=cmd_coverage_report)

    sp = sub.add_parser("load-promises", help="Lataa kuratoidut lupaukset JSON-tiedostosta")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_load_promises)

    sp = sub.add_parser("serve", help="Käynnistä verkkopalvelin")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(func=cmd_serve)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())

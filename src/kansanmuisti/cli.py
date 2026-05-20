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


def cmd_power_analysis(args):
    from .analyze.government import compute_power_analysis
    with db.session() as conn:
        res = compute_power_analysis(conn)
    _log(f"Vallan vaikutus + hallituksen läpimeno laskettu: {res}")


def cmd_rhetoric_map(args):
    from .analyze.rhetoricmap import compute_rhetoric_map
    with db.session() as conn:
        res = compute_rhetoric_map(conn)
    _log(f"Retoriikkakartta laskettu: {res}")


def cmd_word_style(args):
    from .analyze.wordstyle import compute_word_style
    with db.session() as conn:
        res = compute_word_style(conn)
    _log(f"Puhetyyli (täyte-/kirosanat) laskettu: {res}")


def cmd_vaalikone(args):
    from .collect.vaalikone import collect_vaalikone, YLE_2023_URL
    with db.session() as conn:
        res = collect_vaalikone(conn, source=args.file or YLE_2023_URL)
    _log(f"Vaalikone (Yle, avoin CC-BY) ladattu: {res}")


def cmd_photos(args):
    from .collect.photos import collect_photos
    with db.session() as conn:
        res = collect_photos(conn, only_missing=not args.refresh)
    _log(f"Kuvat: tarkistettu {res['checked']}, löytyi {res['found']} (Wikimedia Commons).")


def cmd_embed(args):
    from .analyze.embeddings import embed_speeches
    with db.session() as conn:
        res = embed_speeches(conn, limit=args.limit)
    _log(f"Puheet upotettu (merkityshaku): {res}")


def cmd_party_words(args):
    from .analyze.fightinwords import compute_party_words
    with db.session() as conn:
        res = compute_party_words(conn)
    _log(f"Erottavat sanat laskettu: {res}")


def cmd_political_map(args):
    from .analyze.politmap import compute_political_map
    with db.session() as conn:
        res = compute_political_map(conn)
    _log(f"Poliittinen kartta laskettu: {res}")


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


def cmd_llm_stance(args):
    from .analyze.stance import compute_stance
    with db.session() as conn:
        res = compute_stance(conn, limit=args.limit, model=args.model,
                             max_calls=args.max_calls, only_with_votes=not args.all_speeches)
    if res.get("skipped_no_key") and not res.get("live_calls"):
        _log("HUOM: ANTHROPIC_API_KEY puuttuu → uusia kantoja ei muodostettu "
             "(luettiin vain välimuisti). Aseta avain ja aja uudelleen.")
    _log(f"Kanta-analyysi (M1): {res}")


def cmd_words_votes(args):
    from .analyze.wordsvotes import compute_words_votes
    with db.session() as conn:
        res = compute_words_votes(conn)
    _log(f"Sanat vs. äänet -tilikirja (M2): {res}")


def cmd_stance_export(args):
    from .analyze.stance import export_candidates
    with db.session() as conn:
        res = export_candidates(conn, limit=args.limit, out=args.out,
                                clean_votes_only=not args.all_speeches)
    _log(f"Vietiin {res['candidates']} puhetta analysoitavaksi → {res['out']}")


def cmd_load_llm_demo(args):
    import glob
    import os
    from .analyze.stance import load_stance_demo
    from .analyze.wordsvotes import compute_words_votes
    paths = (sorted(glob.glob(os.path.join(args.path, "*.json")))
             if os.path.isdir(args.path) else [args.path])
    with db.session() as conn:
        tot = {"inserted": 0, "skipped_quote_mismatch": 0}
        for p in paths:
            rs = load_stance_demo(conn, p)
            tot["inserted"] += rs["inserted"]
            tot["skipped_quote_mismatch"] += rs["skipped_quote_mismatch"]
            _log(f"  {p}: {rs}")
        rv = compute_words_votes(conn)
    _log(f"Kannat ladattu (yht {tot}); tilikirja rakennettu: {rv}")


def cmd_llm_explain(args):
    from .analyze.explain import compute_explainers
    with db.session() as conn:
        res = compute_explainers(conn, limit=args.limit, model=args.model, max_calls=args.max_calls)
    if res.get("skipped_no_key") and not res.get("live_calls"):
        _log("HUOM: ANTHROPIC_API_KEY puuttuu → uusia selityksiä ei muodostettu.")
    _log(f"Lakiselittäjä (M24): {res}")


def cmd_load_explainer_demo(args):
    from .analyze.explain import load_explainer_demo
    with db.session() as conn:
        res = load_explainer_demo(conn, args.path)
    _log(f"Lakiselittäjä-demo ladattu: {res}")


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

    sp = sub.add_parser("word-style", help="Laske täyte- ja kirosanat per edustaja")
    sp.set_defaults(func=cmd_word_style)

    sp = sub.add_parser("power-analysis", help="Vallan vaikutus + hallituksen läpimeno")
    sp.set_defaults(func=cmd_power_analysis)

    sp = sub.add_parser("rhetoric-map", help="Retoriikkakartta puheupotuksista (vaatii km embed)")
    sp.set_defaults(func=cmd_rhetoric_map)

    sp = sub.add_parser("vaalikone", help="Lataa Ylen avoin vaalikonedata (CC-BY, puoluetaso)")
    sp.add_argument("--file", help="Paikallinen CSV (esim. nimellinen Yle-data); oletus lataa avoimen")
    sp.set_defaults(func=cmd_vaalikone)

    sp = sub.add_parser("photos", help="Hae edustajien kuvat Wikimedia Commonsista")
    sp.add_argument("--refresh", action="store_true", help="Hae myös jo löydetyt uudelleen")
    sp.set_defaults(func=cmd_photos)

    sp = sub.add_parser("embed", help="Upota puheet merkityshakua varten (valinnainen, vaatii sentence-transformers)")
    sp.add_argument("--limit", type=int, help="Rajoita puheiden määrää (testaus)")
    sp.set_defaults(func=cmd_embed)

    sp = sub.add_parser("party-words", help="Laske puolueita erottavat sanat (fightin' words)")
    sp.set_defaults(func=cmd_party_words)

    sp = sub.add_parser("political-map", help="Laske poliittinen kartta (SVD)")
    sp.set_defaults(func=cmd_political_map)

    sp = sub.add_parser("coverage-report", help="Generoi kattavuusraportti (COVERAGE.md)")
    sp.set_defaults(func=cmd_coverage_report)

    sp = sub.add_parser("load-promises", help="Lataa kuratoidut lupaukset JSON-tiedostosta")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_load_promises)

    sp = sub.add_parser("llm-stance", help="M1: poimi puhekannat LLM:llä (vaatii ANTHROPIC_API_KEY)")
    sp.add_argument("--limit", type=int, help="Rajoita käsiteltäviä puheita")
    sp.add_argument("--model", help="Ohita oletusmalli")
    sp.add_argument("--max-calls", type=int, help="Tuotantokutsubudjetti per ajo")
    sp.add_argument("--all-speeches", action="store_true",
                    help="Käsittele myös puheet ilman äänestyskytkentää")
    sp.set_defaults(func=cmd_llm_stance)

    sp = sub.add_parser("words-votes", help="M2: rakenna sanat-vs-äänet-tilikirja kannoista (deterministinen)")
    sp.set_defaults(func=cmd_words_votes)

    sp = sub.add_parser("stance-export", help="Vie puheet Claude Code -analyysiä varten (ei API-avainta)")
    sp.add_argument("--limit", type=int, default=40)
    sp.add_argument("--out", default="data/stance_batch.json")
    sp.add_argument("--all-speeches", action="store_true", help="Älä rajaa puhtaisiin äänestyksiin")
    sp.set_defaults(func=cmd_stance_export)

    sp = sub.add_parser("load-llm-demo", help="Lataa kannat (demo tai Claude Code -analyysi) + rakenna tilikirja")
    sp.add_argument("path", nargs="?", default="seed/llm_stance_demo.json")
    sp.set_defaults(func=cmd_load_llm_demo)

    sp = sub.add_parser("llm-explain", help="M24: selitä HE:t arkikielellä LLM:llä (vaatii ANTHROPIC_API_KEY)")
    sp.add_argument("--limit", type=int)
    sp.add_argument("--model")
    sp.add_argument("--max-calls", type=int)
    sp.set_defaults(func=cmd_llm_explain)

    sp = sub.add_parser("load-explainer-demo", help="Lataa lakiselittäjän demo-otos")
    sp.add_argument("path", nargs="?", default="seed/llm_explainer_demo.json")
    sp.set_defaults(func=cmd_load_explainer_demo)

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

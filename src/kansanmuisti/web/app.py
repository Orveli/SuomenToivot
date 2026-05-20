"""FastAPI-sovellus: äänestäjälle ymmärrettävä, neutraali käyttöliittymä.

Periaatteet (UX + LEGAL_ETHICS):
- Jokaisella sivulla lähdeattribuutio ja linkit alkuperäisaineistoon.
- Lasketut tunnusluvut merkitään aina "laskennallinen indikaattori" ja näytetään
  komponentteineen + luottamustasoineen.
- Neutraali ulkoasu: ei puoluevärejä, ei ohjailevaa järjestystä.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import markdown as _md
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config, db
from . import queries, viz

BASE = Path(__file__).resolve().parent
app = FastAPI(title="SuomenToivot")
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# yhteinen template-konteksti
templates.env.globals["ATTRIBUTION"] = config.DATA_ATTRIBUTION
templates.env.globals["LICENSE"] = config.DATA_LICENSE
templates.env.globals["now_year"] = dt.date.today().year
templates.env.globals["radar_svg"] = viz.radar_svg
templates.env.globals["heat_color"] = viz.heat_color
templates.env.globals["ATTR_LABELS"] = queries.ATTR_LABELS
templates.env.globals["ATTR_ABBR"] = queries.ATTR_ABBR
templates.env.globals["ATTR_ORDER"] = queries.ATTR_ORDER
templates.env.globals["ATTR_HELP"] = queries.ATTR_HELP
templates.env.globals["RADAR_LABELS"] = queries.RADAR_LABELS


def _asset_version() -> str:
    import hashlib
    h = hashlib.md5()
    for f in ("static/style.css", "static/cards.js"):
        try:
            h.update(str((BASE / f).stat().st_mtime_ns).encode())
        except OSError:
            pass
    return h.hexdigest()[:8]


templates.env.globals["ASSET_V"] = _asset_version()


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


def _attach_radar(cards):
    """Liitä kortteihin valmis tutkagraafi (2D) attribuuteista."""
    for m in cards:
        if m.get("attrs"):
            vals = [(queries.RADAR_LABELS[k], (m["attrs"].get(k) or 0) / 99.0)
                    for k in queries.ATTR_ORDER if m["attrs"].get(k) is not None]
            m["radar_svg"] = viz.radar_svg(vals, 200, True) if len(vals) >= 3 else ""
    return cards


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = _conn()
    try:
        feed = queries.front_feed(conn)
        _attach_radar(feed["mps"])
        return render(request, "index.html", overview=queries.overview(conn),
                      topics=queries.topics(conn), feed=feed)
    finally:
        conn.close()


@app.get("/haku", response_class=HTMLResponse)
def haku(request: Request, q: str = "", mode: str = "sana"):
    from ..analyze import embeddings
    conn = _conn()
    try:
        semantic_available = embeddings.is_available()
        semantic = None
        if q and mode == "merkitys" and semantic_available:
            idx = embeddings.get_index()
            if idx:
                hits = idx.search(q, top_k=30)
                semantic = queries.speeches_by_ids(conn, [h[0] for h in hits], scores=dict(hits))
        return render(request, "search.html", results=queries.search(conn, q), q=q,
                      mode=mode, semantic=semantic, semantic_available=semantic_available)
    finally:
        conn.close()


@app.get("/edustaja/{pid}", response_class=HTMLResponse)
def edustaja(request: Request, pid: int):
    conn = _conn()
    try:
        p = queries.person(conn, pid)
        if not p:
            return render(request, "notfound.html", what="Edustajaa")
        return render(request, "person.html",
                      p=p,
                      party_history=queries.person_party_history(conn, pid),
                      terms=queries.person_terms(conn, pid),
                      minister_roles=queries.person_minister_roles(conn, pid),
                      summary=queries.person_summary(conn, pid),
                      topic_activity=queries.person_topic_activity(conn, pid),
                      behavior=queries.person_vote_behavior(conn, pid),
                      deviations=queries.person_deviations(conn, pid),
                      speeches=queries.person_speeches(conn, pid),
                      recent_votes=queries.person_recent_votes(conn, pid),
                      position_changes=queries.person_position_changes(conn, pid),
                      promises=queries.person_promise_alignment(conn, pid),
                      fingerprint=queries.member_party_agreement(conn, pid),
                      word_style=queries.person_word_style(conn, pid))
    finally:
        conn.close()


@app.get("/edustajat", response_class=HTMLResponse)
def edustajat(request: Request, sort: str = "nimi", dir: str = "asc",
              party: str = "", min_eligible: int = 0):
    conn = _conn()
    try:
        rows = queries.member_directory(conn, sort=sort, direction=dir,
                                        party=party or None, min_eligible=min_eligible)
        # sarakemaksimit informatiivisia datapalkkeja varten
        def mx(key):
            vals = [r[key] for r in rows if r[key] is not None]
            return max(vals) if vals else 1
        maxes = {"n_speeches": mx("n_speeches"), "n_votes_cast": mx("n_votes_cast"),
                 "absent_pct": mx("absent_pct"), "deviation_rate": mx("deviation_rate"),
                 "consistency_index": 100}
        return render(request, "representatives.html", members=rows, sort=sort, dir=dir,
                      party=party, min_eligible=min_eligible, maxes=maxes,
                      parties=queries.parties(conn),
                      sort_labels=queries.MEMBER_SORT_LABELS)
    finally:
        conn.close()


@app.get("/kortit", response_class=HTMLResponse)
def kortit(request: Request, party: str = "", sort: str = "puheet", dir: str = "desc",
           min_eligible: int = 0):
    conn = _conn()
    try:
        cards = queries.member_cards(conn, party=party or None, sort=sort, direction=dir,
                                     min_eligible=min_eligible)
        holders = queries.award_holders(conn)
        attrs = queries.member_attributes(conn)
        for cmd in cards:
            cmd["badges"] = holders.get(cmd["person_id"], [])
            cmd["attrs"] = attrs.get(cmd["person_id"])
            queries.card_flair(cmd)
        _attach_radar(cards)
        return render(request, "cards.html", cards=cards, parties=queries.parties(conn),
                      party=party, sort=sort, dir=dir, min_eligible=min_eligible)
    finally:
        conn.close()


@app.get("/lupausvahti", response_class=HTMLResponse)
def lupausvahti(request: Request):
    conn = _conn()
    try:
        return render(request, "promisewatch.html",
                      keeping=queries.promise_keeping_by_party(conn),
                      breakers=queries.promise_breakers_persons(conn))
    finally:
        conn.close()


@app.get("/vaalikone", response_class=HTMLResponse)
def vaalikone(request: Request, s: int = 0):
    conn = _conn()
    try:
        statements = queries.vaalikone_statements(conn)
        if not statements:
            return render(request, "vaalikone.html", statements=[], stance=[], sid=0, statement=None)
        sid = s or statements[0]["id"]
        statement = next((x for x in statements if x["id"] == sid), statements[0])
        return render(request, "vaalikone.html", statements=statements,
                      stance=queries.vaalikone_stance(conn, sid), sid=sid, statement=statement)
    finally:
        conn.close()


@app.get("/valta", response_class=HTMLResponse)
def valta(request: Request):
    conn = _conn()
    try:
        return render(request, "power.html", **queries.power_overview(conn))
    finally:
        conn.close()


@app.get("/retoriikka", response_class=HTMLResponse)
def retoriikka(request: Request):
    conn = _conn()
    try:
        m = queries.rhetoric_map_data(conn)
        chart = ""
        if m["points"]:
            pts = [(r["dim1"], r["dim2"], f'{r["full_name"]} ({r["party"]})', r["party"])
                   for r in m["points"]]
            chart = viz.category_scatter_svg(pts, "Retoriikka-ulottuvuus 1",
                                             "Retoriikka-ulottuvuus 2", centroids=m["centroids"])
        return render(request, "rhetoric.html", chart=chart, meta=m,
                      mismatch=queries.rhetoric_mismatch(conn))
    finally:
        conn.close()


@app.get("/sanat", response_class=HTMLResponse)
def sanat(request: Request):
    conn = _conn()
    try:
        from ..analyze.wordstyle import (FILLER_WORDS, FILLER_PHRASES,
                                         SWEAR_WORDS, SWEAR_PHRASES, MIN_WORDS_LEADERBOARD)
        data = {}
        for cat in ("filler", "swear"):
            data[cat] = {
                "top": queries.word_leaderboard(conn, cat, "desc"),
                "bottom": queries.word_leaderboard(conn, cat, "asc"),
                "zero": queries.word_zero_count(conn, cat),
            }
        lex = {
            "filler": sorted(FILLER_WORDS) + [" ".join(p) for p in FILLER_PHRASES],
            "swear": sorted(SWEAR_WORDS) + [" ".join(p) for p in SWEAR_PHRASES],
        }
        return render(request, "words.html", data=data, lex=lex,
                      min_words=MIN_WORDS_LEADERBOARD)
    finally:
        conn.close()


@app.get("/kartta", response_class=HTMLResponse)
def kartta(request: Request):
    conn = _conn()
    try:
        m = queries.political_map(conn)
        pts = [(r["dim1"], r["dim2"], f'{r["full_name"]} ({r["party"]})', r["party"])
               for r in m["points"]]
        chart = viz.category_scatter_svg(
            pts, xlabel=f'Ulottuvuus 1 (selittää {m["var1"] or "?"} %)',
            ylabel=f'Ulottuvuus 2 ({m["var2"] or "?"} %)', centroids=m["centroids"])
        return render(request, "map.html", chart=chart, meta=m,
                      mavericks=queries.mavericks(conn))
    finally:
        conn.close()


@app.get("/tilastot", response_class=HTMLResponse)
def tilastot(request: Request):
    conn = _conn()
    try:
        data = queries.stats_overview(conn)
        # trendikäyrä (valitut keskeiset aiheet)
        trends = data["trends"]
        focus = ["turvallisuus", "maahanmuutto", "ilmasto", "terveydenhuolto", "energia", "talous"]
        labels = {t["slug"]: t["label"] for t in trends["topics"]}
        series = [(labels.get(s, s), [trends["counts"][s][y] for y in trends["years"]])
                  for s in focus if s in trends["counts"]]
        data["trend_chart"] = viz.line_chart_svg(series, trends["years"])
        scatter = queries.activity_scatter(conn)
        pts = [(r["n_votes_cast"], r["n_speeches"],
                f'{r["full_name"]} ({r["party_current"] or "?"}) — {r["n_speeches"]} puhetta, {r["n_votes_cast"]} ääntä')
               for r in scatter]
        data["scatter_chart"] = viz.scatter_svg(pts, "Ääniä annettu", "Puheenvuoroja")
        return render(request, "stats.html", **data)
    finally:
        conn.close()


@app.get("/puolue", response_class=HTMLResponse)
def puolueet(request: Request):
    conn = _conn()
    try:
        return render(request, "parties.html", parties=queries.parties(conn))
    finally:
        conn.close()


@app.get("/puolue/{code}", response_class=HTMLResponse)
def puolue(request: Request, code: str):
    conn = _conn()
    try:
        return render(request, "party.html", overview=queries.party_overview(conn, code),
                      members=queries.party_members(conn, code),
                      words=queries.party_words(conn, code))
    finally:
        conn.close()


@app.get("/aiheet", response_class=HTMLResponse)
def aiheet(request: Request):
    conn = _conn()
    try:
        return render(request, "topics.html", topics=queries.topics(conn))
    finally:
        conn.close()


@app.get("/aihe/{slug}", response_class=HTMLResponse)
def aihe(request: Request, slug: str):
    conn = _conn()
    try:
        d = queries.topic_detail(conn, slug)
        if not d:
            return render(request, "notfound.html", what="Aihetta")
        own = queries.topic_ownership(conn, slug)
        own_chart = viz.stacked_bars_svg(own["years"], own["parties"], own["series"])
        return render(request, "topic.html", ownership_chart=own_chart, **d)
    finally:
        conn.close()


@app.get("/aanestys/{vote_id}", response_class=HTMLResponse)
def aanestys(request: Request, vote_id: int):
    conn = _conn()
    try:
        d = queries.vote_detail(conn, vote_id)
        if not d:
            return render(request, "notfound.html", what="Äänestystä")
        return render(request, "vote.html", **d)
    finally:
        conn.close()


@app.get("/puhe/{sid}", response_class=HTMLResponse)
def puhe(request: Request, sid: int):
    conn = _conn()
    try:
        d = queries.speech_detail(conn, sid)
        if not d:
            return render(request, "notfound.html", what="Puhetta")
        return render(request, "speech.html", **d)
    finally:
        conn.close()


@app.get("/lupaukset", response_class=HTMLResponse)
def lupaukset(request: Request):
    conn = _conn()
    try:
        promises = queries.all_promises(conn)
        for pr in promises:
            pr["mappings"] = queries.promise_mappings(conn, pr["id"])
        return render(request, "promises.html", promises=promises)
    finally:
        conn.close()


@app.get("/vertailu", response_class=HTMLResponse)
def vertailu(request: Request, a: int = 0, b: int = 0):
    conn = _conn()
    try:
        data = None
        agreement = None
        if a and b:
            data = queries.compare(conn, a, b)
            agreement = queries.pair_agreement(conn, a, b)
        return render(request, "compare.html", data=data, agreement=agreement,
                      persons=queries.list_persons(conn), a=a, b=b)
    finally:
        conn.close()


@app.get("/kattavuus", response_class=HTMLResponse)
def kattavuus(request: Request):
    conn = _conn()
    try:
        return render(request, "coverage.html", coverage=queries.coverage(conn),
                      overview=queries.overview(conn))
    finally:
        conn.close()


@app.get("/menetelmat", response_class=HTMLResponse)
def menetelmat(request: Request):
    md_path = config.ROOT / "docs" / "METHODOLOGY.md"
    html = _md.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables","fenced_code","toc"]) if md_path.exists() else "<p>Puuttuu.</p>"
    return render(request, "doc.html", title="Menetelmäkuvaus", body=html)


@app.get("/etiikka", response_class=HTMLResponse)
def etiikka(request: Request):
    md_path = config.ROOT / "docs" / "LEGAL_ETHICS.md"
    html = _md.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables","fenced_code","toc"]) if md_path.exists() else "<p>Puuttuu.</p>"
    return render(request, "doc.html", title="Juridiikka ja etiikka", body=html)


@app.get("/tietosuoja", response_class=HTMLResponse)
def tietosuoja(request: Request):
    md_path = config.ROOT / "docs" / "PRIVACY.md"
    html = _md.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables","fenced_code","toc"]) if md_path.exists() else "<p>Puuttuu.</p>"
    return render(request, "doc.html", title="Tietosuojaseloste", body=html)


@app.get("/korjaus", response_class=HTMLResponse)
def korjaus_form(request: Request, page_ref: str = "", person_id: str = ""):
    return render(request, "correction.html", page_ref=page_ref, person_id=person_id, sent=False)


@app.post("/korjaus", response_class=HTMLResponse)
def korjaus_post(request: Request, page_ref: str = Form(""), person_id: str = Form(""),
                 contact: str = Form(""), message: str = Form(...)):
    conn = _conn()
    try:
        queries.add_correction(conn, page_ref, person_id or None, contact, message)
        return render(request, "correction.html", page_ref=page_ref, person_id=person_id, sent=True)
    finally:
        conn.close()


@app.get("/yllapito/korjaukset", response_class=HTMLResponse)
def admin_corrections(request: Request, token: str = ""):
    if not config.ADMIN_TOKEN or token != config.ADMIN_TOKEN:
        return HTMLResponse(
            "<p>Pääsy estetty. Aseta KANSANMUISTI_ADMIN_TOKEN ja anna ?token=…</p>",
            status_code=403)
    conn = _conn()
    try:
        return render(request, "admin_corrections.html",
                      corrections=queries.list_corrections(conn), token=token)
    finally:
        conn.close()


@app.post("/yllapito/korjaukset", response_class=HTMLResponse)
def admin_corrections_update(request: Request, token: str = Form(""),
                             correction_id: int = Form(...), status: str = Form(...)):
    if not config.ADMIN_TOKEN or token != config.ADMIN_TOKEN:
        return HTMLResponse("Pääsy estetty.", status_code=403)
    conn = _conn()
    try:
        queries.set_correction_status(conn, correction_id, status)
        return RedirectResponse(f"/yllapito/korjaukset?token={token}", status_code=303)
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}

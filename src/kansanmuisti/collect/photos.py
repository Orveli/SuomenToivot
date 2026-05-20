"""Kerää edustajien kuvat Wikipedian/Wikimedia Commonsin kautta.

Lähde: fi.wikipedia.org pageimages-API (lead-kuva), joka osoittaa Wikimedia
Commonsin tiedostoon. Kuvat ovat pääosin vapaasti lisensoituja (CC/PD), mutta
kullakin on oma lisenssinsä → tallennamme attribuutiolinkin (Commons-tiedostosivu)
ja näytämme kuvalähteen käyttöliittymässä. Täsmäys: edustajan koko nimi = artikkelin
otsikko (redirectit ja normalisoinnit huomioitu).

Huom: tämä on ulkoinen, vapaaehtoinen rikaste — ei Eduskunnan avointa dataa.
"""
from __future__ import annotations

import datetime as dt
import time
import urllib.parse
import urllib.request
import json
import re

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731
API = "https://fi.wikipedia.org/w/api.php"
UA = "SuomenToivot/0.1 (kansalaisprojekti; https://github.com/Orveli/SuomenToivot)"
THUMB_SIZE = 320


def _api(titles):
    q = {"action": "query", "prop": "pageimages", "piprop": "thumbnail",
         "pithumbsize": str(THUMB_SIZE), "format": "json", "redirects": "1",
         "titles": "|".join(titles)}
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))


def _commons_file_url(thumb_url: str) -> str:
    """Johda Commons-tiedostosivu pikkukuvan URL:sta (attribuutio)."""
    m = re.search(r"/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/", thumb_url)
    if m:
        return "https://commons.wikimedia.org/wiki/File:" + m.group(1)
    return "https://commons.wikimedia.org/"


def collect_photos(conn, batch: int = 20, only_missing: bool = True, delay: float = 0.3) -> dict:
    rows = conn.execute(
        "SELECT person_id, full_name, photo_url FROM person WHERE full_name IS NOT NULL").fetchall()
    targets = [(r["person_id"], r["full_name"]) for r in rows
               if not (only_missing and r["photo_url"])]
    n_found = 0
    for i in range(0, len(targets), batch):
        chunk = targets[i:i + batch]
        names = [name for _pid, name in chunk]
        try:
            d = _api(names)
        except Exception:
            time.sleep(2)
            continue
        query = d.get("query", {})
        # rakenna ketju: kysytty nimi -> normalisoitu -> redirect -> lopullinen otsikko
        fwd = {}
        for r in query.get("normalized", []):
            fwd[r["from"]] = r["to"]
        for r in query.get("redirects", []):
            fwd[r["from"]] = r["to"]

        def resolve(name):
            seen = set()
            cur = name
            while cur in fwd and cur not in seen:
                seen.add(cur)
                cur = fwd[cur]
            return cur

        title_thumb = {}
        for _pid, pg in query.get("pages", {}).items():
            if "thumbnail" in pg:
                title_thumb[pg["title"]] = pg["thumbnail"]["source"]

        for pid, name in chunk:
            final = resolve(name)
            thumb = title_thumb.get(final)
            if thumb:
                conn.execute(
                    "UPDATE person SET photo_url=?, photo_credit_url=? WHERE person_id=?",
                    (thumb, _commons_file_url(thumb), pid))
                n_found += 1
        conn.commit()
        time.sleep(delay)
    return {"checked": len(targets), "found": n_found}

"""HTTP-klientti Eduskunnan avoimen datan taulu-API:lle.

API: https://avoindata.eduskunta.fi/api/v1/tables/{Taulu}/rows
  - perPage, page : sivutus
  - columnName, columnValue : yksinkertainen suodatus
Vastaus: {columnNames: [...], rowData: [[...]], hasMore: bool, ...}

Klientti on stdlib-pohjainen (urllib) jotta keruu toimii ilman ulkoisia riippuvuuksia.
Throttle + uudelleenyritys eksponentiaalisella backoffilla.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Dict, Iterator, List, Optional

from .. import config


class EduskuntaClient:
    def __init__(self, base: str | None = None, delay: float | None = None,
                 timeout: int | None = None, max_retries: int = 5):
        self.base = (base or config.API_BASE).rstrip("/")
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.max_retries = max_retries
        self._last_request = 0.0

    # -- matala taso ---------------------------------------------------------
    def _get(self, url: str) -> dict:
        # kohtelias throttle
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._last_request = time.monotonic()
                return data
            except Exception as e:  # noqa: BLE001 — verkko­virheet uusittavissa
                last_err = e
                time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"API-pyyntö epäonnistui {self.max_retries} kertaa: {url}: {last_err}")

    def table_page(self, table: str, page: int = 0, per_page: int = 100,
                   column: Optional[str] = None, value: Optional[str] = None) -> dict:
        params = {"perPage": per_page, "page": page}
        if column is not None:
            params["columnName"] = column
            params["columnValue"] = value or ""
        url = f"{self.base}/tables/{table}/rows?" + urllib.parse.urlencode(params)
        return self._get(url)

    # -- korkea taso ---------------------------------------------------------
    @staticmethod
    def to_dicts(payload: dict) -> List[Dict[str, object]]:
        cols = payload["columnNames"]
        return [dict(zip(cols, row)) for row in payload.get("rowData", [])]

    def iter_table(self, table: str, per_page: int = 100, start_page: int = 0,
                   column: Optional[str] = None, value: Optional[str] = None,
                   max_pages: Optional[int] = None) -> Iterator[Dict[str, object]]:
        """Iteroi taulun rivit (dict-muodossa) sivu kerrallaan kunnes hasMore=False."""
        page = start_page
        pages_done = 0
        while True:
            payload = self.table_page(table, page=page, per_page=per_page,
                                      column=column, value=value)
            for row in self.to_dicts(payload):
                yield row
            pages_done += 1
            if not payload.get("hasMore"):
                break
            if max_pages is not None and pages_done >= max_pages:
                break
            page += 1

    def filter_rows(self, table: str, column: str, value: str,
                    per_page: int = 100) -> List[Dict[str, object]]:
        """Hae kaikki rivit, joissa column == value (sivutettuna)."""
        out: List[Dict[str, object]] = []
        for row in self.iter_table(table, per_page=per_page, column=column, value=value):
            out.append(row)
        return out

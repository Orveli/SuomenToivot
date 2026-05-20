"""LLM-analyysikerroksen perusta: Anthropic Messages -asiakas (stdlib urllib),
pakotettu JSON-skeema (tool_use), pysyvä välimuisti ja budjettiraja.

Suunnitteluperiaatteet (LEGAL_ETHICS.md / METHODOLOGY.md):
- Riippuvuusvapaa: vain stdlib (urllib). Ydin toimii ilman avainta.
- Toistettava & jaettava: jokainen vastaus tallennetaan llm_cache-tauluun
  hashilla (malli + systeemi + käyttäjä + skeema). Uudelleenajo on ilmainen ja
  deterministinen; tulokset voidaan jakaa tietokannan mukana.
- Lähteistetty: skeemat pakottavat jokaiseen väitteeseen suoran lainauksen
  (evidence_quote) ja luottamustason. Mallia ohjeistetaan olemaan keksimättä.
- Budjetti: enint. config.LLM_MAX_CALLS tuotantokutsua per ajo (välimuistiosumat
  eivät kuluta budjettia).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import urllib.error
import urllib.request

from .. import config

NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()  # noqa: E731


class LLMUnavailable(RuntimeError):
    """Heitetään, kun avainta ei ole eikä vastausta löydy välimuistista."""


class BudgetExceeded(RuntimeError):
    """Heitetään, kun ajon tuotantokutsubudjetti täyttyy."""


def ensure_cache(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS llm_cache ("
        " key TEXT PRIMARY KEY, model TEXT, response_json TEXT, created_at TEXT)")
    conn.commit()


def _cache_key(model: str, system: str, user: str, tool_schema: dict) -> str:
    h = hashlib.sha256()
    for part in (model, system, user, json.dumps(tool_schema, sort_keys=True, ensure_ascii=False)):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _http_call(system: str, user: str, tool: dict, model: str) -> dict:
    """Yksi pakotettu tool_use -kutsu Anthropic Messages -rajapintaan."""
    body = json.dumps({
        "model": model,
        "max_tokens": config.LLM_MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": tool["name"]},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{config.LLM_API_BASE}/messages", data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": config.LLM_API_KEY,
            "anthropic-version": config.LLM_VERSION,
        })
    with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    for block in payload.get("content", []):
        if block.get("type") == "tool_use":
            return block["input"]
    raise LLMUnavailable("Vastaus ei sisältänyt tool_use-lohkoa")


class LLMRunner:
    """Kutsujen ajaja: hoitaa välimuistin ja budjetin yhden analyysiajon ajan."""

    def __init__(self, conn, *, model: str | None = None, max_calls: int | None = None,
                 use_cache_only: bool | None = None):
        self.conn = conn
        self.model = model or config.LLM_MODEL
        self.max_calls = config.LLM_MAX_CALLS if max_calls is None else max_calls
        # Jos avainta ei ole, toimitaan pelkän välimuistin varassa.
        self.cache_only = (not config.llm_enabled()) if use_cache_only is None else use_cache_only
        self.calls = 0          # tuotantokutsut (kuluttavat budjettia)
        self.cache_hits = 0
        self.misses = 0         # välimuistin ohi mutta avainta ei → ohitetut
        ensure_cache(conn)

    def extract(self, system: str, user: str, tool: dict) -> dict | None:
        """Palauta strukturoitu tulos (tool input) tai None jos ei saatavilla.

        Determinismi: vastaus haetaan ensin välimuistista. Vain välimuistin ohi
        mennään verkkoon (jos avain on ja budjetti riittää)."""
        key = _cache_key(self.model, system, user, tool)
        row = self.conn.execute(
            "SELECT response_json FROM llm_cache WHERE key=?", (key,)).fetchone()
        if row is not None:
            self.cache_hits += 1
            return json.loads(row["response_json"])
        if self.cache_only:
            self.misses += 1
            return None
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"Tuotantokutsubudjetti täynnä ({self.max_calls}). Nosta KANSANMUISTI_LLM_MAX_CALLS.")
        result = _http_call(system, user, tool, self.model)
        self.calls += 1
        self.conn.execute(
            "INSERT OR REPLACE INTO llm_cache(key,model,response_json,created_at) VALUES(?,?,?,?)",
            (key, self.model, json.dumps(result, ensure_ascii=False), NOW()))
        self.conn.commit()
        return result

    def stats(self) -> dict:
        return {"model": self.model, "live_calls": self.calls,
                "cache_hits": self.cache_hits, "skipped_no_key": self.misses,
                "cache_only": self.cache_only}

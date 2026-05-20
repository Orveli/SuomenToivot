"""Keskitetty konfiguraatio. Ympäristömuuttujat voivat ohittaa oletukset."""
from __future__ import annotations

import os
from pathlib import Path

# Projektin juuri = .../Kansanmuisti
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("KANSANMUISTI_DATA", ROOT / "data"))
DB_PATH = Path(os.environ.get("KANSANMUISTI_DB", DATA_DIR / "kansanmuisti.sqlite3"))
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SEED_DIR = ROOT / "seed"

# Eduskunnan avoin data
API_BASE = os.environ.get(
    "KANSANMUISTI_API", "https://avoindata.eduskunta.fi/api/v1"
)
# Kohtelias throttle (s) peräkkäisten pyyntöjen välillä
REQUEST_DELAY = float(os.environ.get("KANSANMUISTI_DELAY", "0.05"))
REQUEST_TIMEOUT = int(os.environ.get("KANSANMUISTI_TIMEOUT", "120"))
USER_AGENT = "Kansanmuisti/0.1 (julkisen tiedon kansalaispalvelu; +https://github.com/)"

# Lisenssi ja attribuutio (LEGAL_ETHICS.md)
# Ylläpitonäkymän suojaus (korjauspyyntöjen käsittely). Tyhjä = näkymä pois käytöstä.
ADMIN_TOKEN = os.environ.get("KANSANMUISTI_ADMIN_TOKEN", "")

DATA_LICENSE = "CC BY 4.0"
DATA_ATTRIBUTION = "Lähde: Eduskunta – avoin data (avoindata.eduskunta.fi), CC BY 4.0, muokattu/yhdistelty."

# ---------------------------------------------------------------------------
# LLM-analyysikerros (valinnainen). Ydin toimii ilman avainta; LLM-näkymät
# degradoituvat siististi (näyttävät "ei vielä ajettu"). Tulokset välimuistissa
# (llm_cache) → toistettavia ja jaettavissa tietokannassa. Periaate säilyy:
# jokainen LLM-väite on lähteistetty alkuperäiseen puheeseen/äänestykseen,
# näytetään lainaus, ei motiiviväitteitä, epävarmuus merkitään.
# ---------------------------------------------------------------------------
LLM_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_API_BASE = os.environ.get("KANSANMUISTI_LLM_API", "https://api.anthropic.com/v1")
LLM_MODEL = os.environ.get("KANSANMUISTI_LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_VERSION = os.environ.get("KANSANMUISTI_LLM_API_VERSION", "2023-06-01")
LLM_MAX_TOKENS = int(os.environ.get("KANSANMUISTI_LLM_MAX_TOKENS", "1536"))
LLM_TIMEOUT = int(os.environ.get("KANSANMUISTI_LLM_TIMEOUT", "120"))
# Turvaraja: enint. näin monta TUOTANTOkutsua (ei välimuistiosumaa) per ajo.
LLM_MAX_CALLS = int(os.environ.get("KANSANMUISTI_LLM_MAX_CALLS", "500"))


def llm_enabled() -> bool:
    return bool(LLM_API_KEY)

# Keruun oletusaikaikkuna (täysi tavoite: 2015–2025). Voidaan ohittaa CLI:llä.
DEFAULT_START_YEAR = int(os.environ.get("KANSANMUISTI_START_YEAR", "2015"))
DEFAULT_END_YEAR = int(os.environ.get("KANSANMUISTI_END_YEAR", "2025"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)

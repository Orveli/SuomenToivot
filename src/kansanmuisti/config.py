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

# Keruun oletusaikaikkuna (täysi tavoite: 2015–2025). Voidaan ohittaa CLI:llä.
DEFAULT_START_YEAR = int(os.environ.get("KANSANMUISTI_START_YEAR", "2015"))
DEFAULT_END_YEAR = int(os.environ.get("KANSANMUISTI_END_YEAR", "2025"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)

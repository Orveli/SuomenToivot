"""Merkityshaku (semanttinen haku) puheenvuoroihin — VALINNAINEN moduuli.

Käyttää paikallista monikielistä lausemallia (sentence-transformers) upottamaan
puheet vektoreiksi. Haku vertaa kyselyn vektoria puheiden vektoreihin (kosini).

Periaate ja rajaus (METHODOLOGY): tämä on **haun/löytämisen apuväline**, EI väitteiden
tai pisteytysten perusta. Malli on "musta laatikko", joten emme johda siitä faktoja —
jokainen tulos linkittyy alkuperäiseen puheeseen, jonka käyttäjä lukee itse. Ydin
(sana­haku FTS) toimii ilman tätä moduulia; jos sentence-transformers tai upotukset
puuttuvat, käyttöliittymä putoaa takaisin sanahakuun.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List, Optional, Tuple

from .. import config

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMB_PATH = config.DATA_DIR / "speech_embeddings.npy"
IDS_PATH = config.DATA_DIR / "speech_emb_ids.npy"
MAX_CHARS = 1500  # katkaise pitkät puheet (malli rajaa joka tapauksessa)


def is_available() -> bool:
    """Onko merkityshaku käytettävissä (kirjasto + upotukset olemassa)?"""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return EMB_PATH.exists() and IDS_PATH.exists()


def _load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def embed_speeches(conn, batch_size: int = 256, limit: Optional[int] = None,
                   progress: bool = True) -> dict:
    """Upota kaikki puheet ja tallenna vektorit levylle (kertaluontoinen)."""
    import numpy as np
    model = _load_model()
    rows = conn.execute(
        "SELECT id, text FROM speech WHERE text IS NOT NULL AND text!='' ORDER BY id").fetchall()
    if limit:
        rows = rows[:limit]
    ids = np.array([r["id"] for r in rows], dtype=np.int64)
    texts = [(r["text"] or "")[:MAX_CHARS] for r in rows]
    emb = model.encode(texts, batch_size=batch_size, show_progress_bar=progress,
                       normalize_embeddings=True, convert_to_numpy=True)
    EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(EMB_PATH, emb.astype("float32"))
    np.save(IDS_PATH, ids)
    return {"speeches": int(len(ids)), "dim": int(emb.shape[1]),
            "path": str(EMB_PATH), "computed_at": dt.datetime.now().isoformat()}


class SemanticIndex:
    """Ladattava kerran ja pidettävä muistissa (web-prosessi)."""

    def __init__(self):
        import numpy as np
        self._np = np
        self.emb = np.load(EMB_PATH, mmap_mode="r")
        self.ids = np.load(IDS_PATH)
        self.model = _load_model()

    def search(self, query: str, top_k: int = 30) -> List[Tuple[int, float]]:
        np = self._np
        q = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = self.emb @ q  # vektorit normalisoitu -> kosini = pistetulo
        k = min(top_k, len(sims))
        idx = np.argpartition(-sims, k - 1)[:k]
        idx = idx[np.argsort(-sims[idx])]
        return [(int(self.ids[i]), float(sims[i])) for i in idx]


_INDEX: Optional[SemanticIndex] = None


def get_index() -> Optional[SemanticIndex]:
    """Lataa indeksi laiskasti; palauta None jos ei käytettävissä."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    if not is_available():
        return None
    try:
        _INDEX = SemanticIndex()
    except Exception:
        return None
    return _INDEX

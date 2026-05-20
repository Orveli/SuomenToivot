-- Kansanmuisti-tietokantaskeema (SQLite). Idempotentti: CREATE ... IF NOT EXISTS.
-- Periaate: jokaisella faktalla provenienssi (source_url + fetched_at). Tulkinnat erillisissä analysis_*-tauluissa.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- Henkilöt ja niiden historiat
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person (
    person_id           INTEGER PRIMARY KEY,
    last_name           TEXT,
    first_name          TEXT,
    full_name           TEXT,
    party_current       TEXT,          -- ryhmätunnus (esim. 'kok')
    party_current_name  TEXT,
    is_minister         INTEGER DEFAULT 0,
    birth_year          TEXT,
    gender              TEXT,
    electoral_district  TEXT,
    profession          TEXT,
    active_from         TEXT,          -- aikaisin edustajatoimen alku
    active_to           TEXT,          -- viimeisin edustajatoimen loppu (NULL = jatkuu)
    source_url          TEXT,
    photo_url           TEXT,          -- Wikimedia Commons -pikkukuva (hotlink)
    photo_credit_url    TEXT,          -- Commons-tiedostosivu (attribuutio)
    fetched_at          TEXT
);

CREATE TABLE IF NOT EXISTS person_party (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL,
    group_code  TEXT,
    group_name  TEXT,
    start_date  TEXT,
    end_date    TEXT,
    FOREIGN KEY (person_id) REFERENCES person(person_id)
);

CREATE TABLE IF NOT EXISTS person_term (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL,
    start_date  TEXT,
    end_date    TEXT,
    FOREIGN KEY (person_id) REFERENCES person(person_id)
);

CREATE TABLE IF NOT EXISTS person_minister_role (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL,
    title       TEXT,
    government  TEXT,
    start_date  TEXT,
    end_date    TEXT,
    FOREIGN KEY (person_id) REFERENCES person(person_id)
);

-- ---------------------------------------------------------------------------
-- Äänestykset
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vote (
    vote_id              INTEGER PRIMARY KEY,
    vp_year              INTEGER,
    session_number       INTEGER,
    session_date         TEXT,
    title                TEXT,
    extra_title          TEXT,
    main_item_title      TEXT,
    item_title           TEXT,
    treatment_title      TEXT,
    treatment_stage      TEXT,
    legislative_item     TEXT,          -- esim. 'HE 174/2024 vp'
    legislative_item_url TEXT,
    result_yes           INTEGER,
    result_no            INTEGER,
    result_empty         INTEGER,
    result_absent        INTEGER,
    result_total         INTEGER,
    minutes_url          TEXT,
    url                  TEXT,
    is_procedural        INTEGER DEFAULT 0,   -- heuristinen: menettelyäänestys (METHODOLOGY.md)
    fetched_at           TEXT
);

CREATE TABLE IF NOT EXISTS vote_record (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vote_id     INTEGER NOT NULL,
    person_id   INTEGER,
    first_name  TEXT,
    last_name   TEXT,
    party       TEXT,                   -- ryhmä äänestyshetkellä
    vote_value  TEXT,                   -- normalisoitu: 'Jaa' | 'Ei' | 'Tyhjää' | 'Poissa'
    FOREIGN KEY (vote_id) REFERENCES vote(vote_id)
);

-- ---------------------------------------------------------------------------
-- Puheenvuorot (teksti PTK-dokumenteista, VaskiData)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS speech (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    external_key      TEXT UNIQUE,      -- PTK:n PuheenvuoroOsa muuTunnus
    person_id         INTEGER,
    first_name        TEXT,
    last_name         TEXT,
    party             TEXT,
    session_key       TEXT,             -- '2024/50'
    ptk_id            TEXT,             -- 'PTK 50/2024 vp'
    speech_type       TEXT,             -- T (varsinainen) | V (vastaus) | P
    started_at        TEXT,
    legislative_item  TEXT,
    text              TEXT,
    word_count        INTEGER,
    url               TEXT,
    fetched_at        TEXT
);

-- ---------------------------------------------------------------------------
-- Vaalikone (Yle, avoin CC-BY, anonyymi): ehdokkaiden väittämävastaukset.
-- Puoluetason aggregaatti (avoin data ei sisällä nimiä). Nimellinen data
-- (per ehdokas -> edustaja) edellyttää erillistä pyyntöä Yleltä (ks. docs).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vaalikone_statement (
    id        INTEGER PRIMARY KEY,
    election  TEXT,                  -- esim. 'eduskuntavaalit2023'
    text      TEXT
);

CREATE TABLE IF NOT EXISTS vaalikone_party_stance (
    election     TEXT,
    party        TEXT,               -- vaalikoneen puoluenimi (esim. 'Kokoomus')
    party_code   TEXT,               -- normalisoitu (kok, ps, ...) jos tunnistettu
    statement_id INTEGER,
    mean         REAL,               -- keskiarvo 1–5 (5 = täysin samaa mieltä)
    n            INTEGER,            -- vastanneita ehdokkaita
    agree_pct    REAL,               -- osuus, joka samaa mieltä (4–5)
    PRIMARY KEY (election, party, statement_id)
);

-- ---------------------------------------------------------------------------
-- Säädösasiakirjat (HE = hallituksen esitys ym.) — sisältö VaskiDatasta.
-- Käytetään äänestysten aiheluokittelun rikastamiseen (otsikko + pääas. sisältö).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legislation (
    eduskunta_tunnus  TEXT PRIMARY KEY,   -- esim. 'HE 8/2024 vp'
    doc_type          TEXT,               -- 'HE', 'LA', ...
    title             TEXT,
    summary           TEXT,               -- esityksen pääasiallinen sisältö (alkukappaleet)
    url               TEXT,
    fetched_at        TEXT
);

-- ---------------------------------------------------------------------------
-- Aihetaksonomia ja luokittelut (METHODOLOGY.md)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topic (
    id     INTEGER PRIMARY KEY,
    slug   TEXT UNIQUE,
    label  TEXT
);

CREATE TABLE IF NOT EXISTS topic_keyword (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id  INTEGER NOT NULL,
    keyword   TEXT NOT NULL,            -- normalisoitu prefiksi
    weight    REAL DEFAULT 1.0,
    FOREIGN KEY (topic_id) REFERENCES topic(id)
);

CREATE TABLE IF NOT EXISTS speech_topic (
    speech_id  INTEGER NOT NULL,
    topic_id   INTEGER NOT NULL,
    score      REAL,
    is_primary INTEGER DEFAULT 0,
    PRIMARY KEY (speech_id, topic_id)
);

CREATE TABLE IF NOT EXISTS vote_topic (
    vote_id    INTEGER NOT NULL,
    topic_id   INTEGER NOT NULL,
    score      REAL,
    is_primary INTEGER DEFAULT 0,
    PRIMARY KEY (vote_id, topic_id)
);

-- ---------------------------------------------------------------------------
-- Lupaukset (kuratoitu, lähteistetty siemenaineisto) + lupaus↔äänestys-kytkentä
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promise (
    id            INTEGER PRIMARY KEY,
    scope         TEXT,                 -- 'party' | 'person'
    party_code    TEXT,
    person_id     INTEGER,
    topic_slug    TEXT,
    text          TEXT,
    source_title  TEXT,
    source_url    TEXT,
    source_year   INTEGER,
    curated_by    TEXT,
    curated_at    TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS promise_vote_map (
    id              INTEGER PRIMARY KEY,
    promise_id      INTEGER NOT NULL,
    vote_id         INTEGER NOT NULL,
    expected_value  TEXT,               -- 'Jaa' | 'Ei' (lupausta tukeva ääni)
    rationale       TEXT,
    source_note     TEXT,
    curated_by      TEXT,
    mapping_version TEXT,
    FOREIGN KEY (promise_id) REFERENCES promise(id),
    FOREIGN KEY (vote_id) REFERENCES vote(vote_id)
);

-- ---------------------------------------------------------------------------
-- Analyysitulokset (lasketut tunnusluvut — EROTETTU faktoista)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_party_deviation (
    person_id      INTEGER NOT NULL,
    vote_id        INTEGER NOT NULL,
    party          TEXT,
    member_value   TEXT,
    party_line     TEXT,                -- 'Jaa'|'Ei'|'TIE'|'UNDEFINED'
    classification TEXT,                -- 'follows'|'deviates'|'absent'|'ineligible'
    PRIMARY KEY (person_id, vote_id)
);

CREATE TABLE IF NOT EXISTS analysis_party_line (
    vote_id  INTEGER NOT NULL,
    party    TEXT NOT NULL,
    line     TEXT,                          -- 'Jaa'|'Ei'|'TIE'|'UNDEFINED'
    PRIMARY KEY (vote_id, party)
);

CREATE TABLE IF NOT EXISTS analysis_member_summary (
    person_id            INTEGER PRIMARY KEY,
    period               TEXT,
    n_votes_total        INTEGER,
    n_votes_eligible     INTEGER,
    n_deviations         INTEGER,
    deviation_rate       REAL,
    n_votes_cast         INTEGER,
    n_absent             INTEGER,
    n_speeches           INTEGER,
    speech_vote_alignment REAL,         -- komponentti A (0..1)
    party_line_score     REAL,          -- komponentti B (0..1)
    consistency_index    INTEGER,       -- 0..100 (läpinäkyvä indikaattori)
    confidence_score     REAL,          -- 0..1
    confidence_level     TEXT,          -- 'korkea'|'kohtalainen'|'matala'
    flags                TEXT,          -- pilkuin eroteltu epävarmuusliput
    computed_at          TEXT
);

CREATE TABLE IF NOT EXISTS analysis_member_topic (
    person_id   INTEGER NOT NULL,
    topic_id    INTEGER NOT NULL,
    n_speeches  INTEGER DEFAULT 0,
    n_votes     INTEGER DEFAULT 0,
    PRIMARY KEY (person_id, topic_id)
);

CREATE TABLE IF NOT EXISTS analysis_power_effect (
    party     TEXT NOT NULL,
    status    TEXT NOT NULL,            -- 'gov' | 'opp'
    n_votes   INTEGER,
    win_pct   REAL,                     -- osuus, jossa puoluelinja == voittava puoli
    PRIMARY KEY (party, status)
);

CREATE TABLE IF NOT EXISTS analysis_gov_winrate (
    vp_year   INTEGER PRIMARY KEY,
    n_votes   INTEGER,
    gov_wins  INTEGER,
    pct       REAL
);

CREATE TABLE IF NOT EXISTS analysis_gov_lost (
    vote_id   INTEGER PRIMARY KEY,        -- substantiiviäänestys, jossa hallituslinja hävisi
    margin    INTEGER
);

CREATE TABLE IF NOT EXISTS analysis_rhetoric_map (
    person_id  INTEGER PRIMARY KEY,
    party      TEXT,
    dim1       REAL,
    dim2       REAL,
    nearest_party TEXT,                  -- lähin retoriikkakeskipiste
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS analysis_word_usage (
    person_id        INTEGER NOT NULL,
    category         TEXT NOT NULL,          -- 'filler' | 'swear'
    n_hits           INTEGER,
    n_words          INTEGER,
    per_1000         REAL,                   -- osumia / 1000 sanaa
    lexicon_version  TEXT,
    computed_at      TEXT,
    PRIMARY KEY (person_id, category)
);

CREATE TABLE IF NOT EXISTS analysis_word_hits (
    person_id  INTEGER NOT NULL,
    category   TEXT NOT NULL,
    word       TEXT NOT NULL,
    n          INTEGER,
    PRIMARY KEY (person_id, category, word)
);

CREATE TABLE IF NOT EXISTS analysis_party_words (
    party    TEXT NOT NULL,
    word     TEXT NOT NULL,
    zscore   REAL,                  -- log-odds z (Monroe et al.)
    n_party  INTEGER,               -- esiintymät ryhmän puheissa
    n_total  INTEGER,               -- esiintymät koko aineistossa
    rank     INTEGER,
    PRIMARY KEY (party, word)
);

CREATE TABLE IF NOT EXISTS analysis_political_map (
    person_id      INTEGER PRIMARY KEY,
    period         TEXT,
    party          TEXT,                  -- ryhmä, jota käytettiin (nykyinen)
    dim1           REAL,                  -- pääakseli (selittää eniten vaihtelusta)
    dim2           REAL,                  -- toinen akseli
    dist_own       REAL,                  -- etäisyys oman ryhmän keskipisteeseen
    nearest_party  TEXT,                  -- lähin ryhmäkeskipiste (voi olla eri kuin oma)
    n_votes        INTEGER,
    computed_at    TEXT
);

CREATE TABLE IF NOT EXISTS analysis_position_change (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id    INTEGER NOT NULL,
    topic_id     INTEGER,
    item_base    TEXT,
    from_value   TEXT, from_date TEXT,
    to_value     TEXT, to_date   TEXT,
    gap_days     INTEGER,
    note         TEXT
);

-- ---------------------------------------------------------------------------
-- Kattavuus, keruun tila, korjauskanava
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coverage_stat (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    metric       TEXT,
    dimension    TEXT,
    value        TEXT,
    computed_at  TEXT
);

CREATE TABLE IF NOT EXISTS ingest_state (
    job          TEXT PRIMARY KEY,      -- esim. 'votes:2024'
    last_pk      TEXT,
    last_page    INTEGER,
    status       TEXT,                  -- 'running'|'done'|'partial'
    n_items      INTEGER DEFAULT 0,
    updated_at   TEXT,
    note         TEXT
);

CREATE TABLE IF NOT EXISTS correction_request (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT,
    page_ref    TEXT,
    person_id   INTEGER,
    contact     TEXT,
    message     TEXT,
    status      TEXT DEFAULT 'open'
);

-- ---------------------------------------------------------------------------
-- Indeksit
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_vote_record_vote ON vote_record(vote_id);
CREATE INDEX IF NOT EXISTS idx_vote_record_person ON vote_record(person_id);
-- Estä saman edustajan kahdentuminen samassa äänestyksessä (lähde palauttaa toisinaan dupleja)
CREATE UNIQUE INDEX IF NOT EXISTS ux_vote_record ON vote_record(vote_id, person_id);
CREATE INDEX IF NOT EXISTS idx_vote_year ON vote(vp_year);
CREATE INDEX IF NOT EXISTS idx_speech_person ON speech(person_id);
CREATE INDEX IF NOT EXISTS idx_speech_session ON speech(session_key);
CREATE INDEX IF NOT EXISTS idx_speech_topic_topic ON speech_topic(topic_id);
CREATE INDEX IF NOT EXISTS idx_vote_topic_topic ON vote_topic(topic_id);
CREATE INDEX IF NOT EXISTS idx_person_party_person ON person_party(person_id);
CREATE INDEX IF NOT EXISTS idx_dev_person ON analysis_party_deviation(person_id);

-- Kokotekstihaku puheille (FTS5, external content)
CREATE VIRTUAL TABLE IF NOT EXISTS speech_fts USING fts5(
    text,
    content='speech',
    content_rowid='id',
    tokenize='unicode61'
);

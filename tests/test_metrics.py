"""Tunnuslukujen yksikkötestit kiinteällä fixture-datalla (METHODOLOGY §5, §6, §4)."""


def test_party_line_and_deviation(conn):
    # vote 100: kok enemmistö Jaa (1,2 Jaa, 3 Ei) -> henkilö 3 poikkeaa
    row = conn.execute(
        "SELECT party_line, classification FROM analysis_party_deviation"
        " WHERE vote_id=100 AND person_id=3").fetchone()
    assert row["party_line"] == "Jaa"
    assert row["classification"] == "deviates"
    # henkilö 1 seuraa linjaa
    row1 = conn.execute(
        "SELECT classification FROM analysis_party_deviation WHERE vote_id=100 AND person_id=1"
    ).fetchone()
    assert row1["classification"] == "follows"


def test_absent_excluded_from_eligible(conn):
    # henkilö 5 oli Poissa äänestyksessä 101 -> classification 'absent'
    row = conn.execute(
        "SELECT classification FROM analysis_party_deviation WHERE vote_id=101 AND person_id=5"
    ).fetchone()
    assert row["classification"] == "absent"


def test_deviation_rate_person3(conn):
    s = conn.execute(
        "SELECT n_votes_eligible, n_deviations, deviation_rate FROM analysis_member_summary"
        " WHERE person_id=3").fetchone()
    # henkilö 3: äänestykset 100(Ei vs linja Jaa=poikkeaa),101(Jaa=linjassa),102(Jaa=linjassa)
    # eligible=3, deviations=1 -> rate ~0.333
    assert s["n_votes_eligible"] == 3
    assert s["n_deviations"] == 1
    assert abs(s["deviation_rate"] - (1 / 3)) < 1e-6


def test_consistency_index_in_range_and_components(conn):
    for r in conn.execute("SELECT person_id, consistency_index, party_line_score,"
                          " confidence_level FROM analysis_member_summary"):
        if r["consistency_index"] is not None:
            assert 0 <= r["consistency_index"] <= 100
        assert r["confidence_level"] in ("korkea", "kohtalainen", "matala")


def test_position_change_detected_person3(conn):
    # henkilö 3: HE 1/2024 vp Ei (100, maalis) -> Jaa (102, touko)
    rows = conn.execute(
        "SELECT from_value, to_value, item_base FROM analysis_position_change WHERE person_id=3"
    ).fetchall()
    assert any(r["from_value"] == "Ei" and r["to_value"] == "Jaa"
               and r["item_base"] == "HE 1/2024 vp" for r in rows)


def test_speech_vote_alignment_present_for_speaker(conn):
    # henkilö 1 puhui terveydenhuollosta ja verotuksesta lähellä äänestyksiä -> A > 0
    s = conn.execute(
        "SELECT speech_vote_alignment FROM analysis_member_summary WHERE person_id=1").fetchone()
    assert s["speech_vote_alignment"] is not None
    assert s["speech_vote_alignment"] > 0


def test_low_sample_flag(conn):
    # pieni aineisto -> LOW_SAMPLE-lippu odotettavissa
    s = conn.execute("SELECT flags FROM analysis_member_summary WHERE person_id=1").fetchone()
    assert "LOW_SAMPLE" in (s["flags"] or "")

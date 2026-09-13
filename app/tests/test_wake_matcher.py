from scorpion.wake_matcher import WakeMatcher


def test_accepts_canonical_variant_and_trailing_command():
    matcher = WakeMatcher("Scorpion", aliases={"skorpion", "scorpian"})
    match = matcher.match("Skorpion, öffne den Rechner")
    assert match is not None
    assert match.trailing_text == "öffne den Rechner"


def test_accepts_canonical_word():
    matcher = WakeMatcher("Scorpion")
    match = matcher.match("Scorpion")
    assert match is not None
    assert match.trailing_text == ""
    assert match.normalized_alias == "scorpion"


def test_rejects_unrelated_fuzzy_word():
    matcher = WakeMatcher("Scorpion", aliases=set(), max_edit_distance=2)
    assert matcher.match("skulpturen sind schön") is None


def test_fuzzy_match_is_conservative_for_short_tokens():
    matcher = WakeMatcher("Scorpion", aliases=set(), max_edit_distance=2)
    assert matcher.match("scorp hi") is None

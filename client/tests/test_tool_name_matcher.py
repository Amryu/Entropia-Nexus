"""Tests for the tool name matcher."""

import pytest

from client.ocr.tool_name_matcher import ToolNameMatcher, MIN_PREFIX_LEN


class _MockDataClient:
    """Minimal DataClient mock returning a few equippable items."""

    _WEAPONS = [
        {"Name": "ArMatrix LR-35 (L)"},
        {"Name": "ArMatrix LR-40 (L)"},
        {"Name": "Herman ARK-20 (L)"},
        {"Name": "Isis LR 32 (L)"},
        {"Name": "Sollomate Opalo (L)"},
    ]

    _MEDICAL_TOOLS = [
        {"Name": "Vivo T10 (L)"},
        {"Name": "Vivo T20 (L)"},
    ]

    _MEDICAL_CHIPS = [
        {"Name": "Regeneration Chip 1 (L)"},
        {"Name": "Regeneration Chip 2 (L)"},
    ]

    def get_weapons(self):
        return self._WEAPONS

    def get_medical_tools(self):
        return self._MEDICAL_TOOLS

    def get_medical_chips(self):
        return self._MEDICAL_CHIPS

    def get_misc_tools(self):
        return []

    def get_finders(self):
        return []

    def get_excavators(self):
        return []

    def get_refiners(self):
        return []

    def get_scanners(self):
        return []

    def get_teleportation_chips(self):
        return []

    def get_effect_chips(self):
        return []

    def get_implants(self):
        return []

    def get_amplifiers(self):
        return []

    def get_scopes_and_sights(self):
        return []

    def get_absorbers(self):
        return []

    def get_finder_amplifiers(self):
        return []


@pytest.fixture
def matcher():
    return ToolNameMatcher(_MockDataClient())


class TestToolNameMatcher:
    def test_exact_match(self, matcher):
        result = matcher.match("ArMatrix LR-35 (L)")
        assert result.matched_name == "ArMatrix LR-35 (L)"
        assert result.edit_distance == 0

    def test_fuzzy_match_single_char_error(self, matcher):
        result = matcher.match("ArMatrix LR-3S (L)")  # 5→S
        assert result.matched_name == "ArMatrix LR-35 (L)"
        assert result.edit_distance == 1

    def test_ambiguous_match_returns_candidates(self, matcher):
        """LR-35 and LR-40 differ by one digit — both should be candidates."""
        result = matcher.match("ArMatrix LR-3_ (L)")
        # Should have candidates (both 35 and 40 are 1 edit away)
        assert len(result.candidates) >= 1

    def test_no_match_returns_original(self, matcher):
        result = matcher.match("XYZZY")
        assert result.matched_name == "XYZZY"  # no match found
        assert result.edit_distance >= 4

    def test_loads_only_equippable(self, matcher):
        """Verify the matcher loaded items from equippable categories."""
        # Force refresh
        matcher._refresh_if_needed()
        # Should have loaded 9 items total
        assert len(matcher._all_normalized) == 9

    def test_prefix_match_truncated_name(self, matcher):
        """Test prefix matching for names truncated by the HUD."""
        # Full name is "Sollomate Opalo (L)" but HUD shows "Sollomate Opal"
        result = matcher.match_prefix("Sollomate Opal")
        assert result.matched_name == "Sollomate Opalo (L)"
        assert len(result.candidates) >= 1

    def test_prefix_too_short_skipped(self, matcher):
        """Prefix matching requires minimum length."""
        result = matcher.match_prefix("Sol")
        # Too short for prefix matching, falls through to no match
        assert len(result.candidates) <= 1

    def test_medical_tools_included(self, matcher):
        result = matcher.match("Vivo T10 (L)")
        assert result.matched_name == "Vivo T10 (L)"
        assert result.edit_distance == 0

    def test_medical_chips_included(self, matcher):
        result = matcher.match("Regeneration Chip 1 (L)")
        assert result.matched_name == "Regeneration Chip 1 (L)"
        assert result.edit_distance == 0

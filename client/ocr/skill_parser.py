import json
import os
import time
import urllib.request
import urllib.error
from difflib import SequenceMatcher
from typing import Optional

from ..core.gil_yield import GilYielder
from ..core.logger import get_logger

log_skills = get_logger("SkillMatcher")
log_ranks = get_logger("RankVerifier")

SKILLS_API_URL = "https://api.entropianexus.com/skills"
RANKS_API_URL = "https://api.entropianexus.com/enumerations/Skill%20Ranks"
CACHE_MAX_AGE_SECONDS = 86400  # 24 hours


class SkillMatcher:
    """Matches OCR text against the known skills reference list using fuzzy matching.

    Fetches skills from api.entropianexus.com/skills and caches the result
    locally. Falls back to cached data if the API is unreachable.
    """

    def __init__(self, cache_path: str = None):
        if cache_path is None:
            cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "skill_reference.json")
        self._cache_path = cache_path
        self._skills = self._load_skills()
        self._name_to_skill = {s["name"].lower(): s for s in self._skills}
        self._skill_names = [s["name"] for s in self._skills]

    def _load_skills(self) -> list[dict]:
        """Load skills from API (with local cache fallback)."""
        # Try API if cache is missing or stale
        if self._cache_is_stale():
            api_skills = self._fetch_from_api()
            if api_skills:
                self._write_cache(api_skills)
                return api_skills

        # Fall back to cached file
        if os.path.exists(self._cache_path):
            log_skills.info("Using cached skills from %s", self._cache_path)
            return self._read_cache()

        raise FileNotFoundError(
            f"No skill data available. API unreachable and no cache at {self._cache_path}"
        )

    def _cache_is_stale(self) -> bool:
        if not os.path.exists(self._cache_path):
            return True
        age = time.time() - os.path.getmtime(self._cache_path)
        return age > CACHE_MAX_AGE_SECONDS

    def _fetch_from_api(self) -> list[dict] | None:
        """Fetch skills from the Nexus API and normalize to cache format."""
        try:
            log_skills.info("Fetching skills from %s", SKILLS_API_URL)
            req = urllib.request.Request(SKILLS_API_URL, headers={
                "Accept": "application/json",
                "User-Agent": "NexusClient/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            log_skills.warning("API fetch failed: %s", e)
            return None

        # Normalize API response to simplified format
        skills = []
        for item in raw:
            skills.append({
                "id": item["Id"],
                "name": item["Name"],
                "category": item.get("Category", {}).get("Name", "Unknown"),
                "hidden": item.get("Properties", {}).get("IsHidden", False),
            })

        log_skills.info("Fetched %d skills from API", len(skills))
        return skills

    def _read_cache(self) -> list[dict]:
        with open(self._cache_path, "r") as f:
            return json.load(f)

    def _write_cache(self, skills: list[dict]) -> None:
        os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump(skills, f, indent=2)
        log_skills.info("Cached %d skills to %s", len(skills), self._cache_path)

    def match(self, ocr_text: str, threshold: float = 0.80) -> Optional[dict]:
        """Find the best matching skill for the given OCR text.

        Returns the skill dict if similarity >= threshold, else None.
        """
        ocr_lower = ocr_text.strip().lower()

        # Exact match first
        if ocr_lower in self._name_to_skill:
            return self._name_to_skill[ocr_lower]

        # Fuzzy match
        best_match = None
        best_ratio = 0.0
        yielder = GilYielder()
        for skill in self._skills:
            ratio = SequenceMatcher(None, ocr_lower, skill["name"].lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = skill
            yielder.yield_if_needed()

        if best_ratio >= threshold:
            return best_match
        return None

    def get_all_skills(self) -> list[dict]:
        return list(self._skills)

    def get_skills_by_category(self, category: str) -> list[dict]:
        return [s for s in self._skills if s["category"] == category]

    def get_categories(self) -> list[str]:
        seen = set()
        categories = []
        for s in self._skills:
            cat = s["category"]
            if cat not in seen:
                seen.add(cat)
                categories.append(cat)
        return categories

    def get_visible_skills(self) -> list[dict]:
        return [s for s in self._skills if not s.get("hidden", False)]


class RankVerifier:
    """Cross-verifies OCR'd rank + points using Skill Ranks thresholds.

    Fetches rank thresholds from api.entropianexus.com/enumerations/Skill%20Ranks
    and caches locally. Each rank has a minimum skill point threshold; the rank
    bar shows progress between the current rank threshold and the next.
    """

    def __init__(self, cache_path: str = None):
        if cache_path is None:
            cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "skill_ranks.json")
        self._cache_path = cache_path
        self._ranks = self._load_ranks()  # sorted by threshold ascending
        self._name_to_threshold = {r["name"].lower(): r["threshold"] for r in self._ranks}
        self._rank_names = [r["name"] for r in self._ranks]

    def _load_ranks(self) -> list[dict]:
        """Load rank thresholds from API (with local cache fallback)."""
        if self._cache_is_stale():
            api_ranks = self._fetch_from_api()
            if api_ranks:
                self._write_cache(api_ranks)
                return api_ranks

        if os.path.exists(self._cache_path):
            log_ranks.info("Using cached ranks from %s", self._cache_path)
            return self._read_cache()

        log_ranks.warning("No rank data available — cross-verification disabled")
        return []

    def _cache_is_stale(self) -> bool:
        if not os.path.exists(self._cache_path):
            return True
        age = time.time() - os.path.getmtime(self._cache_path)
        return age > CACHE_MAX_AGE_SECONDS

    def _fetch_from_api(self) -> list[dict] | None:
        try:
            log_ranks.info("Fetching ranks from %s", RANKS_API_URL)
            req = urllib.request.Request(RANKS_API_URL, headers={
                "Accept": "application/json",
                "User-Agent": "NexusClient/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            log_ranks.warning("API fetch failed: %s", e)
            return None

        rows = raw.get("Table", {}).get("Rows", [])
        ranks = [{"name": r["Name"], "threshold": int(r["Skill"])} for r in rows]
        ranks.sort(key=lambda r: r["threshold"])
        log_ranks.info("Fetched %d rank thresholds from API", len(ranks))
        return ranks

    def _read_cache(self) -> list[dict]:
        with open(self._cache_path, "r") as f:
            return json.load(f)

    def _write_cache(self, ranks: list[dict]) -> None:
        os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump(ranks, f, indent=2)
        log_ranks.info("Cached %d ranks to %s", len(ranks), self._cache_path)

    def expected_rank(self, points: float) -> Optional[str]:
        """Return the expected rank name for a given skill point total."""
        if not self._ranks:
            return None
        result = self._ranks[0]["name"]
        for rank in self._ranks:
            if points >= rank["threshold"]:
                result = rank["name"]
            else:
                break
        return result

    def match_rank(self, ocr_text: str, threshold: float = 0.75) -> Optional[str]:
        """Fuzzy-match OCR'd text against known rank names.

        Returns the best matching rank name if similarity >= threshold, else None.
        """
        if not self._rank_names or not ocr_text.strip():
            return None

        ocr_lower = ocr_text.strip().lower()

        # Exact match first
        if ocr_lower in self._name_to_threshold:
            return next(r for r in self._rank_names if r.lower() == ocr_lower)

        # Fuzzy match
        best_name = None
        best_ratio = 0.0
        yielder = GilYielder()
        for name in self._rank_names:
            ratio = SequenceMatcher(None, ocr_lower, name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_name = name
            yielder.yield_if_needed()

        if best_ratio >= threshold:
            log_ranks.debug("Rank OCR '%s' matched to '%s' (%.2f)", ocr_text, best_name, best_ratio)
            return best_name
        log_ranks.debug("Rank OCR '%s' no match (best: '%s' at %.2f)", ocr_text, best_name, best_ratio)
        return None

    def verify(self, ocr_rank: str, ocr_points: float, rank_bar_pct: float) -> dict:
        """Cross-verify OCR readings against rank thresholds.

        Returns dict with:
            rank_matches: whether OCR'd rank matches expected rank for the points
            expected_rank: what rank should be based on points
            expected_bar_pct: expected rank bar fill percentage
            bar_diff: difference between expected and actual bar percentage
        """
        if not self._ranks:
            return {"rank_matches": True, "expected_rank": "?",
                    "expected_bar_pct": 0.0, "bar_diff": 0.0}

        expected = self.expected_rank(ocr_points)
        rank_matches = (ocr_rank.lower().strip() == expected.lower()
                        if expected else False)

        # Calculate expected rank bar progress
        expected_bar = 0.0
        for i, rank in enumerate(self._ranks):
            if ocr_points >= rank["threshold"]:
                current_threshold = rank["threshold"]
                next_threshold = (self._ranks[i + 1]["threshold"]
                                  if i + 1 < len(self._ranks)
                                  else current_threshold)
                if next_threshold > current_threshold:
                    expected_bar = ((ocr_points - current_threshold)
                                    / (next_threshold - current_threshold) * 100.0)
                elif ocr_points >= current_threshold:
                    expected_bar = 100.0  # Max rank reached

        bar_diff = abs(rank_bar_pct - expected_bar)

        return {
            "rank_matches": rank_matches,
            "expected_rank": expected or "?",
            "expected_bar_pct": round(expected_bar, 2),
            "bar_diff": round(bar_diff, 2),
        }

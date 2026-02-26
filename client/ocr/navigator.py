from typing import Optional

# The 13 skill categories in the order they appear in the sidebar
SKILL_CATEGORIES = [
    "Attributes",
    "Design",
    "Combat",
    "Construction",
    "Defense",
    "General",
    "Information",
    "Medical",
    "Mining",
    "Science",
    "Mindforce",
    "Beauty",
    "Social",
]


class SkillsNavigator:
    """Parses pagination text from OCR. Navigation is manual (user clicks)."""

    def parse_pagination_text(self, text: str) -> Optional[tuple[int, int]]:
        """Parse pagination text like '1/3' into (current_page, total_pages).

        Returns None if parsing fails.
        """
        text = text.strip()
        if "/" in text:
            parts = text.split("/")
            try:
                return (int(parts[0].strip()), int(parts[1].strip()))
            except (ValueError, IndexError):
                pass
        return None

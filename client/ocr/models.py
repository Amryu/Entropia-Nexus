from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillReading:
    """A single skill as read from the game UI."""
    skill_name: str
    rank: str
    current_points: float
    progress_percent: float  # 0.00-100.00, up to 2 decimal precision
    category: str
    scan_timestamp: datetime


@dataclass
class SkillScanResult:
    """Complete result of a full skills scan."""
    skills: list[SkillReading] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    scan_start: datetime = None
    scan_end: datetime = None
    total_expected: int = 0
    total_found: int = 0


@dataclass
class ScanProgress:
    """Progress state for the overlay."""
    total_skills_expected: int
    skills_found: int
    current_category: str
    current_page: int
    total_pages: int
    missing_names: list[str] = field(default_factory=list)

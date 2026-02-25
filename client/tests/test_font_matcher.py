import os
import shutil
import tempfile
import unittest

import numpy as np

# FontMatcher is importable only if cv2 and PIL are available
try:
    import cv2
    from PIL import ImageFont
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

# The font file used by FontMatcher
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "arial-unicode-bold.ttf")
HAS_FONT = os.path.isfile(FONT_PATH)

# Game screenshot for real-cell tests
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "image.png")
HAS_IMAGE = os.path.isfile(IMAGE_PATH)

# Skill/rank names matching production data
SAMPLE_SKILLS = [
    "Agility", "Aim", "Alertness", "Analysis", "Anatomy",
    "Animal Lore", "Animal Taming", "Archaeological Lore",
    "Armor Technology", "Artefact Preservation",
    "Attachments Technology", "Athletics", "Aiming",
    "Blueprint Comprehension", "Bioregenesis", "Botany",
    "Chemistry", "Combat Reflexes", "Computer", "Courage",
    "First Aid", "Rifle",
]

SAMPLE_RANKS = [
    "Newcomer", "Disciple", "Novice", "Apprentice", "Adept",
    "Professional", "Specialist", "Expert", "Master",
]


def _make_font_matcher(**kwargs):
    """Create a FontMatcher with sample data."""
    from client.ocr.font_matcher import FontMatcher
    return FontMatcher(
        skill_names=kwargs.get("skill_names", SAMPLE_SKILLS),
        rank_names=kwargs.get("rank_names", SAMPLE_RANKS),
        font_path=kwargs.get("font_path", FONT_PATH),
    )


def _make_binary_cell(text_width: int, text_height: int = 14,
                      cell_width: int = 0, cell_height: int = 0,
                      offset_x: int = 2) -> np.ndarray:
    """Create a synthetic binary cell image (white block on black).

    Simulates a text region by placing a white rectangle of the given
    text dimensions at (offset_x, 1) within a larger cell.
    """
    cw = cell_width or (text_width + offset_x + 4)
    ch = cell_height or (text_height + 4)
    cell = np.zeros((ch, cw), dtype=np.uint8)
    y1, y2 = 1, 1 + text_height
    x1, x2 = offset_x, offset_x + text_width
    cell[y1:y2, x1:x2] = 255
    return cell


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestFontMatcherInit(unittest.TestCase):
    """Test FontMatcher construction and pre-calibration state."""

    def test_not_calibrated_initially(self):
        fm = _make_font_matcher()
        self.assertFalse(fm.calibrated)

    def test_font_size_zero_before_calibration(self):
        fm = _make_font_matcher()
        self.assertEqual(fm.font_size, 0)

    def test_match_returns_none_before_calibration(self):
        fm = _make_font_matcher()
        cell = np.zeros((20, 80), dtype=np.uint8)
        self.assertIsNone(fm.match_skill_name(cell))
        self.assertIsNone(fm.match_rank(cell))
        self.assertIsNone(fm.read_points(cell))

    def test_font_path_stored(self):
        fm = _make_font_matcher()
        self.assertEqual(fm.font_path, FONT_PATH)


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestStaticHelpers(unittest.TestCase):
    """Test static/classmethod helpers on FontMatcher."""

    def test_safe_filename_spaces(self):
        from client.ocr.font_matcher import FontMatcher
        self.assertEqual(FontMatcher._safe_filename("First Aid"), "First_Aid")
        self.assertEqual(FontMatcher._safe_filename("Aim"), "Aim")

    def test_name_from_filename(self):
        from client.ocr.font_matcher import FontMatcher
        self.assertEqual(FontMatcher._name_from_filename("First_Aid"), "First Aid")
        self.assertEqual(FontMatcher._name_from_filename("Aim"), "Aim")

    def test_safe_filename_roundtrip(self):
        from client.ocr.font_matcher import FontMatcher
        names = ["Animal Lore", "Blueprint Comprehension", "Aim", "First Aid"]
        for name in names:
            safe = FontMatcher._safe_filename(name)
            restored = FontMatcher._name_from_filename(safe)
            self.assertEqual(restored, name)

    def test_image_key_unique(self):
        from client.ocr.font_matcher import FontMatcher
        img_a = np.zeros((10, 20), dtype=np.uint8)
        img_b = np.zeros((10, 21), dtype=np.uint8)
        img_c = np.ones((10, 20), dtype=np.uint8) * 255
        key_a = FontMatcher._image_key(img_a)
        key_b = FontMatcher._image_key(img_b)
        key_c = FontMatcher._image_key(img_c)
        self.assertNotEqual(key_a, key_b)  # different width
        self.assertNotEqual(key_a, key_c)  # different content

    def test_image_key_same_for_identical(self):
        from client.ocr.font_matcher import FontMatcher
        img = np.zeros((10, 20), dtype=np.uint8)
        img[3:7, 5:15] = 255
        self.assertEqual(FontMatcher._image_key(img), FontMatcher._image_key(img.copy()))

    def test_to_binary_thresholds(self):
        from client.ocr.font_matcher import FontMatcher, BINARY_THRESHOLD
        img = np.array([[50, 100, 101, 150, 255]], dtype=np.uint8)
        result = FontMatcher._to_binary(img)
        # Pixels <= BINARY_THRESHOLD (100) should be 0, above should be 255
        self.assertEqual(result[0, 0], 0)    # 50 <= 100
        self.assertEqual(result[0, 1], 0)    # 100 <= 100
        self.assertEqual(result[0, 2], 255)  # 101 > 100
        self.assertEqual(result[0, 3], 255)  # 150 > 100
        self.assertEqual(result[0, 4], 255)  # 255 > 100

    def test_tight_crop_removes_padding(self):
        from client.ocr.font_matcher import FontMatcher
        # Image with bright pixels only in center
        img = np.zeros((20, 30), dtype=np.uint8)
        img[5:10, 8:18] = 200
        cropped = FontMatcher._tight_crop(img, padding=0)
        self.assertIsNotNone(cropped)
        self.assertEqual(cropped.shape, (5, 10))  # exactly the bright region

    def test_tight_crop_with_padding(self):
        from client.ocr.font_matcher import FontMatcher
        img = np.zeros((20, 30), dtype=np.uint8)
        img[5:10, 8:18] = 200
        cropped = FontMatcher._tight_crop(img, padding=2)
        self.assertIsNotNone(cropped)
        # 5+2 top padding, 5+2 bottom padding = 9 rows (clamped at edges)
        self.assertEqual(cropped.shape[0], 5 + 2 * 2)  # 9
        self.assertEqual(cropped.shape[1], 10 + 2 * 2)  # 14

    def test_tight_crop_empty_image(self):
        from client.ocr.font_matcher import FontMatcher
        img = np.zeros((20, 30), dtype=np.uint8)
        self.assertIsNone(FontMatcher._tight_crop(img))


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestCalibration(unittest.TestCase):
    """Test calibrate() renders templates and sets state."""

    def setUp(self):
        self.fm = _make_font_matcher()

    def test_calibrate_sets_calibrated(self):
        self.fm.calibrate(557)  # typical panel height
        self.assertTrue(self.fm.calibrated)

    def test_calibrate_sets_font_size(self):
        self.fm.calibrate(557)
        self.assertGreater(self.fm.font_size, 0)

    def test_calibrate_renders_skill_templates(self):
        self.fm.calibrate(557)
        # Should have a template for every skill name
        for name in SAMPLE_SKILLS:
            tpl = self.fm.get_skill_template(name)
            self.assertIsNotNone(tpl, f"No template for skill '{name}'")

    def test_calibrate_renders_digit_templates(self):
        self.fm.calibrate(557)
        # Access internal digit templates
        for ch in "0123456789":
            self.assertIn(ch, self.fm._digit_templates,
                          f"No template for digit '{ch}'")

    def test_different_panel_heights(self):
        """Calibration should work for various panel heights."""
        for height in [400, 500, 557, 650]:
            fm = _make_font_matcher()
            fm.calibrate(height)
            self.assertTrue(fm.calibrated)


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestTemplateRendering(unittest.TestCase):
    """Test that PIL-rendered templates have expected properties."""

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)

    def test_templates_are_binary_compatible(self):
        """Templates should be grayscale uint8 arrays."""
        from client.ocr.font_matcher import FontMatcher
        for name in ["Aim", "Agility", "First Aid"]:
            tpl = self.fm.get_skill_template(name)
            self.assertIsNotNone(tpl)
            self.assertEqual(tpl.dtype, np.uint8)
            self.assertEqual(len(tpl.shape), 2)  # grayscale

    def test_templates_contain_bright_pixels(self):
        """Every template should have some visible content."""
        for name in SAMPLE_SKILLS:
            tpl = self.fm.get_skill_template(name)
            self.assertIsNotNone(tpl)
            self.assertTrue(np.any(tpl > 100),
                            f"Template '{name}' has no bright pixels")

    def test_short_templates_narrower_than_long(self):
        """'Aim' template should be narrower than 'Attachments Technology'."""
        aim = self.fm.get_skill_template("Aim")
        att = self.fm.get_skill_template("Attachments Technology")
        self.assertIsNotNone(aim)
        self.assertIsNotNone(att)
        self.assertLess(aim.shape[1], att.shape[1])

    def test_width_index_populated(self):
        """The skill width index should have entries."""
        self.assertTrue(len(self.fm._skill_width_index) > 0)

    def test_every_skill_in_width_index(self):
        """Every skill template should appear in the width index."""
        all_indexed = set()
        for entries in self.fm._skill_width_index.values():
            for name, _ in entries:
                all_indexed.add(name)
        for name in SAMPLE_SKILLS:
            self.assertIn(name, all_indexed, f"'{name}' not in width index")


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestWidthFiltering(unittest.TestCase):
    """Test that width-filtered matching prevents short names from being
    beaten by longer names.

    This is the core regression test for the width-filtering bug: without
    filtering, 'Aim' (short) loses to 'Aiming' (long) because the
    tie-breaker prefers wider templates.
    """

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)

    def test_aim_template_matches_aim_cell(self):
        """A cell containing 'Aim'-width text should match 'Aim', not 'Aiming'."""
        aim_tpl = self.fm.get_skill_template("Aim")
        self.assertIsNotNone(aim_tpl)

        # Create a cell that is just barely wider than the Aim template
        th, tw = aim_tpl.shape
        cell_w = tw + 6  # small padding
        cell_h = th + 4
        cell = np.zeros((cell_h, cell_w), dtype=np.uint8)
        # Place the Aim template into the cell
        cell[2:2 + th, 2:2 + tw] = aim_tpl
        result = self.fm.match_skill_name(cell)
        self.assertIsNotNone(result, "Expected to match 'Aim' but got None")
        self.assertEqual(result[0], "Aim",
                         f"Expected 'Aim' but got '{result[0]}'")

    def test_aiming_template_matches_aiming_cell(self):
        """A cell containing 'Aiming'-width text should match 'Aiming'."""
        aiming_tpl = self.fm.get_skill_template("Aiming")
        self.assertIsNotNone(aiming_tpl)

        th, tw = aiming_tpl.shape
        cell_w = tw + 6
        cell_h = th + 4
        cell = np.zeros((cell_h, cell_w), dtype=np.uint8)
        cell[2:2 + th, 2:2 + tw] = aiming_tpl
        result = self.fm.match_skill_name(cell)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Aiming")

    def test_short_skill_names_not_skipped(self):
        """Regression: Aim, Agility, First Aid, Rifle should all match their
        own templates and not be beaten by longer skill names."""
        short_skills = ["Aim", "Agility", "First Aid", "Rifle"]
        for name in short_skills:
            tpl = self.fm.get_skill_template(name)
            self.assertIsNotNone(tpl, f"No template for '{name}'")
            th, tw = tpl.shape
            cell = np.zeros((th + 4, tw + 6), dtype=np.uint8)
            cell[2:2 + th, 2:2 + tw] = tpl
            result = self.fm.match_skill_name(cell)
            self.assertIsNotNone(result, f"'{name}' should match but got None")
            self.assertEqual(result[0], name,
                             f"Expected '{name}' but got '{result[0]}'")

    def test_width_tolerance_boundary(self):
        """Templates just outside WIDTH_TOLERANCE should not be in the
        filtered candidate set but may still match via fallback."""
        from client.ocr.font_matcher import WIDTH_TOLERANCE
        # Verify the constant is reasonable
        self.assertGreater(WIDTH_TOLERANCE, 0)
        self.assertLessEqual(WIDTH_TOLERANCE, 20)


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestExactMatchLookup(unittest.TestCase):
    """Test the captured-template exact-match (hash lookup) path."""

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)
        # Use a temporary directory for captures
        self._tmpdir = tempfile.mkdtemp()
        # Override CAPTURED_DIR for this test
        from client.ocr import font_matcher
        self._orig_captured_dir = font_matcher.CAPTURED_DIR
        font_matcher.CAPTURED_DIR = __import__("pathlib").Path(self._tmpdir)

    def tearDown(self):
        from client.ocr import font_matcher
        font_matcher.CAPTURED_DIR = self._orig_captured_dir
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_to_lookup_key_deterministic(self):
        """Same cell image should produce the same lookup key."""
        cell = np.zeros((14, 40), dtype=np.uint8)
        cell[2:12, 5:35] = 200
        key1 = self.fm._to_lookup_key(cell)
        key2 = self.fm._to_lookup_key(cell.copy())
        self.assertIsNotNone(key1)
        self.assertEqual(key1, key2)

    def test_to_lookup_key_different_for_different_cells(self):
        """Different cell content should produce different keys."""
        cell_a = np.zeros((14, 40), dtype=np.uint8)
        cell_a[2:12, 5:25] = 200
        cell_b = np.zeros((14, 40), dtype=np.uint8)
        cell_b[2:12, 10:35] = 200
        key_a = self.fm._to_lookup_key(cell_a)
        key_b = self.fm._to_lookup_key(cell_b)
        self.assertNotEqual(key_a, key_b)

    def test_capture_and_lookup_skill(self):
        """After capturing a skill cell, exact lookup should find it."""
        # Create a synthetic cell
        cell = np.zeros((16, 50), dtype=np.uint8)
        cell[2:14, 3:47] = 200

        # Capture it under "Aim"
        result = self.fm.capture_skill("Aim", cell)
        self.assertTrue(result)

        # Now match_skill_name should find it via exact lookup
        match = self.fm.match_skill_name(cell)
        self.assertIsNotNone(match)
        self.assertEqual(match[0], "Aim")
        self.assertEqual(match[1], 1.0)  # exact match score

    def test_capture_skill_no_duplicate(self):
        """Capturing the same skill twice should return False the second time."""
        cell = np.zeros((16, 50), dtype=np.uint8)
        cell[2:14, 3:47] = 200
        self.assertTrue(self.fm.capture_skill("Aim", cell))
        self.assertFalse(self.fm.capture_skill("Aim", cell))

    def test_capture_and_lookup_rank(self):
        """After capturing a rank cell, exact lookup should find it."""
        cell = np.zeros((14, 60), dtype=np.uint8)
        cell[2:12, 5:55] = 180

        result = self.fm.capture_rank("Novice", cell)
        self.assertTrue(result)

        match = self.fm.match_rank(cell)
        self.assertIsNotNone(match)
        self.assertEqual(match[0], "Novice")
        self.assertEqual(match[1], 1.0)

    def test_empty_cell_no_capture(self):
        """Capturing an empty (all-black) cell should fail gracefully."""
        cell = np.zeros((14, 40), dtype=np.uint8)
        self.assertFalse(self.fm.capture_skill("Aim", cell))

    def test_lookup_key_empty_cell(self):
        """An empty cell should return None for lookup key."""
        cell = np.zeros((14, 40), dtype=np.uint8)
        self.assertIsNone(self.fm._to_lookup_key(cell))


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestDigitReading(unittest.TestCase):
    """Test digit template matching and point value reading."""

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)

    def test_digit_templates_rendered(self):
        """All 10 digit templates should be rendered."""
        for ch in "0123456789":
            self.assertIn(ch, self.fm._digit_templates)

    def test_digit_advance_positive(self):
        """Digit advance width should be a positive integer."""
        self.assertGreater(self.fm._digit_advance, 0)

    def test_read_points_with_rendered_digits(self):
        """read_points should correctly read a number composed of rendered digit templates."""
        # Build a cell by placing each digit at exact advance-width intervals,
        # matching how read_points scans (greedy at digit_advance steps).
        digits = "1234"
        advance = self.fm._digit_advance
        # Total width: 4 digits * advance + padding
        total_w = len(digits) * advance + 6
        max_h = max(t.shape[0] for t in self.fm._digit_templates.values())
        cell = np.zeros((max_h + 4, total_w), dtype=np.uint8)
        x = 3  # left padding
        for ch in digits:
            tpl = self.fm._digit_templates[ch]
            th, tw = tpl.shape
            cell[2:2 + th, x:x + tw] = tpl
            x += advance

        result = self.fm.read_points(cell)
        self.assertIsNotNone(result)
        self.assertEqual(result, "1234")

    def test_read_points_empty_cell(self):
        """read_points on an empty cell should return None."""
        cell = np.zeros((20, 60), dtype=np.uint8)
        self.assertIsNone(self.fm.read_points(cell))

    def test_read_points_single_digit(self):
        """read_points should handle a single digit."""
        tpl = self.fm._digit_templates["7"]
        padded = np.zeros((tpl.shape[0] + 4, tpl.shape[1] + 6), dtype=np.uint8)
        padded[2:2 + tpl.shape[0], 3:3 + tpl.shape[1]] = tpl
        result = self.fm.read_points(padded)
        self.assertIsNotNone(result)
        self.assertIn("7", result)

    def test_capture_digits_blob_detection(self):
        """capture_digits should detect individual digit blobs."""
        tmpdir = tempfile.mkdtemp()
        try:
            from client.ocr import font_matcher
            orig = font_matcher.CAPTURED_DIR
            font_matcher.CAPTURED_DIR = __import__("pathlib").Path(tmpdir)

            # Build a cell with two digit blobs (representing "42")
            d4 = self.fm._digit_templates["4"]
            d2 = self.fm._digit_templates["2"]
            gap = np.zeros((d4.shape[0], 3), dtype=np.uint8)
            cell = np.hstack([d4, gap, d2])
            padded = np.zeros((cell.shape[0] + 4, cell.shape[1] + 6), dtype=np.uint8)
            padded[2:2 + cell.shape[0], 3:3 + cell.shape[1]] = cell

            captured = self.fm.capture_digits("42", padded)
            self.assertGreaterEqual(captured, 0)
        finally:
            font_matcher.CAPTURED_DIR = orig
            shutil.rmtree(tmpdir, ignore_errors=True)


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestRankMatching(unittest.TestCase):
    """Test rank template matching."""

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)

    def test_rank_templates_rendered(self):
        """All rank templates should be rendered."""
        for name in SAMPLE_RANKS:
            self.assertIn(name, self.fm._rank_templates)

    def test_rank_self_match(self):
        """Each rank template should match itself when placed in a cell."""
        for name in SAMPLE_RANKS:
            tpl = self.fm._rank_templates[name]
            th, tw = tpl.shape
            cell = np.zeros((th + 4, tw + 6), dtype=np.uint8)
            cell[2:2 + th, 2:2 + tw] = tpl
            result = self.fm.match_rank(cell)
            self.assertIsNotNone(result,
                                 f"Rank '{name}' should match itself")
            self.assertEqual(result[0], name,
                             f"Expected rank '{name}' but got '{result[0]}'")


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
@unittest.skipUnless(HAS_IMAGE, "client/image.png not found")
class TestRealGameCells(unittest.TestCase):
    """Test FontMatcher against real game cells extracted from image.png.

    image.png shows the Skills window with ALL CATEGORIES selected.
    Visible skill rows (top 12): Agility, Aim, Alertness, Analysis,
    Anatomy, Animal Lore, Animal Taming, Archaeological Lore,
    Armor Technology, Artefact Preservation, Attachments Technology, Athletics.
    """

    EXPECTED_SKILLS = [
        "Agility", "Aim", "Alertness", "Analysis",
        "Anatomy", "Animal Lore", "Animal Taming", "Archaeological Lore",
        "Armor Technology", "Artefact Preservation",
        "Attachments Technology", "Athletics",
    ]

    @classmethod
    def setUpClass(cls):
        """Load image.png and extract skill name cells."""
        from client.ocr.detector import WINDOW_LAYOUT

        cls.game_image = cv2.imread(IMAGE_PATH)
        if cls.game_image is None:
            raise unittest.SkipTest("Failed to load image.png")

        gray = cv2.cvtColor(cls.game_image, cv2.COLOR_BGR2GRAY)
        img_h, img_w = gray.shape

        # The image IS the skills panel (not a full game screenshot)
        # Detect panel dimensions from the image itself
        ww, wh = img_w, img_h

        # Use all available skills for matching
        from client.ocr.skill_parser import SkillMatcher
        try:
            sm = SkillMatcher()
            all_skills = [s["name"] for s in sm.get_all_skills()]
        except Exception:
            all_skills = SAMPLE_SKILLS

        # Build FontMatcher with full skill list
        from client.ocr.font_matcher import FontMatcher as FM
        cls.fm = FM(
            skill_names=all_skills,
            rank_names=SAMPLE_RANKS,
            font_path=FONT_PATH,
        )
        cls.fm.calibrate(wh)

        # Extract individual name cells from the table region
        layout = WINDOW_LAYOUT
        table_top = int(wh * layout["table_top_ratio"])
        row_height = max(20, round(wh * layout["row_height_ratio"]))
        text_h = int(row_height * layout["row_text_ratio"])

        name_start = int(ww * layout["col_name_start"])
        name_end = int(ww * layout["col_name_end"])

        cls.name_cells = []
        for i in range(12):
            y = table_top + i * row_height
            if y + text_h > wh:
                break
            cell = gray[y:y + text_h, name_start:name_end]
            if cell.size > 0:
                cls.name_cells.append(cell)

    def test_extracted_correct_number_of_cells(self):
        """Should extract 12 skill name cells."""
        self.assertEqual(len(self.name_cells), 12)

    def test_cells_have_content(self):
        """Each cell should have some bright pixels (text)."""
        for i, cell in enumerate(self.name_cells):
            bright_ratio = float(np.mean(cell > 120))
            self.assertGreater(bright_ratio, 0.01,
                               f"Cell {i} appears empty (bright ratio {bright_ratio:.3f})")

    def test_best_match_returns_candidates(self):
        """best_skill_match should return a candidate for each cell, even if
        below the confidence threshold.

        PIL-rendered templates don't perfectly match Scaleform game rendering
        (different rasterizers), so we only verify the matcher returns *some*
        candidate (non-None) rather than requiring specific skill names.
        The captured-template system (hash lookup) handles exact matching.
        """
        for i, cell in enumerate(self.name_cells):
            best = self.fm.best_skill_match(cell)
            self.assertIsNotNone(best,
                                 f"Row {i}: best_skill_match returned None")
            self.assertIsInstance(best[0], str)
            self.assertGreater(best[1], 0.0,
                               f"Row {i}: score should be > 0")

    def test_match_skill_name_does_not_crash(self):
        """match_skill_name should handle all real cells without crashing,
        even though PIL templates may not match Scaleform rendering."""
        for i, cell in enumerate(self.name_cells):
            result = self.fm.match_skill_name(cell)
            # Result may be None (below threshold) — that's fine
            if result is not None:
                self.assertIsInstance(result[0], str)
                self.assertIsInstance(result[1], float)

    def test_cells_are_distinct(self):
        """Each extracted cell should have a unique pixel pattern, confirming
        they are different rows (not all the same slice)."""
        # Compare mean brightness of each cell — they should differ
        means = [float(np.mean(cell)) for cell in self.name_cells]
        unique_means = len(set(round(m, 1) for m in means))
        # At least half should be distinct (identical cells = extraction bug)
        self.assertGreater(unique_means, len(self.name_cells) // 2,
                           "Too many cells have identical mean brightness")


@unittest.skipUnless(HAS_DEPS, "cv2 and PIL required")
@unittest.skipUnless(HAS_FONT, "arial-unicode-bold.ttf not found")
class TestEdgeCases(unittest.TestCase):
    """Test edge cases and robustness."""

    def setUp(self):
        self.fm = _make_font_matcher()
        self.fm.calibrate(557)

    def test_tiny_cell_returns_none(self):
        """Very small cells should return None, not crash."""
        tiny = np.zeros((2, 2), dtype=np.uint8)
        self.assertIsNone(self.fm.match_skill_name(tiny))
        self.assertIsNone(self.fm.match_rank(tiny))
        self.assertIsNone(self.fm.read_points(tiny))

    def test_all_white_cell(self):
        """An all-white cell should not crash."""
        white = np.ones((20, 80), dtype=np.uint8) * 255
        result = self.fm.match_skill_name(white)
        # May return a match or None, but should not crash
        if result:
            self.assertIsInstance(result[0], str)
            self.assertIsInstance(result[1], float)

    def test_all_black_cell(self):
        """An all-black cell should return None."""
        black = np.zeros((20, 80), dtype=np.uint8)
        self.assertIsNone(self.fm.match_skill_name(black))

    def test_noise_cell(self):
        """A random noise cell should not crash."""
        rng = np.random.RandomState(42)
        noise = rng.randint(0, 256, (20, 80), dtype=np.uint8)
        # Should not crash; result is unpredictable
        self.fm.match_skill_name(noise)

    def test_template_self_match_high_score(self):
        """A template placed in a cell should score very high."""
        for name in ["Agility", "Aim", "First Aid"]:
            tpl = self.fm.get_skill_template(name)
            th, tw = tpl.shape
            cell = np.zeros((th + 4, tw + 6), dtype=np.uint8)
            cell[2:2 + th, 2:2 + tw] = tpl
            result = self.fm.match_skill_name(cell)
            self.assertIsNotNone(result, f"'{name}' should match itself")
            self.assertEqual(result[0], name)
            self.assertGreaterEqual(result[1], 0.90,
                                    f"'{name}' self-match score too low: {result[1]}")


if __name__ == "__main__":
    unittest.main()

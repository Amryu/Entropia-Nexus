"""Tests for the CRNN radar coordinate recognizer."""

import unittest

import numpy as np

try:
    import onnxruntime
    HAS_ORT = True
except ImportError:
    HAS_ORT = False


class TestPreprocess(unittest.TestCase):
    """Preprocessing pipeline (no model needed)."""

    def test_output_shape(self):
        from client.ocr.onnxtr_recognizer import _preprocess
        img = np.random.randint(0, 255, (20, 60, 3), dtype=np.uint8)
        self.assertEqual(_preprocess(img).shape, (1, 3, 32, 128))

    def test_tall_image(self):
        from client.ocr.onnxtr_recognizer import _preprocess
        img = np.random.randint(0, 255, (64, 200, 3), dtype=np.uint8)
        self.assertEqual(_preprocess(img).shape, (1, 3, 32, 128))

    def test_wide_image_cropped(self):
        from client.ocr.onnxtr_recognizer import _preprocess
        img = np.random.randint(0, 255, (32, 300, 3), dtype=np.uint8)
        self.assertEqual(_preprocess(img).shape, (1, 3, 32, 128))

    def test_dtype(self):
        from client.ocr.onnxtr_recognizer import _preprocess
        result = _preprocess(np.zeros((32, 128, 3), dtype=np.uint8))
        self.assertEqual(result.dtype, np.float32)

    def test_normalized_finite(self):
        from client.ocr.onnxtr_recognizer import _preprocess
        result = _preprocess(np.full((32, 128, 3), 255, dtype=np.uint8))
        self.assertTrue(np.all(np.isfinite(result)))


class TestCtcDecode(unittest.TestCase):
    """CTC decoding logic (no model needed)."""

    def test_all_blank(self):
        from client.ocr.onnxtr_recognizer import _ctc_decode, BLANK_IDX
        logits = np.zeros((1, 10, BLANK_IDX + 1), dtype=np.float32)
        logits[0, :, BLANK_IDX] = 10.0
        text, conf = _ctc_decode(logits)
        self.assertEqual(text, "")
        self.assertEqual(conf, 0.0)

    def test_single_digit(self):
        from client.ocr.onnxtr_recognizer import _ctc_decode, VOCAB
        idx_5 = VOCAB.index("5")
        logits = np.zeros((1, 5, len(VOCAB) + 1), dtype=np.float32)
        logits[0, :3, len(VOCAB)] = 10.0  # blank
        logits[0, 3:, idx_5] = 10.0       # "5"
        text, conf = _ctc_decode(logits)
        self.assertEqual(text, "5")
        self.assertGreater(conf, 0.9)

    def test_consecutive_dedup(self):
        from client.ocr.onnxtr_recognizer import _ctc_decode, VOCAB
        idx_3 = VOCAB.index("3")
        logits = np.zeros((1, 6, len(VOCAB) + 1), dtype=np.float32)
        logits[0, :, idx_3] = 10.0
        text, conf = _ctc_decode(logits)
        self.assertEqual(text, "3")

    def test_blank_separator_repeats(self):
        from client.ocr.onnxtr_recognizer import _ctc_decode, VOCAB
        idx_3 = VOCAB.index("3")
        blank = len(VOCAB)
        logits = np.zeros((1, 5, len(VOCAB) + 1), dtype=np.float32)
        logits[0, 0, idx_3] = 10.0
        logits[0, 1, idx_3] = 10.0   # dup, collapsed
        logits[0, 2, blank] = 10.0   # separator
        logits[0, 3, idx_3] = 10.0   # new "3"
        logits[0, 4, idx_3] = 10.0   # dup
        text, conf = _ctc_decode(logits)
        self.assertEqual(text, "33")


class TestRecognizeCoordinate(unittest.TestCase):
    """Edge cases for the public API."""

    def test_none_input(self):
        from client.ocr.onnxtr_recognizer import recognize_coordinate
        self.assertIsNone(recognize_coordinate(None))

    def test_empty_input(self):
        from client.ocr.onnxtr_recognizer import recognize_coordinate
        self.assertIsNone(recognize_coordinate(np.array([])))


@unittest.skipUnless(HAS_ORT, "onnxruntime not installed")
class TestModelIntegration(unittest.TestCase):
    """Integration tests that load the model."""

    def test_model_loads(self):
        from client.ocr.onnxtr_recognizer import is_available
        self.assertTrue(is_available())

    def test_vocab_matches_output(self):
        from client.ocr.onnxtr_recognizer import _ensure_session, VOCAB
        session = _ensure_session()
        out_classes = session.get_outputs()[0].shape[-1]
        self.assertEqual(out_classes, len(VOCAB) + 1)

    def test_returns_expected_format(self):
        from client.ocr.onnxtr_recognizer import recognize_coordinate
        img = np.zeros((32, 100, 3), dtype=np.uint8)
        result = recognize_coordinate(img, row="lon")
        if result is not None:
            value, conf = result
            self.assertIsInstance(value, int)
            self.assertIsInstance(conf, float)


if __name__ == "__main__":
    unittest.main()

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


class ImagePreprocessor:
    """Preprocesses captured game UI images for OCR accuracy."""

    def __init__(self):
        if cv2 is None:
            raise ImportError("opencv-python is required. Install with: pip install opencv-python")

    def preprocess_for_ocr(self, image: np.ndarray, scale_factor: float = 2.0) -> np.ndarray:
        """Full preprocessing pipeline for OCR on game UI text.

        Steps: grayscale -> upscale -> threshold -> denoise
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Upscale for better OCR accuracy on small text
        if scale_factor != 1.0:
            h, w = gray.shape
            gray = cv2.resize(gray, (int(w * scale_factor), int(h * scale_factor)),
                              interpolation=cv2.INTER_CUBIC)

        # Adaptive threshold for game UI (dark background, light text)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return binary

    def preprocess_light_text_dark_bg(self, image: np.ndarray, scale_factor: float = 2.0) -> np.ndarray:
        """Optimized for the skills window: light text on dark background."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if scale_factor != 1.0:
            h, w = gray.shape
            gray = cv2.resize(gray, (int(w * scale_factor), int(h * scale_factor)),
                              interpolation=cv2.INTER_CUBIC)

        # Simple threshold: light text on dark background
        _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)

        return binary

    def preprocess_for_template_matching(self, image: np.ndarray) -> np.ndarray:
        """Binary threshold at native resolution for font template matching.

        Same threshold as preprocess_light_text_dark_bg but without the 2x
        upscale — template matching doesn't need it and skipping the resize
        saves time.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) \
            if len(image.shape) == 3 else image
        _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
        return binary

    def extract_rows(self, table_image: np.ndarray, row_height: int,
                      row_pitch: int = 0) -> list[np.ndarray]:
        """Split a table image into individual row strips.

        Args:
            table_image: Cropped table area.
            row_height: Height of each row's content area.
            row_pitch: Distance between consecutive row starts (height + gap).
                       Defaults to row_height if 0.
        """
        if row_pitch <= 0:
            row_pitch = row_height
        h, w = table_image.shape[:2]
        rows = []
        for y in range(0, h - row_height + 1, row_pitch):
            row = table_image[y:y + row_height]
            rows.append(row)
        return rows

    def extract_columns(self, row_image: np.ndarray, col_ranges: list[tuple[int, int]]) -> list[np.ndarray]:
        """Extract column regions from a row image.

        col_ranges: list of (start_x, end_x) pixel ranges
        """
        return [row_image[:, start:end] for start, end in col_ranges]

import numpy as np

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None


_ALPHA_SPACE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "


class OCRRecognizer:
    """Wraps Tesseract OCR for text recognition on preprocessed images."""

    def __init__(self, tesseract_path: str = ""):
        if pytesseract is None:
            raise ImportError("pytesseract is required. Install with: pip install pytesseract")
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        else:
            raise FileNotFoundError(
                "Tesseract not found. Install from https://github.com/UB-Mannheim/tesseract/wiki "
                "and either add it to PATH or set tesseract_path in config.json"
            )

    def read_text(self, image: np.ndarray, config: str = "--psm 7") -> str:
        """Read text from a preprocessed image.

        Args:
            image: Preprocessed binary image (numpy array)
            config: Tesseract config string. PSM 7 = single text line.
        """
        pil_image = Image.fromarray(image)
        text = pytesseract.image_to_string(pil_image, config=config).strip()
        return text

    def read_skill_name(self, image: np.ndarray) -> str:
        """Read a skill name (letters and spaces only, no digits/punctuation)."""
        pil_image = Image.fromarray(image)
        config = f"--psm 7 -c tessedit_char_whitelist={_ALPHA_SPACE}"
        return pytesseract.image_to_string(pil_image, config=config).strip()

    def read_rank(self, image: np.ndarray) -> str:
        """Read a skill rank name (letters and spaces only, no digits/punctuation)."""
        pil_image = Image.fromarray(image)
        config = f"--psm 7 -c tessedit_char_whitelist={_ALPHA_SPACE}"
        return pytesseract.image_to_string(pil_image, config=config).strip()

    def read_number(self, image: np.ndarray) -> str:
        """Read a numeric value from an image (digits and decimal points only)."""
        pil_image = Image.fromarray(image)
        config = "--psm 7 -c tessedit_char_whitelist=0123456789."
        text = pytesseract.image_to_string(pil_image, config=config).strip()
        return text

    def read_with_confidence(self, image: np.ndarray, config: str = "--psm 7") -> list[dict]:
        """Read text with per-word confidence scores.

        Returns list of dicts with 'text' and 'conf' keys.
        """
        pil_image = Image.fromarray(image)
        data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)

        results = []
        for i, word in enumerate(data["text"]):
            if word.strip():
                results.append({
                    "text": word.strip(),
                    "conf": float(data["conf"][i]),
                    "left": data["left"][i],
                    "top": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                })
        return results

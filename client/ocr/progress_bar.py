import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

# Teal/cyan fill color range in HSV (from the game UI)
# These are approximate and may need calibration
FILL_HUE_LOW = 140
FILL_HUE_HIGH = 190
FILL_SAT_LOW = 50
FILL_VAL_LOW = 80


class ProgressBarReader:
    """Reads the fill percentage of skill progress bars from the game UI.

    The progress bar is a horizontal bar with a teal fill color on a dark background.
    Sub-pixel interpolation at the boundary achieves up to 2 decimal precision.
    """

    def __init__(self):
        if cv2 is None:
            raise ImportError("opencv-python is required. Install with: pip install opencv-python")
        self._tracer = None

    def set_tracer(self, tracer) -> None:
        """Set the OcrTracer for detailed trace output."""
        self._tracer = tracer

    def read_progress(self, bar_image: np.ndarray) -> float:
        """Read the fill percentage of a progress bar image.

        Args:
            bar_image: Cropped image of just the progress bar (BGR format).

        Returns:
            Fill percentage 0.00-100.00, rounded to 2 decimals.
        """
        if bar_image is None or bar_image.size == 0:
            return 0.0

        h, w = bar_image.shape[:2]
        if w < 2 or h < 1:
            return 0.0

        hsv = cv2.cvtColor(bar_image, cv2.COLOR_BGR2HSV)

        # Create mask for the filled (teal) region
        mask = self._create_fill_mask(hsv)

        # Average across rows to get a 1D fill profile
        col_fill = np.mean(mask, axis=0) / 255.0  # 0.0 to 1.0 per column

        # Find the fill boundary with sub-pixel precision
        fill_width = self._find_fill_boundary(col_fill)

        # Calculate percentage
        percent = (fill_width / w) * 100.0
        result = round(max(0.0, min(100.0, percent)), 2)

        if self._tracer and self._tracer.enabled:
            self._tracer.log("BAR", f"fill={result:.2f}% boundary={fill_width:.1f}/{w}")

        return result

    def _create_fill_mask(self, hsv: np.ndarray) -> np.ndarray:
        """Create a binary mask of the filled region based on HSV color."""
        h_channel = hsv[:, :, 0]  # Hue (0-180 in OpenCV)
        s_channel = hsv[:, :, 1]  # Saturation (0-255)
        v_channel = hsv[:, :, 2]  # Value (0-255)

        # Map our expected hue range (140-190 degrees) to OpenCV's 0-180 scale
        hue_low = FILL_HUE_LOW // 2
        hue_high = FILL_HUE_HIGH // 2

        mask = (
            (h_channel >= hue_low) & (h_channel <= hue_high) &
            (s_channel >= FILL_SAT_LOW) &
            (v_channel >= FILL_VAL_LOW)
        ).astype(np.uint8) * 255

        return mask

    def _find_fill_boundary(self, col_profile: np.ndarray) -> float:
        """Find the fill boundary with sub-pixel interpolation.

        Args:
            col_profile: 1D array of fill ratios (0.0-1.0) per column.

        Returns:
            Fill width in pixels (can be fractional for sub-pixel precision).
        """
        threshold = 0.3  # Column is "filled" if more than 30% of its pixels match
        n = len(col_profile)

        if n == 0:
            return 0.0

        # If completely filled or completely empty
        if np.all(col_profile >= threshold):
            return float(n)
        if np.all(col_profile < threshold):
            return 0.0

        # Scan from left to find the transition point
        last_filled = -1
        for i in range(n):
            if col_profile[i] >= threshold:
                last_filled = i
            elif last_filled >= 0:
                # Found the boundary: transition from filled to unfilled
                # Sub-pixel interpolation using the fill ratio at boundary
                frac = col_profile[i] / threshold if threshold > 0 else 0
                return last_filled + 1.0 + frac
                break

        if last_filled >= 0:
            # Bar fills to the edge
            return last_filled + 1.0

        return 0.0

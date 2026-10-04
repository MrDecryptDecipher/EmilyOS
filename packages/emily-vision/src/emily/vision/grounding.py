"""GUI Grounding engine for mapping natural language UI queries to screen elements."""

import logging
from typing import Any

from emily.vision.ocr import LocalOCREngine
from emily.vision.types import BoundingBox, OCRResult, ScreenFrame, UIElement

logger = logging.getLogger(__name__)


class GUIGroundingEngine:
    """Detects UI elements and grounds target labels to exact screen coordinates."""

    def __init__(self, ocr_engine: LocalOCREngine | None = None) -> None:
        self.ocr_engine = ocr_engine or LocalOCREngine()

    def analyze_screen(self, image_bytes: bytes, width: int = 1920, height: int = 1080) -> ScreenFrame:
        """Process screenshot and return detected OCR and UI elements."""
        ocr_results = self.ocr_engine.extract_text_from_image(image_bytes)

        elements: list[UIElement] = []
        for idx, res in enumerate(ocr_results):
            el_type = "button" if "click" in res.text.lower() or "submit" in res.text.lower() else "text"
            elements.append(
                UIElement(
                    element_id=f"el_{idx+1}",
                    label=res.text,
                    element_type=el_type,
                    bbox=res.bbox,
                    confidence=res.confidence,
                )
            )

        import uuid
        frame_id = f"frame_{uuid.uuid4().hex[:8]}"
        return ScreenFrame(
            frame_id=frame_id,
            width=width,
            height=height,
            image_bytes=image_bytes,
            ocr_results=ocr_results,
            elements=elements,
        )

    def locate_element_by_label(self, frame: ScreenFrame, query: str) -> UIElement | None:
        """Locate UI element matching natural language query."""
        query_lower = query.lower().strip()
        best_match: UIElement | None = None
        best_score = 0.0

        for el in frame.elements:
            lbl_lower = el.label.lower()
            if query_lower == lbl_lower:
                return el
            if query_lower in lbl_lower:
                score = len(query_lower) / len(lbl_lower)
                if score > best_score:
                    best_score = score
                    best_match = el

        return best_match

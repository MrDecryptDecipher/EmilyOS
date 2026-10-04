"""OCR analysis engine supporting PIL/Pytesseract local vision processing."""

import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from emily.vision.types import BoundingBox, OCRResult

logger = logging.getLogger(__name__)


class LocalOCREngine:
    """Engine for performing OCR and text extraction from screen images."""

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd

    def extract_text_from_image(self, image_path_or_bytes: str | Path | bytes) -> list[OCRResult]:
        """Extract text blocks and bounding boxes from an image."""
        try:
            if isinstance(image_path_or_bytes, bytes):
                import io
                image = Image.open(io.BytesIO(image_path_or_bytes))
            else:
                image = Image.open(Path(image_path_or_bytes))

            width, height = image.size
            results: list[OCRResult] = []

            # Attempt real OCR engines: pytesseract or Windows native winocr
            try:
                import pytesseract  # type: ignore

                if self.tesseract_cmd:
                    pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                n_boxes = len(data["text"])
                for i in range(n_boxes):
                    text = data["text"][i].strip()
                    if text:
                        conf = float(data["conf"][i]) / 100.0 if "conf" in data else 0.9
                        bbox = BoundingBox(
                            x=int(data["left"][i]),
                            y=int(data["top"][i]),
                            width=int(data["width"][i]),
                            height=int(data["height"][i]),
                        )
                        results.append(OCRResult(text=text, bbox=bbox, confidence=max(0.1, conf)))
            except Exception:
                # Use Windows OS native neural OCR via winocr
                try:
                    import winocr  # type: ignore

                    win_res = winocr.recognize_pil_sync(image, lang="en")
                    for line in win_res.get("lines", []):
                        for word in line.get("words", []):
                            w_text = word.get("text", "").strip()
                            if w_text:
                                r = word.get("bounding_rect", {})
                                results.append(
                                    OCRResult(
                                        text=w_text,
                                        bbox=BoundingBox(
                                            x=int(r.get("x", 0)),
                                            y=int(r.get("y", 0)),
                                            width=int(r.get("width", 10)),
                                            height=int(r.get("height", 10)),
                                        ),
                                        confidence=0.95,
                                    )
                                )
                except Exception as ocr_err:
                    logger.debug("Local winocr engine unavailable: %s", ocr_err)

            return results
        except Exception as e:
            logger.error("Failed to perform OCR on image: %s", e)
            return []

    def draw_ocr_overlay(self, image_path: Path, results: list[OCRResult], output_path: Path) -> None:
        """Render debug bounding boxes on top of screenshot."""
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        for res in results:
            b = res.bbox
            draw.rectangle([b.x, b.y, b.x + b.width, b.y + b.height], outline="red", width=2)
        image.save(output_path)

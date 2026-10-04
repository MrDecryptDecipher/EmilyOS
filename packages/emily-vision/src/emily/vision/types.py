"""Core data types for Vision & GUI Grounding."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class UIElement:
    element_id: str
    label: str
    element_type: str  # button, input, link, text, window, header
    bbox: BoundingBox
    confidence: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "label": self.label,
            "element_type": self.element_type,
            "bbox": self.bbox.to_dict(),
            "center": [self.bbox.center_x, self.bbox.center_y],
            "confidence": self.confidence,
            "attributes": self.attributes,
        }


@dataclass
class OCRResult:
    text: str
    bbox: BoundingBox
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
        }


@dataclass
class ScreenFrame:
    frame_id: str
    width: int
    height: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    image_bytes: bytes | None = None
    ocr_results: list[OCRResult] = field(default_factory=list)
    elements: list[UIElement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "width": self.width,
            "height": self.height,
            "timestamp": self.timestamp.isoformat(),
            "ocr_count": len(self.ocr_results),
            "element_count": len(self.elements),
        }

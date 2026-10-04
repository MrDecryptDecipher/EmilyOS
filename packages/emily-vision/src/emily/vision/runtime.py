"""Vision Runtime & Subsystem integration for Emily OS."""

import logging
from typing import Any

from emily.events.bus import InProcessEventBus
from emily.events.envelope import EventEnvelope
from emily.kernel.subsystem import BaseSubsystem
from emily.tools.registry import ToolRegistry
from emily.vision.grounding import GUIGroundingEngine
from emily.vision.ocr import LocalOCREngine
from emily.vision.tools import register_vision_tools
from emily.vision.types import ScreenFrame

logger = logging.getLogger(__name__)


class VisionRuntime:
    """Core runtime executing desktop vision capture, OCR, and GUI grounding."""

    def __init__(self) -> None:
        self.ocr_engine = LocalOCREngine()
        self.grounding_engine = GUIGroundingEngine(self.ocr_engine)
        self._last_frame: ScreenFrame | None = None

    def capture_and_ground(self, image_bytes: bytes | None = None) -> ScreenFrame:
        """Capture or ground a screen frame."""
        if not image_bytes:
            import io
            import sys
            if sys.platform == "win32":
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
                    if h_desk:
                        user32.SetThreadDesktop(h_desk)
                except Exception:
                    pass
            from PIL import ImageGrab
            
            try:
                # Capture actual screen instead of mock
                img = ImageGrab.grab()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
            except Exception as e:
                # A blank image is not a screen capture and makes downstream OCR
                # appear successful while returning fabricated observations.
                raise RuntimeError(f"real screen capture unavailable: {e}") from e

        frame = self.grounding_engine.analyze_screen(image_bytes)
        self._last_frame = frame
        return frame

    @property
    def last_frame(self) -> ScreenFrame | None:
        return self._last_frame


    def capture_webcam(self) -> bytes | None:
        from emily.vision.camera import WebcamCapture
        return WebcamCapture.capture_frame(0)

    def analyze_objects(self, image_bytes: bytes) -> dict:
        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO
            
            # Lazy load model
            if not hasattr(self, '_yolo_model'):
                logger.info("Loading YOLOv8 model for object detection...")
                self._yolo_model = YOLO("yolov8n.pt")
                
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            results = self._yolo_model(img, verbose=False)
            
            detected = []
            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = result.names[cls_id]
                    if conf > 0.3:
                        detected.append({"object": name, "confidence": conf})
            
            return {"objects": detected}
        except Exception as e:
            logger.exception(f"Error in analyze_objects: {e}")
            return {"error": str(e)}

    def analyze_emotions(self, image_bytes: bytes) -> dict:
        try:
            import cv2
            import numpy as np
            import os
            os.environ['TF_USE_LEGACY_KERAS'] = '1'
            from deepface import DeepFace
            
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Use deepface to analyze ONLY emotion (avoids downloading 500MB gender/age models)
            # enforce_detection=False so it doesn't crash if no face is visible
            objs = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False, detector_backend='opencv')
            
            # DeepFace can return a list if multiple faces are found
            if isinstance(objs, list):
                if len(objs) == 0:
                    return {"faces": []}
                # Process the first face for simplicity
                face = objs[0]
            else:
                face = objs
                
            if "face_confidence" in face and face["face_confidence"] < 0.5:
                 return {"faces": [], "note": "No clear face detected."}
                 
            return {
                "faces": [{
                    "dominant_emotion": face.get("dominant_emotion"),
                    "emotion_scores": face.get("emotion")
                }]
            }
        except Exception as e:
            logger.exception(f"Error in analyze_emotions: {e}")
            return {"error": str(e)}
class VisionSubsystem(BaseSubsystem):
    """Emily Kernel Subsystem for Vision & GUI Grounding capabilities."""

    name: str = "vision"

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__()
        self.tool_registry = tool_registry
        self.runtime = VisionRuntime()

    async def on_start(self, ctx: Any) -> None:
        logger.info("Starting VisionSubsystem")
        registry = self.tool_registry or getattr(ctx, "tool_registry", None)
        if registry:
            register_vision_tools(registry, self.runtime)

    async def on_stop(self, ctx: Any) -> None:
        logger.info("Stopping VisionSubsystem")

import cv2
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class WebcamCapture:
    """Simple hardware abstraction for pulling a frame from a webcam."""
    
    @staticmethod
    def capture_frame(device_id: int = 0) -> Optional[bytes]:
        """
        Connects to the webcam, captures a single frame, releases the camera, 
        and returns the frame as a PNG byte buffer.
        """
        try:
            import sys
            api_pref = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
            cap = cv2.VideoCapture(device_id, api_pref)
            if not cap.isOpened():
                logger.error(f'Could not open webcam {device_id}')
                return None
                
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error('Failed to capture frame from webcam')
                return None
                
            ret, buffer = cv2.imencode('.png', frame)
            if not ret:
                logger.error('Failed to encode frame')
                return None
                
            return buffer.tobytes()
            
        except Exception as e:
            logger.exception(f'Error capturing webcam frame: {e}')
            return None

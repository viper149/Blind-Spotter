"""Computer Vision Detection Engine for Blind-Spotter.
Samples silent webcam frames at 1-2 FPS, detects faces via OpenCV DNN SSD
with automatic Haar Cascade fallback, and identifies onlookers behind the user.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from src.config import AppConfig, ConfigManager
from src.notifier import Notifier, default_notifier
from src.paths import get_resource_path

logger = logging.getLogger("blind_spotter.detector")


class OnlookerDetector:
    """Background webcam observer and shoulder-surfing detector."""

    def __init__(
        self,
        config_mgr: ConfigManager,
        notifier: Optional[Notifier] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_alert: Optional[Callable[[], None]] = None,
    ) -> None:
        self.config_mgr = config_mgr
        self.notifier = notifier or default_notifier
        self.on_status_change = on_status_change
        self.on_alert = on_alert

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

        self._dnn_net: Optional[cv2.dnn.Net] = None
        self._haar_cascade: Optional[cv2.CascadeClassifier] = None
        self._backend_name = "Unknown"

        self._last_alert_time: float = 0.0
        self._consecutive_onlooker_count: int = 0
        self._latest_face_count: int = 0

        self._init_face_detectors()

    @property
    def config(self) -> AppConfig:
        return self.config_mgr.config

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def latest_face_count(self) -> int:
        return self._latest_face_count

    def _init_face_detectors(self) -> None:
        """Initialize OpenCV DNN SSD detector or fallback to Haar Cascade.
        Resolves model weights dynamically using get_resource_path() for
        compatibility with both developer checkout and frozen PyInstaller bundles.
        """
        proto_path = get_resource_path("models/deploy.prototxt")
        caffe_path = get_resource_path("models/res10_300x300_ssd_iter_140000_fp16.caffemodel")

        if proto_path.exists() and caffe_path.exists():
            try:
                self._dnn_net = cv2.dnn.readNetFromCaffe(str(proto_path), str(caffe_path))
                self._backend_name = "OpenCV DNN (SSD ResNet-10)"
                logger.info("Loaded primary face detector: %s", self._backend_name)
                return
            except Exception as e:
                logger.warning("Failed to load DNN model (%s). Falling back to Haar Cascade.", e)

        # Fallback to Haar Cascade
        try:
            haar_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar_cascade = cv2.CascadeClassifier(haar_path)
            self._backend_name = "Haar Cascade (OpenCV Default)"
            logger.info("Loaded fallback face detector: %s", self._backend_name)
        except Exception as e:
            logger.error("Failed to load Haar Cascade: %s", e)
            self._backend_name = "None"

    def _detect_faces_dnn(self, frame: np.ndarray, conf_threshold: float) -> List[Tuple[int, int, int, int]]:
        """Detect faces using OpenCV DNN SSD."""
        if self._dnn_net is None:
            return []

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1.0,
            size=(300, 300),
            mean=(104.0, 177.0, 123.0),
            swapRB=False,
            crop=False,
        )
        self._dnn_net.setInput(blob)
        detections = self._dnn_net.forward()

        boxes = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence >= conf_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")
                # Filter negative or degenerate boxes
                if x2 > x1 and y2 > y1:
                    boxes.append((x1, y1, x2 - x1, y2 - y1))
        return boxes

    def _detect_faces_haar(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces using OpenCV Haar Cascade."""
        if self._haar_cascade is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def _detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect bounding boxes for all faces in frame."""
        conf = self.config.confidence_threshold
        if self._dnn_net is not None:
            return self._detect_faces_dnn(frame, conf)
        elif self._haar_cascade is not None:
            return self._detect_faces_haar(frame)
        return []

    def start(self) -> None:
        """Start the background detector thread."""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._detection_loop, daemon=True, name="DetectorThread")
        self._thread.start()
        logger.info("Detector thread started.")
        if self.on_status_change:
            self.on_status_change("Active")

    def stop(self) -> None:
        """Stop detection thread cleanly."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Detector thread stopped.")
        if self.on_status_change:
            self.on_status_change("Stopped")

    def pause(self) -> None:
        """Pause webcam capture."""
        self._paused = True
        logger.info("Detection paused.")
        if self.on_status_change:
            self.on_status_change("Paused")

    def resume(self) -> None:
        """Resume webcam capture."""
        self._paused = False
        logger.info("Detection resumed.")
        if self.on_status_change:
            self.on_status_change("Active")

    def toggle_pause(self) -> bool:
        """Toggle pause state. Returns new paused boolean."""
        if self._paused:
            self.resume()
        else:
            self.pause()
        return self._paused

    def _detection_loop(self) -> None:
        """Continuous low-latency sampling loop with resilient camera auto-reconnect and crash guards."""
        cap: Optional[cv2.VideoCapture] = None
        current_camera_idx: Optional[int] = None
        consecutive_read_failures: int = 0

        while self._running:
            try:
                if self._paused:
                    if cap is not None:
                        cap.release()
                        cap = None
                        current_camera_idx = None
                        consecutive_read_failures = 0
                    time.sleep(0.5)
                    continue

                target_camera_idx = self.config.camera_index

                # If camera index changed dynamically from settings, reopen capture
                if cap is not None and current_camera_idx != target_camera_idx:
                    logger.info(
                        "Camera index changed from %s to %d. Switching webcam...",
                        current_camera_idx,
                        target_camera_idx,
                    )
                    cap.release()
                    cap = None
                    current_camera_idx = None
                    consecutive_read_failures = 0

                # Ensure camera is opened
                if cap is None or not cap.isOpened():
                    camera_idx = target_camera_idx
                    # DirectShow backend on Windows is faster and avoids popups
                    cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        # Fallback to default backend
                        cap = cv2.VideoCapture(camera_idx)

                    if not cap.isOpened():
                        logger.warning("Unable to open camera index %d. Retrying in 2 seconds...", camera_idx)
                        time.sleep(2.0)
                        continue

                    current_camera_idx = camera_idx
                    consecutive_read_failures = 0
                    # Set low resolution for minimal CPU & memory usage (640x480)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    # Zero-latency: eliminate DirectShow internal 5-frame lag buffer
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Flush hardware buffer to guarantee reading the instantaneous current frame
                cap.grab()
                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_read_failures += 1
                    logger.debug("Failed to grab camera frame (failure %d).", consecutive_read_failures)
                    if consecutive_read_failures >= 5:
                        logger.warning("Multiple consecutive camera read failures. Resetting video capture handle...")
                        cap.release()
                        cap = None
                        current_camera_idx = None
                        consecutive_read_failures = 0
                    time.sleep(0.3)
                    continue

                # Successful frame read
                consecutive_read_failures = 0

                faces = self._detect_faces(frame)
                num_faces = len(faces)
                self._latest_face_count = num_faces

                # Face logic:
                # 0 faces: away
                # 1 face: primary user (safe)
                # 2+ faces: onlooker detected
                if num_faces >= 2:
                    self._consecutive_onlooker_count += 1
                    logger.debug(
                        "Candidate onlooker detected! (%d faces, streak: %d/%d)",
                        num_faces,
                        self._consecutive_onlooker_count,
                        self.config.consecutive_frames_required,
                    )
                else:
                    self._consecutive_onlooker_count = 0

                # Check if threshold reached
                if self._consecutive_onlooker_count >= self.config.consecutive_frames_required:
                    now = time.time()
                    if (now - self._last_alert_time) >= self.config.cooldown_seconds:
                        self._last_alert_time = now
                        logger.warning("ALERT CONFIRMED: %d people detected behind screen!", num_faces)

                        # Trigger alerts
                        self.notifier.trigger_onlooker_alert(
                            lock_screen=self.config.lock_screen_on_alert,
                            play_sound=self.config.play_sound,
                        )

                        if self.on_alert:
                            self.on_alert()

            except Exception as e:
                logger.error("Error during detection loop: %s", e, exc_info=True)
                time.sleep(0.5)

            # Sleep between samples (~4-5 FPS rate for ultra-low latency)
            time.sleep(self.config.sample_interval)

        if cap is not None:
            cap.release()
            logger.info("Camera released cleanly.")

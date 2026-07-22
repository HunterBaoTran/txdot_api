from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

from .contracts import Detection


class PersonDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]: ...

    @property
    @abstractmethod
    def ready(self) -> bool: ...


class SyntheticPersonDetector(PersonDetector):
    """Detect saturated markers in the generated video for repeatable offline demos."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 110, 90]), np.array([179, 255, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width * height < 1_200 or height < 70:
                continue
            detections.append(
                Detection(
                    bbox_xyxy=(float(x), float(y), float(x + width), float(y + height)),
                    confidence=0.99,
                )
            )
        return sorted(detections, key=lambda item: item.bbox_xyxy[0])

    @property
    def ready(self) -> bool:
        return True


class YoloPersonDetector(PersonDetector):
    def __init__(self, confidence: float = 0.35, model_name: str = "yolo11n.pt") -> None:
        self.confidence = confidence
        self.model_name = model_name
        self._model = None

    def _load(self) -> None:
        if self._model is None:
            config_root = Path.cwd() / ".runtime"
            config_root.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("YOLO_CONFIG_DIR", str(config_root))
            from ultralytics import YOLO

            self._model = YOLO(self.model_name)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        self._load()
        result = self._model.predict(
            frame, classes=[0], conf=self.confidence, verbose=False, device="cpu"
        )[0]
        detections: list[Detection] = []
        for box in result.boxes:
            xyxy = tuple(float(value) for value in box.xyxy[0].cpu().tolist())
            detections.append(
                Detection(bbox_xyxy=xyxy, confidence=float(box.conf[0]), class_name="person")
            )
        return detections

    @property
    def ready(self) -> bool:
        return self._model is not None


def create_detector(mode: str, confidence: float) -> PersonDetector:
    if mode == "synthetic":
        return SyntheticPersonDetector()
    if mode == "yolo":
        return YoloPersonDetector(confidence=confidence)
    raise ValueError(f"Unsupported detector: {mode}")

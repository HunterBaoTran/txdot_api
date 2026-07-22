from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .time import utc_now


@dataclass(slots=True)
class FramePacket:
    frame: np.ndarray
    captured_at: datetime
    sequence: int


class VideoSource(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> FramePacket | None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def fps(self) -> float: ...


class OpenCVSource(VideoSource):
    def __init__(self, source: str | int, loop: bool = False) -> None:
        self.source = source
        self.loop = loop
        self._capture: cv2.VideoCapture | None = None
        self._sequence = 0
        self._fps = 0.0

    def open(self) -> None:
        self.close()
        source: Any = self.source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        if isinstance(source, str) and not Path(source).exists():
            raise FileNotFoundError(f"Video file does not exist: {source}")
        self._capture = cv2.VideoCapture(source)
        if not self._capture.isOpened():
            self.close()
            raise RuntimeError(f"Unable to open video source: {source}")
        self._fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0)

    def read(self) -> FramePacket | None:
        if self._capture is None:
            raise RuntimeError("Video source is not open")
        ok, frame = self._capture.read()
        if not ok and self.loop:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        self._sequence += 1
        return FramePacket(frame=frame, captured_at=utc_now(), sequence=self._sequence)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    @property
    def fps(self) -> float:
        return self._fps


class FileLoopSource(OpenCVSource):
    def __init__(self, source: str) -> None:
        super().__init__(source, loop=True)


class WebcamSource(OpenCVSource):
    def __init__(self, index: int = 0) -> None:
        super().__init__(index, loop=False)


def create_source(source_type: str, source: str | int, loop: bool = True) -> VideoSource:
    if source_type == "file_loop":
        return FileLoopSource(str(source))
    if source_type == "webcam":
        return WebcamSource(int(source))
    raise ValueError(f"Unsupported source type: {source_type}")

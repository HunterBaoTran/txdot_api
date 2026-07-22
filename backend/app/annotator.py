from __future__ import annotations

import cv2
import numpy as np

from .contracts import TrackObservation, ZoneConfig

ZONE_COLORS = {
    "table": (66, 196, 166),
    "seat": (80, 154, 255),
    "restricted": (92, 92, 239),
    "queue": (225, 164, 78),
    "dealer": (188, 112, 225),
}


def _hex_to_bgr(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return fallback
    red, green, blue = (int(value[index : index + 2], 16) for index in (1, 3, 5))
    return blue, green, red


def annotate_frame(
    frame: np.ndarray,
    zones: list[ZoneConfig],
    tracks: list[TrackObservation],
    show_overlays: bool = True,
) -> np.ndarray:
    output = frame.copy()
    height, width = output.shape[:2]
    if show_overlays:
        overlay = output.copy()
        for zone in zones:
            points = np.asarray(
                [(int(x * width), int(y * height)) for x, y in zone.polygon_normalized],
                dtype=np.int32,
            )
            color = _hex_to_bgr(zone.color, ZONE_COLORS.get(zone.zone_type, (180, 180, 180)))
            cv2.fillPoly(overlay, [points], color)
            cv2.polylines(output, [points], True, color, 2)
            anchor = tuple(points[0])
            cv2.putText(output, zone.name, anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1)
        output = cv2.addWeighted(overlay, 0.12, output, 0.88, 0)
    for track in tracks:
        x1, y1, x2, y2 = (int(value) for value in track.bbox_xyxy)
        color = (56, 220, 255)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        label = f"Person #{track.track_id}"
        cv2.rectangle(output, (x1, max(0, y1 - 24)), (x1 + 112, y1), color, -1)
        cv2.putText(
            output, label, (x1 + 5, y1 - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (18, 24, 32), 1
        )
    return output


def encode_jpeg(frame: np.ndarray, quality: int = 82) -> bytes:
    ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Unable to encode annotated frame")
    return data.tobytes()

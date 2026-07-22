from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

DEMO_COLORS = [(44, 194, 255), (120, 235, 104), (255, 128, 94)]


def ensure_demo_video(path: str | Path, duration_seconds: int = 18, fps: int = 15) -> Path:
    """Create a rights-safe synthetic MP4 with moving anonymous markers."""
    output = Path(path)
    if output.exists() and output.stat().st_size > 0:
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = 960, 540
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Unable to create deterministic demo video at {output}")
    total = duration_seconds * fps
    for index in range(total):
        frame = np.full((height, width, 3), (17, 24, 35), dtype=np.uint8)
        cv2.ellipse(frame, (480, 285), (330, 170), 0, 0, 360, (33, 49, 61), -1)
        cv2.ellipse(frame, (480, 285), (330, 170), 0, 0, 360, (76, 94, 102), 4)
        phase = index / total
        paths = [
            (int(50 + min(phase * 2, 1) * 250), 150),
            (480, int(30 + min(max(phase - 0.18, 0) * 2.2, 1) * 130)),
            (int(910 - min(max(phase - 0.35, 0) * 2.2, 1) * 240), 350),
        ]
        visible = [True, phase > 0.18, 0.35 < phase < 0.88]
        for marker_id, ((x, y), color, show) in enumerate(
            zip(paths, DEMO_COLORS, visible, strict=True), 1
        ):
            if not show:
                continue
            cv2.rectangle(frame, (x - 24, y - 58), (x + 24, y + 58), color, -1)
            cv2.circle(frame, (x, y - 78), 20, color, -1)
            cv2.putText(
                frame, f"SIM {marker_id}", (x - 35, y + 87), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
        cv2.putText(
            frame,
            "VERATEX RIGHTS-SAFE SYNTHETIC DEMO",
            (28, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (210, 220, 225),
            2,
        )
        cv2.putText(
            frame,
            "No real people or recorded footage",
            (30, 66),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (130, 150, 160),
            1,
        )
        writer.write(frame)
    writer.release()
    return output


if __name__ == "__main__":
    created = ensure_demo_video("data/demo.mp4")
    print(f"Created deterministic demo video: {created.resolve()}")

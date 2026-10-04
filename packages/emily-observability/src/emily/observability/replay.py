"""Mission execution recording & replay engine for post-mortem analysis."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from emily.core.ids import new_id


@dataclass
class ReplayFrame:
    frame_id: str
    mission_id: str
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "mission_id": self.mission_id,
            "step_name": self.step_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "timestamp": self.timestamp.isoformat(),
        }


class ExecutionReplayEngine:
    """Records step-by-step mission execution frames and allows exact replay."""

    def __init__(self, replay_dir: Path | str | None = None) -> None:
        self.replay_dir = Path(replay_dir) if replay_dir else Path("logs/replays")
        self.replay_dir.mkdir(parents=True, exist_ok=True)

    def record_step(
        self,
        mission_id: str,
        step_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> ReplayFrame:
        """Record a single execution frame."""
        frame_id = new_id("frame")
        frame = ReplayFrame(
            frame_id=frame_id,
            mission_id=mission_id,
            step_name=step_name,
            input_data=input_data,
            output_data=output_data,
        )
        file_path = self.replay_dir / f"{mission_id}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(frame.to_dict()) + "\n")
        return frame

    def load_replay(self, mission_id: str) -> list[ReplayFrame]:
        """Load recorded frames for a mission replay."""
        file_path = self.replay_dir / f"{mission_id}.jsonl"
        if not file_path.exists():
            return []
        frames: list[ReplayFrame] = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line.strip())
                    frames.append(
                        ReplayFrame(
                            frame_id=d["frame_id"],
                            mission_id=d["mission_id"],
                            step_name=d["step_name"],
                            input_data=d["input_data"],
                            output_data=d["output_data"],
                        )
                    )
        return frames

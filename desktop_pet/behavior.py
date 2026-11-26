from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable


POSE_DURATIONS_MS: dict[str, int] = {
    "idle": 0,
    "wave": 2600,
    "wink": 2200,
    "sleep": 30 * 60 * 1000,
    "stretch": 3400,
    "yawn": 4000,
    "think": 5200,
    "cheer": 3000,
    "shy": 4000,
    "read": 30 * 60 * 1000,
    "drink": 6200,
}

ACTIVE_AUTO_POSES = (
    "wave",
    "wink",
    "stretch",
    "yawn",
    "think",
    "cheer",
    "shy",
    "drink",
)
REST_AUTO_POSES = ("sleep", "read")
REST_AFTER_SECONDS = 10 * 60.0


@dataclass(slots=True)
class PetBehavior:
    auto_enabled: bool = True
    rest_after_seconds: float = REST_AFTER_SECONDS
    clock: Callable[[], float] = time.monotonic
    randomizer: random.Random = field(default_factory=random.Random)
    last_interaction: float = field(init=False)

    def __post_init__(self) -> None:
        self.last_interaction = self.clock()

    def touch(self) -> None:
        self.last_interaction = self.clock()

    def idle_for_seconds(self) -> float:
        return max(0.0, self.clock() - self.last_interaction)

    def next_auto_pose(self) -> str:
        if not self.auto_enabled:
            return "idle"
        pool = (
            REST_AUTO_POSES
            if self.idle_for_seconds() >= self.rest_after_seconds
            else ACTIVE_AUTO_POSES
        )
        return self.randomizer.choice(pool)

    @staticmethod
    def duration_ms(pose: str) -> int:
        return POSE_DURATIONS_MS.get(pose, 0)

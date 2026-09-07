from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    UNKNOWN = "unknown"
    ENTRY = "entry"
    INDEX = "index"
    PAGE = "friend_page"
    SELECTED = "friend_selected"


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


@dataclass(frozen=True)
class FriendTarget:
    box: Box
    confidence: float
    needs_light: bool | None
    collectible: bool | None
    relative: tuple[float, float]
    evidence: dict

    @property
    def center(self):
        return self.box.center

    @property
    def ambiguous(self):
        return self.needs_light is None or self.collectible is None

    @property
    def actions(self):
        if self.ambiguous:
            return ()
        return tuple(
            a
            for a, yes in [("collect", self.collectible), ("light", self.needs_light)]
            if yes
        )


@dataclass
class Observation:
    state: State
    viewport: Box
    targets: list[FriendTarget] = field(default_factory=list)
    anchors: dict[str, Box] = field(default_factory=dict)
    page_token: tuple = ()
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

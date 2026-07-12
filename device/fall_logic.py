import math
from collections import deque
from dataclasses import dataclass


ASPECT_MIN = 0.50
SH_HIP_GAP_MAX = 0.26
WINDOW_SEC = 1.5
ENTER_FRAC = 0.60
EXIT_FRAC = 0.30
CONFIRM_SEC = 5.0

UNKNOWN = "UNKNOWN"
UPRIGHT_FRAME = "UPRIGHT_FRAME"
DOWN_FRAME = "DOWN_FRAME"

UPRIGHT = "UPRIGHT"
DOWN = "DOWN"
FALL_CONFIRMED = "FALL_CONFIRMED"
RECOVERED = "RECOVERED"


def frame_verdict(diagnostics, n_persons):
    """Classify one frame, in the required UNKNOWN/DOWN/UPRIGHT order."""
    if n_persons == 0:
        return UNKNOWN

    aspect = diagnostics.get("aspect", "")
    sh_hip_gap_norm = diagnostics.get("sh_hip_gap_norm", "")
    try:
        aspect = float(aspect)
        sh_hip_gap_norm = float(sh_hip_gap_norm)
        has_features = (
            math.isfinite(aspect)
            and math.isfinite(sh_hip_gap_norm)
        )
    except (TypeError, ValueError):
        has_features = False
    if not has_features:
        return UNKNOWN
    if sh_hip_gap_norm < SH_HIP_GAP_MAX and aspect > ASPECT_MIN:
        return DOWN_FRAME
    return UPRIGHT_FRAME


@dataclass(frozen=True)
class Transition:
    old_state: str
    new_state: str
    at: float


@dataclass(frozen=True)
class TrackCandidate:
    index: int
    confidence: float
    center: tuple[float, float]
    bbox: tuple[float, float, float, float]


class SubjectTracker:
    def __init__(self, max_jump_fraction=0.5):
        self.max_jump_fraction = max_jump_fraction
        self.previous_center = None
        self.last_seen = None

    def select(self, candidates, frame_width, now):
        if not candidates:
            self._expire_if_lost(now)
            return None

        if self.previous_center is None:
            return self._accept(max(candidates, key=lambda candidate: candidate.confidence), now)

        nearest = min(candidates, key=self._distance_from_previous)
        if self._distance_from_previous(nearest) <= frame_width * self.max_jump_fraction:
            return self._accept(nearest, now)

        if self.last_seen is not None and now - self.last_seen >= WINDOW_SEC:
            self.previous_center = None
            return self._accept(max(candidates, key=lambda candidate: candidate.confidence), now)
        return None

    def reset(self):
        self.previous_center = None
        self.last_seen = None

    def _accept(self, candidate, now):
        self.previous_center = candidate.center
        self.last_seen = now
        return candidate

    def _distance_from_previous(self, candidate):
        return math.dist(self.previous_center, candidate.center)

    def _expire_if_lost(self, now):
        if self.last_seen is not None and now - self.last_seen >= WINDOW_SEC:
            self.reset()


class FallStateMachine:
    def __init__(self):
        self.state = UPRIGHT
        self.down_since = None
        self._window = deque()

    @property
    def down_fraction(self):
        known = [verdict for _, verdict in self._window if verdict != UNKNOWN]
        if not known:
            return None
        return known.count(DOWN_FRAME) / len(known)

    def update(self, verdict, now):
        self._window.append((now, verdict))
        cutoff = now - WINDOW_SEC
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

        fraction = self.down_fraction
        transitions = []
        if verdict == UNKNOWN:
            if self.state == DOWN and now - self.down_since >= CONFIRM_SEC:
                transitions.append(self._transition(FALL_CONFIRMED, now))
            return transitions

        if self.state == UPRIGHT and fraction is not None and fraction >= ENTER_FRAC:
            self.down_since = now
            transitions.append(self._transition(DOWN, now))
        elif self.state == DOWN and now - self.down_since >= CONFIRM_SEC:
            transitions.append(self._transition(FALL_CONFIRMED, now))

        if self.state == DOWN and fraction is not None and fraction <= EXIT_FRAC:
            transitions.append(self._transition(UPRIGHT, now))
            self.down_since = None
        return transitions

    def clear(self, now):
        if self.state != FALL_CONFIRMED:
            return []
        transitions = [self._transition(RECOVERED, now)]
        transitions.append(self._transition(UPRIGHT, now))
        self.down_since = None
        self._window.clear()
        return transitions

    def _transition(self, new_state, now):
        old_state = self.state
        self.state = new_state
        return Transition(old_state, new_state, now)

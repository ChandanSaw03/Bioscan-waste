"""Batch aggregation: accumulate frame-level mass estimates into batches.

A batch is a time window (or frame count) over which per-frame composition
estimates are averaged and then converted to a single mass-by-class vector.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Batch:
    """Aggregated batch of frames. Matches design.md §2 interface.

    Attributes:
        batch_id: Unique identifier for this batch.
        t_start: Timestamp of the first frame in the batch.
        t_end: Timestamp of the last frame in the batch.
        mass_by_class: Estimated mass (kg) per class.
        n_frames: Number of frames aggregated.
        mass_source: 'vision' or 'load_cell_calibrated'.
        hazard_flags: Set of hazard items detected in this batch.
        avg_confidence: Mean classifier confidence across all frames.
    """

    batch_id: str
    t_start: datetime
    t_end: datetime
    mass_by_class: dict[str, float]
    n_frames: int
    mass_source: str = "vision"
    hazard_flags: set[str] = field(default_factory=set)
    avg_confidence: float = 0.0

    @property
    def total_mass_kg(self) -> float:
        """Total estimated mass across all classes (kg)."""
        return sum(self.mass_by_class.values())

    def composition_fractions(self) -> dict[str, float]:
        """Mass fraction per class (0–1, sums to 1)."""
        total = self.total_mass_kg
        if total <= 0:
            return {cls: 0.0 for cls in self.mass_by_class}
        return {cls: m / total for cls, m in self.mass_by_class.items()}

    def group_fractions(self, groups: dict[str, list[str]]) -> dict[str, float]:
        """Mass fraction per group (organic / combustible / inert)."""
        fracs = self.composition_fractions()
        result: dict[str, float] = {}
        for group_name, class_list in groups.items():
            result[group_name] = sum(fracs.get(c, 0.0) for c in class_list)
        return result


class BatchAggregator:
    """Accumulates per-frame mass estimates and produces Batch objects.

    Usage:
        agg = BatchAggregator(energy_classes)
        for frame_mass in ...:
            agg.add_frame(frame_mass, timestamp, hazards, confidence)
            if agg.is_ready(window_seconds=60):
                batch = agg.finalize()
    """

    def __init__(self, energy_classes: list[str]) -> None:
        self._energy_classes = energy_classes
        self._reset()

    def _reset(self) -> None:
        """Clear accumulated state for the next batch."""
        self._frame_masses: list[dict[str, float]] = []
        self._timestamps: list[datetime] = []
        self._hazard_flags: set[str] = set()
        self._confidences: list[float] = []

    def add_frame(
        self,
        mass_by_class: dict[str, float],
        timestamp: datetime,
        hazard_flags: set[str] | None = None,
        avg_confidence: float = 0.0,
    ) -> None:
        """Add a single frame's mass estimate to the batch."""
        self._frame_masses.append(mass_by_class)
        self._timestamps.append(timestamp)
        if hazard_flags:
            self._hazard_flags |= hazard_flags
        self._confidences.append(avg_confidence)

    @property
    def n_frames(self) -> int:
        """Number of frames accumulated so far."""
        return len(self._frame_masses)

    def is_ready(self, window_seconds: float = 60.0, window_frames: int = 0) -> bool:
        """Check if the batch window has elapsed.

        Args:
            window_seconds: Time window in seconds (0 to disable).
            window_frames: Frame count window (0 to disable).

        Returns:
            True if the batch is ready to finalize.
        """
        if self.n_frames == 0:
            return False

        if window_frames > 0 and self.n_frames >= window_frames:
            return True

        if window_seconds > 0 and len(self._timestamps) >= 2:
            elapsed = (self._timestamps[-1] - self._timestamps[0]).total_seconds()
            if elapsed >= window_seconds:
                return True

        return False

    def finalize(self) -> Batch:
        """Produce a Batch from accumulated frames, then reset.

        Mass is summed across frames (each frame contributes the mass
        visible in that frame's tiles). In practice, with continuous belt
        motion, each frame sees new material so summing is appropriate.

        Returns:
            A Batch object with aggregated results.
        """
        if self.n_frames == 0:
            raise ValueError("Cannot finalize an empty batch")

        # Sum mass across frames
        total_mass: dict[str, float] = {cls: 0.0 for cls in self._energy_classes}
        for frame_mass in self._frame_masses:
            for cls, m in frame_mass.items():
                if cls in total_mass:
                    total_mass[cls] += m

        avg_conf = (
            sum(self._confidences) / len(self._confidences)
            if self._confidences else 0.0
        )

        batch = Batch(
            batch_id=str(uuid.uuid4())[:8],
            t_start=self._timestamps[0],
            t_end=self._timestamps[-1],
            mass_by_class=total_mass,
            n_frames=self.n_frames,
            mass_source="vision",
            hazard_flags=self._hazard_flags.copy(),
            avg_confidence=avg_conf,
        )

        self._reset()
        return batch

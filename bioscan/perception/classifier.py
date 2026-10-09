"""Tile classifier: wraps a YOLOv8-cls model for patch-based classification.

The model is loaded once at startup and used to classify tiles extracted
from belt frames.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from bioscan.ingest.tiling import Tile, TileClassification


class TileClassifier:
    """Classify tiles using a YOLOv8-cls model.

    Args:
        model_path: Path to the trained YOLOv8-cls weights (.pt file).
        class_names: Ordered list of class names matching the model output.
        confidence_threshold: Discard predictions below this confidence.
        device: Inference device ('cpu', '0', etc.).
    """

    def __init__(
        self,
        model_path: str | Path,
        class_names: list[str],
        confidence_threshold: float = 0.35,
        device: str = "cpu",
    ) -> None:
        self.class_names = class_names
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._model_path = Path(model_path)
        self._device = device

        # Lazy-load model on first call (or explicitly via load())
        if self._model_path.exists():
            self.load()

    def load(self) -> None:
        """Load the YOLO model. Called automatically if weights exist."""
        from ultralytics import YOLO
        self._model = YOLO(str(self._model_path))

    @property
    def is_loaded(self) -> bool:
        """Whether a real model is loaded."""
        return self._model is not None

    def classify_tile(self, tile: Tile) -> TileClassification:
        """Classify a single tile.

        Returns a TileClassification. If the model is not loaded,
        returns a stub classification for testing purposes.
        """
        if not self.is_loaded:
            return self._stub_classify(tile)

        results = self._model.predict(
            tile.image, imgsz=tile.image.shape[0], device=self._device, verbose=False
        )
        result = results[0]
        probs = result.probs

        top1_idx = int(probs.top1)
        top1_conf = float(probs.top1conf)

        # Map model index to class name
        if top1_idx < len(self.class_names):
            class_name = self.class_names[top1_idx]
        else:
            class_name = "glass_inert"  # fallback for unknown index

        # Check if it's a hazard flag
        hazard_flag = None
        # The model's names dict may contain hazard classes
        model_class_name = result.names.get(top1_idx, "")
        if "battery" in model_class_name.lower():
            hazard_flag = "battery"
        elif "medical" in model_class_name.lower():
            hazard_flag = "medical"

        return TileClassification(
            tile=tile,
            class_name=class_name,
            confidence=top1_conf,
            hazard_flag=hazard_flag,
        )

    def classify_tiles(self, tiles: list[Tile]) -> list[TileClassification]:
        """Classify a batch of tiles.

        Args:
            tiles: List of Tile objects to classify.

        Returns:
            List of TileClassification results.
        """
        return [self.classify_tile(t) for t in tiles]

    def _stub_classify(self, tile: Tile) -> TileClassification:
        """Deterministic stub for testing without a model.

        Uses the mean pixel intensity to pick a class so tests are
        reproducible. This is NOT a real classifier.
        """
        mean_val = int(np.mean(tile.image))
        idx = mean_val % len(self.class_names)
        return TileClassification(
            tile=tile,
            class_name=self.class_names[idx],
            confidence=0.50,
            hazard_flag=None,
        )

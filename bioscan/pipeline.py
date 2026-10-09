"""End-to-end processing pipeline for BioScan."""

from __future__ import annotations

import base64
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from bioscan.batch.aggregator import BatchAggregator
from bioscan.config_loader import BioScanConfig, load_config
from bioscan.energy.engine import EnergyEngine, BatchEnergy
from bioscan.ingest.tiling import tile_frame, aggregate_tile_classifications
from bioscan.log.writer import CSVLogger
from bioscan.mass.estimator import estimate_mass_from_composition
from bioscan.perception.classifier import TileClassifier


class BioScanPipeline:
    """Wires together ingest, perception, mass, batching, and energy.

    Args:
        config: BioScanConfig object.
        model_path: Path to YOLOv8-cls weights.
    """

    def __init__(self, config: BioScanConfig, model_path: str = "models/tile_classifier_best.pt") -> None:
        self.config = config
        self.classifier = TileClassifier(
            model_path=model_path,
            class_names=config.energy_classes,
            confidence_threshold=config.thresholds.min_confidence,
        )
        self.aggregator = BatchAggregator(config.energy_classes)
        self.engine = EnergyEngine(config)
        self.logger = CSVLogger()

    def process_file(self, video_path: str) -> dict:
        """Process a video file or image and return the energy result for the batch.

        All frames in the file are aggregated into a single batch.
        
        Returns:
            JSON-serializable dictionary with composition and energy metrics.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video source: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
            
        target_fps = self.config.grid.min_belt_coverage  # Using logic from camera.yaml fps_process ?
        # Actually camera.yaml has fps_process ? Wait, config_loader didn't expose fps_process.
        # Fallback: process every N frames to hit ~5 FPS
        frame_interval = max(int(fps / 5.0), 1)

        frame_count = 0
        t_start = datetime.now()
        
        last_frame_annotated = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                # 1. Tile
                tiles = tile_frame(frame, self.config.grid)
                
                # 2. Classify
                classifications = self.classifier.classify_tiles(tiles)
                
                # 3. Aggregate tiles to frame composition
                comp = aggregate_tile_classifications(classifications, self.config.energy_classes)
                
                # 4. Estimate mass
                mass_by_class = estimate_mass_from_composition(comp, self.config)
                
                # 5. Add to batch
                self.aggregator.add_frame(
                    mass_by_class=mass_by_class,
                    timestamp=datetime.now(),
                    hazard_flags=comp.hazard_flags,
                    avg_confidence=comp.avg_confidence,
                )
                
                # Draw simple grid & classifications on the last frame for the UI
                annotated = frame.copy()
                for tc in classifications:
                    color = (0, 255, 0)
                    if tc.hazard_flag:
                        color = (0, 0, 255)
                    elif tc.confidence < self.config.thresholds.min_confidence:
                        color = (128, 128, 128)
                        
                    x, y = tc.tile.x, tc.tile.y
                    w, h = tc.tile.image.shape[1], tc.tile.image.shape[0]
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(annotated, tc.class_name, (x + 5, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                last_frame_annotated = annotated

            frame_count += 1
            
        cap.release()

        # 6. Finalize batch and evaluate energy
        if self.aggregator.n_frames == 0:
            raise ValueError("No frames processed from the video.")
            
        batch = self.aggregator.finalize()
        energy = self.engine.evaluate(batch)
        
        # 7. Log to CSV
        self.logger.log_batch(batch, energy)
        
        # 8. Base64 encode the annotated frame
        frame_b64 = None
        if last_frame_annotated is not None:
            _, buffer = cv2.imencode('.jpg', last_frame_annotated)
            frame_b64 = base64.b64encode(buffer).decode('utf-8')

        return {
            "batch_id": batch.batch_id,
            "total_mass_kg": batch.total_mass_kg,
            "mass_by_class": batch.mass_by_class,
            "fractions": batch.composition_fractions(),
            "energy": {
                "biogas": {
                    "ch4_nm3": {"low": energy.ch4_nm3.low, "mid": energy.ch4_nm3.mid, "high": energy.ch4_nm3.high},
                    "elec_kwh": {"low": energy.elec_biogas_kwh.low, "mid": energy.elec_biogas_kwh.mid, "high": energy.elec_biogas_kwh.high},
                },
                "incineration": {
                    "heat_mj": {"low": energy.heat_mj.low, "mid": energy.heat_mj.mid, "high": energy.heat_mj.high},
                    "elec_kwh": {"low": energy.elec_wte_kwh.low, "mid": energy.elec_wte_kwh.mid, "high": energy.elec_wte_kwh.high},
                }
            },
            "recommendation": energy.recommendation,
            "reason": energy.reason,
            "hazard_flags": list(batch.hazard_flags),
            "annotated_frame_b64": frame_b64,
        }

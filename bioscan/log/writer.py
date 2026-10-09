"""CSV logger for batch records."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bioscan.batch.aggregator import Batch
from bioscan.energy.engine import BatchEnergy
from bioscan.log.s3 import upload_to_s3


class CSVLogger:
    """Appends batch records to a CSV file."""

    def __init__(self, log_path: str | Path = "logs/batches.csv") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Create file with headers if it doesn't exist
        if not self.log_path.exists():
            df = pd.DataFrame(columns=[
                "batch_id", "t_start", "t_end",
                "n_frames", "mass_total_kg",
                "recommendation", "reason"
            ])
            df.to_csv(self.log_path, index=False)

    def log_batch(self, batch: Batch, energy: BatchEnergy) -> None:
        """Append a single batch evaluation to the CSV."""
        record = {
            "batch_id": batch.batch_id,
            "t_start": batch.t_start.isoformat(),
            "t_end": batch.t_end.isoformat(),
            "n_frames": batch.n_frames,
            "mass_total_kg": batch.total_mass_kg,
            "recommendation": energy.recommendation,
            "reason": energy.reason,
            "ch4_nm3_mid": energy.ch4_nm3.mid,
            "elec_biogas_kwh_mid": energy.elec_biogas_kwh.mid,
            "elec_wte_kwh_mid": energy.elec_wte_kwh.mid,
        }

        # Add mass percentages
        fracs = batch.composition_fractions()
        for cls, frac in fracs.items():
            record[f"pct_{cls}"] = round(frac * 100, 1)
            
        record["hazard_flags"] = "|".join(sorted(batch.hazard_flags)) if batch.hazard_flags else ""

        df = pd.DataFrame([record])
        df.to_csv(self.log_path, mode="a", header=False, index=False)
        
        # Sync to S3
        upload_to_s3(self.log_path, f"logs/{self.log_path.name}")

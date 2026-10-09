"""FastAPI backend for BioScan."""

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from bioscan.config_loader import load_config
from bioscan.pipeline import BioScanPipeline
from bioscan.log.s3 import upload_to_s3

app = FastAPI(title="BioScan API", version="0.1.0")

# Allow Streamlit to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Load config and model once at startup."""
    try:
        config = load_config()
        # Attach pipeline to the app state so it is persisted
        app.state.pipeline = BioScanPipeline(config)
    except Exception as e:
        print(f"Failed to initialize pipeline: {e}")
        # Not throwing exception here so the server starts, but /analyze will fail.
        app.state.pipeline_error = str(e)


@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    """Accepts a video or image file, runs BioScan pipeline, returns results."""
    if hasattr(app.state, "pipeline_error"):
        raise HTTPException(status_code=500, detail=app.state.pipeline_error)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
        
    ext = Path(file.filename).suffix.lower()
    
    # Save uploaded file to temp dir
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_fw:
        shutil.copyfileobj(file.file, temp_fw)
        temp_path = temp_fw.name

    try:
        # Run pipeline
        pipeline: BioScanPipeline = app.state.pipeline
        result = pipeline.process_file(temp_path)
        
        # Sync original media to S3 in the background to avoid blocking API too long
        # (Using a synchronous call here for MVP simplicity)
        safe_name = Path(file.filename).name
        upload_to_s3(temp_path, f"uploads/{result['batch_id']}_{safe_name}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return result

from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class RecalculateRequest(BaseModel):
    mass_by_class: Dict[str, float]
    hazard_flags: List[str]
    moisture_offset: float = 0.0
    chp_efficiency: float = 0.38
    wte_efficiency: float = 0.22

@app.post("/recalculate")
async def recalculate_energy(req: RecalculateRequest):
    """Fast recalculation of energy based on slider values, skipping video processing."""
    if hasattr(app.state, "pipeline_error"):
        raise HTTPException(status_code=500, detail=app.state.pipeline_error)
        
    pipeline: BioScanPipeline = app.state.pipeline
    cfg = pipeline.config
    
    # Temporarily override efficiencies for this request
    # Note: we construct a temporary batch, we don't modify the global config struct to avoid race conditions.
    # Since BioScanConfig is frozen, we will pass offsets directly if the engine supported them. Wait, the 
    # engine doesn't take efficiency offsets on the evaluate function.
    # Let's create a temporary config copy
    from dataclasses import replace
    temp_cfg = replace(cfg, chp_efficiency=req.chp_efficiency, wte_efficiency=req.wte_efficiency)
    
    # Temporarily inject the moisture_offset into the uncertainty config so the engine picks it up?
    # No, moisture is used per-class. We can just modify the uncertainty moisture_abs for a hacky slider demo,
    # but the slider is supposed to shift the *base* moisture, not just uncertainty.
    # We will adjust the base moisture in waste_factors.
    new_factors = {}
    from bioscan.config_loader import WasteClassFactors
    for cls, f in temp_cfg.waste_factors.items():
        new_moisture = max(0.0, min(0.99, f.moisture + req.moisture_offset))
        new_factors[cls] = WasteClassFactors(
            density_g_cm3=f.density_g_cm3,
            thickness_cm=f.thickness_cm,
            moisture=new_moisture,
            vs_fraction=f.vs_fraction,
            bmp_nm3_ch4_per_kg_vs=f.bmp_nm3_ch4_per_kg_vs,
            lhv_mj_per_kg=f.lhv_mj_per_kg,
        )
    temp_cfg = replace(temp_cfg, waste_factors=new_factors)
    
    from bioscan.batch.aggregator import Batch
    batch = Batch(
        batch_id="recalc", 
        t_start=datetime.now(), 
        t_end=datetime.now(), 
        mass_by_class=req.mass_by_class, 
        n_frames=1, 
        hazard_flags=set(req.hazard_flags)
    )
    
    from bioscan.energy.engine import EnergyEngine
    temp_engine = EnergyEngine(temp_cfg)
    energy = temp_engine.evaluate(batch)
    
    return {
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
    }


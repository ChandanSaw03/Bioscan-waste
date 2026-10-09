# BioScan: Architecture

**Vision-Based Biomass Potential Estimator**: a camera over a conveyor belt identifies waste composition and estimates the energy-generation potential (biogas or incineration) of each batch.

---

## 1. System Overview

BioScan turns a video feed into an energy estimate in six stages:

```
 Camera / Video file
        │
        ▼
 [1] Ingestion        OpenCV capture, frame sampling, belt tile gridding
        │
        ▼
 [2] Perception       YOLOv8-cls: patch-based classification on each grid tile
        │
        ▼
 [3] Composition      Aggregate tile shares per frame -> batch composition percentage
        │
        ▼
 [4] Mass Estimation  tile area share → volume → mass (per-class density factors)
        │
        ▼
 [5] Batch Aggregator Accumulate frame-level composition into time batches
        │
        ▼
 [6] Energy Engine    Biogas path (CH4) and incineration path (LHV)
        │
        ▼
 [7] Logging + UI     Pandas → CSV/SQLite → Streamlit dashboard
```

### Design principle

The camera only tells us **what** is on the belt and **how much surface area** it covers. Everything else (mass, moisture, energy) comes from calibrated per-class factors held in a config file. This keeps the ML part simple and the energy part transparent and auditable.

---

## 2. Components

### 2.1 Ingestion (`bioscan/ingest/`)
- `VideoSource`: abstracts a webcam, an RTSP stream, or a recorded video file behind one interface. A file source is what makes the demo work without hardware.
- Frame sampling: process every Nth frame (default: 5 FPS effective) to keep latency low.
- Belt ROI: crop to the belt region defined in `config/camera.yaml` so background is ignored.
- Optional perspective correction (homography) so pixel area maps to a consistent real-world area (cm²/pixel).

### 2.2 Perception (`bioscan/perception/`)
- Model: **YOLOv8-cls** (Ultralytics). Patch-based classification. We tile the belt ROI into a grid of squares and classify each tile independently. This relies on an assumption that tiled mass distribution approximates image surface representation better than tight bounding boxes. (YOLOv8-seg is an optional later upgrade).
- Output per tile: `class_id`, `confidence`, `hazard_flag`.
- Class taxonomy (v1, 7 energy classes + hazards):

| Class | Group | Energy relevance |
|---|---|---|
| `food_organic` | Organic | Biogas (high) / incineration (low, wet) |
| `agri_residue` | Organic | Biogas (medium) / incineration (medium) |
| `paper_cardboard` | Combustible | Incineration (medium), biogas (low) |
| `plastic` | Combustible | Incineration (very high), biogas (none) |
| `textile` | Combustible | Incineration (medium) |
| `metal` | Inert | None (flagged for recovery) |
| `glass_inert` | Inert | None |
| Hazards (`battery`, `medical`) | - | Flagged warnings, skipped for energy |

- Training data: RealWaste, Garbage Dataset V2, ZeroWaste, and custom food/crop images.

### 2.3 Composition (`bioscan/ingest/tiling.py`)
- Frames are tiled into a grid. Time-based tracking is obsolete in this mode; instead, we sample frames dynamically.
- Each tile contributes fractionally to the overall batch area.

### 2.4 Mass Estimation (`bioscan/mass/`)
Mass is estimated from visible tile area using per-class factors:

```
total_area   = n_tiles * tile_cm2
area_c       = total_area * tile_share[class]
volume_cm3   = area_c × effective_thickness_cm[class]
mass_kg      = volume_cm3 × bulk_density_g_cm3[class] / 1000
```

- `effective_thickness_cm` and `bulk_density` live in `config/waste_factors.yaml`.
- **Optional calibration hook:** if a belt load cell is available, total estimated mass is rescaled to match the measured weight, and the composition ratios are kept. This sharply reduces error and is a strong "future work" or hardware-upgrade story.
- Known limitation: stacked or occluded material is invisible to a top-down camera. Handled by an uncertainty margin (see §6).

### 2.5 Batch Aggregator (`bioscan/batch/`)
- A **batch** is a time window (e.g., 60 s) or a fixed count of objects, configurable.
- Produces a composition table: mass and percentage by class, plus an organic/combustible/inert group summary.

### 2.6 Energy Engine (`bioscan/energy/`)
Two independent pathways, both computed for every batch so users can compare.

**Pathway A: Anaerobic digestion (biogas)**

```
CH4_Nm3  = Σ over classes ( mass_kg × (1 − moisture) × VS_fraction × BMP_Nm3_per_kg_VS )
Energy_kWh_thermal = CH4_Nm3 × 9.97          # lower heating value of methane
Electricity_kWh    = Energy_kWh_thermal × chp_efficiency   # default ~0.38
```

**Pathway B: Waste-to-energy incineration**

```
Energy_MJ          = Σ over classes ( mass_kg × LHV_MJ_per_kg )
Energy_kWh_thermal = Energy_MJ / 3.6
Electricity_kWh    = Energy_kWh_thermal × wte_efficiency   # default ~0.22
```

- LHV (lower heating value) already accounts for moisture, so values are specified for wet waste as received.
- Each pathway returns a **point estimate plus a low/high range** derived from the uncertainty settings.
- A **recommendation** field picks the pathway with higher estimated electricity yield and notes when the batch is unsuitable (e.g., >70% inert, or too much plastic for a digester).

> All numeric factors in `config/` are **starting placeholders from published literature ranges**. They must be reviewed against local waste characterization data before any real-world claim is made.

### 2.7 Logging (`bioscan/logging/`)
- A Pandas DataFrame is appended per batch, then persisted to CSV (default) or SQLite.
- Per-batch record schema:

| Field | Type | Description |
|---|---|---|
| `batch_id` | str | Unique ID |
| `t_start`, `t_end` | datetime | Batch window |
| `n_objects` | int | Objects counted |
| `mass_total_kg` | float | Estimated total mass |
| `pct_<class>` | float | Mass percentage per class (8 columns) |
| `ch4_nm3_low/mid/high` | float | Biogas path |
| `elec_biogas_kwh_low/mid/high` | float | Biogas path |
| `elec_wte_kwh_low/mid/high` | float | Incineration path |
| `recommendation` | str | `biogas`, `incineration`, `mixed`, `reject` |
| `mass_source` | str | `vision` or `load_cell_calibrated` |

### 2.8 Dashboard (`app/`)
- **Streamlit** app with:
  - Live annotated video frame (masks + labels)
  - Composition donut chart for the current batch
  - Energy gauges: biogas vs. incineration kWh
  - Rolling table and line chart of past batches
  - Download button for the log CSV
  - Sidebar sliders for moisture, efficiency, and thickness assumptions, so judges can see the model respond live

---

## 3. Data Flow (single batch)

1. Frame arrives → cropped to belt ROI.
2. YOLOv8-cls determines class breakdown of each tile.
3. Each tile receives proportionate area.
4. Estimator evaluates volume and translates into mass.
5. At batch end, masses are accumulated and evaluated.
6. Energy Engine applies factors from config and produces low/mid/high estimates for both pathways.
7. The record is appended to the log and pushed to the dashboard.

---

## 4. Repository Layout

```
bioscan/
├── app/
│   └── dashboard.py              # Streamlit UI
├── bioscan/
│   ├── ingest/                   # VideoSource, ROI, homography
│   ├── perception/               # model loading, inference wrapper
│   ├── tracking/                 # tracker + counting line
│   ├── mass/                     # area → mass
│   ├── batch/                    # batch aggregation
│   ├── energy/                   # biogas + incineration engines
│   ├── logging/                  # Pandas/CSV/SQLite persistence
│   └── pipeline.py               # wires stages together
├── config/
│   ├── camera.yaml               # ROI, cm²/pixel, belt speed, fps
│   ├── classes.yaml              # taxonomy and label mapping
│   ├── waste_factors.yaml        # density, thickness, moisture, VS, BMP, LHV
│   └── energy.yaml               # efficiencies, batch window, uncertainty
├── data/
│   ├── raw/  processed/  samples/
├── models/                       # trained weights
├── notebooks/                    # EDA, training, calibration
├── tests/
├── docs/                         # prd.md, design.md, phases.md, rules.md
├── requirements.txt
└── README.md
```

---

## 5. Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.10+ | Ecosystem, speed of development |
| Backend | FastAPI | Robust REST API layer |
| Video | OpenCV | Standard, handles webcam/file/RTSP |
| Detection | Ultralytics YOLOv8-cls | Patch-based tile classification |
| Data | Pandas, NumPy | Calculations and logging |
| Config | PyYAML | Human-editable factors |
| UI | Streamlit, Plotly | Fast dashboard for demo |
| Storage | CSV + AWS S3 | S3 via Boto3 IAM Roles |
| Deployment| Docker | Scalable AWS EC2 single instance |
| Testing | pytest | Unit tests on energy math |

---

## 6. Uncertainty and Limitations

| Source of error | Mitigation |
|---|---|
| Area ≠ mass (thickness varies) | Per-class thickness factors; optional load-cell calibration |
| Occlusion and stacking | Single-layer belt spreading; widen the uncertainty band when belt density is high |
| Moisture varies widely | Moisture as an adjustable parameter; lower LHV for wet organics |
| Mixed or dirty materials | `other` handling and confidence thresholds; low-confidence mass assigned proportionally |
| Domain shift (lighting, camera angle) | Fixed lighting, augmentation, small on-site fine-tune set |
| Literature factors ≠ local waste | Config-driven; recalibrate with local waste audit |

The system reports **ranges, not single numbers**, and labels itself as a *screening estimator*, not a certified measurement.

---

## 7. Deployment Modes

1. **Demo mode:** recorded video or webcam + laptop. Used for the hackathon.
2. **Edge mode (future):** Jetson or Raspberry Pi + camera, exporting the model to ONNX/TensorRT.
3. **Plant mode (future):** multiple cameras, PLC/SCADA integration, and a load cell for calibration.

---

## 8. Extensibility

- Add a class: edit `classes.yaml` and `waste_factors.yaml`, then retrain.
- Add an energy pathway (e.g., pyrolysis, RDF/pelletizing): implement a new module with the same interface (`estimate(composition) → EnergyResult`).
- Swap the detector: the perception layer exposes a single `detect(frame)` interface.

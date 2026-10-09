# BioScan: Design Document

Detailed technical and UX design. Read `architecture.md` first for the high-level structure.

---

## 1. Design Goals

1. **Transparent:** every energy number can be traced to a visible factor.
2. **Configurable:** local waste data changes YAML, not code.
3. **Demo-robust:** works from a recorded video with no hardware.
4. **Honest:** shows ranges and limitations, not false precision.

---

## 2. Module Interfaces

```python
# perception
class Detector:
    def detect(self, frame: np.ndarray) -> list[Detection]: ...

@dataclass
class Detection:
    track_id: int | None
    class_name: str
    confidence: float
    mask: np.ndarray        # bool array, belt-ROI coordinates
    bbox: tuple[int, int, int, int]

# mass
class MassEstimator:
    def estimate(self, det: Detection) -> float: ...   # kg

# batch
@dataclass
class Batch:
    batch_id: str
    t_start: datetime
    t_end: datetime
    mass_by_class: dict[str, float]    # kg
    n_objects: int
    mass_source: str                   # "vision" | "load_cell_calibrated"

# energy
@dataclass
class EnergyResult:
    low: float
    mid: float
    high: float

@dataclass
class BatchEnergy:
    ch4_nm3: EnergyResult
    elec_biogas_kwh: EnergyResult
    elec_wte_kwh: EnergyResult
    recommendation: str                # biogas | incineration | mixed | reject
    reason: str

class EnergyEngine:
    def evaluate(self, batch: Batch) -> BatchEnergy: ...
```

Each stage depends only on the previous stage's output type, so stages can be tested in isolation.

---

## 3. Configuration Design

### 3.1 `config/waste_factors.yaml` (placeholder values: calibrate locally)

```yaml
# moisture: fraction of wet mass that is water
# vs_fraction: volatile solids as a fraction of dry mass
# bmp_nm3_ch4_per_kg_vs: biochemical methane potential
# lhv_mj_per_kg: lower heating value, wet basis (as received)
# density_g_cm3 / thickness_cm: used for area -> mass

food_organic:
  density_g_cm3: 0.60
  thickness_cm: 4.0
  moisture: 0.70
  vs_fraction: 0.90
  bmp_nm3_ch4_per_kg_vs: 0.45
  lhv_mj_per_kg: 4.0
agri_residue:
  density_g_cm3: 0.25
  thickness_cm: 6.0
  moisture: 0.40
  vs_fraction: 0.85
  bmp_nm3_ch4_per_kg_vs: 0.28
  lhv_mj_per_kg: 10.0
paper_cardboard:
  density_g_cm3: 0.15
  thickness_cm: 2.0
  moisture: 0.10
  vs_fraction: 0.85
  bmp_nm3_ch4_per_kg_vs: 0.10
  lhv_mj_per_kg: 14.0
plastic:
  density_g_cm3: 0.08
  thickness_cm: 3.0
  moisture: 0.02
  vs_fraction: 0.0       # not digestible
  bmp_nm3_ch4_per_kg_vs: 0.0
  lhv_mj_per_kg: 32.0
textile:
  density_g_cm3: 0.12
  thickness_cm: 2.0
  moisture: 0.10
  vs_fraction: 0.0       # treated as non-digestible in MVP
  bmp_nm3_ch4_per_kg_vs: 0.0
  lhv_mj_per_kg: 16.0
wood:
  density_g_cm3: 0.40
  thickness_cm: 4.0
  moisture: 0.20
  vs_fraction: 0.0       # slowly degradable; excluded from MVP digestion
  bmp_nm3_ch4_per_kg_vs: 0.0
  lhv_mj_per_kg: 15.0
metal:
  density_g_cm3: 0.50
  thickness_cm: 2.0
  moisture: 0.0
  vs_fraction: 0.0
  bmp_nm3_ch4_per_kg_vs: 0.0
  lhv_mj_per_kg: 0.0
glass_inert:
  density_g_cm3: 0.70
  thickness_cm: 2.0
  moisture: 0.0
  vs_fraction: 0.0
  bmp_nm3_ch4_per_kg_vs: 0.0
  lhv_mj_per_kg: 0.0
```

> `density_g_cm3` here is an **effective bulk density of the visible pile** (including air gaps), not material density. It is a calibration knob, not a physical constant.

### 3.2 `config/energy.yaml`

```yaml
methane_lhv_kwh_per_nm3: 9.97
chp_efficiency: 0.38
wte_efficiency: 0.22
batch:
  mode: time          # time | count
  window_seconds: 60
  window_objects: 50
uncertainty:
  mass_rel: 0.25      # ±25% mass
  moisture_abs: 0.10  # ±0.10 moisture fraction
  bmp_rel: 0.20
  lhv_rel: 0.15
thresholds:
  min_confidence: 0.35
  reject_inert_fraction: 0.70
  digester_max_plastic_fraction: 0.10
  min_organic_fraction_biogas: 0.40
```

### 3.3 `config/camera.yaml`

```yaml
source: "samples/belt_demo.mp4"   # path, webcam index, or rtsp:// URL
fps_process: 5
roi: [x, y, w, h]
cm2_per_pixel: 0.05
belt_speed_cm_s: 20.0
counting_line_y: 0.5               # fraction of ROI height
```

---

## 4. Algorithms

### 4.1 Counting each object once
1. Tracker assigns `track_id`.
2. Keep a set `counted_ids`.
3. When an object's centroid crosses `counting_line_y` and its ID is not in `counted_ids`, add it and compute its mass using its **largest observed mask** so far, which is less sensitive to partial views at the frame edge.

### 4.2 Mass estimation
```
mass_kg = mask_px × cm2_per_pixel × thickness_cm × density_g_cm3 / 1000
```

### 4.3 Biogas
For each class *c* with mass *m_c*:
```
dry_c  = m_c × (1 − moisture_c)
vs_c   = dry_c × vs_fraction_c
CH4_c  = vs_c × bmp_c
CH4    = Σ CH4_c
kWh_th = CH4 × 9.97
kWh_el = kWh_th × chp_efficiency
```

### 4.4 Incineration
```
MJ     = Σ m_c × lhv_c
kWh_th = MJ / 3.6
kWh_el = kWh_th × wte_efficiency
```

### 4.5 Uncertainty (MVP method)
Compute each estimate three times:
- **low:** mass × (1 − mass_rel), moisture + moisture_abs, BMP × (1 − bmp_rel), LHV × (1 − lhv_rel)
- **mid:** nominal
- **high:** the mirror image of low

This is a simple bounding approach, not a statistical confidence interval, and the UI labels it as an *estimated range*.

### 4.6 Recommendation logic
```
if inert_fraction ≥ reject_inert_fraction            → reject ("mostly non-combustible")
elif organic_fraction ≥ min_organic_fraction_biogas
     and plastic_fraction ≤ digester_max_plastic_fraction
     and elec_biogas_mid ≥ elec_wte_mid × 0.8          → biogas
elif elec_wte_mid > elec_biogas_mid                    → incineration
else                                                   → mixed ("split organics and combustibles")
```
Every outcome includes a one-line human-readable reason.

### 4.7 Optional load-cell calibration
```
scale = measured_kg / Σ vision_mass
mass_c ← mass_c × scale     (composition ratios preserved)
mass_source = "load_cell_calibrated"
```

---

## 5. Model Design

| Item | Decision |
|---|---|
| Base model | `yolov8n-seg` (fast demo) → `yolov8s-seg` if accuracy needs it |
| Input size | 640 |
| Classes | 8 (see `architecture.md`) |
| Training | Transfer learning from COCO weights, ~50–100 epochs |
| Augmentation | Brightness/contrast, blur, rotation, mosaic, hue shift |
| Splits | Train 70 / val 20 / test 10, split by **source video or scene**, not by frame |
| Evaluation | mAP50, per-class precision/recall, plus **composition error** on test clips |
| Export | `.pt` for demo; ONNX for edge later |

**Why composition error matters more than mAP:** the product output is a composition percentage, so a model with a good mAP but a systematic bias on one class can still produce poor estimates.

---

## 6. Data Strategy

1. **Public sources:** RealWaste, Garbage Dataset V2, ZeroWaste (remap labels to taxonomy).
2. **Custom set:** Custom images of food waste and crop residue on a belt-like surface `data/custom/`.
3. **Calibration clips:** a few short videos with a known weighed composition, used to check mass estimates and tune thickness/density factors.
4. Record the dataset version and label mapping alongside each trained model.

---

## 7. Dashboard UX Design

### 7.1 Layout (single page, Streamlit)

```
┌───────────────────────────────────────────────────────────────┐
│  BioScan: Biomass Potential Estimator            [source ▼]   │
├───────────────────────────┬───────────────────────────────────┤
│                           │  CURRENT BATCH                    │
│   LIVE ANNOTATED FRAME    │  Mass: 12.4 kg   Objects: 38      │
│   (masks + class labels)  │  [ composition donut chart ]      │
│                           │                                   │
├───────────────────────────┼───────────────────────────────────┤
│  BIOGAS                   │  INCINERATION                     │
│  CH₄: 1.2 Nm³             │  Heat: 38 MJ                      │
│  Electricity: 4.5 kWh     │  Electricity: 2.3 kWh             │
│  range [3.1 – 5.9]        │  range [1.7 – 2.9]                │
├───────────────────────────┴───────────────────────────────────┤
│  RECOMMENDATION:  ● BIOGAS: organic-rich, low plastic         │
├───────────────────────────────────────────────────────────────┤
│  BATCH HISTORY (table + line chart)            [Download CSV] │
├───────────────────────────────────────────────────────────────┤
│  SIDEBAR: moisture ±, CHP eff., WTE eff., confidence threshold│
└───────────────────────────────────────────────────────────────┘
```

### 7.2 UX principles
- **Color encodes group:** green = organic, amber = combustible, grey = inert. Use the same colors for mask overlays and charts.
- **Ranges are always visible** next to point estimates.
- **Recommendation badge** uses color plus text (not color alone) for accessibility.
- **Sidebar sliders** update estimates immediately: this is the main "wow" moment in a live demo.
- Footer disclaimer: *"Screening estimate. Not a certified measurement."*

---

## 8. Error Handling

| Situation | Behavior |
|---|---|
| Video source fails to open | Show clear error; fall back to the sample video if configured |
| Empty belt (no detections) | Skip the batch; show "Waiting for material…" |
| Model file missing | Fail at startup with a message naming the expected path |
| Config value missing or invalid | Validate at load; report the offending key |
| Low average confidence in a batch | Flag the batch `low_confidence` and widen the range |

---

## 9. Testing Strategy

| Level | What | How |
|---|---|---|
| Unit | Energy math | Hand-calculated examples (e.g., 10 kg food waste → expected Nm³ CH₄) |
| Unit | Mass estimator | Synthetic masks with known pixel counts |
| Unit | Recommendation logic | Table-driven cases for each branch |
| Unit | Config validation | Missing and invalid keys |
| Integration | Pipeline on sample video | Assert a log row is produced with sane values |
| Model | Held-out test set | mAP50 and composition error against targets |
| Smoke | Dashboard | Launches and renders from the sample video |

---

## 10. Performance Notes

- Process every Nth frame rather than all frames.
- Use `yolov8n-seg` first. Move up only if accuracy requires it.
- Run inference in a worker thread so the UI stays responsive.
- Cache loaded config and model once per session.

---

## 11. Security and Ethics

- No personal data is captured. The ROI should exclude workers where possible, and any frames containing people must not be stored.
- Logs contain only aggregate numbers, not images, by default.
- Present outputs as estimates and never as guarantees of energy output.

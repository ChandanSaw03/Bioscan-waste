# BioScan: Development Phases

A phased plan that always keeps a **working demo** available. Each phase ends with something runnable. Time estimates assume a small team over a ~36–48 hour hackathon, followed by optional post-hackathon phases.

---

## Phase Overview

| Phase | Name | Output | Hackathon time |
|---|---|---|---|
| 0 | Setup and scoping | Repo, environment, decisions locked | 1–2 h |
| 1 | Data and baseline model | Trained 8-class segmentation model | 6–10 h |
| 2 | Pipeline core | Video → composition by mass | 5–7 h |
| 3 | Energy engine | Biogas and incineration estimates + recommendation | 4–5 h |
| 4 | Dashboard and logging | Live demo UI + CSV logs | 5–6 h |
| 5 | Calibration and polish | Tuned factors, tests, demo script | 4–5 h |
| 6 | Pitch preparation | Slides, narrative, backup demo | 2–3 h |
| 7+ | Post-hackathon | Hardware, edge, pilots | Later |

Phases 2 and 3 can run in parallel once the interfaces in `design.md` §2 are agreed.

---

## Phase 0: Setup and Scoping (1–2 h)

**Goals:** make the decisions that block everything else.

**Tasks**
- [ ] Create the repo with the layout from `architecture.md` §4
- [ ] Set up the virtual environment and `requirements.txt` (ultralytics, opencv-python, pandas, numpy, pyyaml, streamlit, plotly, pytest)
- [ ] Decide the demo waste scenario (municipal, agricultural, or both)
- [ ] Source or record 2–3 sample belt videos
- [ ] Assign roles (ML, pipeline/energy, UI/pitch)
- [ ] Agree on the class taxonomy and the interfaces in `design.md`

**Done when:** a fresh clone installs and runs a "hello world" that reads a video frame.

---

## Phase 1: Data and Baseline Model (6–10 h)

**Goals:** a detector that is *good enough*, not perfect.

**Tasks**
- [ ] Download TACO / TrashNet / ZeroWaste and remap labels to the 8 classes
- [ ] Collect and annotate a small custom set of food and agricultural waste
- [ ] Split by scene or video, not by frame
- [ ] Fine-tune `yolov8n-seg`
- [ ] Evaluate mAP50, per-class precision/recall, and a confusion matrix
- [ ] Save weights to `models/` and record the dataset version

**Fallback:** if segmentation labels are too costly, train a detection model (boxes) first and apply a box-fill-ratio correction to the area.

**Done when:** mAP50 ≥ 0.50 and organic vs. plastic are reliably separated on test images.

---

## Phase 2: Pipeline Core (5–7 h)

**Goals:** video in, composition by mass out.

**Tasks**
- [ ] `VideoSource` for file, webcam, and RTSP
- [ ] Belt ROI crop and `cm2_per_pixel` configuration
- [ ] `Detector` wrapper with a confidence threshold
- [ ] Tracking and counting-line logic
- [ ] `MassEstimator` using per-class factors
- [ ] `Batch` aggregation (time window and count modes)
- [ ] Unit tests for mass estimation and counting

**Done when:** running the pipeline on a sample video prints a composition table per batch.

---

## Phase 3: Energy Engine (4–5 h)

**Goals:** transparent, tested energy math.

**Tasks**
- [ ] Load and validate `waste_factors.yaml` and `energy.yaml`
- [ ] Biogas pathway (CH₄ Nm³ → kWh thermal → kWh electric)
- [ ] Incineration pathway (LHV → MJ → kWh)
- [ ] Low/mid/high uncertainty bounds
- [ ] Recommendation logic with human-readable reasons
- [ ] Optional load-cell scale hook (stub is acceptable for MVP)
- [ ] Unit tests with hand-calculated examples

**Done when:** a hard-coded composition produces expected numbers and the recommendation changes sensibly as composition changes.

---

## Phase 4: Dashboard and Logging (5–6 h)

**Goals:** a demo-ready interface.

**Tasks**
- [ ] Pandas log writer (CSV) with the schema in `architecture.md` §2.7
- [ ] Streamlit layout from `design.md` §7
- [ ] Live annotated frame with group colors
- [ ] Composition donut, energy panels with ranges, and recommendation badge
- [ ] Batch history table and trend chart
- [ ] Sidebar assumption sliders wired to the engine
- [ ] CSV download
- [ ] Run the pipeline in a worker thread so the UI stays responsive

**Done when:** `streamlit run app/dashboard.py` shows a live, updating dashboard from the sample video.

---

## Phase 5: Calibration and Polish (4–5 h)

**Goals:** credible numbers and a reliable demo.

**Tasks**
- [ ] Weigh a known staged mix and compare to the vision estimate; tune thickness and density factors
- [ ] Measure composition error on test clips against the NFR-4 target
- [ ] Cross-check energy outputs against literature ranges for sanity
- [ ] Add edge-case handling (empty belt, low confidence, missing config)
- [ ] Write the README with run instructions and the limitations section
- [ ] Record a **backup demo video** in case live hardware fails

**Done when:** all tests pass, the README is accurate, and the demo runs three times in a row without intervention.

---

## Phase 6: Pitch Preparation (2–3 h)

**Narrative outline**
1. **Problem:** cities waste energy potential because they can't see what's in their waste.
2. **Solution:** a camera turns a conveyor belt into a real-time energy meter.
3. **Demo:** live belt → composition → biogas vs. incineration → recommendation → change an assumption.
4. **How it works:** the pipeline diagram, with one slide on transparent, config-driven math.
5. **Honesty slide:** limitations and how load cells and local calibration close the gap.
6. **Impact and roadmap:** edge deployment, multi-site dashboards, CO₂-avoided reporting.

**Tasks**
- [ ] Slides (≤ 8)
- [ ] 2-minute demo script, rehearsed
- [ ] Prepared answers for likely questions (accuracy, moisture, real-world deployment, cost)

---

## Post-Hackathon Phases

### Phase 7: Pilot Readiness
- Local waste characterization audit to replace placeholder factors
- Larger, site-specific labeled dataset
- Load-cell integration and automatic calibration
- Model export to ONNX/TensorRT; test on Jetson or Raspberry Pi

### Phase 8: Plant Integration
- Multi-camera support
- PLC/SCADA or MQTT output of batch results
- SQLite or Postgres storage; authentication on the dashboard
- Alerts for contamination (batteries, hazardous items)

### Phase 9: Scale and Insight
- City-wide multi-facility dashboard
- Seasonal composition and yield forecasting
- Additional pathways (pyrolysis, RDF/pellets, composting)
- CO₂-avoided and carbon-credit reporting

---

## Milestone Checklist

- [ ] **M1:** Repo and environment working (end of Phase 0)
- [ ] **M2:** Model detects 8 classes on test images (end of Phase 1)
- [ ] **M3:** Video → composition table (end of Phase 2)
- [ ] **M4:** Composition → energy + recommendation (end of Phase 3)
- [ ] **M5:** Live dashboard demo (end of Phase 4)
- [ ] **M6:** Calibrated, tested, documented (end of Phase 5)
- [ ] **M7:** Pitch ready (end of Phase 6)

## Cut List (if time runs out)

Drop in this order, keeping the core demo intact:
1. Load-cell hook
2. RTSP support
3. SQLite (keep CSV)
4. Uncertainty bounds (keep point estimates, but state the limitation)
5. Count-mode batching (keep time-window)
6. Custom data collection (rely on public datasets plus augmentation)

**Never cut:** the energy math tests, the limitations statement, and the backup demo video.

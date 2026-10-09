# BioScan: Product Requirements Document (PRD)

**Product:** Vision-Based Biomass Potential Estimator
**Version:** 0.1 (hackathon MVP)
**Related docs:** `architecture.md`, `design.md`, `phases.md`, `rules.md`

---

## 1. Problem Statement

Cities and agri-processors receive mixed waste with no fast way to know how much usable energy it contains. Decisions about whether a load should go to a **biogas digester**, a **waste-to-energy incinerator**, or be **rejected or sorted first** are made on gut feel or slow lab analysis (days, per-sample, expensive).

Consequences:
- Digesters get contaminated with plastics or starved of organics.
- Incinerators receive wet, low-calorific loads that waste fuel.
- Planners can't forecast energy output or size renewable energy infrastructure with real data.

## 2. Product Vision

A camera over a conveyor belt that tells operators, **in near real time**, what a waste batch is made of and how much energy it could produce via biogas or incineration, so each load is routed to its best use.

## 3. Target Users

| Persona | Needs | How BioScan helps |
|---|---|---|
| **City planner / municipal engineer** | Forecast renewable energy from waste streams | Aggregated composition and energy logs over time |
| **Plant operator** | Route each load correctly, avoid contamination | Per-batch recommendation: biogas / incineration / reject |
| **Agri-processing manager** | Value crop residue and food waste | Biogas yield estimate for organic-heavy loads |
| **Sustainability / ESG analyst** | Evidence for waste-to-energy projects | Exportable, timestamped composition and yield data |
| **Hackathon judge** | Clear demo, technical depth, real impact | Live demo with adjustable assumptions |

## 4. Goals and Non-Goals

### Goals (MVP)
1. Detect and patch-classify waste items from an image/video using a grid into 7 classes (+ hazards).
2. Estimate batch composition by **mass percentage**.
3. Estimate energy potential for **both** biogas and incineration, with a low/mid/high range.
4. Recommend a pathway per batch.
5. Log every batch and visualize it in a live dashboard.
6. Run end-to-end from a recorded video (no hardware required).

### Non-Goals (MVP)
- Certified or regulatory-grade measurement.
- Robotic sorting or physical diversion of waste.
- Chemical analysis (e.g., actual biochemical methane potential tests).
- Hazardous or medical waste handling.
- Multi-camera or plant-wide orchestration.

## 5. User Stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-1 | Operator | see live composition of waste on the belt | I know what's arriving now |
| US-2 | Operator | get a routing recommendation per batch | I send it to the right process |
| US-3 | Planner | see estimated kWh from biogas vs. incineration | I can compare options |
| US-4 | Planner | download batch logs as CSV | I can analyze trends offline |
| US-5 | Analyst | adjust moisture and efficiency assumptions | I can test scenarios |
| US-6 | Operator | see confidence ranges, not a single number | I understand the uncertainty |
| US-7 | Developer | change waste factors in config without code edits | I can calibrate to local waste |
| US-8 | Judge | run the demo from a sample video | I can evaluate without hardware |

## 6. Functional Requirements

### 6.1 Capture and Perception
- **FR-1** Accept input from a webcam, a video file, or an RTSP stream via FastAPI backend.
- **FR-2** Crop to a configurable belt region and tile it into a grid (e.g. 224x224 patches).
- **FR-3** Detect and classify tiles into the 7-class taxonomy (+ hazards).
- **FR-4** Discard tiles below a configurable confidence threshold (default 0.35).
- **FR-5** Aggregate tile data into batch estimates.

### 6.2 Estimation
- **FR-6** Convert each object's mask area to estimated mass using per-class thickness and density factors.
- **FR-7** Aggregate masses into batches by time window or object count.
- **FR-8** Output composition by class and by group (organic / combustible / inert).
- **FR-9** Compute biogas yield (Nm³ CH₄) and electricity (kWh) per batch.
- **FR-10** Compute incineration heat (MJ / kWh thermal) and electricity (kWh) per batch.
- **FR-11** Provide low/mid/high bounds for each energy estimate.
- **FR-12** Produce a recommendation: `biogas`, `incineration`, `mixed`, or `reject`, with a one-line reason.

### 6.3 Configuration
- **FR-13** All waste factors (density, thickness, moisture, VS, BMP, LHV) are editable in YAML.
- **FR-14** Efficiencies, batch window, and uncertainty bounds are editable in YAML.
- **FR-15** Optional load-cell input rescales total mass while preserving composition ratios.

### 6.4 Logging and Output
- **FR-16** Append each batch to a persistent log (CSV by default).
- **FR-17** Dashboard shows live annotated frame, composition chart, energy gauges, and batch history.
- **FR-18** Dashboard allows adjusting key assumptions at runtime.
- **FR-19** Users can download the log as CSV.

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Inference throughput | ≥ 5 FPS on a laptop (GPU preferred, CPU acceptable at reduced FPS) |
| NFR-2 | End-to-end batch latency | Result shown within 5 s of batch end |
| NFR-3 | Detection quality | mAP50 ≥ 0.60 on the held-out set (MVP target) |
| NFR-4 | Composition accuracy | Mean absolute error ≤ 15 percentage points per group on test clips |
| NFR-5 | Setup | Runs from a clean clone in ≤ 15 minutes using `requirements.txt` |
| NFR-6 | Transparency | Every energy number traceable to a config factor |
| NFR-7 | Reproducibility | Fixed seeds; model version recorded in each log row |
| NFR-8 | Offline operation | No cloud dependency at runtime |

## 8. Success Metrics

**Hackathon**
- Live demo runs end-to-end without manual intervention.
- Judges can change an assumption and see the estimate update.
- Clear before/after story: "gut feel" vs. quantified batch estimate.

**Technical**
- NFR-3 and NFR-4 met on the test set.
- Energy engine unit tests pass against hand-calculated examples.

**Product (post-hackathon)**
- Estimated vs. measured energy within ±25% after local calibration.
- Operators accept the recommendation in most of the pilot batches.

## 9. Assumptions and Constraints

- A single top-down camera with fixed, even lighting.
- Waste is spread in roughly **one layer** on the belt.
- Per-class factors come from literature and must be recalibrated locally.
- Hackathon timeframe limits custom data collection to a small set.
- Hardware may be unavailable, so recorded video is the primary demo path.

## 10. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Not enough labeled food/agri waste images | Poor organic detection | High | Merge datasets, augment, collect a small custom set |
| Area-to-mass error | Wrong energy estimate | High | Ranges, load-cell option, clear disclaimers |
| Occlusion on a crowded belt | Under-counting | Medium | Single-layer spreading; widen uncertainty |
| Tracking double counts | Inflated mass | Medium | Counting line; belt-displacement fallback |
| Literature factors don't match local waste | Biased estimates | Medium | Config-driven, calibration notebook |
| Overclaiming accuracy | Credibility loss | Medium | Position as a *screening estimator* |

## 11. Out of Scope but on the Roadmap

- Load-cell and moisture-sensor fusion
- Additional pathways (pyrolysis, RDF/pellets, composting)
- Edge deployment (Jetson / Raspberry Pi)
- City-wide dashboard across multiple facilities
- Carbon-credit and CO₂-avoided reporting
- Contamination alerts (e.g., batteries or hazardous items)

## 12. Open Questions

1. What waste mix is the demo targeting: municipal solid waste, agricultural residue, or both?
2. Is a physical belt available, or will the demo use recorded or staged video?
3. Which region's waste data should the default factors reflect?
4. Is a GPU available on the demo machine?

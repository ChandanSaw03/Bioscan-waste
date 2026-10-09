# ♻️ BioScan: Biomass Potential Estimator

**A vision-based screening tool that estimates the energy-generation potential of municipal waste.**

A camera looks at waste on a conveyor belt. BioScan identifies what the waste is made of, estimates the composition by mass, and calculates how much energy the batch could yield through **biogas (anaerobic digestion)** or **incineration (waste-to-energy)**. It then recommends where the batch should go.

> ⚠️ **Screening estimate. Not a certified measurement.** All energy factors are literature-based placeholders and must be calibrated against local waste data before any real-world use.

---

## Why this matters

Cities and processors usually don't know how much energy their waste contains until lab analysis, which is slow and expensive. Sending the wrong load to the wrong process wastes energy: plastic contaminates digesters, and wet food waste lowers the efficiency of incinerators. BioScan gives a fast, transparent first estimate so each batch can be routed to its best use.

---

## How it works

```
Video / image
     │
     ▼
Frame sampling + belt crop (OpenCV)
     │
     ▼
Tile each frame into a grid → classify every tile (YOLOv8-cls)
     │
     ▼
Composition by area → mass (per-class thickness and density, from config)
     │
     ▼
Energy engine: biogas path + incineration path, each with low / mid / high
     │
     ▼
Recommendation (biogas / incineration / mixed / reject) + reason
     │
     ▼
FastAPI  →  Streamlit dashboard  →  CSV log
```

### Waste classes

| BioScan class | Source label (Garbage Dataset V2) | Energy relevance |
|---|---|---|
| `food_organic` | biological | Main biogas feedstock |
| `paper_cardboard` | paper, cardboard | Incineration, minor biogas |
| `plastic` | plastic | Very high incineration value, no biogas |
| `textile` | clothes, shoes | Incineration |
| `metal` | metal | None (recovery) |
| `glass_inert` | glass | None |
| `residual` | trash | Low-value mixed waste |
| ⚠ hazard flag | battery | Never counted in energy; raises an alert |

### Energy model

**Biogas**
```
CH4 (Nm³)  = Σ mass × (1 − moisture) × VS_fraction × BMP
Thermal    = CH4 × 9.97 kWh/Nm³
Electric   = Thermal × CHP efficiency
```

**Incineration**
```
Heat (MJ)  = Σ mass × LHV
Thermal    = MJ / 3.6
Electric   = Thermal × WTE efficiency
```

Every estimate is returned as **low / mid / high**. All factors live in `config/*.yaml` and can be edited without touching code.

---

## Quick start (Docker)

**Requirements:** Docker with the Compose plugin (on Windows, Docker Desktop with WSL integration).

```bash
git clone https://github.com/<your-username>/bioscan.git
cd bioscan

# optional: add a short belt/mixed-waste clip (MP4, under 60 s) for demos
cp /path/to/your_clip.mp4 data/samples/

docker compose up --build
```

Then open **http://localhost:8501**, upload a video or image, and use the sidebar to adjust moisture and efficiency assumptions. The estimates update with your changes.

The API runs on port `8000` inside the Compose network.

### Run without Docker

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn bioscan.api:app --port 8000          # adjust module path to match the repo
streamlit run app/dashboard.py               # adjust path to match the repo
```

---

## Using the dashboard

1. Upload an MP4, JPG or PNG (up to 200 MB).
2. View the composition, the biogas and incineration estimates with ranges, and the recommendation.
3. Move the sidebar sliders (moisture offset, CHP efficiency, WTE efficiency) to see how the estimate responds.
4. Review **Batch History** and download the log as CSV.

## API

```bash
curl -X POST http://localhost:8000/analyze -F "file=@data/samples/clip.mp4"
```

Returns JSON with the composition, energy estimates (low/mid/high), the recommendation, and a reason string.

---

## Configuration

| File | Contents |
|---|---|
| `config/classes.yaml` | Label mapping from dataset classes to BioScan classes |
| `config/waste_factors.yaml` | Density, thickness, moisture, volatile solids, BMP, LHV per class |
| `config/energy.yaml` | CHP and WTE efficiency, batch window, uncertainty bounds, thresholds |
| `config/camera.yaml` | Belt region, scale (cm² per pixel), frame rate |

> The factors are **placeholders from published literature ranges**, not measurements from your site.

---

## Deploy on AWS (EC2)

1. Launch an **Ubuntu 24.04** EC2 instance (**t3.large** or larger; 8 GB RAM, 30 GB disk). Smaller instances run out of memory when building the image.
2. Security group: allow **SSH (22)** from your IP only, and **TCP 8501** for the dashboard. Do not expose port 8000.
3. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # then log out and back in
   ```
4. Deploy:
   ```bash
   git clone https://github.com/<your-username>/bioscan.git
   cd bioscan
   docker compose up -d --build
   ```
5. Open `http://<EC2-public-IP>:8501`.

Stop the instance when you are not demoing, and set an AWS budget alert.

---

## Project structure

> Adjust this section to match your repository.

```
bioscan/
├── app/                 # Streamlit dashboard
├── bioscan/             # API, pipeline, classifier, mass and energy modules
├── config/              # YAML configuration
├── data/
│   └── samples/         # demo clips
├── models/              # trained weights
├── tests/               # pytest suite
├── docs/                # architecture, PRD, design, phases, rules
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

Detailed design lives in [`docs/`](docs/): `architecture.md`, `prd.md`, `design.md`, `phases.md`, `rules.md`.

---

## Results

> Fill this in with **measured** numbers from your evaluation run. Do not report figures you did not measure.

| Metric | Value |
|---|---|
| Test accuracy (Garbage Dataset V2 split) | _TBD_ |
| Accuracy on belt-style validation images | _TBD_ |
| Per-class precision / recall | _see evaluation output_ |

---

## Limitations

- **Area is not mass.** A camera sees surface area, not weight. Mass comes from per-class thickness and density factors, so absolute values can be far off until calibrated. A load cell would fix this.
- **Domain gap.** The training data is mostly single items on clean backgrounds, while real belts show cluttered piles. Accuracy on real belt footage is expected to be lower than on the test split.
- **Occlusion.** Material buried under other material is invisible to a top-down camera.
- **Moisture** varies widely and strongly affects both pathways. Use the sidebar slider to explore it.
- **Municipal waste only.** Agricultural residue and wood are out of scope.
- **Placeholder factors.** Energy parameters are not site-calibrated.

## Roadmap

- Load-cell calibration of total mass
- Instance segmentation (YOLOv8-seg) for more precise areas
- Live camera mode on an edge device (Jetson / Raspberry Pi) sending results to the cloud dashboard
- Moisture sensing, and calibration with local waste audits
- Multi-site dashboard and CO₂-avoided reporting

---

## Tech stack

Python · OpenCV · Ultralytics YOLOv8 · Pandas · FastAPI · Streamlit · Docker · AWS EC2

## Data and licenses

Trained on the **Garbage Dataset V2** (Kaggle), found through the [waste-datasets-review](https://github.com/AgaMiko/waste-datasets-review) list. Check the dataset's license before any commercial use. Raw datasets are not included in this repository.

## Disclaimer

BioScan is a hackathon prototype for screening-level estimates. It must not be used for billing, regulatory reporting, or safety-critical decisions.

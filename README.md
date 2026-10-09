# BioScan: Vision-Based Biomass Energy Potential Estimator

BioScan turns a video feed or image of a conveyor belt into an energy estimate, using patch-based YOLOv8-cls grid classification to determine waste composition and calculate the energetic pathways for biogas and incineration.

## Stack
- **Backend:** FastAPI (Python 3.10+) 
- **Frontend:** Streamlit
- **Model:** Ultralytics YOLOv8-cls (CPU compatible)
- **Deployment:** Docker & Docker Compose (AWS EC2 ready via S3 upload hook)

---

## 🚀 Quickstart (Docker)

To run the whole pipeline with Docker, you just need Docker and Docker Compose installed.

1. **Build and Run**
   ```bash
   docker-compose up --build
   ```
2. **Access the Application**
   - **Streamlit Dashboard:** http://localhost:8501
   - **FastAPI Backend Swagger:** http://localhost:8000/docs
   
3. **AWS EC2 / S3 Integration (Optional)**
   If you configure an IAM profile on your EC2 instance, you can automatically backup your video process runs and log CSVs to S3 by adding the Env variable to your shell before starting:
   ```bash
   export BIOSCAN_S3_BUCKET="my-s3-logging-bucket"
   docker-compose up -d
   ```

---

## 🛠 Local Development (No Docker)

1. **Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the Backend (Port 8000)**
   ```bash
   uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Run the Frontend (Port 8501)**
   ```bash
   streamlit run app/dashboard.py
   ```

---

## 🧠 Data Processing & Training

Wait to run tests and train the model locally! 
Ensure datasets are placed correctly (or you download `RealWaste` with Kaggle). 

**Prepare the Datasets:**
```bash
# Remap Garbage Dataset V2
python scripts/remap_garbage_v2.py
# Download and Remap RealWaste
python scripts/download_realwaste.py --kaggle
# Prepare Yolo splits
python scripts/prepare_dataset.py
```

**Train the Tile Classifier (on CPU or GPU):**
```bash
python scripts/train_classifier.py --epochs 50 --imgsz 224 --data data/classifier_dataset
```
*(The best model is automatically saved to `models/tile_classifier_best.pt` upon completion.)*

---

## 🧪 Testing

We use `pytest` to guarantee the behavior of the internal calculations (Mass, Time Aggregation, and Energy logic).

```bash
pytest
```

---

## ⚠️ Limitations & Disclaimers
**Screening Estimate.** Not a certified measurement. Measurements reflect estimates computed by visual tiling proportions scaling average bulk physical properties (Moisture, Thickness, VS Fraction). Real deployment logic dictates replacing `config/waste_factors.yaml` placeholders with local audited waste characteristics. 

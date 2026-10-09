"""Streamlit Dashboard for BioScan.

Matches the UX design specified in docs/design.md section 7.
Connects to the FastAPI backend at http://localhost:8000.
"""

import base64
import os
import io

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.environ.get("BIOSCAN_API_URL", "http://localhost:8000")


st.set_page_config(
    page_title="BioScan | Biomass Potential Estimator",
    page_icon="♻️",
    layout="wide",
)

# -----------------------------------------------------------------------------
# CSS Styling & layout
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* BioScan Color Theme */
    .metric-box {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 5px 0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #A0A0A0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-range {
        font-size: 0.9rem;
        color: #6c757d;
    }
    .badge {
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
        margin-top: 10px;
        color: white;
    }
    .badge-bg-biogas { background-color: #2e7d32; }
    .badge-bg-incineration { background-color: #f57c00; }
    .badge-bg-mixed { background-color: #1565c0; }
    .badge-bg-reject { background-color: #d32f2f; }
    .disclaimer {
        text-align: center;
        color: #888;
        font-style: italic;
        margin-top: 50px;
        padding-top: 20px;
        border-top: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def parse_response(result: dict) -> None:
    """Load API result into session state."""
    st.session_state["result"] = result
    # Initialize slider defaults based on the API response or standard defaults if missing
    if "sliders" not in st.session_state:
        st.session_state["sliders"] = {
            "moisture_offset": 0.0,
            "chp": 0.38,
            "wte": 0.22,
        }

def recalculate_energy() -> None:
    """Ping the /recalculate endpoint when sliders change."""
    res = st.session_state.get("result")
    if not res:
        return
        
    payload = {
        "mass_by_class": res["mass_by_class"],
        "hazard_flags": res["hazard_flags"],
        "moisture_offset": st.session_state.moisture_offset_slider,
        "chp_efficiency": st.session_state.chp_slider,
        "wte_efficiency": st.session_state.wte_slider,
    }
    
    try:
        req = requests.post(f"{API_URL}/recalculate", json=payload)
        if req.status_code == 200:
            data = req.json()
            # Update only energy and recommendation
            st.session_state["result"]["energy"] = data["energy"]
            st.session_state["result"]["recommendation"] = data["recommendation"]
            st.session_state["result"]["reason"] = data["reason"]
        else:
            st.error(f"Recalculation error: {req.text}")
    except requests.exceptions.RequestException:
        st.error("Cannot reach the API. Is it running?")


def make_donut_chart(fractions: dict) -> go.Figure:
    """Plotly composition donut chart."""
    labels = list(fractions.keys())
    values = list(fractions.values())
    
    # Simple color mapping for design.md
    colors = {
        "food_organic": "#66bb6a",
        "agri_residue": "#81c784",
        "paper_cardboard": "#ffb74d",
        "plastic": "#ff9800",
        "textile": "#f57c00",
        "metal": "#9e9e9e",
        "glass_inert": "#757575",
    }
    marker_colors = [colors.get(c, "#aaaaaa") for c in labels]

    fig = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=.5,
        marker=dict(colors=marker_colors)
    )])
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    return fig


def render_metric_box(title: str, val1_labels: tuple, val2_labels: tuple) -> None:
    """HTML block for an energy metric box."""
    v1_title, v1_mid, v1_rng = val1_labels
    v2_title, v2_mid, v2_rng = val2_labels
    
    html = f"""
    <div class="metric-box">
        <h3 style="margin-top: 0;">{title}</h3>
        <div style="display: flex; justify-content: space-between;">
            <div>
                <div class="metric-label">{v1_title}</div>
                <div class="metric-value">{v1_mid}</div>
                <div class="metric-range">{v1_rng}</div>
            </div>
            <div>
                <div class="metric-label">{v2_title}</div>
                <div class="metric-value">{v2_mid}</div>
                <div class="metric-range">{v2_rng}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Main UI
# -----------------------------------------------------------------------------

st.title("♻️ BioScan: Biomass Potential Estimator")

# Sidebar
st.sidebar.header("Assumptions & Adjustments")
st.sidebar.markdown("Test the engine's sensitivity in real time.")
st.sidebar.slider("Moisture Offset (absolute)", -0.20, 0.20, 0.0, 0.01, key="moisture_offset_slider", on_change=recalculate_energy)
st.sidebar.slider("Biogas CHP Efficiency", 0.20, 0.60, 0.38, 0.01, key="chp_slider", on_change=recalculate_energy)
st.sidebar.slider("Incineration WTE Efficiency", 0.10, 0.40, 0.22, 0.01, key="wte_slider", on_change=recalculate_energy)

# File uploader
st.write("Upload a conveyor-belt sample video or image to analyze.")
uploaded_file = st.file_uploader("Choose a file", type=["mp4", "jpg", "jpeg", "png"])

if uploaded_file is not None:
    if st.button("Analyze File", type="primary"):
        with st.spinner("Processing through the pipeline..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                res = requests.post(f"{API_URL}/analyze", files=files)
                if res.status_code == 200:
                    parse_response(res.json())
                else:
                    st.error(f"API Error: {res.status_code} - {res.text}")
            except requests.exceptions.RequestException:
                st.error("Cannot reach the API. Is it running?")

# If we have a result, render the dashboard
if "result" in st.session_state:
    data = st.session_state.result
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Live Annotated Frame")
        if data.get("annotated_frame_b64"):
            img_bytes = base64.b64decode(data["annotated_frame_b64"])
            st.image(img_bytes, use_column_width=True)
        else:
            st.info("No frame available.")
            
        if data.get("hazard_flags"):
            st.warning(f"⚠️ Hazards Detected: {', '.join(data['hazard_flags'])}")
            
    with col2:
        st.subheader("Current Batch (id: {data['batch_id']})")
        st.write(f"**Total Mass:** {data['total_mass_kg']:.1f} kg")
        st.plotly_chart(make_donut_chart(data["fractions"]), use_container_width=True)
        
    st.markdown("---")
    
    # Energy Panels
    eco1, eco2 = st.columns(2)
    
    bg = data["energy"]["biogas"]
    wte = data["energy"]["incineration"]
    
    with eco1:
        v1 = ("CH₄ (Nm³)", f"{bg['ch4_nm3']['mid']:.1f}", f"[{bg['ch4_nm3']['low']:.1f} - {bg['ch4_nm3']['high']:.1f}]")
        v2 = ("Electricity (kWh)", f"{bg['elec_kwh']['mid']:.1f}", f"[{bg['elec_kwh']['low']:.1f} - {bg['elec_kwh']['high']:.1f}]")
        render_metric_box("Biogas", v1, v2)
        
    with eco2:
        v1 = ("Heat (MJ)", f"{wte['heat_mj']['mid']:.1f}", f"[{wte['heat_mj']['low']:.1f} - {wte['heat_mj']['high']:.1f}]")
        v2 = ("Electricity (kWh)", f"{wte['elec_kwh']['mid']:.1f}", f"[{wte['elec_kwh']['low']:.1f} - {wte['elec_kwh']['high']:.1f}]")
        render_metric_box("Incineration", v1, v2)

    # Recommendation Badge
    rec = data["recommendation"]
    reason = data["reason"]
    badge_class = f"badge-bg-{rec}"
    st.markdown(f'<div class="badge {badge_class}">RECOMMENDATION: {rec.upper()}</div>', unsafe_allow_html=True)
    st.write(f"*{reason}*")


# Batch History & Download
st.markdown("---")
st.subheader("Batch History")

log_path = "logs/batches.csv"
if os.path.exists(log_path):
    try:
        df = pd.read_csv(log_path)
        st.dataframe(df.tail(10))
        
        # Download button
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Log CSV",
            data=csv_buffer.getvalue(),
            file_name="bioscan_batches.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.write("Could not load history.")
else:
    st.info("No batches logged yet.")

st.markdown('<div class="disclaimer">Screening estimate. Not a certified measurement.</div>', unsafe_allow_html=True)

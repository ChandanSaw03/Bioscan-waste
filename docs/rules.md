# BioScan: Project Rules

Rules for everyone working on this repo: teammates and AI coding assistants alike. Read `architecture.md` and `design.md` first. When a rule here conflicts with a convenient shortcut, the rule wins.

---

## 1. Core Principles

1. **Transparency over cleverness.** Every energy number must trace back to a named factor in `config/`. No hidden constants.
2. **Honesty over polish.** Always report ranges, and always label output as a *screening estimate*. Never claim certified or guaranteed accuracy.
3. **Config over code.** Waste factors, efficiencies, thresholds, and camera settings live in YAML, never hard-coded.
4. **A working demo at all times.** Never leave `main` in a state where the sample video demo fails.
5. **Small, testable modules.** Each pipeline stage depends only on the previous stage's output type.

---

## 2. Scope Rules

- Build only what is in `prd.md` §6 (functional requirements) for the MVP.
- Do not add new waste classes, pathways, or hardware integrations without updating `architecture.md` and `prd.md` first.
- Do not add physical sorting or actuation, hazardous or medical waste handling, or any claim of regulatory-grade measurement.
- If a task is ambiguous, state the assumption in the PR or commit message rather than silently choosing.

---

## 3. Code Style

- **Python 3.10+**, formatted with `black` (line length 100) and linted with `ruff`.
- Type hints on all public functions. Use `dataclass` for data containers, as defined in `design.md` §2.
- Docstrings (one-line minimum) on every public class and function, stating **units** for any physical quantity.
- Names: `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants.
- No wildcard imports. No unused code left behind.
- Prefer pure functions for calculations (mass, energy). Keep I/O at the edges of the pipeline.

### Units (mandatory)
Encode units in names or docstrings and never mix them silently.

| Quantity | Unit | Naming |
|---|---|---|
| Mass | kg | `mass_kg` |
| Area | cm² | `area_cm2` |
| Length / thickness | cm | `thickness_cm` |
| Density | g/cm³ | `density_g_cm3` |
| Volume of methane | Nm³ | `ch4_nm3` |
| Heating value | MJ/kg | `lhv_mj_per_kg` |
| Energy | kWh (electric / thermal stated) | `elec_kwh`, `thermal_kwh` |
| Fractions | 0–1, never 0–100 | `moisture`, `vs_fraction` |

Percentages appear only in the UI layer; all internal values are fractions.

---

## 4. Energy and Science Rules

- **Never invent numbers.** Every default in `waste_factors.yaml` and `energy.yaml` must be a placeholder from published literature ranges and commented as such. Cite the source in a comment or in `docs/sources.md` when known.
- Keep **wet-basis vs. dry-basis** explicit. LHV values are wet-basis; BMP applies to volatile solids (VS) of dry mass.
- Always compute **low / mid / high**. A single number must never be shown without its range.
- Both pathways (biogas and incineration) are computed for every batch.
- The recommendation logic must return a **reason string**. Never return a bare label.
- Any change to the energy formulas requires an updated unit test with a hand-calculated expected value.
- If load-cell calibration is applied, set `mass_source = "load_cell_calibrated"`. Otherwise it stays `"vision"`.

---

## 5. ML and Data Rules

- **Split by scene or source video, never by frame.** Frame-level splits leak data and inflate metrics.
- Record, for every trained model: dataset version, label mapping, training config, and metrics. Store the model version in every log row.
- Keep the test set **untouched** until final evaluation. Do not tune on it.
- Report **composition error** (percentage-point error per group) alongside mAP. mAP alone does not measure what the product outputs.
- Respect dataset licenses. Do not commit raw third-party datasets to git; commit download or remap scripts instead.
- Never commit images containing identifiable people. Crop or blur if present.
- Set random seeds for training and evaluation.

---

## 6. Pipeline Rules

- Each object is counted **once** (counting-line logic). Do not sum per-frame masses.
- Use the largest observed mask per tracked object when estimating its mass.
- Detections below `min_confidence` are discarded, and batches with a low average confidence are flagged `low_confidence` with a widened range.
- Empty belt means no batch is logged. Do not write zero-mass rows.
- The pipeline must run from a video **file** with no hardware attached.
- Never block the UI thread with inference. Use a worker thread or process.

---

## 7. Configuration Rules

- Validate all config at load time and fail fast with a message naming the missing or invalid key.
- Do not read config values from scattered places. Load once and pass objects explicitly.
- Fractions in config must be within [0, 1]. Reject anything else.
- Config changes that alter results should be noted in the commit message.

---

## 8. Logging and Output Rules

- Log schema follows `architecture.md` §2.7. Adding or renaming columns requires updating that section.
- Logs contain **aggregate numbers only**, with no raw frames by default.
- The CSV must always be loadable with `pandas.read_csv` without special handling.
- The dashboard footer must keep the disclaimer: *"Screening estimate. Not a certified measurement."*

---

## 9. Testing Rules

- Run `pytest` before every merge to `main`.
- Required tests: energy math (hand-calculated), mass estimator, recommendation branches, config validation, and a pipeline smoke test on the sample video.
- Tests must not require a GPU, a webcam, or internet access.
- A bug fix includes a regression test.

---

## 10. Git and Collaboration Rules

- Branch names: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`.
- Commit messages: imperative mood, e.g. `Add biogas pathway with uncertainty bounds`.
- Keep PRs small and focused, with a one-paragraph description and a note on what was tested.
- Do not commit model weights over 50 MB to git. Use Git LFS or a download script.
- Do not commit secrets, API keys, or personal data.
- `main` stays demo-ready. Work-in-progress goes on branches.

---

## 11. Documentation Rules

- The five docs (`architecture.md`, `prd.md`, `design.md`, `phases.md`, `rules.md`) are the source of truth. Update them in the **same PR** as any change that contradicts them.
- README must always contain: install steps, how to run the demo, how to run tests, and the limitations section.
- Document every assumption that affects numeric results.

---

## 12. Rules for AI Coding Assistants

When generating or modifying code in this repo:

1. Read `architecture.md` and `design.md` before writing code. Follow the module interfaces exactly.
2. Do not hard-code waste factors, efficiencies, or thresholds. Read them from config.
3. Do not fabricate datasets, benchmark results, or accuracy numbers. If a value is unknown, leave a clearly marked placeholder or ask.
4. Preserve units and naming conventions from §3.
5. Add or update tests whenever energy, mass, or recommendation logic changes.
6. Keep changes minimal and scoped to the request. Do not refactor unrelated files.
7. Do not add dependencies without noting why in the PR and updating `requirements.txt`.
8. When uncertain about scope, check `prd.md` §4 (non-goals) before adding a feature.
9. Never remove the uncertainty ranges or the disclaimer to make output look cleaner.

---

## 13. Definition of Done

A task is done when:
- [ ] It meets the relevant requirement in `prd.md`
- [ ] It follows the interfaces in `design.md`
- [ ] Tests are added or updated and passing
- [ ] No hard-coded factors or unit mix-ups
- [ ] Docs updated if behavior or structure changed
- [ ] The sample-video demo still runs end to end

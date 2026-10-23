# SETUP_REPORT (2026-10-23, WSL2 Ubuntu 26.04, Python 3.11.17 via uv)
- torch 2.11.0+cu128: PASS (cuda=True, sm_120 in arch list)
- XGBoost 3.2.0 device=cuda hist: PASS (removed conflicting xgboost-cpu pkg)
- CatBoost 1.2.10 task_type=GPU: PASS
- LightGBM 4.7.0 CPU n_jobs=-1: PASS (no system libgomp1 & no sudo: venv activate adds torch/lib to LD_LIBRARY_PATH; proper fix: sudo apt install libgomp1)
- TabPFN 8.2.0: PASS (GPU, 18s; license accepted, TABPFN_TOKEN in .env auto-loaded by venv activate)
- TabICL: PASS (GPU, 21s)
- AutoGluon presets=extreme time_limit=120: PASS (no OOM, 3 models in 120s on toy data)
- HF deberta-v3-base bf16, 20-40 steps: PASS on transformers 4.57.6. transformers 5.20 made DeBERTa loss go UP (roberta was fine on 5.x), so pinned <5 (hub 0.36.2; only synthefy-nori complains)

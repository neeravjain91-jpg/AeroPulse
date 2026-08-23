"""Optional RUL methodology validation using NASA C-MAPSS style files.

This script is intentionally separate from the MALE-UAV runtime model because
C-MAPSS is a turbofan degradation benchmark, not aero-piston-engine data. It
validates the modelling *method*, not target-engine accuracy.

Expected input directory example (FD001):
  train_FD001.txt
  test_FD001.txt
  RUL_FD001.txt
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

parser = argparse.ArgumentParser()
parser.add_argument("--cmapss-dir", required=True)
parser.add_argument("--subset", default="FD001")
parser.add_argument("--rul-cap", type=float, default=125.0)
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(args.cmapss_dir).expanduser().resolve()
OUT = ROOT / "models"
OUT.mkdir(exist_ok=True)

columns = (
    ["unit", "cycle"]
    + [f"setting_{i}" for i in range(1, 4)]
    + [f"sensor_{i}" for i in range(1, 22)]
)
train_path = DATA / f"train_{args.subset}.txt"
test_path = DATA / f"test_{args.subset}.txt"
rul_path = DATA / f"RUL_{args.subset}.txt"

train = pd.read_csv(train_path, sep=r"\s+", header=None, names=columns)
test = pd.read_csv(test_path, sep=r"\s+", header=None, names=columns)
true_extra = pd.read_csv(rul_path, sep=r"\s+", header=None, names=["extra_rul"])

max_cycle = train.groupby("unit")["cycle"].transform("max")
train["RUL"] = (max_cycle - train["cycle"]).clip(upper=args.rul_cap)

# Remove nearly constant sensors in the training benchmark.
feature_candidates = columns[2:]
std = train[feature_candidates].std()
features = [name for name in feature_candidates if float(std[name]) > 1e-8]
# Cycle itself is useful as a degradation-progress covariate.
features = ["cycle"] + features

model = RandomForestRegressor(
    n_estimators=220,
    max_depth=22,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1,
)
model.fit(train[features], train["RUL"])

# C-MAPSS test truth gives RUL after the final observed test cycle for each unit.
# Evaluate predictions only at each unit's final observed point.
last_rows = test.sort_values(["unit", "cycle"]).groupby("unit").tail(1).copy()
last_rows = last_rows.sort_values("unit")
last_rows["true_RUL"] = true_extra["extra_rul"].to_numpy()[: len(last_rows)]
pred = model.predict(last_rows[features])

mae = float(mean_absolute_error(last_rows["true_RUL"], pred))
rmse = float(mean_squared_error(last_rows["true_RUL"], pred) ** 0.5)
metrics = {
    "subset": args.subset,
    "mae_cycles": mae,
    "rmse_cycles": rmse,
    "rul_cap_cycles": args.rul_cap,
    "features": features,
    "domain_note": "NASA C-MAPSS is turbofan data. These metrics validate an RUL methodology, not MALE-UAV aero-piston-engine RUL accuracy.",
}

joblib.dump(
    {
        "model": model,
        "features": features,
        "subset": args.subset,
        "domain": "NASA C-MAPSS turbofan methodology validation only",
    },
    OUT / "cmapss_rul_method.joblib",
)
(OUT / "cmapss_rul_metrics.json").write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics, indent=2))

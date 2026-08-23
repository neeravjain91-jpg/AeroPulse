from __future__ import annotations

from pathlib import Path
import argparse
import json
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

parser = argparse.ArgumentParser(description="Train AeroPulse-X models")
parser.add_argument("--data-dir", required=True, help="Path to FINAL_DATASET directory")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(args.data_dir).expanduser().resolve()
if (DATA / "FINAL_DATASET").exists():
    DATA = DATA / "FINAL_DATASET"
OUT = ROOT / "models"
SAMPLE_OUT = ROOT / "data_sample"
OUT.mkdir(exist_ok=True)
SAMPLE_OUT.mkdir(exist_ok=True)
metrics: dict = {}

# Rich ACES feature set. These are raw/measured fields only; robust anomaly score
# and derived sigma columns are intentionally excluded to prevent target leakage.
rich_features = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "CHT", "Fuel_Flow",
    "Oil_Temp", "Oil_Pressure", "Battery_Voltage", "Battery_Current",
    "Alternator_Temp", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    "Operating_State",
]
legacy_features = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "Fuel_Flow", "Oil_Temp",
    "Oil_Pressure", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    "Operating_State",
]

aces_health_path = DATA / "ACES" / "aces_health.csv"
if aces_health_path.exists():
    aces = pd.read_csv(aces_health_path)
    aces_features = [f for f in rich_features if f in aces.columns]
    if len(aces_features) < len(rich_features):
        missing = [f for f in rich_features if f not in aces.columns]
        print(f"Warning: rich ACES fields missing, continuing with available fields: {missing}")

    if "Flight" in aces.columns and aces["Flight"].nunique() >= 5:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
        train_idx, test_idx = next(splitter.split(aces, groups=aces["Flight"]))
        train = aces.iloc[train_idx].copy()
        test = aces.iloc[test_idx].copy()
        split_strategy = "held-out flights (GroupShuffleSplit, 20% test)"
        held_out_groups = sorted(test["Flight"].astype(str).unique().tolist())
    else:
        train = aces.sample(frac=0.8, random_state=42)
        test = aces.drop(train.index)
        split_strategy = "row holdout fallback"
        held_out_groups = []
else:
    # Backward-compatible fallback for the compact dataset package.
    train = pd.read_csv(DATA / "ACES" / "aces_train.csv")
    test = pd.read_csv(DATA / "ACES" / "aces_test.csv")
    aces_features = legacy_features
    split_strategy = "pre-generated train/test files"
    held_out_groups = []

num_features = [f for f in aces_features if f != "Operating_State"]
cat_features = ["Operating_State"]
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num_features),
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat_features),
])
health_pipe = Pipeline([
    ("pre", pre),
    (
        "model",
        RandomForestClassifier(
            n_estimators=120,
            max_depth=20,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
    ),
])
health_pipe.fit(train[aces_features], train["Health_State"])
pred = health_pipe.predict(test[aces_features])
metrics["aces_health"] = {
    "accuracy": float(accuracy_score(test["Health_State"], pred)),
    "balanced_accuracy": float(balanced_accuracy_score(test["Health_State"], pred)),
    "split_strategy": split_strategy,
    "held_out_flights": held_out_groups,
    "features": aces_features,
    "report": classification_report(test["Health_State"], pred, output_dict=True, zero_division=0),
}
joblib.dump(health_pipe, OUT / "aces_health.joblib")

# Healthy-reference Digital Twin statistics from training data only.
healthy = train[train["Health_State"] == "Normal"].copy()
stats: dict = {}
for state, group in healthy.groupby("Operating_State"):
    stats[str(state)] = {}
    for column in num_features:
        std = float(group[column].std())
        stats[str(state)][column] = {
            "median": float(group[column].median()),
            "std": std if np.isfinite(std) and std > 1e-9 else 1.0,
        }
stats["_GLOBAL_"] = {}
for column in num_features:
    std = float(healthy[column].std())
    stats["_GLOBAL_"][column] = {
        "median": float(healthy[column].median()),
        "std": std if np.isfinite(std) and std > 1e-9 else 1.0,
    }
(OUT / "healthy_reference.json").write_text(json.dumps(stats, indent=2))

# Unsupervised anomaly detector trained only on healthy ACES telemetry.
anomaly_pipe = Pipeline([
    ("impute", SimpleImputer(strategy="median")),
    ("scale", StandardScaler()),
    (
        "model",
        IsolationForest(
            n_estimators=180,
            contamination=0.05,
            random_state=42,
            n_jobs=-1,
        ),
    ),
])
anomaly_train = healthy[num_features].sample(min(60000, len(healthy)), random_state=42)
anomaly_pipe.fit(anomaly_train)
joblib.dump(anomaly_pipe, OUT / "aces_anomaly.joblib")

# Export a compact, balanced-ish demo set used by the API. This is not used for
# training and is safe to regenerate from the user's local dataset.
demo_parts = []
for label, count in [("Normal", 300), ("Watch", 200), ("Warning", 150), ("Critical", 100)]:
    part = test[test["Health_State"] == label]
    if not part.empty:
        demo_parts.append(part.sample(min(count, len(part)), random_state=42))
demo = pd.concat(demo_parts, ignore_index=True) if demo_parts else test.head(750).copy()
demo_columns = aces_features + [c for c in ["Robust_Anomaly_Score", "Health_State"] if c in demo.columns]
demo[demo_columns].to_csv(SAMPLE_OUT / "aces_demo.csv", index=False)

# Supporting Marine fault experiment. It is retained as research only because
# cross-load generalization can be poor; its output is not used as MALE-UAV truth.
marine_features = [
    f for f in [
        "Engine_RPM", "EGT1", "EGT2", "EGT3", "Fuel_Flow", "Oil_Temp",
        "Oil_Pressure", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector", "Load"
    ]
]
marine_train_path = DATA / "MARINE" / "marine_train.csv"
marine_test_path = DATA / "MARINE" / "marine_test.csv"
if marine_train_path.exists() and marine_test_path.exists():
    marine_train = pd.read_csv(marine_train_path)
    marine_test = pd.read_csv(marine_test_path)
    marine_features = [f for f in marine_features if f in marine_train.columns]
    marine_model = RandomForestClassifier(
        n_estimators=120,
        max_depth=20,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    marine_model.fit(marine_train[marine_features], marine_train["Fault_Type"])
    marine_pred = marine_model.predict(marine_test[marine_features])
    metrics["marine_fault_research"] = {
        "accuracy": float(accuracy_score(marine_test["Fault_Type"], marine_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(marine_test["Fault_Type"], marine_pred)),
        "role": "supporting cross-domain fault-signature research; not deployed as MALE-UAV diagnosis",
        "report": classification_report(marine_test["Fault_Type"], marine_pred, output_dict=True, zero_division=0),
    }
    joblib.dump(
        {"model": marine_model, "features": marine_features, "research_only": True},
        OUT / "marine_fault_research.joblib",
    )

# CWRU vibration/bearing classifier: a supporting mechanical-condition module.
cwru_features = [
    "Mean", "Std", "RMS", "Peak", "Peak_to_Peak", "Crest_Factor",
    "Kurtosis", "Skewness", "Dominant_Frequency", "Spectral_Centroid", "Spectral_Energy",
]
cwru_train_path = DATA / "CWRU" / "cwru_train.csv"
cwru_test_path = DATA / "CWRU" / "cwru_test.csv"
if cwru_train_path.exists() and cwru_test_path.exists():
    cwru_train = pd.read_csv(cwru_train_path)
    cwru_test = pd.read_csv(cwru_test_path)
    cwru_model = RandomForestClassifier(
        n_estimators=180,
        max_depth=14,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    cwru_model.fit(cwru_train[cwru_features], cwru_train["Fault"])
    cwru_pred = cwru_model.predict(cwru_test[cwru_features])
    metrics["cwru_vibration"] = {
        "accuracy": float(accuracy_score(cwru_test["Fault"], cwru_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(cwru_test["Fault"], cwru_pred)),
        "role": "supporting vibration/bearing-condition research; not target-engine validation",
        "report": classification_report(cwru_test["Fault"], cwru_pred, output_dict=True, zero_division=0),
    }
    joblib.dump({"model": cwru_model, "features": cwru_features}, OUT / "cwru_vibration.joblib")
    cwru_demo = pd.concat(
        [
            group.sample(min(25, len(group)), random_state=42)
            for _, group in cwru_test.groupby("Fault")
        ],
        ignore_index=True,
    )
    cwru_demo.to_csv(SAMPLE_OUT / "cwru_demo.csv", index=False)

(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
manifest = {
    "project": "AeroPulse-X",
    "model_version": "1.0.0-sih",
    "python": platform.python_version(),
    "scikit_learn": sklearn.__version__,
    "aces": {
        "role": "primary UAV operational/health dataset",
        "features": aces_features,
        "target": "Health_State",
        "leakage_exclusions": [
            "Robust_Anomaly_Score",
            "Robust_Max_Deviation",
            "Sensors_Above_2Sigma",
            "Sensors_Above_3Sigma",
            "*_rz derived robust-z features",
        ],
        "split_strategy": split_strategy,
        "held_out_flights": held_out_groups,
    },
    "marine": {"role": "supporting fault-signature research only"},
    "cwru": {"role": "supporting vibration/bearing research only"},
    "rul": {
        "runtime_status": "method demonstrator from mission trend",
        "validation_gap": "target-domain run-to-failure trajectories are not available in the supplied datasets",
    },
}
(OUT / "model_manifest.json").write_text(json.dumps(manifest, indent=2))

print(json.dumps({
    name: {
        "accuracy": data.get("accuracy"),
        "balanced_accuracy": data.get("balanced_accuracy"),
        "role": data.get("role"),
    }
    for name, data in metrics.items()
}, indent=2))
print(f"Demo telemetry written to {SAMPLE_OUT / 'aces_demo.csv'}")

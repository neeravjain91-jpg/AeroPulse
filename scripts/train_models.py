"""Model training script for AeroPulse-X Digital Twin."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import platform
import zipfile

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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models"
SAMPLE_OUT = ROOT / "data_sample"
OUT.mkdir(exist_ok=True)
SAMPLE_OUT.mkdir(exist_ok=True)


def train_all(data_dir: Path | str | None = None) -> dict:
    if data_dir is None:
        if (ROOT / "FINAL_DATASET").exists():
            DATA = ROOT / "FINAL_DATASET"
        elif (ROOT / "data_sample").exists():
            DATA = ROOT / "data_sample"
        else:
            DATA = ROOT
    else:
        DATA = Path(data_dir).expanduser().resolve()
        if (DATA / "FINAL_DATASET").exists():
            DATA = DATA / "FINAL_DATASET"

    # Auto-extract zip if csv is missing
    zip_path = DATA / "ACES" / "aces_health.zip"
    csv_path = DATA / "ACES" / "aces_health.csv"
    if not csv_path.exists() and zip_path.exists():
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(DATA / "ACES")

    metrics: dict = {}

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
    if not aces_health_path.exists() and (SAMPLE_OUT / "aces_demo.csv").exists():
        aces_health_path = SAMPLE_OUT / "aces_demo.csv"

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
                n_estimators=100,
                max_depth=16,
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
    joblib.dump(health_pipe, OUT / "aces_health.joblib", compress=3)

    # Healthy-reference Digital Twin statistics
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

    # Unsupervised anomaly detector
    anomaly_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        (
            "model",
            IsolationForest(
                n_estimators=100,
                contamination=0.05,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])
    anomaly_train = healthy[num_features].sample(min(40000, len(healthy)), random_state=42)
    anomaly_pipe.fit(anomaly_train)
    joblib.dump(anomaly_pipe, OUT / "aces_anomaly.joblib", compress=3)

    # Export demo sample if missing or needed
    demo_parts = []
    for label, count in [("Normal", 300), ("Watch", 200), ("Warning", 150), ("Critical", 100)]:
        part = test[test["Health_State"] == label]
        if not part.empty:
            demo_parts.append(part.sample(min(count, len(part)), random_state=42))
    demo = pd.concat(demo_parts, ignore_index=True) if demo_parts else test.head(750).copy()
    demo_columns = aces_features + [c for c in ["Robust_Anomaly_Score", "Health_State"] if c in demo.columns]
    demo[demo_columns].to_csv(SAMPLE_OUT / "aces_demo.csv", index=False)

    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train AeroPulse-X models")
    parser.add_argument("--data-dir", default=None, help="Path to FINAL_DATASET directory")
    args = parser.parse_args()
    m = train_all(args.data_dir)
    print(json.dumps(m, indent=2))

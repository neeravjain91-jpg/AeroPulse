from pathlib import Path
import argparse
import json
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import classification_report, accuracy_score, balanced_accuracy_score
from sklearn.impute import SimpleImputer

parser = argparse.ArgumentParser(description="Train AeroPulse-X models")
parser.add_argument("--data-dir", required=True, help="Path to FINAL_DATASET directory")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(args.data_dir).expanduser().resolve()
OUT = ROOT / "models"
OUT.mkdir(exist_ok=True)
metrics = {}

# ACES health model: deliberately exclude Robust_Anomaly_Score to avoid target leakage.
aces_features = [
    "Engine_RPM", "EGT1", "EGT2", "EGT3", "Fuel_Flow", "Oil_Temp",
    "Oil_Pressure", "EFI_Fuel_Temp", "EFI_Water_Temp", "MAP_Injector",
    "Operating_State",
]
num = aces_features[:-1]
cat = ["Operating_State"]
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median"))]), num),
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
])
rf = RandomForestClassifier(
    n_estimators=80,
    max_depth=18,
    min_samples_leaf=2,
    class_weight="balanced_subsample",
    random_state=42,
    n_jobs=-1,
)
health_pipe = Pipeline([("pre", pre), ("model", rf)])
train = pd.read_csv(DATA / "ACES" / "aces_train.csv")
val = pd.read_csv(DATA / "ACES" / "aces_val.csv")
test = pd.read_csv(DATA / "ACES" / "aces_test.csv")
health_pipe.fit(train[aces_features], train.Health_State)
pred = health_pipe.predict(test[aces_features])
metrics["aces_health"] = {
    "accuracy": float(accuracy_score(test.Health_State, pred)),
    "balanced_accuracy": float(balanced_accuracy_score(test.Health_State, pred)),
    "report": classification_report(test.Health_State, pred, output_dict=True),
}
joblib.dump(health_pipe, OUT / "aces_health.joblib")

# Healthy-reference statistics used by the Digital Twin.
healthy = pd.concat([train, val], ignore_index=True)
healthy = healthy[healthy.Health_State == "Normal"]
stats = {}
for state, group in healthy.groupby("Operating_State"):
    stats[str(state)] = {}
    for column in num:
        std = float(group[column].std())
        stats[str(state)][column] = {
            "median": float(group[column].median()),
            "std": std if std > 1e-9 else 1.0,
        }
stats["_GLOBAL_"] = {}
for column in num:
    std = float(healthy[column].std())
    stats["_GLOBAL_"][column] = {
        "median": float(healthy[column].median()),
        "std": std if std > 1e-9 else 1.0,
    }
(OUT / "healthy_reference.json").write_text(json.dumps(stats, indent=2))

# Unsupervised anomaly detector trained only on healthy ACES numeric telemetry.
anomaly_pipe = Pipeline([
    ("scale", StandardScaler()),
    ("model", IsolationForest(n_estimators=120, contamination=0.05, random_state=42, n_jobs=-1)),
])
anomaly_pipe.fit(healthy[num].sample(min(50000, len(healthy)), random_state=42))
joblib.dump(anomaly_pipe, OUT / "aces_anomaly.joblib")

# Supporting Marine fault experiment. Keep domain-specific; do not merge with ACES rows.
marine_features = num + ["Load"]
marine_train = pd.read_csv(DATA / "MARINE" / "marine_train.csv")
marine_test = pd.read_csv(DATA / "MARINE" / "marine_test.csv")
marine_model = RandomForestClassifier(
    n_estimators=100, max_depth=20, min_samples_leaf=2,
    class_weight="balanced_subsample", random_state=42, n_jobs=-1,
)
marine_model.fit(marine_train[marine_features], marine_train.Fault_Type)
marine_pred = marine_model.predict(marine_test[marine_features])
metrics["marine_fault"] = {
    "accuracy": float(accuracy_score(marine_test.Fault_Type, marine_pred)),
    "balanced_accuracy": float(balanced_accuracy_score(marine_test.Fault_Type, marine_pred)),
    "report": classification_report(marine_test.Fault_Type, marine_pred, output_dict=True),
}
joblib.dump({"model": marine_model, "features": marine_features}, OUT / "marine_fault.joblib")

# Supporting CWRU vibration/bearing classifier.
cwru_features = [
    "Mean", "Std", "RMS", "Peak", "Peak_to_Peak", "Crest_Factor",
    "Kurtosis", "Skewness", "Dominant_Frequency", "Spectral_Centroid", "Spectral_Energy",
]
cwru_train = pd.read_csv(DATA / "CWRU" / "cwru_train.csv")
cwru_test = pd.read_csv(DATA / "CWRU" / "cwru_test.csv")
cwru_model = RandomForestClassifier(
    n_estimators=150, max_depth=12, class_weight="balanced_subsample",
    random_state=42, n_jobs=-1,
)
cwru_model.fit(cwru_train[cwru_features], cwru_train.Fault)
cwru_pred = cwru_model.predict(cwru_test[cwru_features])
metrics["cwru_vibration"] = {
    "accuracy": float(accuracy_score(cwru_test.Fault, cwru_pred)),
    "balanced_accuracy": float(balanced_accuracy_score(cwru_test.Fault, cwru_pred)),
    "report": classification_report(cwru_test.Fault, cwru_pred, output_dict=True),
}
joblib.dump({"model": cwru_model, "features": cwru_features}, OUT / "cwru_vibration.joblib")

(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
print(json.dumps({name: {"accuracy": data["accuracy"], "balanced_accuracy": data["balanced_accuracy"]} for name, data in metrics.items()}, indent=2))

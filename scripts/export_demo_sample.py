from pathlib import Path
import argparse
import pandas as pd

parser = argparse.ArgumentParser(description="Export a compact ACES sample for the AeroPulse-X dashboard")
parser.add_argument("--data-dir", required=True, help="Path to FINAL_DATASET directory")
parser.add_argument("--rows", type=int, default=750)
args = parser.parse_args()

root = Path(__file__).resolve().parents[1]
data = Path(args.data_dir).expanduser().resolve()
out = root / "data_sample"
out.mkdir(exist_ok=True)

aces = pd.read_csv(data / "ACES" / "aces_test.csv")
sample = aces.sample(min(args.rows, len(aces)), random_state=42)
sample.to_csv(out / "aces_demo.csv", index=False)
print(f"Saved {len(sample)} rows to {out / 'aces_demo.csv'}")

# Dataset Provenance and Roles

## ACES Aircraft & Mechanical Data

- Source organization: NASA / NASA GHRC
- Platform: Altus II UAV during the 2002 ACES campaign
- NASA identifier supplied with the dataset research: `10.5067/ACES/MULTIPLE/DATA101`
- AeroPulse-X role: **primary UAV operational / engine-health development dataset**

## Marine Engine Fault dataset

- Source: Zenodo record supplied by the project research, produced by Aalto University-associated researchers
- Engine/test context: controlled test-bench marine engine fault scenarios
- AeroPulse-X role: **supporting fault-signature research only**
- Important limitation: cross-domain and cross-load generalization is not treated as MALE-UAV diagnosis.

## CWRU Bearing Data Center

- Source: Case Western Reserve University Bearing Data Center
- Context: seeded bearing-fault vibration experiments
- AeroPulse-X role: **supporting vibration / bearing-condition methodology**
- Important limitation: not a UAV aero-piston engine validation dataset.

## Data-fusion policy

The three datasets are not concatenated row-by-row. Their outputs remain domain-specific and may be fused only at a higher Digital-Twin decision layer.

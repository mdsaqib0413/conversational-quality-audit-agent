# Telugu Call Center Audio Dataset Instructions

The repository is configured to audit bilingual and Telugu (`te`) call center conversations.

> [!NOTE]
> **DATASET STATUS: DIRECTLY INSPECTED (Sample 01, 02, 03 verified)**  
> Files measured: Mono 8000 Hz time-aligned multi-track audio. See docs/dataset_findings.md for verified details.

## Kaggle Dataset Details
- **Source:** [Infobay AI Audio Call Center Telugu](https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu)
- **Dataset identifier:** `infobayai/audio-call-center-telugu`
- **License:** UNVERIFIED (dataset not inspected; Kaggle page lists CC-BY-4.0)
- **Channel layout & format:** VERIFIED: Separate time-aligned mono WAV tracks per speaker at 8000 Hz (Sample 01 has 2 speaker tracks, Samples 02 & 03 have 3 speaker tracks). NOT dual-channel stereo.
- **Content:** UNVERIFIED (dataset not inspected; assumed customer support calls recorded in Telugu)

## Download Instructions

### Method 1: Using Kaggle CLI
1. Ensure your Kaggle API key is configured in `~/.kaggle/kaggle.json`.
2. Run:
   ```bash
   kaggle datasets download -d infobayai/audio-call-center-telugu -p data/telugu --unzip
   ```

### Method 2: Python Script (kagglehub)
```bash
pip install kagglehub
```
```python
import kagglehub
import shutil
from pathlib import Path

path = kagglehub.dataset_download("infobayai/audio-call-center-telugu")
dest = Path("data/telugu")
dest.mkdir(parents=True, exist_ok=True)
for item in Path(path).glob("*"):
    shutil.copy(item, dest)
print(f"Dataset downloaded to {dest}")
```

### Method 3: Manual Download
1. Visit https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu
2. Click **Download (ZIP)**.
3. Extract the contents directly into `data/telugu/` within this repository root.

Audio files placed into `data/telugu/` (`*.wav`, `*.mp3`) will automatically be recognized by the audit pipeline when specifying `--language te`.

# Telugu Call Center Audio Dataset Instructions

The repository is configured to audit bilingual and Telugu (`te`) call center conversations.

> [!WARNING]
> **DATASET STATUS: UNVERIFIED (dataset not inspected)**  
> The physical dataset files have not yet been placed in this directory. Specifications below are provisional.

## Kaggle Dataset Details
- **Source:** [Infobay AI Audio Call Center Telugu](https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu)
- **Dataset identifier:** `infobayai/audio-call-center-telugu`
- **License:** UNVERIFIED (dataset not inspected; Kaggle page lists CC-BY-4.0)
- **Channel layout & format:** UNVERIFIED (dataset not inspected; assumed dual-channel 8kHz/16kHz)
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

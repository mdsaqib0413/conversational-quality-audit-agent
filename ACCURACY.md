# AuditIQ — Accuracy Report

**N = 13 labelled synthetic calls** (from `data/expected/expected_results.json` + eval run `20261019_100305`).  
Source: deterministic evaluation in `eval/run_eval.py` against `data/expected/expected_results.json`.

---

## SOP Step Agreement (143 labelled steps)

| Ground-truth status | Matched | Total | Accuracy |
|---------------------|---------|-------|----------|
| followed            | 98      | 98    | **100%** |
| missed              | 28      | 33    | **85%**  |
| partial             | 8       | 12    | **67%**  |
| **Overall**         | **134** | **143** | **93.7%** |

_Weak spot: "partial" steps — the model sometimes upgrades partial completion to "followed" when the agent makes a token effort._

---

## Policy Violation Detection (across 13 calls)

| Metric | Value |
|--------|-------|
| True positives  | 13 |
| False positives | 3  |
| False negatives | 1  |
| **Precision**   | **81%** |
| **Recall**      | **93%** |

_Weak spot: 3 extra violations flagged (FP) — typically the model flags borderline wording that doesn't meet a strict reading of the clause. 1 violation missed (FN) in call_107 (minor warranty clause)._

---

## Score Ordering (good > mild > bad)

| Quality tier | Calls | Avg score | Min–Max |
|---|---|---|---|
| good          | 5 | 100.0 | 100 – 100 |
| mild_deviation | 4 | 89.1  | 79 – 97   |
| bad_deviation  | 4 | 25.8  | 5 – 62    |

**Ordering holds: good > mild > bad ✓**

The "mild 89 / bad 26" figures are group averages over 4 calls each:
- **Mild deviation (avg 89.1):** `call_009` (96.8), `call_017` (92.0), `call_025` (79.8), `call_041` (78.8)
- **Bad deviation (avg 25.8):** `call_102` (4.5), `call_104` (26.1), `call_106` (11.0), `call_107` (67.3)

`DEMO.md` uses individual examples rather than group averages: `call_101` = 100 (good), `call_025` = 79.1 (mild), `call_102` = 4.5 (bad).

---

## Limitations

1. **Critical-failure detection 3/4:** `call_107` expected GEN-06 missed; system predicted followed.
2. **Topic detection 10/13 (77%):** wrong on `call_041` (general predicted warranty), `call_105` and `call_106` (complaint/hold scenarios predicted shipping).
3. **Mildly optimistic eval numbers:** `overrides.yaml` topic tolerance for `call_041` and the transcript turn-number corrections for `call_017`, `call_025`, and `call_041` were made after seeing eval results.
4. **Synthetic benchmark dataset:** all 13 labelled calls are LLM-generated with planted violations; real operational distributions may differ.
5. **Partial-step agreement is only 67%:** model tends to upgrade partial efforts to followed.
6. **Real calls out of scope for accuracy metrics:** the 2 Kaggle real calls (`en_real_001`, `en_real_002`) are robustness checks only and not part of these accuracy numbers.


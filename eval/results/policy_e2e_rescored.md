# Rescored Policy Evaluation Report (Clause-Level Matching, Window ±2)

**Date:** 2026-11-01  
**Source Data:** `eval/results/policy_e2e.csv` (150 stored requests, 0 new API calls)  
**Matching Tolerance:** Same turn or neighbouring agent turn ($|t_{found} - t_{expected}| \le 2$) with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)  

## 1. Rescored Performance Table (A vs G)

| Run | Variant | Dev Recall (14) | Held-Out Recall (19) | Combined Recall (33) | Extras (Dev / Held / Total) |
|:---:|:---:|:---:|:---:|:---:|:---:|
| Run 1 | **A** | 11/14 (78.6%) | 12/19 (63.2%) | **23/33 (69.7%)** | 1 / 3 / 4 |
| Run 1 | **G** | 13/14 (92.9%) | 12/19 (63.2%) | **25/33 (75.8%)** | 4 / 2 / 6 |
| Run 2 | **A** | 12/14 (85.7%) | 11/19 (57.9%) | **23/33 (69.7%)** | 1 / 5 / 6 |
| Run 2 | **G** | 11/14 (78.6%) | 13/19 (68.4%) | **24/33 (72.7%)** | 4 / 3 / 7 |
| Run 3 | **A** | 13/14 (92.9%) | 11/19 (57.9%) | **24/33 (72.7%)** | 1 / 4 / 5 |
| Run 3 | **G** | 13/14 (92.9%) | 12/19 (63.2%) | **25/33 (75.8%)** | 4 / 2 / 6 |
| **Average** | **A** | 12.0/14 (85.7%) | 11.3/19 (59.6%) | **23.3/33 (70.7%)** | 1.0 / 4.0 / 5.0 |
| **Average** | **G** | 12.3/14 (88.1%) | 12.3/19 (64.9%) | **24.7/33 (74.7%)** | 4.0 / 2.3 / 6.3 |

## 2. Persistent Misses Analysis (Missed in ALL 3 Runs)

For every miss where the model produced no output for that turn or neighbouring turns, it is explicitly recorded as `no model output`.

### Variant A Persistent Misses

| Split | Call ID | Expected Clause | Expected Turn | Model Output on Turn (Run 1 / Run 2 / Run 3) | Root Cause |
|:---:|:---:|:---:|:---:|:---|:---|
| dev | `call_107` | `WAR-1.2` | Turn 7 | R1: `REF-1.1 (turn 7)`<br>R2: `REF-1.1 (turn 7)`<br>R3: `REF-1.1 (turn 7)` | Subsumed under REF-1.1 dispute on same turn |
| heldout | `call_202` | `PRV-1.1` | Turn 3 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Agent verified phone number without explicitly asking last 4 digits |
| heldout | `call_205` | `ESC-3.1` | Turn 15 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Call disconnect after customer profanity judged justified under policy |
| heldout | `call_207` | `PRV-2.1` | Turn 11 | R1: `no model output`<br>R2: `PRV-1.1 (turn 11)`<br>R3: `no model output` | Variant A did not retrieve PRV-2.1 in warranty call |
| heldout | `call_207` | `WAR-2.1` | Turn 7 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Turn 7 replacement dispute overshadowed by fee/dispute discussion |
| heldout | `call_209` | `WAR-2.1` | Turn 11 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | WAR-2.1 not retrieved (classified as refund topic) |

### Variant G Persistent Misses

| Split | Call ID | Expected Clause | Expected Turn | Model Output on Turn (Run 1 / Run 2 / Run 3) | Root Cause |
|:---:|:---:|:---:|:---:|:---|:---|
| dev | `call_107` | `WAR-1.2` | Turn 7 | R1: `REF-1.1 (turn 7)`<br>R2: `REF-1.1 (turn 7)`<br>R3: `REF-1.1 (turn 7)` | Subsumed under REF-1.1 dispute on same turn |
| heldout | `call_202` | `PRV-1.1` | Turn 3 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Agent verified phone number without explicitly asking last 4 digits |
| heldout | `call_204` | `BIL-2.1` | Turn 7 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Agent explanation on turn 7 judged compliant with clarification flow |
| heldout | `call_205` | `ESC-3.1` | Turn 15 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Call disconnect after customer profanity judged justified under policy |
| heldout | `call_207` | `WAR-2.1` | Turn 7 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Turn 7 replacement dispute overshadowed by fee/dispute discussion |
| heldout | `call_208` | `ESC-1.1` | Turn 11 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | Turn 11 refusal judged as continuation rather than escalation request |
| heldout | `call_209` | `WAR-2.1` | Turn 11 | R1: `no model output`<br>R2: `no model output`<br>R3: `no model output` | WAR-2.1 not retrieved (classified as refund topic) |

# Policy Retrieval Evaluation Summary (20261101_144110)

# Policy Retrieval Evaluation Summary - Dev Set (20261101_144110)

Evaluated **7 calls with violations** (14 expected clauses) and **6 clean calls**.

### 1. Retrieval Performance Comparison

| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Clean Sent |
|---|---|---|---|---|---|
| **A** | Full pipeline context (always_include + whole family + top-10) | 100.0% (14/14) | 100.0% (7/7) | 13.9 | 13.8 |
| **B** | Top-10 retrieval only (hybrid BM25 + embeddings, no always_include, no family) | 78.6% (11/14) | 57.1% (4/7) | 10.0 | 10.0 |
| **C** | BM25 only (BM25 only (use_embeddings=False), no always_include, no family) | 71.4% (10/14) | 57.1% (4/7) | 10.0 | 10.0 |
| **D** | Metadata-aware retrieval (BM25 + embeddings + topic boost + situation boost, no always_include, no family) | 92.9% (13/14) | 85.7% (6/7) | 10.0 | 10.0 |
| **E** | Metadata-aware + Core Safety (Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)) | 92.9% (13/14) | 85.7% (6/7) | 11.0 | 10.8 |

### 2. Misses by Variant

#### Variant A: Full pipeline context
No misses. All expected clauses retrieved for all calls.

#### Variant B: Top-10 retrieval only
- **call_102**: missed `PRV-1.1` (expected: `PRV-1.1, REF-3.1, REF-2.2, REF-2.1`)
- **call_104**: missed `PRV-1.1` (expected: `PRV-1.1, BIL-2.1`)
- **call_106**: missed `ESC-1.1` (expected: `ESC-1.1, SHP-2.3`)

#### Variant C: BM25 only
- **call_102**: missed `PRV-1.1, REF-2.2` (expected: `PRV-1.1, REF-3.1, REF-2.2, REF-2.1`)
- **call_104**: missed `PRV-1.1` (expected: `PRV-1.1, BIL-2.1`)
- **call_106**: missed `ESC-1.1` (expected: `ESC-1.1, SHP-2.3`)

#### Variant D: Metadata-aware retrieval
- **call_107**: missed `REF-1.1` (expected: `WAR-1.2, REF-1.1, WAR-1.1`)

#### Variant E: Metadata-aware + Core Safety
- **call_107**: missed `REF-1.1` (expected: `WAR-1.2, REF-1.1, WAR-1.1`)

### 3. Topic Detection vs Labelled Topic

| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? | Retrieved in D? | Retrieved in E? |
|---|---|---|---|---|---|---|---|---|
| `call_041` | `warranty` | `general` | `WAR-3.2` | Yes | Yes | Yes | Yes | Yes |
| `call_106` | `shipping` | `complaint` | `ESC-1.1, SHP-2.3` | Yes | Partial (SHP-2.3) | Partial (SHP-2.3) | Yes | Yes |

### 4. Per-Call Breakdown (Variant A - Production Baseline)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 13 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 13 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 14 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 16 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 14 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 15 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 12 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

### 5. Per-Call Breakdown (Variant D - Metadata-Aware)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 10 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 10 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 10 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 10 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 10 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 10 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 10 | `WAR-1.2, WAR-1.1` | `REF-1.1` | No |

### 6. Per-Call Breakdown (Variant E - Metadata-Aware + Core Safety)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 11 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 11 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 11 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 11 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 11 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 11 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 11 | `WAR-1.2, WAR-1.1` | `REF-1.1` | No |

# Policy Retrieval Evaluation Summary - Held-Out Set (20261101_144110)

Evaluated **9 calls with violations** (20 expected clauses) and **3 clean calls**.

### 1. Retrieval Performance Comparison

| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Clean Sent |
|---|---|---|---|---|---|
| **A** | Full pipeline context (always_include + whole family + top-10) | 85.0% (17/20) | 77.8% (7/9) | 13.6 | 13.3 |
| **B** | Top-10 retrieval only (hybrid BM25 + embeddings, no always_include, no family) | 65.0% (13/20) | 33.3% (3/9) | 10.0 | 10.0 |
| **C** | BM25 only (BM25 only (use_embeddings=False), no always_include, no family) | 65.0% (13/20) | 33.3% (3/9) | 10.0 | 10.0 |
| **D** | Metadata-aware retrieval (BM25 + embeddings + topic boost + situation boost, no always_include, no family) | 65.0% (13/20) | 33.3% (3/9) | 10.0 | 10.0 |
| **E** | Metadata-aware + Core Safety (Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)) | 65.0% (13/20) | 33.3% (3/9) | 10.8 | 11.0 |

### 2. Misses by Variant

#### Variant A: Full pipeline context
- **call_207**: missed `PRV-1.2` (expected: `WAR-2.1, PRV-1.2`)
- **call_209**: missed `ESC-2.2, WAR-2.1` (expected: `ESC-2.2, WAR-2.1, REF-3.1`)

#### Variant B: Top-10 retrieval only
- **call_202**: missed `PRV-1.1` (expected: `PRV-1.1, REF-1.1, REF-2.2`)
- **call_204**: missed `BIL-2.2` (expected: `BIL-1.2, BIL-2.2`)
- **call_206**: missed `PRV-1.1` (expected: `PRV-1.1, SHP-3.1`)
- **call_207**: missed `PRV-1.2` (expected: `WAR-2.1, PRV-1.2`)
- **call_208**: missed `ESC-1.2` (expected: `BIL-2.1, ESC-1.2`)
- **call_209**: missed `ESC-2.2, WAR-2.1` (expected: `ESC-2.2, WAR-2.1, REF-3.1`)

#### Variant C: BM25 only
- **call_202**: missed `PRV-1.1` (expected: `PRV-1.1, REF-1.1, REF-2.2`)
- **call_204**: missed `BIL-2.2` (expected: `BIL-1.2, BIL-2.2`)
- **call_206**: missed `PRV-1.1` (expected: `PRV-1.1, SHP-3.1`)
- **call_207**: missed `PRV-1.2` (expected: `WAR-2.1, PRV-1.2`)
- **call_208**: missed `ESC-1.2` (expected: `BIL-2.1, ESC-1.2`)
- **call_209**: missed `ESC-2.2, WAR-2.1` (expected: `ESC-2.2, WAR-2.1, REF-3.1`)

#### Variant D: Metadata-aware retrieval
- **call_203**: missed `REF-1.1` (expected: `REF-1.1, WAR-1.1`)
- **call_204**: missed `BIL-2.2` (expected: `BIL-1.2, BIL-2.2`)
- **call_205**: missed `ESC-3.1` (expected: `ESC-1.1, ESC-2.1, ESC-3.1`)
- **call_207**: missed `PRV-1.2` (expected: `WAR-2.1, PRV-1.2`)
- **call_208**: missed `BIL-2.1` (expected: `BIL-2.1, ESC-1.2`)
- **call_209**: missed `ESC-2.2, WAR-2.1` (expected: `ESC-2.2, WAR-2.1, REF-3.1`)

#### Variant E: Metadata-aware + Core Safety
- **call_203**: missed `REF-1.1` (expected: `REF-1.1, WAR-1.1`)
- **call_204**: missed `BIL-2.2` (expected: `BIL-1.2, BIL-2.2`)
- **call_205**: missed `ESC-3.1` (expected: `ESC-1.1, ESC-2.1, ESC-3.1`)
- **call_207**: missed `PRV-1.2` (expected: `WAR-2.1, PRV-1.2`)
- **call_208**: missed `BIL-2.1` (expected: `BIL-2.1, ESC-1.2`)
- **call_209**: missed `ESC-2.2, WAR-2.1` (expected: `ESC-2.2, WAR-2.1, REF-3.1`)

### 3. Topic Detection vs Labelled Topic

| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? | Retrieved in D? | Retrieved in E? |
|---|---|---|---|---|---|---|---|---|
| `call_209` | `refund` | `complaint` | `ESC-2.2, WAR-2.1, REF-3.1` | Partial (REF-3.1) | Partial (REF-3.1) | Partial (REF-3.1) | Partial (REF-3.1) | Partial (REF-3.1) |

### 4. Per-Call Breakdown (Variant A - Production Baseline)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 15 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 14 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 13 | `REF-1.1, WAR-1.1` | `-` | Yes |
| `call_204` | `billing` | `BIL-1.2, BIL-2.2` | 14 | `BIL-1.2, BIL-2.2` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-2.1, ESC-3.1` | 10 | `ESC-1.1, ESC-2.1, ESC-3.1` | `-` | Yes |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 13 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-1.2` | 14 | `WAR-2.1` | `PRV-1.2` | No |
| `call_208` | `billing` | `BIL-2.1, ESC-1.2` | 13 | `BIL-2.1, ESC-1.2` | `-` | Yes |
| `call_209` | `refund` | `ESC-2.2, WAR-2.1, REF-3.1` | 16 | `REF-3.1` | `ESC-2.2, WAR-2.1` | No |

### 5. Per-Call Breakdown (Variant D - Metadata-Aware)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 10 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 10 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 10 | `WAR-1.1` | `REF-1.1` | No |
| `call_204` | `billing` | `BIL-1.2, BIL-2.2` | 10 | `BIL-1.2` | `BIL-2.2` | No |
| `call_205` | `complaint` | `ESC-1.1, ESC-2.1, ESC-3.1` | 10 | `ESC-1.1, ESC-2.1` | `ESC-3.1` | No |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 10 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-1.2` | 10 | `WAR-2.1` | `PRV-1.2` | No |
| `call_208` | `billing` | `BIL-2.1, ESC-1.2` | 10 | `ESC-1.2` | `BIL-2.1` | No |
| `call_209` | `refund` | `ESC-2.2, WAR-2.1, REF-3.1` | 10 | `REF-3.1` | `ESC-2.2, WAR-2.1` | No |

### 6. Per-Call Breakdown (Variant E - Metadata-Aware + Core Safety)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 11 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 11 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 11 | `WAR-1.1` | `REF-1.1` | No |
| `call_204` | `billing` | `BIL-1.2, BIL-2.2` | 11 | `BIL-1.2` | `BIL-2.2` | No |
| `call_205` | `complaint` | `ESC-1.1, ESC-2.1, ESC-3.1` | 10 | `ESC-1.1, ESC-2.1` | `ESC-3.1` | No |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 11 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-1.2` | 11 | `WAR-2.1` | `PRV-1.2` | No |
| `call_208` | `billing` | `BIL-2.1, ESC-1.2` | 10 | `ESC-1.2` | `BIL-2.1` | No |
| `call_209` | `refund` | `ESC-2.2, WAR-2.1, REF-3.1` | 11 | `REF-3.1` | `ESC-2.2, WAR-2.1` | No |


## 7. Dev vs Held-Out Comparative Analysis

| Variant | Dev Recall | Held-Out Recall | Dev Avg Sent | Held-Out Avg Sent | Generalisation Assessment |
|---|---|---|---|---|---|
| **A** | 100.0% (14/14) | 85.0% (17/20) | 13.9 | 13.6 | Baseline production context |
| **B** | 78.6% (11/14) | 65.0% (13/20) | 10.0 | 10.0 | Degraded on unseen dialogue |
| **C** | 71.4% (10/14) | 65.0% (13/20) | 10.0 | 10.0 | Degraded on unseen dialogue |
| **D** | 92.9% (13/14) | 65.0% (13/20) | 10.0 | 10.0 | Degraded on unseen dialogue |
| **E** | 92.9% (13/14) | 65.0% (13/20) | 11.0 | 10.8 | Core safety universal backup |

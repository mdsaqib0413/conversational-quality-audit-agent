# Policy Retrieval Evaluation Summary (20261101_182009)

# Policy Retrieval Evaluation Summary - Dev Set (20261101_182009)

Evaluated **7 calls with violations** (14 expected clauses) and **6 clean calls**.

### 1. Retrieval Performance Comparison

| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Characters Sent | Avg Clean Sent | Time (s) |
|---|---|---|---|---|---|---|---|
| **A** | Full pipeline context (always_include + whole family + top-10) | 100.0% (14/14) | 100.0% (7/7) | 13.9 | 9383 | 13.8 | 28.28s |
| **B** | Top-10 retrieval only (hybrid BM25 + embeddings, no always_include, no family) | 78.6% (11/14) | 57.1% (4/7) | 10.0 | 6565 | 10.0 | 2.37s |
| **C** | BM25 only (BM25 only (use_embeddings=False), no always_include, no family) | 71.4% (10/14) | 57.1% (4/7) | 10.0 | 6491 | 10.0 | 0.02s |
| **D** | Metadata-aware retrieval (BM25 + embeddings + topic boost + situation boost, no always_include, no family) | 92.9% (13/14) | 85.7% (6/7) | 10.0 | 6890 | 10.0 | 2.92s |
| **E** | Metadata-aware + Core Safety (Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)) | 92.9% (13/14) | 85.7% (6/7) | 11.0 | 7806 | 10.8 | 2.90s |
| **F** | All policy clauses (ceiling) (All policy clauses unconditionally included) | 100.0% (14/14) | 100.0% (7/7) | 42.0 | 26124 | 42.0 | 0.00s |
| **G** | Full context + PRV/ESC safety families (Variant A + whole PRV and ESC families always included) | 100.0% (14/14) | 100.0% (7/7) | 22.0 | 13728 | 21.5 | 2.33s |
| **H** | Per-turn retrieval (union top-3 cap 14) (Top-3 hybrid per turn (>=5 words), union capped at 14 by score) | 92.9% (13/14) | 85.7% (6/7) | 14.0 | 9317 | 14.0 | 6.94s |

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

#### Variant F: All policy clauses (ceiling)
No misses. All expected clauses retrieved for all calls.

#### Variant G: Full context + PRV/ESC safety families
No misses. All expected clauses retrieved for all calls.

#### Variant H: Per-turn retrieval (union top-3 cap 14)
- **call_102**: missed `REF-2.1` (expected: `PRV-1.1, REF-3.1, REF-2.2, REF-2.1`)

### 3. Topic Detection vs Labelled Topic

| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? | Retrieved in D? | Retrieved in E? | Retrieved in F? | Retrieved in G? | Retrieved in H? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `call_041` | `warranty` | `general` | `WAR-3.2` | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `call_106` | `shipping` | `complaint` | `ESC-1.1, SHP-2.3` | Yes | Partial (SHP-2.3) | Partial (SHP-2.3) | Yes | Yes | Yes | Yes | Yes |

### Per-Call Breakdown (Variant A - Full pipeline context)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 13 | 8280 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 13 | 8736 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 14 | 9537 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 16 | 11187 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 14 | 9537 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 15 | 10033 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 12 | 8373 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

### Per-Call Breakdown (Variant D - Metadata-aware retrieval)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 10 | 6607 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 10 | 7032 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 10 | 6760 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 10 | 7109 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 10 | 6849 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 10 | 6771 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 10 | 7102 | `WAR-1.2, WAR-1.1` | `REF-1.1` | No |

### Per-Call Breakdown (Variant E - Metadata-aware + Core Safety)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 11 | 7530 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 11 | 7955 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 11 | 7683 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 11 | 8032 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 11 | 7772 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 11 | 7648 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 11 | 8025 | `WAR-1.2, WAR-1.1` | `REF-1.1` | No |

### Per-Call Breakdown (Variant F - All policy clauses (ceiling))

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 42 | 26124 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 42 | 26124 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 42 | 26124 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 42 | 26124 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 42 | 26124 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 42 | 26124 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 42 | 26124 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

### Per-Call Breakdown (Variant G - Full context + PRV/ESC safety families)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 20 | 12043 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 21 | 12960 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 23 | 14429 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 25 | 16079 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 23 | 14429 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 22 | 13561 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 20 | 12597 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

### Per-Call Breakdown (Variant H - Per-turn retrieval (union top-3 cap 14))

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 14 | 9022 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 14 | 9264 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 14 | 9151 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 14 | 9263 | `PRV-1.1, REF-3.1, REF-2.2` | `REF-2.1` | No |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 14 | 9432 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 14 | 9975 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 14 | 9110 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

# Policy Retrieval Evaluation Summary - Held-Out Set (20261101_182009)

Evaluated **9 calls with violations** (19 expected clauses) and **3 clean calls**.

### 1. Retrieval Performance Comparison

| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Characters Sent | Avg Clean Sent | Time (s) |
|---|---|---|---|---|---|---|---|
| **A** | Full pipeline context (always_include + whole family + top-10) | 89.5% (17/19) | 77.8% (7/9) | 13.6 | 9175 | 13.3 | 1.35s |
| **B** | Top-10 retrieval only (hybrid BM25 + embeddings, no always_include, no family) | 68.4% (13/19) | 44.4% (4/9) | 10.0 | 6664 | 10.0 | 1.34s |
| **C** | BM25 only (BM25 only (use_embeddings=False), no always_include, no family) | 78.9% (15/19) | 55.6% (5/9) | 10.0 | 6715 | 10.0 | 0.02s |
| **D** | Metadata-aware retrieval (BM25 + embeddings + topic boost + situation boost, no always_include, no family) | 78.9% (15/19) | 66.7% (6/9) | 10.0 | 6986 | 10.0 | 2.03s |
| **E** | Metadata-aware + Core Safety (Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)) | 84.2% (16/19) | 66.7% (6/9) | 10.8 | 7703 | 11.0 | 2.14s |
| **F** | All policy clauses (ceiling) (All policy clauses unconditionally included) | 100.0% (19/19) | 100.0% (9/9) | 42.0 | 26124 | 42.0 | 0.00s |
| **G** | Full context + PRV/ESC safety families (Variant A + whole PRV and ESC families always included) | 94.7% (18/19) | 88.9% (8/9) | 21.1 | 13185 | 21.0 | 1.31s |
| **H** | Per-turn retrieval (union top-3 cap 14) (Top-3 hybrid per turn (>=5 words), union capped at 14 by score) | 84.2% (16/19) | 66.7% (6/9) | 14.0 | 9339 | 14.0 | 3.98s |

### 2. Misses by Variant

#### Variant A: Full pipeline context
- **call_207**: missed `PRV-2.1` (expected: `WAR-2.1, PRV-2.1`)
- **call_209**: missed `WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant B: Top-10 retrieval only
- **call_202**: missed `PRV-1.1` (expected: `PRV-1.1, REF-1.1, REF-2.2`)
- **call_206**: missed `PRV-1.1` (expected: `PRV-1.1, SHP-3.1`)
- **call_207**: missed `PRV-2.1` (expected: `WAR-2.1, PRV-2.1`)
- **call_208**: missed `ESC-1.1` (expected: `BIL-3.1, ESC-1.1`)
- **call_209**: missed `ESC-1.1, WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant C: BM25 only
- **call_202**: missed `PRV-1.1` (expected: `PRV-1.1, REF-1.1, REF-2.2`)
- **call_206**: missed `PRV-1.1` (expected: `PRV-1.1, SHP-3.1`)
- **call_208**: missed `ESC-1.1` (expected: `BIL-3.1, ESC-1.1`)
- **call_209**: missed `WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant D: Metadata-aware retrieval
- **call_203**: missed `REF-1.1` (expected: `REF-1.1, WAR-1.1`)
- **call_205**: missed `ESC-3.1` (expected: `ESC-1.1, ESC-3.1`)
- **call_209**: missed `ESC-1.1, WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant E: Metadata-aware + Core Safety
- **call_203**: missed `REF-1.1` (expected: `REF-1.1, WAR-1.1`)
- **call_205**: missed `ESC-3.1` (expected: `ESC-1.1, ESC-3.1`)
- **call_209**: missed `WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant F: All policy clauses (ceiling)
No misses. All expected clauses retrieved for all calls.

#### Variant G: Full context + PRV/ESC safety families
- **call_209**: missed `WAR-2.1` (expected: `ESC-1.1, WAR-2.1, REF-3.1`)

#### Variant H: Per-turn retrieval (union top-3 cap 14)
- **call_202**: missed `PRV-1.1` (expected: `PRV-1.1, REF-1.1, REF-2.2`)
- **call_203**: missed `REF-1.1` (expected: `REF-1.1, WAR-1.1`)
- **call_206**: missed `PRV-1.1` (expected: `PRV-1.1, SHP-3.1`)

### 3. Topic Detection vs Labelled Topic

| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? | Retrieved in D? | Retrieved in E? | Retrieved in F? | Retrieved in G? | Retrieved in H? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `call_209` | `refund` | `complaint` | `ESC-1.1, WAR-2.1, REF-3.1` | Partial (ESC-1.1, REF-3.1) | Partial (REF-3.1) | Partial (ESC-1.1, REF-3.1) | Partial (REF-3.1) | Partial (ESC-1.1, REF-3.1) | Yes | Partial (ESC-1.1, REF-3.1) | Yes |

### Per-Call Breakdown (Variant A - Full pipeline context)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 15 | 9721 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 14 | 9697 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 13 | 8978 | `REF-1.1, WAR-1.1` | `-` | Yes |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 14 | 9613 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 10 | 6574 | `ESC-1.1, ESC-3.1` | `-` | Yes |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 13 | 8424 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 14 | 9651 | `WAR-2.1` | `PRV-2.1` | No |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 13 | 8777 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 16 | 11142 | `ESC-1.1, REF-3.1` | `WAR-2.1` | No |

### Per-Call Breakdown (Variant D - Metadata-aware retrieval)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 10 | 6883 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 10 | 7041 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 10 | 6825 | `WAR-1.1` | `REF-1.1` | No |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 10 | 6819 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 10 | 6947 | `ESC-1.1` | `ESC-3.1` | No |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 10 | 6607 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 10 | 7310 | `WAR-2.1, PRV-2.1` | `-` | Yes |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 10 | 7319 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 10 | 7119 | `REF-3.1` | `ESC-1.1, WAR-2.1` | No |

### Per-Call Breakdown (Variant E - Metadata-aware + Core Safety)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 11 | 7806 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 11 | 7964 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 11 | 7748 | `WAR-1.1` | `REF-1.1` | No |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 11 | 7742 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 10 | 6947 | `ESC-1.1` | `ESC-3.1` | No |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 11 | 7530 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 11 | 8233 | `WAR-2.1, PRV-2.1` | `-` | Yes |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 10 | 7319 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 11 | 8042 | `ESC-1.1, REF-3.1` | `WAR-2.1` | No |

### Per-Call Breakdown (Variant F - All policy clauses (ceiling))

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 42 | 26124 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 42 | 26124 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 42 | 26124 | `REF-1.1, WAR-1.1` | `-` | Yes |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 42 | 26124 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 42 | 26124 | `ESC-1.1, ESC-3.1` | `-` | Yes |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 42 | 26124 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 42 | 26124 | `WAR-2.1, PRV-2.1` | `-` | Yes |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 42 | 26124 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 42 | 26124 | `ESC-1.1, WAR-2.1, REF-3.1` | `-` | Yes |

### Per-Call Breakdown (Variant G - Full context + PRV/ESC safety families)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 22 | 13484 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 23 | 14589 | `PRV-1.1, REF-1.1, REF-2.2` | `-` | Yes |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 21 | 13202 | `REF-1.1, WAR-1.1` | `-` | Yes |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 22 | 13837 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 14 | 8664 | `ESC-1.1, ESC-3.1` | `-` | Yes |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 21 | 12648 | `PRV-1.1, SHP-3.1` | `-` | Yes |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 22 | 13875 | `WAR-2.1, PRV-2.1` | `-` | Yes |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 21 | 13001 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 24 | 15366 | `ESC-1.1, REF-3.1` | `WAR-2.1` | No |

### Per-Call Breakdown (Variant H - Per-turn retrieval (union top-3 cap 14))

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|---|
| `call_201` | `shipping` | `SHP-2.1` | 14 | 10138 | `SHP-2.1` | `-` | Yes |
| `call_202` | `refund` | `PRV-1.1, REF-1.1, REF-2.2` | 14 | 9344 | `REF-1.1, REF-2.2` | `PRV-1.1` | No |
| `call_203` | `warranty` | `REF-1.1, WAR-1.1` | 14 | 9242 | `WAR-1.1` | `REF-1.1` | No |
| `call_204` | `billing` | `BIL-2.1, BIL-2.3` | 14 | 9211 | `BIL-2.1, BIL-2.3` | `-` | Yes |
| `call_205` | `complaint` | `ESC-1.1, ESC-3.1` | 14 | 9865 | `ESC-1.1, ESC-3.1` | `-` | Yes |
| `call_206` | `shipping` | `PRV-1.1, SHP-3.1` | 14 | 8914 | `SHP-3.1` | `PRV-1.1` | No |
| `call_207` | `warranty` | `WAR-2.1, PRV-2.1` | 14 | 8972 | `WAR-2.1, PRV-2.1` | `-` | Yes |
| `call_208` | `billing` | `BIL-3.1, ESC-1.1` | 14 | 8941 | `BIL-3.1, ESC-1.1` | `-` | Yes |
| `call_209` | `refund` | `ESC-1.1, WAR-2.1, REF-3.1` | 14 | 9423 | `ESC-1.1, WAR-2.1, REF-3.1` | `-` | Yes |


## 7. Dev vs Held-Out Comparative Analysis

> [!IMPORTANT]
> **Dataset Split Status Note:** The held-out set has now been evaluated and inspected for retrieval analysis. It has therefore been seen and effectively transitions into a secondary development / validation set; future variants must not be over-tuned to it.

### Cross-Split Retrieval Performance

| Variant | Dev Recall | Held-Out Recall | Dev Avg Sent | Held-Out Avg Sent | Dev Avg Chars | Held-Out Avg Chars | Generalisation Assessment |
|---|---|---|---|---|---|---|---|
| **A** | 100.0% (14/14) | 89.5% (17/19) | 13.9 | 13.6 | 9383 | 9175 | Baseline production context |
| **B** | 78.6% (11/14) | 68.4% (13/19) | 10.0 | 10.0 | 6565 | 6664 | Degraded on unseen dialogue |
| **C** | 71.4% (10/14) | 78.9% (15/19) | 10.0 | 10.0 | 6491 | 6715 | Degraded on unseen dialogue |
| **D** | 92.9% (13/14) | 78.9% (15/19) | 10.0 | 10.0 | 6890 | 6986 | Degraded on unseen dialogue |
| **E** | 92.9% (13/14) | 84.2% (16/19) | 11.0 | 10.8 | 7806 | 7703 | Core safety universal backup |
| **F** | 100.0% (14/14) | 100.0% (19/19) | 42.0 | 42.0 | 26124 | 26124 | Ceiling baseline (all clauses sent unconditionally) |
| **G** | 100.0% (14/14) | 94.7% (18/19) | 22.0 | 21.1 | 13728 | 13185 | Cross-cutting safety families guarantee zero safety misses |
| **H** | 92.9% (13/14) | 84.2% (16/19) | 14.0 | 14.0 | 9317 | 9339 | Per-turn union without topic bias |

### Critical Clauses Analysis (PRV & ESC Families)

- **PRV-2.1 (call_207 - Warranty Topic):** In `call_207`, the customer inquiry focused on warranty, but a sensitive personal data breach (`PRV-2.1`, CVV request) occurred. Variant A missed `PRV-2.1` because it only retrieved the warranty family and core safety (`PRV-1.1`, `ESC-1.1`, `ESC-1.2`). Variants F and G successfully retrieved `PRV-2.1` by including the full PRV family.
- **ESC-1.1 (call_209 - Topic Mismatch Complaint vs Refund):** In `call_209`, the topic was labelled `complaint` with escalation clause `ESC-1.1`, while topic detection classified it as `refund`. Because `ESC-1.1` is in `ALWAYS_INCLUDE`, Variants A, G, and F all successfully retrieved `ESC-1.1`.

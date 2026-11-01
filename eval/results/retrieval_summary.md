# Policy Retrieval Evaluation Summary (20261101_124539)

Evaluated **7 calls** with policy violations (**14 total expected clauses**).

## 1. Retrieval Performance Comparison

| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent |
|---|---|---|---|---|
| **A** | Full pipeline context (always_include + whole family + top-10) | 100.0% (14/14) | 100.0% (7/7) | 14.0 |
| **B** | Top-10 retrieval only (hybrid BM25 + embeddings, no always_include, no family) | 78.6% (11/14) | 57.1% (4/7) | 10.0 |
| **C** | BM25 only (BM25 only (use_embeddings=False), no always_include, no family) | 71.4% (10/14) | 57.1% (4/7) | 10.0 |

## 2. Misses by Variant

### Variant A: Full pipeline context
No misses. All expected clauses retrieved for all calls.

### Variant B: Top-10 retrieval only
- **call_102**: missed `PRV-1.1` (expected: `PRV-1.1, REF-3.1, REF-2.2, REF-2.1`)
- **call_104**: missed `PRV-1.1` (expected: `PRV-1.1, BIL-2.1`)
- **call_106**: missed `ESC-1.1` (expected: `ESC-1.1, SHP-2.3`)

### Variant C: BM25 only
- **call_102**: missed `PRV-1.1, REF-2.2` (expected: `PRV-1.1, REF-3.1, REF-2.2, REF-2.1`)
- **call_104**: missed `PRV-1.1` (expected: `PRV-1.1, BIL-2.1`)
- **call_106**: missed `ESC-1.1` (expected: `ESC-1.1, SHP-2.3`)

## 3. Topic Detection vs Labelled Topic

| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? |
|---|---|---|---|---|---|---|
| `call_041` | `warranty` | `general` | `WAR-3.2` | Yes | Yes | Yes |
| `call_106` | `shipping` | `complaint` | `ESC-1.1, SHP-2.3` | Yes | Partial (SHP-2.3) | Partial (SHP-2.3) |

## 4. Per-Call Breakdown (Variant A - Production)

| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |
|---|---|---|---|---|---|---|
| `call_017` | `shipping` | `SHP-2.1` | 13 | `SHP-2.1` | `-` | Yes |
| `call_025` | `warranty` | `WAR-2.1` | 13 | `WAR-2.1` | `-` | Yes |
| `call_041` | `warranty` | `WAR-3.2` | 14 | `WAR-3.2` | `-` | Yes |
| `call_102` | `refund` | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | 16 | `PRV-1.1, REF-3.1, REF-2.2, REF-2.1` | `-` | Yes |
| `call_104` | `billing` | `PRV-1.1, BIL-2.1` | 14 | `PRV-1.1, BIL-2.1` | `-` | Yes |
| `call_106` | `shipping` | `ESC-1.1, SHP-2.3` | 15 | `ESC-1.1, SHP-2.3` | `-` | Yes |
| `call_107` | `warranty` | `WAR-1.2, REF-1.1, WAR-1.1` | 13 | `WAR-1.2, REF-1.1, WAR-1.1` | `-` | Yes |

# Evaluation summary

Calls evaluated: **13**

| Metric | Result |
|---|---|
| Topic accuracy | 92% |
| SOP step exact-match (judged steps) | 94% over 143 steps |
| SOP deviation detection (missed/partial) | precision 100%, recall 91%, F1 0.95 |
| Policy violation detection (clause level) | precision 81%, recall 93%, F1 0.87 |
| Severity agreement on matched violations | 77% |
| Average score by call quality | {'good': 100.0, 'mild_deviation': 89.1, 'bad_deviation': 25.8} |
| Scores ordered good > mild > bad | True |
| Critical-failure detection | {'tp': 3, 'fp': 0, 'fn': 1, 'tn': 9} |

## Gap detection

| Gap | precision | recall | tp/fp/fn |
|---|---|---|---|
| customer_repeating | 0% | 0% | 0/1/0 |
| dead_air | 100% | 100% | 1/0/0 |
| hold_too_long | 100% | 100% | 1/0/0 |
| interruption | 100% | 100% | 2/0/0 |
| no_closing | 67% | 100% | 2/1/0 |
| no_empathy | 80% | 80% | 4/1/1 |
| no_summary | 0% | 0% | 0/2/1 |
| other | 0% | 0% | 0/1/0 |
| unresolved_issue | 0% | 0% | 0/1/0 |

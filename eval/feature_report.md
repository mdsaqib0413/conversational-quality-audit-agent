# Feature test report

Generated 2026-10-21T00:52:32 · 13 calls, 0 with AI audits

| Result | Count |
|---|---|
| PASS | 5 |
| SKIP | 8 |

| Feature | Check | Expected | Actual | Result |
|---|---|---|---|---|
| Topic detection | Calls whose topic is recognised | >= 85% | 92% (12/13) | PASS |
| Situation signals | Expected signals that were detected | >= 100% | 100% (8/8) | PASS |
| Choosing the script steps to judge | Labelled steps that were put up for judging | >= 100% | 100% (13/13) | PASS |
| Silences, holds and interruptions | Counts that match exactly | >= 100% | 100% (52/52) | PASS |
| Silences, holds and interruptions | Agent talk share within 6 points of expected | >= 95% | 100% (13/13) | PASS |
| Score arithmetic | Script score matches independent arithmetic | >= 100% | 100% (13/13) | PASS |
| Score arithmetic | Rules score matches independent arithmetic | >= 100% | 100% (13/13) | PASS |
| Score arithmetic | A missed critical step never scores above 70 | >= 100% | 100% (4/4) | PASS |
| Script (SOP) judging | Steps judged exactly as labelled | >= 90% | needs AI audits | SKIP |
| Script (SOP) judging | Real problems that were caught | >= 85% | needs AI audits | SKIP |
| Script (SOP) judging | Flagged problems that were real | >= 90% | needs AI audits | SKIP |
| Company-rule (policy) check | Real rule violations that were found | >= 90% | needs AI audits | SKIP |
| Company-rule (policy) check | Reported violations that were real | >= 85% | needs AI audits | SKIP |
| Company-rule (policy) check | Severity matches the label | >= 75% | needs AI audits | SKIP |
| Evidence integrity | Audits with no unverifiable quote | >= 98% | needs AI audits | SKIP |
| Scores and grades | Grade inside the expected range | >= 100% | needs AI audits | SKIP |
| Scores and grades | Score inside the expected band | >= 100% | needs AI audits | SKIP |
| Scores and grades | Critical failures flagged and capped | >= 100% | needs AI audits | SKIP |
| Scores and grades | Script score near the expected value | >= 90% | needs AI audits | SKIP |
| Scores and grades | Overall score near the estimate | >= 80% | needs AI audits | SKIP |
| Emotion and tone | Customer's starting mood | >= 75% | needs AI audits | SKIP |
| Emotion and tone | Customer's ending mood | >= 75% | needs AI audits | SKIP |
| Emotion and tone | Mood trend (better / same / worse) | >= 70% | needs AI audits | SKIP |
| Emotion and tone | Agent tone matches expectation | >= 80% | needs AI audits | SKIP |
| Conversation gaps | Timing gaps reported exactly | >= 100% | needs AI audits | SKIP |
| Conversation gaps | Expected empathy / recap / closing gaps reported | >= 60% | needs AI audits | SKIP |
| AI request budget | Audits within budget | >= 100% | needs AI audits | SKIP |
| Report outputs | HTML has every section | >= 100% | no data | SKIP |
| Report outputs | PDF is produced | >= 100% | no data | SKIP |
| Report outputs | JSON reloads to the same report | >= 100% | no data | SKIP |
| Report outputs | Text from calls cannot inject HTML | >= 100% | no data | SKIP |

## Calls where actual differs from expected

| Call | Feature | Item | Expected | Actual | Level |
|---|---|---|---|---|---|
| call_041 | topic | Topic | general | warranty | hard |

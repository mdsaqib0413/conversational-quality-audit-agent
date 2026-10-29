# AuditIQ — 3-Minute Demo Script

## Calls to have open before starting
| Role | Call ID | Why |
|------|---------|-----|
| Good agent | `call_101` | Perfect refund call, grade A, 100/100 |
| Mild deviation | `call_025` | Missed empathy step, minor warranty violation, grade C |
| Bad agent | `call_102` | 4 policy violations incl. critical privacy breach, grade D, critical failure |

---

## (a) Problem — 30 s
> "QA teams manually review fewer than 2% of support calls — too slow, too biased, and zero real-time feedback. AuditIQ audits every call automatically: transcription, speaker separation, compliance check, and a scored report — in under a minute."

---

## (b) Upload & Report + Audio Player — 45 s
**Page:** Sidebar → **Audit a call**

1. Toggle sidebar **Dark mode** — note instant theme switch across all UI chrome, cards, and player.
2. Radio: *Pick a sample call* → select **`call_102 · recording (mono, speakers found by AI)`**
3. Click **Run audit on this sample** — watch the 5-step progress bar.
4. Report opens automatically on the **Report** page with the **Call player & interactive timeline** at top.
5. Click key moment **"Agent deviated at 01:05..."** or **"Agent said 30 days..."** — audio seeks and plays instantly; waveform pin highlights.
6. Point to the red **Critical failure** banner and score **4.5 / 100 · Grade D**.

> _"From raw MP3 to scored audit and audio playback with key-moment navigation, zero human effort."_

---

## (c) SOP Checklist with Evidence — 30 s
**Page:** Report → tab **Call script**

- Switch to **Table** view.
- Show the **Missed** column: GEN-02 (identity verification), GEN-03 (recording disclosure), REF-S1 (eligibility check) — all red, marked CRITICAL.
- Click any step card to expand the verbatim **evidence quote** and **turn number**.

> _"Every finding cites the exact words and the turn it came from — no hallucination."_

---

## (d) Policy Violation & Policies Involved — 30 s
**Page:** Report → tab **Company rules**

- Show violation **REF-3.1** (critical): agent quoted a **14-day return window**; policy says **7 days for electronics**.
- Point to the side-by-side: *"What was said (clickable turn)" / "What the policy says"* and the **−30 pts** penalty chip.
- Scroll to **Policies & SOPs involved**: grouped by family (Refund, Warranty, Privacy, Escalation) with status chips (*Violated*, *Followed*, *No issue found*).

> _"The system retrieves authoritative clauses, highlights involved policies, and proves where the agent stated the wrong figure."_


---

## (e) Good vs Bad Comparison — 20 s
**Page:** Sidebar → **Dashboard**

- Grade board: `call_101` in the **A** column (100/100, Clean), `call_102` in the **D** column (4.5/100, Critical failure).
- Point to the score bar chart across all calls.

> _"At a glance, a manager sees every agent ranked by grade — no spreadsheet needed."_

---

## (f) Real Call — Scam Banner — 20 s
**Page:** Sidebar → **Report** → filter **Real** → select **`en_real_001  ·  Not scored`**

- Show the orange **Real call** disclaimer and the red **"Not scored"** verdict banner.
- Point to the risk flags: remote-access tools, OTP requests.

> _"The pipeline even flags when a call doesn't fit any ShopEase policy — and warns that it may be a scam attempt."_

---

## (g) Phase 2 Teaser — 15 s
**Page:** Sidebar → **Live assist**

- Pick any transcript, drag the *"How far into the call"* slider.
- Show the **detected topic**, confidence %, and **rules to keep in view** updating live.

> _"Phase 2: the same engine, running live — pushing the right policy clause to the agent's screen before they make a mistake."_

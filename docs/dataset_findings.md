# Telugu Dataset Findings: Kaggle Audio Call Center Telugu

## 1. Verified Facts (Direct File Measurements)
The following audio files under `data/telugu/` were directly inspected and measured:

- **Sample - 01:**
  - `SPEAKER_00.wav`, `SPEAKER_01.wav`
  - Audio Format: Mono, 8000 Hz sample rate
  - Duration: 349.6 seconds each
  - Channel Layout: 2 individual mono files with identical duration (time-aligned per-speaker tracks on a shared timeline).

- **Sample - 02:**
  - `SPEAKER_00.wav`, `SPEAKER_01.wav`, `SPEAKER_02.wav`
  - Audio Format: Mono, 8000 Hz sample rate
  - Duration: 448.6 seconds each
  - Channel Layout: 3 individual mono files with identical duration (time-aligned per-speaker tracks on a shared timeline).

- **Sample - 03:**
  - `SPEAKER_00.wav`, `SPEAKER_01.wav`, `SPEAKER_02.wav`
  - Audio Format: Mono, 8000 Hz sample rate
  - Duration: 379.4 seconds each
  - Channel Layout: 3 individual mono files with identical duration (time-aligned per-speaker tracks on a shared timeline).

### Key Architectural Discovery
**This dataset is NOT dual-channel stereo audio.** Across all inspected samples, the data consists of multiple separate mono tracks (2 tracks in Sample 01, 3 tracks in Samples 02 and 03) sharing an identical timeline duration. Any assumption of "dual-channel agent-left / customer-right" is incorrect for this dataset and must not be used for the Telugu pipeline.

---

## 2. Preliminary Observations (Unverified - Not Citations of Fact)
- **Track Activity Dynamics:** A preliminary loudness scan suggested Sample 01's two tracks show alternating active speech with silence gaps, whereas Sample 02 and Sample 03's three tracks exhibit near-continuous energy on most tracks across much of the recording.
- **Human Review Requirement:** This observation is not a conclusion regarding turn-taking; a human must listen carefully to the 3-speaker tracks of Samples 02 and 03 to determine whether conversational turn-taking, crosstalk, or background audio explains the activity patterns.

---

## 3. Not Yet Verified (Requires Direct Human Inspection)
The following items remain strictly **UNVERIFIED**:
1. **License & Redistribution Rights:** Dataset licensing terms from the publisher/Kaggle metadata have not been formally confirmed.
2. **Telugu Language Confirmation:** Acoustic verification that spoken dialogue is exclusively or predominantly Telugu requires human listening.
3. **Domain & Call-Center Content:** Whether the calls represent actual e-commerce/retail customer support or general conversational inquiries requires human listening.
4. **Channel Isolation vs Bleed-Through:** Whether the separate speaker tracks represent clean independent acoustic capture or contain acoustic cross-bleed from the same physical room requires human listening.
5. **PII Exposure:** Whether real customer names, phone numbers, addresses, or financial data are present in the recordings requires human listening and compliance review.

---

## 4. Open Action Items for Human Auditors
- [ ] Listen to `Sample - 01` (Tracks 00 & 01): Identify speaker roles (which track corresponds to agent vs customer).
- [ ] Listen to `Sample - 02` & `Sample - 03` (Tracks 00, 01 & 02): Identify who the third speaker is (supervisor, automated IVR, teleconference participant, or background noise) and verify turn alternation.
- [ ] Determine track acoustic purity (clean microphone separation vs room bleed).

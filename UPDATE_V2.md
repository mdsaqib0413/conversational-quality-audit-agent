# Backend v2 drop-in (unzip over your project, say "yes" to overwrite)

What changed
- src/audit/llm.py: the old file had a SyntaxError (nothing could import it). Rewritten: Gemini + optional
  OpenAI-compatible fallback (Groq/Ollama), per-minute waits, daily-quota fallback chain, request counter.
- New backend: rag.py (policies + SOP parsing, hybrid retrieval), topic.py, diarize.py, transcribe.py, sop_check.py,
  policy_check.py, scoring.py, emotion.py, evidence.py, pipeline.py, report.py (PDF), evaluation.py.
- app/streamlit_app.py: upload -> audit -> report, policy lookup, live-assist preview (Phase 2).
- eval/run_eval.py, scripts/audit_cli.py, scripts/audio_smoke_test.py, scripts/repair_violation_turns.py.
- generate_transcripts.py: violation turn is now located from the dialogue instead of guessing the middle turn.
- data/transcripts: call_017, call_025, call_041 violation labels corrected (turns 9, 7, 9).
- tests/: 67 offline tests. The old tests/test_basic.py is replaced.

After unzipping (your .env is NOT touched)
  pip install -r requirements.txt
  python -m pytest tests -q                       # must say 67 passed
  python eval/run_eval.py --no-llm --include-unverified    # free
  python scripts/audio_smoke_test.py data/audio/call_001_stereo.mp3   # free, needs no API key
  streamlit run app/streamlit_app.py

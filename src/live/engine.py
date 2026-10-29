"""Thread-safe LiveSession engine for streaming audio transcription and rolling-window analysis."""

from __future__ import annotations

import logging
import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .analysis import run_live_analysis
from .rules import LiveRuleEngine
from .schemas import LiveAlert, LiveSnapshot, LiveTurn

logger = logging.getLogger(__name__)

SMALL_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}

MAGNITUDES = {
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100000,
    "crore": 10000000,
}

BRAND_CORRECTIONS = {
    "shopee": "ShopEase",
    "shop ease": "ShopEase",
    "shopeez": "ShopEase",
    "shop eez": "ShopEase",
    "shopease": "ShopEase",
}


def apply_brand_corrections(text: str) -> str:
    """Correct brand terms like shopee, shop ease to ShopEase."""
    if not text:
        return text
    pat = re.compile(r"\b(?:shop\s*ease|shopeez?|shop\s+eez)\b", re.IGNORECASE)
    return pat.sub("ShopEase", text)


def _parse_number_tokens(tokens: List[str]) -> int:
    total = 0
    current = 0
    for tok in tokens:
        if tok in SMALL_NUMS:
            current += SMALL_NUMS[tok]
        elif tok == "hundred":
            current = (current if current else 1) * 100
        elif tok in MAGNITUDES:
            mult = MAGNITUDES[tok]
            total += (current if current else 1) * mult
            current = 0
    return total + current


def normalize_spoken_numbers(text: str) -> str:
    """Finds sequences of spoken number words and replaces them with digits (e.g. eight thousand five hundred -> 8500)."""
    if not text:
        return text
    num_words = set(SMALL_NUMS.keys()) | set(MAGNITUDES.keys()) | {"and"}
    words = re.split(r"(\s+)", text)
    result = []
    i = 0
    while i < len(words):
        token = words[i]
        token_clean = re.sub(r"[^\w]", "", token.lower())
        if token_clean in num_words and token_clean != "and":
            seq = [token_clean]
            raw_indices = [i]
            j = i + 1
            while j < len(words):
                next_raw = words[j]
                if re.match(r"^\s+$", next_raw):
                    j += 1
                    continue
                next_clean = re.sub(r"[^\w]", "", next_raw.lower())
                if next_clean in num_words:
                    seq.append(next_clean)
                    raw_indices.append(j)
                    j += 1
                else:
                    break
            if seq and seq[-1] == "and":
                seq.pop()
                raw_indices.pop()
            valid = [w for w in seq if w in SMALL_NUMS or w in MAGNITUDES]
            if valid:
                val = _parse_number_tokens(seq)
                result.append(str(val))
                i = raw_indices[-1] + 1
                continue
        result.append(token)
        i += 1
    return "".join(result)


def collapse_immediate_repeats(text: str) -> str:
    """Collapses immediate repeats such as 'eight thousand 8500' or 'supervisor. supervisors need it'."""
    if not text:
        return text
    t = normalize_spoken_numbers(text)
    # Collapse pattern: word number followed by digit number like "8000 8500" -> "8500"
    t = re.sub(r"\b\d{1,2}000\s+(\d{4,5})\b", r"\1", t)
    # Collapse exact duplicated numbers like "8500 8500" -> "8500"
    t = re.sub(r"\b(\d+)\s+\1\b", r"\1", t)
    # Also "eight thousand 8500" if any part remained
    t = re.sub(r"\b(?:[A-Za-z]+\s+thousand)\s+(\d{4,5})\b", r"\1", t, flags=re.IGNORECASE)

    # Collapse repeated word stem with punctuation/space, e.g. "supervisor. supervisors"
    def _stem_dedupe(match):
        w1, w2, sep = match.group(1), match.group(2), match.group(3)
        s1, s2 = w1.lower(), w2.lower()
        if s1 == s2 or (len(s1) >= 4 and (s2.startswith(s1) or s1.startswith(s2))):
            return w2 + sep
        return match.group(0)

    t = re.sub(r"\b([A-Za-z]{4,})[,\.]?\s+([A-Za-z]{4,})(\s+|$)", _stem_dedupe, t)
    return t.strip()


def dedupe_word_overlap(prev_text: str, next_text: str, max_check_words: int = 8) -> str:
    """Remove overlapping words at the boundary between consecutive overlapping chunks with spoken number normalization."""
    if not prev_text or not next_text:
        return next_text.strip()

    def _clean_tokens(tokens: List[str]) -> List[str]:
        return [re.sub(r"[^\w]", "", w.lower()) for w in tokens]

    def _find_overlap(p_tokens: List[str], n_tokens: List[str], max_k: int) -> int:
        for k in range(min(len(p_tokens), len(n_tokens), max_k), 0, -1):
            match = True
            for a, b in zip(p_tokens[-k:], n_tokens[:k]):
                if a == b:
                    continue
                if a.isdigit() and b.isdigit() and (a.endswith(b) or b.endswith(a)):
                    continue
                if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
                    continue
                match = False
                break
            if match:
                return k
        return 0

    # 1. First attempt: check overlap on raw spoken words
    p_raw_words = apply_brand_corrections(prev_text).strip().split()
    n_raw_words = apply_brand_corrections(next_text).strip().split()
    if p_raw_words and n_raw_words:
        k_raw = _find_overlap(_clean_tokens(p_raw_words), _clean_tokens(n_raw_words), max_check_words)
        if k_raw > 0:
            tail = " ".join(n_raw_words[k_raw:]).strip()
            tail_norm = normalize_spoken_numbers(tail)
            return collapse_immediate_repeats(tail_norm)

    # 2. Second attempt: check overlap after spoken number normalization
    p_norm = normalize_spoken_numbers(apply_brand_corrections(prev_text))
    n_norm = normalize_spoken_numbers(apply_brand_corrections(next_text))

    prev_words = p_norm.strip().split()
    next_words = n_norm.strip().split()

    if not prev_words or not next_words:
        return next_text.strip()

    k_norm = _find_overlap(_clean_tokens(prev_words), _clean_tokens(next_words), max_check_words)
    if k_norm > 0:
        tail = " ".join(next_words[k_norm:]).strip()
    else:
        tail = n_norm.strip()

    combined = collapse_immediate_repeats(f"{p_norm.strip()} {tail}".strip())
    prefix = p_norm.strip()
    if combined.startswith(prefix):
        return combined[len(prefix):].strip()
    return tail


class LiveSession:
    """Thread-safe live audit session managing streaming audio, transcription, and state snapshots."""

    def __init__(
        self,
        model_size: str = "base.en",
        chunk_duration_sec: float = 3.5,
        overlap_sec: float = 0.5,
        rule_engine: Optional[LiveRuleEngine] = None,
        transcriber_fn: Optional[Callable[[np.ndarray], str]] = None,
        stereo_exact: bool = True,
        call_id: str = "",
    ):
        self.model_size = model_size
        self.chunk_duration_sec = chunk_duration_sec
        self.overlap_sec = overlap_sec
        self.rule_engine = rule_engine or LiveRuleEngine()
        self.transcriber_fn = transcriber_fn
        self.stereo_exact = stereo_exact
        self.call_id = call_id

        self._lock = threading.RLock()
        self._audio_queue: queue.Queue[Tuple[str, bytes, float]] = queue.Queue()
        self._buffers: Dict[str, bytearray] = {"agent": bytearray(), "customer": bytearray()}
        self._buffer_start_times: Dict[str, float] = {"agent": 0.0, "customer": 0.0}

        self.turns: List[LiveTurn] = []
        self.accumulated_alerts: List[LiveAlert] = []
        self.last_speech_time: float = 0.0
        self.last_silence_sec: float = 0.0
        self.total_duration_sec: float = 0.0
        self.latency_ms: float = 0.0
        self.status: str = "idle"
        self.end_suggested: bool = False

        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._model = None
        self._latest_snapshot: Optional[LiveSnapshot] = None

    def _get_model(self):
        if self._model is None and self.transcriber_fn is None:
            from faster_whisper import WhisperModel

            logger.info("Initializing faster-whisper LiveSession model: %s", self.model_size)
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def start(self) -> None:
        """Start the background transcription worker."""
        with self._lock:
            if self.status == "running":
                return
            self.status = "running"
            self._stop_event.clear()
            self.rule_engine.reset()
            self.accumulated_alerts.clear()
            self.turns.clear()
            self._buffers = {"agent": bytearray(), "customer": bytearray()}
            self._buffer_start_times = {"agent": 0.0, "customer": 0.0}
            self.last_speech_time = 0.0
            self.last_silence_sec = 0.0
            self.total_duration_sec = 0.0
            self.end_suggested = False

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="LiveSessionWorker")
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop the background transcription worker cleanly."""
        self._stop_event.set()
        with self._lock:
            if self.status != "ended":
                self.status = "stopped"
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._update_snapshot()

    def flush_and_end(self) -> None:
        """Flush remaining audio, finalize all partial turns, set status ENDED, and update snapshot."""
        self._stop_event.set()

        # Join worker first so it no longer competes for the lock
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        with self._lock:
            while True:
                try:
                    spk, data, t0 = self._audio_queue.get_nowait()
                    buf = self._buffers[spk]
                    if len(buf) == 0:
                        self._buffer_start_times[spk] = t0
                    buf.extend(data)
                except queue.Empty:
                    break

            bytes_per_sec = 16000 * 2
            for spk in ["agent", "customer"]:
                buf = self._buffers[spk]
                if len(buf) >= int(bytes_per_sec * 0.2):
                    chunk_data = bytes(buf)
                    buf.clear()
                    chunk_t0 = self._buffer_start_times[spk]
                    chunk_t1 = chunk_t0 + len(chunk_data) / bytes_per_sec
                    samples = np.frombuffer(chunk_data, dtype=np.int16).astype(np.float32) / 32768.0
                    try:
                        text = self._transcribe_samples(samples)
                    except Exception as e:
                        logger.warning("Error on final flush chunk: %s", e)
                        text = ""
                    if text:
                        text = apply_brand_corrections(text)
                        self._merge_turn(spk, text, chunk_t0, chunk_t1)

            # Finalize partial turn flag: no (speaking...) left
            for t in self.turns:
                t.partial = False

            self.status = "ended"

        self._update_snapshot()

    def push_audio(self, speaker: str, pcm16_16k_bytes: bytes, t0: float) -> None:
        """Feed a slice of 16kHz mono 16-bit PCM audio into the session queue."""
        if self.status != "running" and not self._stop_event.is_set():
            self.start()
        self._audio_queue.put((speaker, pcm16_16k_bytes, t0))

    def _transcribe_samples(self, samples: np.ndarray) -> str:
        """Transcribe a chunk of float32 16kHz mono samples with initial_prompt and hotwords."""
        if self.transcriber_fn:
            return self.transcriber_fn(samples)

        m = self._get_model()
        prompt = "ShopEase, Rs, rupees, order ID, supervisor, refund, replacement, warranty, AnyDesk, TeamViewer, OTP"
        segments, _ = m.transcribe(
            samples,
            beam_size=1,
            vad_filter=True,
            language="en",
            condition_on_previous_text=False,
            initial_prompt=prompt,
            hotwords=prompt.replace(",", ""),
        )
        texts = [s.text.strip() for s in segments if s.text and s.text.strip()]
        raw = " ".join(texts).strip()
        return apply_brand_corrections(raw)

    def _check_end_suggested(self, turns: List[LiveTurn], silence_sec: float) -> bool:
        """Detect closing phrases followed by >= 8s silence or >= 30s total silence."""
        if silence_sec >= 30.0:
            return True
        close_pat = re.compile(
            r"\b(?:bye|goodbye|have a (?:nice|good|great|wonderful) day|thank you for (?:calling|choosing)|take care)\b",
            re.IGNORECASE,
        )
        has_closing = any(close_pat.search(t.text) for t in turns)
        if has_closing and silence_sec >= 8.0:
            return True
        return False

    def _worker_loop(self) -> None:
        """Background worker: pulls audio, transcribes chunks, merges turns, updates snapshot."""
        bytes_per_sec = 16000 * 2  # 16kHz * 2 bytes/sample
        chunk_bytes = int(self.chunk_duration_sec * bytes_per_sec)
        overlap_bytes = int(self.overlap_sec * bytes_per_sec)
        step_bytes = chunk_bytes - overlap_bytes

        while not self._stop_event.is_set():
            has_data = False
            while True:
                try:
                    spk, data, t0 = self._audio_queue.get_nowait()
                    has_data = True
                    buf = self._buffers[spk]
                    if len(buf) == 0:
                        self._buffer_start_times[spk] = t0
                    buf.extend(data)
                    self.total_duration_sec = max(self.total_duration_sec, t0 + len(data) / bytes_per_sec)
                except queue.Empty:
                    break

            processed_any = False
            t_loop_start = time.perf_counter()

            for spk in ["agent", "customer"]:
                buf = self._buffers[spk]
                if len(buf) >= chunk_bytes:
                    chunk_data = bytes(buf[:chunk_bytes])
                    chunk_t0 = self._buffer_start_times[spk]
                    chunk_t1 = chunk_t0 + len(chunk_data) / bytes_per_sec

                    del buf[:step_bytes]
                    self._buffer_start_times[spk] = chunk_t0 + step_bytes / bytes_per_sec

                    samples = np.frombuffer(chunk_data, dtype=np.int16).astype(np.float32) / 32768.0
                    try:
                        text = self._transcribe_samples(samples)
                    except Exception as e:
                        logger.warning("Transcription error on live chunk: %s", e)
                        text = ""

                    if text:
                        self._merge_turn(spk, text, chunk_t0, chunk_t1)
                        self.last_speech_time = chunk_t1
                        self.last_silence_sec = 0.0
                    else:
                        self.last_silence_sec = max(0.0, self.total_duration_sec - self.last_speech_time)

                    processed_any = True

            self.end_suggested = self._check_end_suggested(self.turns, self.last_silence_sec)

            if processed_any or has_data:
                self.latency_ms = (time.perf_counter() - t_loop_start) * 1000.0
                self._update_snapshot()

            time.sleep(0.08)

        self._update_snapshot()

    def _merge_turn(self, speaker: str, new_chunk_text: str, t_start: float, t_end: float) -> None:
        """Merge a transcribed chunk into the turns list with overlap deduplication."""
        new_chunk_text = collapse_immediate_repeats(apply_brand_corrections(new_chunk_text))
        with self._lock:
            if not self.turns:
                turn = LiveTurn(
                    speaker=speaker,
                    start=t_start,
                    end=t_end,
                    text=new_chunk_text,
                    partial=(self.status != "ended"),
                    turn_id=1,
                )
                self.turns.append(turn)
                return

            last_turn = self.turns[-1]

            if last_turn.speaker == speaker and (t_start - last_turn.end) < 1.8:
                deduped = dedupe_word_overlap(last_turn.text, new_chunk_text)
                if deduped:
                    combined = f"{last_turn.text} {deduped}".strip()
                    last_turn.text = collapse_immediate_repeats(combined)
                last_turn.end = max(last_turn.end, t_end)
                last_turn.partial = (self.status != "ended")
            else:
                last_turn.partial = False
                new_id = last_turn.turn_id + 1
                new_turn = LiveTurn(
                    speaker=speaker,
                    start=t_start,
                    end=t_end,
                    text=new_chunk_text,
                    partial=(self.status != "ended"),
                    turn_id=new_id,
                )
                self.turns.append(new_turn)

    def _update_snapshot(self) -> None:
        """Run rolling-window analysis and construct an immutable snapshot for the UI."""
        with self._lock:
            turns_copy = [LiveTurn(t.speaker, t.start, t.end, t.text, t.partial, t.turn_id) for t in self.turns]
            duration = self.total_duration_sec
            silence = self.last_silence_sec
            st = self.status
            cid = self.call_id
            end_sug = self.end_suggested

        snapshot = run_live_analysis(
            turns=turns_copy,
            duration_sec=duration,
            last_silence_sec=silence,
            rule_engine=self.rule_engine,
            accumulated_alerts=self.accumulated_alerts,
            stereo_exact=self.stereo_exact,
            status=st,
            call_id=cid,
        )
        snapshot.latency_ms = self.latency_ms
        snapshot.end_suggested = end_sug

        with self._lock:
            self._latest_snapshot = snapshot

    def get_snapshot(self) -> LiveSnapshot:
        """Thread-safe getter for the latest session snapshot (consumed by st.fragment)."""
        with self._lock:
            if self._latest_snapshot is not None:
                return self._latest_snapshot
            return LiveSnapshot(status=self.status, duration_sec=self.total_duration_sec, call_id=self.call_id)

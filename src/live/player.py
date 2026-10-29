"""Simulate a live audio call stream from a stereo or mono recording at 1x or 2x speed."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import pydub

from .engine import LiveSession

logger = logging.getLogger(__name__)


class LiveSimulator:
    """Reads audio file and streams PCM chunks into LiveSession at real-time or accelerated rate."""

    def __init__(
        self,
        audio_path: Path,
        session: LiveSession,
        speed: float = 1.0,
        chunk_slice_sec: float = 0.5,
    ):
        self.audio_path = Path(audio_path)
        self.session = session
        self.speed = max(0.5, float(speed))
        self.chunk_slice_sec = chunk_slice_sec

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.is_stereo = True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_audio, daemon=True, name="LiveAudioFeeder")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _stream_audio(self) -> None:
        if not self.audio_path.exists():
            logger.error("Simulator audio file not found: %s", self.audio_path)
            self.session.stop()
            return

        try:
            seg = pydub.AudioSegment.from_file(str(self.audio_path))
        except Exception as e:
            logger.error("Failed to load audio for simulation: %s", e)
            self.session.stop()
            return

        self.session.start()

        if seg.channels >= 2:
            self.is_stereo = True
            self.session.stereo_exact = True
            mono_channels = seg.split_to_mono()
            agent_seg = mono_channels[0].set_frame_rate(16000).set_sample_width(2)
            cust_seg = mono_channels[1].set_frame_rate(16000).set_sample_width(2)
        else:
            self.is_stereo = False
            self.session.stereo_exact = False
            agent_seg = seg.set_frame_rate(16000).set_sample_width(2)
            cust_seg = agent_seg  # Monophonic fallback

        agent_raw = agent_seg.raw_data
        cust_raw = cust_seg.raw_data

        bytes_per_slice = int(16000 * 2 * self.chunk_slice_sec)
        total_len = min(len(agent_raw), len(cust_raw))
        offset = 0
        t0 = 0.0

        while offset < total_len and not self._stop_event.is_set():
            t_slice_start = time.perf_counter()

            end_offset = min(total_len, offset + bytes_per_slice)
            agent_chunk = agent_raw[offset:end_offset]
            cust_chunk = cust_raw[offset:end_offset]

            self.session.push_audio("agent", agent_chunk, t0)
            self.session.push_audio("customer", cust_chunk, t0)

            slice_duration = (end_offset - offset) / (16000.0 * 2.0)
            t0 += slice_duration
            offset = end_offset

            # Sleep real-time duration scaled by speed
            target_sleep = slice_duration / self.speed
            elapsed = time.perf_counter() - t_slice_start
            sleep_sec = max(0.001, target_sleep - elapsed)
            time.sleep(sleep_sec)

        # EOF reached: flush remaining audio and set state ended
        time.sleep(0.5)
        if not self._stop_event.is_set():
            self.session.flush_and_end()
        else:
            self.session.stop()

"""Replay simulator converting call transcripts into ordered CaptionEvent streams."""
from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, Iterator, List, Optional, Union

from ..schemas import CallTranscript, DialogueTurn
from ..transcript_io import load_transcript_json
from .events import CaptionEvent


def _parse_source(source: Union[str, Path, dict, CallTranscript], call_id: Optional[str] = None) -> tuple[str, List[DialogueTurn]]:
    """Extract call_id and list of DialogueTurn objects from various input representations."""
    if isinstance(source, CallTranscript):
        return source.call_id or call_id or "live_call", source.turns

    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Transcript or audit file not found: {p}")
        raw = json.loads(p.read_text(encoding="utf-8"))
        cid = call_id or raw.get("call_id") or raw.get("id") or p.stem.split("_")[0]
        # Check if this is a cached audit JSON
        if "transcript" in raw and isinstance(raw["transcript"], dict) and "turns" in raw["transcript"]:
            turns_data = raw["transcript"]["turns"]
            turns = []
            for idx, t in enumerate(turns_data, start=1):
                turns.append(DialogueTurn(
                    turn_id=t.get("turn_id", idx),
                    speaker=t.get("speaker", "agent"),
                    start_time=float(t.get("start_time", 0.0)),
                    end_time=float(t.get("end_time", 0.0)),
                    text=t.get("text", ""),
                    silence_before=float(t.get("silence_before", 0.0)),
                    overlaps_previous=bool(t.get("overlaps_previous", False)),
                ))
            return cid, turns
        # Otherwise treat as raw transcript file (data/transcripts/*.json)
        call_obj, _ = load_transcript_json(p)
        return call_id or call_obj.call_id or cid, call_obj.turns

    if isinstance(source, dict):
        cid = call_id or source.get("call_id") or source.get("id") or "live_call"
        if "transcript" in source and isinstance(source["transcript"], dict):
            turns_data = source["transcript"].get("turns", [])
        else:
            turns_data = source.get("turns", [])

        # If turns lack start_time/end_time, synthesize using transcript_io logic
        if turns_data and "start_time" not in turns_data[0]:
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
                tmp.write(json.dumps(source))
                tmp_path = Path(tmp.name)
            try:
                call_obj, _ = load_transcript_json(tmp_path)
                return cid, call_obj.turns
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        else:
            turns = [
                DialogueTurn(
                    turn_id=t.get("turn_id", idx),
                    speaker=t.get("speaker", "agent"),
                    start_time=float(t.get("start_time", 0.0)),
                    end_time=float(t.get("end_time", 0.0)),
                    text=t.get("text", ""),
                    silence_before=float(t.get("silence_before", 0.0)),
                    overlaps_previous=bool(t.get("overlaps_previous", False)),
                )
                for idx, t in enumerate(turns_data, start=1)
            ]
            return cid, turns

    raise TypeError(f"Unsupported transcript source type: {type(source)}")


class CallSimulator:
    """Replays a call as a sequence of CaptionEvents with speed control and optional interim steps."""

    def __init__(
        self,
        source: Union[str, Path, dict, CallTranscript],
        call_id: Optional[str] = None,
        speed: float = 1.0,
        emit_interim: bool = False,
    ) -> None:
        self.call_id, self.turns = _parse_source(source, call_id=call_id)
        self.speed = max(0.1, float(speed))
        self.emit_interim = emit_interim

    def build_events(self) -> List[CaptionEvent]:
        """Generate ordered list of CaptionEvents (interims + finals)."""
        events: List[CaptionEvent] = []
        for t in self.turns:
            start_ms = int(round(t.start_time * 1000))
            end_ms = int(round(t.end_time * 1000))
            role = t.speaker
            peer_id = f"{role}_0"
            full_text = t.text.strip()

            if self.emit_interim:
                words = full_text.split()
                # Generate intermediate hypotheses for sufficiently long turns
                if len(words) >= 4:
                    dur = max(0, end_ms - start_ms)
                    # Interim slice 1 (approx 40% duration)
                    mid1 = max(1, int(len(words) * 0.4))
                    mid1_ms = start_ms + int(dur * 0.4)
                    events.append(CaptionEvent(
                        call_id=self.call_id,
                        peer_id=peer_id,
                        role=role,
                        text=" ".join(words[:mid1]),
                        start_ms=start_ms,
                        end_ms=mid1_ms,
                        final=False,
                        turn_id=t.turn_id,
                    ))
                    # Interim slice 2 (approx 75% duration)
                    mid2 = max(mid1 + 1, int(len(words) * 0.75))
                    if mid2 < len(words):
                        mid2_ms = start_ms + int(dur * 0.75)
                        events.append(CaptionEvent(
                            call_id=self.call_id,
                            peer_id=peer_id,
                            role=role,
                            text=" ".join(words[:mid2]),
                            start_ms=start_ms,
                            end_ms=mid2_ms,
                            final=False,
                            turn_id=t.turn_id,
                        ))

            # Final committed caption turn
            events.append(CaptionEvent(
                call_id=self.call_id,
                peer_id=peer_id,
                role=role,
                text=full_text,
                start_ms=start_ms,
                end_ms=end_ms,
                final=True,
                turn_id=t.turn_id,
            ))
        return events

    def iter_events(self, realtime: bool = False) -> Iterator[CaptionEvent]:
        """Stream events. If realtime=True, sleep between events scaled by speed factor."""
        events = self.build_events()
        if not realtime or not events:
            for ev in events:
                yield ev
            return

        last_ms = 0
        for ev in events:
            wait_ms = max(0, ev.end_ms - last_ms)
            wait_sec = (wait_ms / 1000.0) / self.speed
            if wait_sec > 0:
                time.sleep(min(wait_sec, 5.0))  # Cap single sleep at 5s to avoid stalling
            last_ms = ev.end_ms
            yield ev


def replay_call(
    source: Union[str, Path, dict, CallTranscript],
    call_id: Optional[str] = None,
    speed: float = 1.0,
    emit_interim: bool = False,
    realtime: bool = False,
) -> Iterator[CaptionEvent]:
    """Convenience helper to replay a call as a generator of CaptionEvents."""
    sim = CallSimulator(source, call_id=call_id, speed=speed, emit_interim=emit_interim)
    yield from sim.iter_events(realtime=realtime)

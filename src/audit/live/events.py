"""CaptionEvent data model for streaming caption feed."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class CaptionEvent:
    """Single caption slice emitted from live speech-to-text.

    Attributes:
        call_id: Unique identifier for the active call.
        peer_id: Unique identifier for the audio peer/channel/stream (e.g. 'agent_0', 'customer_0').
        role: Conversational speaker role ('agent' | 'customer').
        text: Transcribed caption text.
        start_ms: Offset from call start to caption start in milliseconds.
        end_ms: Offset from call start to caption end in milliseconds.
        final: True if caption is finalized/committed, False if interim partial hypothesis.
        turn_id: Optional sequential turn index if known.
    """
    call_id: str
    peer_id: str
    role: str
    text: str
    start_ms: int
    end_ms: int
    final: bool = True
    turn_id: Optional[int] = None

    @property
    def start_sec(self) -> float:
        """Caption start time in seconds."""
        return round(self.start_ms / 1000.0, 3)

    @property
    def end_sec(self) -> float:
        """Caption end time in seconds."""
        return round(self.end_ms / 1000.0, 3)

    @property
    def duration_ms(self) -> int:
        """Duration of this caption in milliseconds."""
        return max(0, self.end_ms - self.start_ms)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CaptionEvent:
        """Instantiate CaptionEvent from dictionary."""
        return cls(
            call_id=str(data.get("call_id", "")),
            peer_id=str(data.get("peer_id", "")),
            role=str(data.get("role", "agent")),
            text=str(data.get("text", "")),
            start_ms=int(data.get("start_ms", 0)),
            end_ms=int(data.get("end_ms", 0)),
            final=bool(data.get("final", True)),
            turn_id=data.get("turn_id"),
        )

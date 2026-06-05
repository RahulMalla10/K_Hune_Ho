from __future__ import annotations
import sys
from datetime import datetime

_STATUS_ICON = {
    "active": "▶",
    "completed": "✓",
    "skipped": "○",
    "error": "✗",
}

def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")

def log_banner(topic: str, *, causal_trace: bool) -> None:
    print(f"KHUNEHO — Analysis started [{_timestamp()}] | Topic: {topic} | Causal trace: {'on' if causal_trace else 'off'}", flush=True)

def log_step(step: int, status: str, message: str) -> None:
    icon = _STATUS_ICON.get(status, "·")
    label = f"[{_timestamp()}] Step {step}/5 {icon}"
    print(f"{label} {message}", flush=True)

def log_detail(message: str) -> None:
    print(f"           {message}", flush=True)

def log_done(topic: str) -> None:
    print(f"KHUNEHO — Analysis complete [{_timestamp()}] | Topic: {topic}", flush=True)

def log_failed(step: int, message: str) -> None:
    print(f"KHUNEHO — Analysis failed [{_timestamp()}] | Step: {step} | {message}", flush=True)
    log_step(step or 0, "error", message)

from __future__ import annotations

import importlib
import os


def get_device() -> str:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    override = os.getenv("AI_FOCUS_DEVICE", "").strip().lower()
    if override:
        if override not in {"mps", "cpu"}:
            raise ValueError("AI_FOCUS_DEVICE must be 'mps' or 'cpu'")
        return override
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return "cpu"
    return "mps" if torch.backends.mps.is_available() else "cpu"

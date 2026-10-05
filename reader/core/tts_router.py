"""Runtime selector that keeps OmniVoice and Higgs model lifecycles separate."""

from __future__ import annotations

import platform
import threading
import time


def selected_engine_name() -> str:
    try:
        from core.settings import get

        value = str(get("tts_engine", "omnivoice") or "omnivoice").lower()
    except Exception:
        value = "omnivoice"
    return value if value in {"omnivoice", "higgs"} else "omnivoice"


def selected_engine_key() -> str:
    name = selected_engine_name()
    if name != "higgs":
        return name
    try:
        from core.settings import get

        backend = str(get("higgs_backend", "auto") or "auto").lower()
    except Exception:
        backend = "auto"
    if backend == "auto":
        backend = (
            "mlx"
            if platform.system() == "Darwin" and platform.machine() == "arm64"
            else "transformers"
        )
    return "higgs-mlx" if backend == "mlx" else "higgs-transformers"


class TTSEngineRouter:
    def __init__(self):
        self._lock = threading.RLock()
        self._engine_key = selected_engine_key()
        self._engine = self._create(self._engine_key)

    @staticmethod
    def _create(name: str):
        if name == "higgs-mlx":
            from core.higgs_mlx_engine import HiggsMLXEngine

            return HiggsMLXEngine()
        if name in {"higgs", "higgs-transformers"}:
            from core.higgs_engine import HiggsTTSEngine

            return HiggsTTSEngine()
        from core.tts_engine import TTSEngine

        engine = TTSEngine()
        engine.engine_name = "omnivoice"
        return engine

    @property
    def engine_name(self) -> str:
        return self._engine.engine_name

    def _select_if_needed(self) -> None:
        wanted = selected_engine_key()
        with self._lock:
            if wanted == self._engine_key:
                return
            self._engine.unload()
            self._engine = self._create(wanted)
            self._engine_key = wanted

    def reload(self) -> None:
        wanted = selected_engine_key()
        with self._lock:
            if wanted != self._engine_key:
                self._engine.unload()
                self._engine = self._create(wanted)
                self._engine_key = wanted
                self._engine.load_async()
            else:
                self._engine.reload()

    def load_async(self) -> None:
        self._select_if_needed()
        self._engine.load_async()

    def unload(self) -> None:
        """Stop the active engine and release its VRAM before local LLM work."""
        with self._lock:
            cancel = getattr(self._engine, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception:
                    pass
            self._engine.unload()

    def wait_until_unloaded(self, timeout: float = 600) -> bool:
        """Wait for an in-flight load to notice cancellation and release VRAM."""
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            with self._lock:
                engine = self._engine
                if not getattr(engine, "_loading", False):
                    engine.unload()
                    return True
            time.sleep(0.1)
        return False

    def status(self) -> dict:
        self._select_if_needed()
        status = self._engine.status()
        status.setdefault("engine", self.engine_name)
        return status

    def cancel(self) -> bool:
        cancel = getattr(self._engine, "cancel", None)
        return bool(cancel()) if callable(cancel) else False

    def __getattr__(self, name):
        return getattr(self._engine, name)

"""Versioned identities for synthesis caches, not already saved book audio."""

import os

NORMALIZATION_VERSION = 2


def reference_identity(path):
    if not path:
        return None
    absolute = os.path.abspath(path)
    try:
        stat = os.stat(absolute)
        return (absolute, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except OSError:
        return (absolute, "missing")


def render_identity(engine):
    """Mirror engine device/dtype selection without loading a model."""
    import torch

    if torch.cuda.is_available():
        dtype = "bfloat16"
        return f"cuda/{dtype}"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        fp32 = os.environ.get("AURIS_STUDIO_HIGGS_MPS_DTYPE", "").lower() in {"fp32", "float32"}
        return "mps/float32" if fp32 else "mps/bfloat16"
    return "cpu/float32"

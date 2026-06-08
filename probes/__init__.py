from __future__ import annotations

from probes.base import BaseProbe, ProbeResult, _REGISTRY, register_probe


def get_probe(name: str) -> type[BaseProbe]:
    return _REGISTRY[name]


def get_all_probes() -> dict[str, type[BaseProbe]]:
    return dict(_REGISTRY)


__all__ = ["BaseProbe", "ProbeResult", "register_probe", "get_probe", "get_all_probes"]

# Auto-import probe modules so @register_probe decorators fire
from probes import (  # noqa: E402, F401
    api_metadata,
    api_models,
    self_report,
    knowledge_cutoff,
    reasoning,
    style_fingerprint,
    context_window,
    logprobs,
    multimodal,
    special_triggers,
    system_prompt_leak,
)

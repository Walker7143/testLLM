from dataclasses import dataclass, field


@dataclass
class ProbeWeight:
    # Low weight: easily spoofed by the proxy (just passes through claimed name)
    self_report: float = 0.1
    api_metadata: float = 0.05
    api_models: float = 0.05
    # High weight: hard to fake, reveals real model identity
    system_prompt_leak: float = 0.35
    knowledge_cutoff: float = 0.15
    reasoning: float = 0.20
    style_fingerprint: float = 0.05
    context_window: float = 0.20
    logprobs: float = 0.25
    multimodal: float = 0.10
    special_triggers: float = 0.10


@dataclass
class Config:
    base_url: str = ""
    api_key: str = ""
    claimed_model: str = ""
    wire_api: str | None = None  # "chat_completions", "responses", or None for auto-detect
    weights: ProbeWeight = field(default_factory=ProbeWeight)
    skip_expensive: bool = False
    probes_filter: list[str] | None = None
    timeout: float = 60.0
    context_window_timeout: float = 120.0
    reference_dir: str = "reference/models"

    def is_probe_enabled(self, name: str) -> bool:
        if self.skip_expensive and name in ("context_window",):
            return False
        if self.probes_filter is not None:
            return name in self.probes_filter
        return True

    def get_weight(self, name: str) -> float:
        return getattr(self.weights, name, 1.0)

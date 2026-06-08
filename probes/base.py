from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from client import LLMClient


@dataclass
class ProbeResult:
    probe_name: str
    score: float  # 0.0-1.0, 1.0 = definitely this model
    confidence: float  # 0.0-1.0, how reliable this probe is
    evidence: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


class BaseProbe(ABC):
    name: str = "unnamed"
    description: str = ""
    default_weight: float = 1.0
    expensive: bool = False

    @abstractmethod
    async def run(
        self,
        client: LLMClient,
        claimed_model: str,
        reference: dict,
    ) -> ProbeResult:
        ...

    def applicable(self, reference: dict) -> bool:
        return True


_REGISTRY: dict[str, type[BaseProbe]] = {}


def register_probe(cls: type[BaseProbe]) -> type[BaseProbe]:
    _REGISTRY[cls.name] = cls
    return cls

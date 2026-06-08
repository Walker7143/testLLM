from __future__ import annotations

from probes.base import BaseProbe, ProbeResult, register_probe


@register_probe
class SpecialTriggersProbe(BaseProbe):
    name = "special_triggers"
    description = "Trigger known model-specific behaviors"
    default_weight = 0.15

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        triggers = reference.get("special_triggers", [])
        if not triggers:
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=["No special triggers in reference data"],
            )

        correct = 0
        total = len(triggers)
        evidence = []

        for trigger in triggers:
            prompt = trigger["prompt"]
            expected = trigger["expected_behavior"]

            resp = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            answer = resp.content.lower()
            triggered = self._check_behavior(answer, expected)

            if triggered:
                correct += 1
                evidence.append(f"[pass] '{prompt[:40]}...' -> {expected}")
            else:
                evidence.append(f"[fail] '{prompt[:40]}...' (expected {expected})")

        score = correct / total if total > 0 else 0.0
        return ProbeResult(
            probe_name=self.name,
            score=score,
            confidence=0.6,
            evidence=[f"{correct}/{total} triggers matched"] + evidence,
            raw_data={"correct": correct, "total": total},
        )

    def _check_behavior(self, answer: str, expected: str) -> bool:
        if expected == "completes_normally":
            # Model produces a normal response (not a refusal)
            return len(answer) > 5 and "cannot" not in answer and "can't" not in answer
        elif expected == "refuses":
            return any(w in answer for w in ["cannot", "can't", "unable", "sorry", "i'm not able"])
        elif expected == "refuses_or_summarizes":
            return any(w in answer for w in ["cannot", "can't", "unable", "sorry", "system", "prompt"])
        elif expected == "specific_format":
            # Just check non-empty
            return len(answer) > 0
        return False

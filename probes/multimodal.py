from __future__ import annotations

import base64

from probes.base import BaseProbe, ProbeResult, register_probe


# A minimal 1x1 red PNG (base64 encoded)
# This is a placeholder - real testing would use a more meaningful image
TEST_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
)


@register_probe
class MultimodalProbe(BaseProbe):
    name = "multimodal"
    description = "Test multimodal (vision) capabilities"
    default_weight = 0.15

    async def run(self, client, claimed_model, reference) -> ProbeResult:
        expects_vision = reference.get("multimodal", {}).get("supports_vision", False)

        # Try sending an image
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What do you see in this image? Describe it briefly."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{TEST_IMAGE_B64}",
                            },
                        },
                    ],
                }
            ]
            resp = await client.chat(messages=messages, max_tokens=100)
            answer = resp.content.lower()

            # If the model says it can't see images, it doesn't support vision
            cant_see = any(phrase in answer for phrase in [
                "cannot see", "can't see", "unable to view", "no image",
                "cannot process image", "don't have the ability",
            ])

            if cant_see and expects_vision:
                score = 0.0
                evidence = ["Model cannot process images, but reference expects vision support"]
            elif cant_see and not expects_vision:
                score = 1.0
                evidence = ["Model correctly does not support vision"]
            elif not cant_see and expects_vision:
                score = 1.0
                evidence = ["Model can process images as expected"]
            else:
                score = 0.0
                evidence = ["Model claims to see images, but reference says no vision support"]

            return ProbeResult(
                probe_name=self.name,
                score=score,
                confidence=0.8,
                evidence=evidence,
                raw_data={"response": resp.content, "expects_vision": expects_vision},
            )

        except Exception as e:
            error_msg = str(e).lower()
            if "image" in error_msg or "vision" in error_msg or "multimodal" in error_msg:
                if expects_vision:
                    return ProbeResult(
                        probe_name=self.name,
                        score=0.0,
                        confidence=0.7,
                        evidence=[f"API rejected image input: {type(e).__name__}"],
                    )
                else:
                    return ProbeResult(
                        probe_name=self.name,
                        score=1.0,
                        confidence=0.7,
                        evidence=["API does not support images, matching reference"],
                    )
            return ProbeResult(
                probe_name=self.name,
                score=0.0,
                confidence=0.0,
                evidence=[f"Error during multimodal test: {type(e).__name__}: {e}"],
            )

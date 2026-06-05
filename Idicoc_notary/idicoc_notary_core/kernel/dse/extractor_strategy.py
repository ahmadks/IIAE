from __future__ import annotations
from typing import Any, Dict, List
from idicoc_notary_core.utils.logger import get_logger
from idicoc_notary_core.utils.hashing import sha256_hex

logger = get_logger("kernel.dse.extractor_strategy")


class ExtractorStrategy:
    """Encapsula la lógica de extracción: oráculo NLI + fallback regex.

    La estrategia expone `analyze(text)` y `detect_contradictions(fragments)`.
    """

    def __init__(self, config: Any | None = None):
        self.config = config

    def _get_nli(self):
        try:
            if self.config is not None:
                cfg_nli = getattr(self.config, "nli_pipeline", None)
                if cfg_nli is not None:
                    return cfg_nli
        except Exception:
            pass

        try:
            from transformers import pipeline as hf_pipeline

            return hf_pipeline(
                "zero-shot-classification",
                model=getattr(self.config, "semantic_nli_model", "facebook/bart-large-mnli"),
            )
        except Exception:
            return None

    def analyze(self, text: str) -> Dict[str, Any]:
        nli = self._get_nli()
        text_lower = (text or "").lower()
        polarity = "affirmative"
        hardness = "soft"
        priority = 1
        extraction_mode = "regex_fallback"

        if nli is not None:
            try:
                result = nli(
                    text,
                    candidate_labels=["entailment", "contradiction", "neutral"],
                    hypothesis_template="This policy represents a state of {}",
                )
                labels = result.get("labels", [])
                best_label = labels[0] if labels else "neutral"
                if best_label == "contradiction":
                    polarity = "negative"
                    hardness = "hard"
                    priority = 10
                elif best_label == "entailment":
                    polarity = "affirmative"
                    hardness = "hard"
                    priority = 9
                else:
                    polarity = "affirmative"
                    hardness = "soft"
                    priority = 5
                extraction_mode = "nli_deterministic"
            except Exception as e:
                logger.warning(f"NLI analysis failed: {e}, falling back to regex rules")
                extraction_mode = "regex_fallback"

        if extraction_mode == "regex_fallback":
            if any(
                kw in text_lower
                for kw in ("not ", "never ", "prohibit", "forbidden", "must not", "no ")
            ):
                polarity = "negative"
                hardness = "hard"
                priority = 10
            elif any(
                kw in text_lower
                for kw in ("must ", "always ", "required", "mandatory", "obligatory")
            ):
                polarity = "affirmative"
                hardness = "hard"
                priority = 9
            elif any(kw in text_lower for kw in ("should ", "prefer", "recommend")):
                polarity = "affirmative"
                hardness = "soft"
                priority = 5

        return {
            "polarity": polarity,
            "hardness": hardness,
            "priority": priority,
            "extraction_mode": extraction_mode,
        }

    def detect_contradictions(self, fragments: List[str]) -> List[Dict[str, Any]]:
        nli = self._get_nli()
        if nli is None or len(fragments) < 2:
            return []

        contradiction_policies: List[Dict[str, Any]] = []
        for i, premise in enumerate(fragments):
            for hypothesis in fragments[i + 1 :]:
                try:
                    result = nli(
                        hypothesis,
                        candidate_labels=["contradiction", "entailment", "neutral"],
                        hypothesis_template="{}",
                    )
                    labels = result.get("labels", [])
                    scores = dict(zip(result.get("labels", []), result.get("scores", [])))
                    contradiction_score = scores.get("contradiction", 0.0)
                    threshold = getattr(self.config, "semantic_nli_conflict_threshold", 0.5)
                    if contradiction_score >= threshold:
                        policy_id = sha256_hex(
                            f"contra|{premise[:64]}|{hypothesis[:64]}|{contradiction_score}"
                        )
                        contradiction_policies.append(
                            {
                                "policy_id": policy_id,
                                "source_text": f"CONTRADICTION: '{premise[:64]}' vs '{hypothesis[:64]}'",
                                "polarity": "negative",
                                "hardness": "hard",
                                "priority": 10,
                                "nli_contradiction_score": contradiction_score,
                            }
                        )
                except Exception as e:
                    logger.debug(f"NLI contradiction check failed: {e}")
                    continue

        return contradiction_policies


__all__ = ["ExtractorStrategy"]

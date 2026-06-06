import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
import json
import os
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.policy_loader.file_loader")


def parse_policy_line(line: str, line_idx: int) -> Dict[str, Any]:
    # 1. Inferencia de Dureza
    hardness = "soft"
    if "[HARD]" in line.upper():
        hardness = "hard"
        line = re.sub(r"\[HARD\]", "", line, flags=re.IGNORECASE).strip()
    elif "[SOFT]" in line.upper():
        line = re.sub(r"\[SOFT\]", "", line, flags=re.IGNORECASE).strip()

    # 2. Detección / Inferencia de Tipo de Política y Patrón
    policy_type = "fact"
    pattern = None
    regex_match = re.search(r"\[REGEX:\s*(.*?)\s*\]", line, flags=re.IGNORECASE)
    if regex_match:
        policy_type = "regex"
        pattern = regex_match.group(1).strip()
        line = re.sub(r"\[REGEX:.*?\]", "", line, flags=re.IGNORECASE).strip()

    # 3. Inferencia de Polaridad
    polarity = "affirmative"
    if "[NEGATIVE]" in line.upper():
        polarity = "negative"
        line = re.sub(r"\[NEGATIVE\]", "", line, flags=re.IGNORECASE).strip()
    elif "[AFFIRMATIVE]" in line.upper():
        polarity = "affirmative"
        line = re.sub(r"\[AFFIRMATIVE\]", "", line, flags=re.IGNORECASE).strip()
    else:
        # Auto-detect using negatives keyword list
        negation_pattern = re.compile(
            r"\b(no|evitar|evite|prohibido|prohíbe|prohibir|nunca|jamás|ni|sin|avoid|never|forbidden|reject|not)\b",
            re.IGNORECASE
        )
        if negation_pattern.search(line) or (policy_type == "regex" and not line.strip()):
            polarity = "negative"

    # 4. ID Determinista
    text_to_hash = line if line.strip() else (pattern or "")
    text_hash = hashlib.sha256(text_to_hash.encode("utf-8")).hexdigest()[:8]
    policy_id = f"free_text_{line_idx+1}_{text_hash}"

    policy = {
        "id": policy_id,
        "policy_id": policy_id,
        "text": line if line.strip() else (pattern or "Regex constraint"),
        "policy_type": policy_type,
        "polarity": polarity,
        "hardness": hardness,
        "priority": 1,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if pattern:
        policy["pattern"] = pattern

    return policy


class FilePolicyLoader:
    """
    Cargador de políticas desde un archivo en lenguaje natural (texto libre) o JSON.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def load_policies(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            logger.warning(f"Policy file not found: {self.file_path}. Returning empty list.")
            return []

        if self.file_path.endswith(".json"):
            return self._load_json()
        return self._load_text()

    def _load_json(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "policies" in data:
                    return data["policies"]
                return []
        except Exception as e:
            logger.error(f"Error reading JSON policy file {self.file_path}: {e}")
            return []

    def _load_text(self) -> List[Dict[str, Any]]:
        policies = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    policies.append(self._parse_policy(line, line_idx))
        except Exception as e:
            logger.error(f"Error reading text policy file {self.file_path}: {e}")
        return policies

    def _parse_policy(self, line: str, line_idx: int) -> Dict[str, Any]:
        p = parse_policy_line(line, line_idx)
        p["source"] = f"file:{os.path.basename(self.file_path)}:{line_idx+1}"
        return p



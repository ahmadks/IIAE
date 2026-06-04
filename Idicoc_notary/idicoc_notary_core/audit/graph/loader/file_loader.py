from typing import Any, Dict, List
import json
import os
from datetime import datetime, timezone
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.policy_loader.file_loader")


def split_policy_line(line: str) -> List[str]:
    """Split a policy line on unescaped delimiters while preserving regex values."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) <= 7:
        return parts

    for idx, part in enumerate(parts[6:], start=6):
        if part.startswith("pattern="):
            return parts[:idx] + ["|".join(parts[idx:])]
    return parts


class FilePolicyLoader:
    """
    Cargador de politicas desde un archivo (texto delimitado por '|' o JSON).

    Formato delimitado:
    texto | tipo | polaridad | dureza | prioridad
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
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    parts = split_policy_line(line)
                    if not parts or not parts[0]:
                        continue

                    # Determinar si el formato tiene ID (al menos 6 campos y el primero no contiene '=')
                    has_id = len(parts) >= 6 and "=" not in parts[0]

                    if has_id:
                        policy_id = parts[0]
                        text = parts[1]
                        policy_type = parts[2] if len(parts) > 2 else "fact"
                        polarity = parts[3] if len(parts) > 3 else "affirmative"
                        hardness = parts[4] if len(parts) > 4 else "soft"
                        try:
                            priority = int(parts[5]) if len(parts) > 5 else 1
                        except ValueError:
                            priority = 1
                        extra_parts = parts[6:]
                    else:
                        policy_id = None
                        text = parts[0]
                        policy_type = parts[1] if len(parts) > 1 else "fact"
                        polarity = parts[2] if len(parts) > 2 else "affirmative"
                        hardness = parts[3] if len(parts) > 3 else "soft"
                        try:
                            priority = int(parts[4]) if len(parts) > 4 else 1
                        except ValueError:
                            priority = 1
                        extra_parts = parts[5:]

                    timestamp = datetime.now(timezone.utc).isoformat()

                    policy: Dict[str, Any] = {
                        "text": text,
                        "policy_type": policy_type,
                        "polarity": polarity,
                        "hardness": hardness,
                        "priority": priority,
                        "timestamp": timestamp,
                        "source": f"file:{os.path.basename(self.file_path)}:{line_idx+1}",
                        "source_text": text,
                    }
                    if policy_id:
                        policy["id"] = policy_id
                        policy["policy_id"] = policy_id

                    # Parse key=value metadata
                    for ep in extra_parts:
                        if "=" in ep:
                            k, v = ep.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if v.isdigit():
                                policy[k] = int(v)
                            else:
                                try:
                                    policy[k] = float(v)
                                except ValueError:
                                    policy[k] = v

                    policies.append(policy)
        except Exception as e:
            logger.error(f"Error reading text policy file {self.file_path}: {e}")

        return policies

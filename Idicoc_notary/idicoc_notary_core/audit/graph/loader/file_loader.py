from typing import Any, Dict, List
import json
import os
from datetime import datetime, timezone
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.axiom_loader.file_loader")

class FileAxiomLoader:
    """
    Cargador de axiomas desde un archivo (texto delimitado por '|' o JSON).
    
    Formato delimitado:
    texto | tipo | polaridad | dureza | prioridad
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def load_axioms(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            logger.warning(f"Axiom file not found: {self.file_path}. Returning empty list.")
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
                elif isinstance(data, dict) and "axioms" in data:
                    return data["axioms"]
                return []
        except Exception as e:
            logger.error(f"Error reading JSON axiom file {self.file_path}: {e}")
            return []

    def _load_text(self) -> List[Dict[str, Any]]:
        axioms = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    
                    parts = [p.strip() for p in line.split("|")]
                    if not parts:
                        continue
                        
                    # Formato: texto | tipo | polaridad | dureza | prioridad
                    text = parts[0]
                    axiom_type = parts[1] if len(parts) > 1 else "fact"
                    polarity = parts[2] if len(parts) > 2 else "affirmative"
                    hardness = parts[3] if len(parts) > 3 else "soft"
                    try:
                        priority = int(parts[4]) if len(parts) > 4 else 1
                    except ValueError:
                        priority = 1

                    timestamp = datetime.now(timezone.utc).isoformat()
                    
                    axiom = {
                        "text": text,
                        "axiom_type": axiom_type,
                        "polarity": polarity,
                        "hardness": hardness,
                        "priority": priority,
                        "timestamp": timestamp,
                        "source": f"file:{os.path.basename(self.file_path)}:{line_idx+1}"
                    }
                    axioms.append(axiom)
        except Exception as e:
            logger.error(f"Error reading text axiom file {self.file_path}: {e}")
            
        return axioms

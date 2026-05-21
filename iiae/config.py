import os
import time
import json
from typing import Any, Dict, Optional


class IIAEConfig:
    """Global SDK configuration.

    The configuration can be supplied directly via keyword arguments,
    read from environment variables, or loaded from a JSON file pointed to by
    ``IIAE_CONFIG_PATH``.  All values have sensible defaults.
    """

    # ---------------------------------------------------------------------
    #   Construction helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _load_json_config(path: str) -> Dict[str, Any]:
        """Load a JSON configuration file.

        Returns an empty dict if the file cannot be read – the caller will fall
        back to defaults / environment variables.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:  # pragma: no cover – defensive only
            # In production we prefer a silent fallback to avoid crashing the
            # service when the file is missing or malformed.
            return {}

    # ---------------------------------------------------------------------
    #   Public initializer
    # ---------------------------------------------------------------------
    def __init__(self, **kwargs: Any) -> None:
        # 1️⃣ Load JSON configuration if the user pointed to it.
        json_cfg: Dict[str, Any] = {}
        json_path = os.getenv("IIAE_CONFIG_PATH")
        if json_path:
            json_cfg = self._load_json_config(json_path)

        # Helper to resolve a setting in the precedence order:
        #   1) explicit kwarg
        #   2) JSON file entry
        #   3) dedicated environment variable
        #   4) default literal
        def resolve(key: str, env: str, default: Any) -> Any:
            if key in kwargs:
                return kwargs[key]
            if key in json_cfg:
                return json_cfg[key]
            return os.getenv(env, default)

        # -----------------------------------------------------------------
        #   Core threshold and model parameters
        # -----------------------------------------------------------------
        self.ds_threshold: float = float(
            resolve("ds_threshold", "IIAE_DS_THRESHOLD", 0.4)
        )
        self.min_len: int = int(resolve("min_len", "IIAE_MIN_LEN", 20))
        self.model_id: str = str(resolve("model_id", "IIAE_MODEL_ID", "llm-v1"))

        # -----------------------------------------------------------------
        #   Enterprise‑wide toggles
        # -----------------------------------------------------------------
        self.strict_mode: bool = (
            str(resolve("strict_mode", "IIAE_STRICT_MODE", "true")).lower() == "true"
        )
        self.timeout_ms: int = int(resolve("timeout_ms", "IIAE_TIMEOUT_MS", 5000))
        self.audit_mode: bool = (
            str(resolve("audit_mode", "IIAE_AUDIT_MODE", "true")).lower() == "true"
        )
        self.max_trips: int = int(resolve("max_trips", "IIAE_MAX_TRIPS", 5))

        # -----------------------------------------------------------------
        #   Security / cryptographic settings
        # -----------------------------------------------------------------
        self.ctm_salt: Optional[str] = resolve("ctm_salt", "IIAE_CTM_SALT", None)

        # -----------------------------------------------------------------
        #   Circuit‑breaker settings
        # -----------------------------------------------------------------
        self.cb_cooldown_ms: int = int(
            resolve("cb_cooldown_ms", "IIAE_CB_COOLDOWN_MS", 60000)
        )
        # Internal state – not exposed to the user but needed by the supervisor.
        self._circuit_open: bool = False
        self._circuit_last_open_ts: Optional[float] = None
        self._circuit_half_open: bool = False

        # -----------------------------------------------------------------
        #   MAO / DQE engine selection
        # -----------------------------------------------------------------
        # The string identifiers ("lexical" | "semantic" | custom) are resolved in the
        # same precedence order as other settings.
        self.mao_engine_name: str = str(
            resolve("mao_engine_name", "IIAE_MAO_ENGINE", "lexical")
        )
        self.dqe_engine_name: str = str(
            resolve("dqe_engine_name", "IIAE_DQE_ENGINE", "lexical")
        )

        # Engine‑specific configuration dictionaries – passed to concrete engines.
        self.mao_engine_params: Dict[str, Any] = (
            kwargs.get("mao_engine_params")
            or json_cfg.get("mao_engine_params")
            or {}
        )
        self.dqe_engine_params: Dict[str, Any] = (
            kwargs.get("dqe_engine_params")
            or json_cfg.get("dqe_engine_params")
            or {}
        )

        # -----------------------------------------------------------------
        #   Audit log redirection (logging layer only — CTM unaffected)
        # -----------------------------------------------------------------
        self.log_destination: str = str(
            resolve("log_destination", "IIAE_LOG_DESTINATION", "stdout")
        )

        # -----------------------------------------------------------------
        #   Flags controlling optional behaviour
        # -----------------------------------------------------------------
        self.enable_mao_filters: bool = (
            str(resolve("enable_mao_filters", "IIAE_ENABLE_MAO", "false")).lower()
            == "true"
        )

        from .logger import configure_logging

        configure_logging(self.log_destination)

    # ---------------------------------------------------------------------
    #   Helper properties for the supervisor (read‑only view)
    # ---------------------------------------------------------------------
    @property
    def circuit_open(self) -> bool:
        return self._circuit_open

    @property
    def circuit_last_open_ts(self) -> Optional[float]:
        return self._circuit_last_open_ts

    # The supervisor may mutate the internal state via these protected setters.
    def _set_circuit_state(self, open_: bool, timestamp: Optional[float] = None) -> None:
        self._circuit_open = open_
        self._circuit_last_open_ts = timestamp
        self._circuit_half_open = not open_

    def _reset_circuit(self) -> None:
        self._circuit_open = False
        self._circuit_half_open = False
        self._circuit_last_open_ts = None

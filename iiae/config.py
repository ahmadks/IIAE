import os

class IIAEConfig:
    """
    External configuration for IIAE SDK.
    Values can be passed directly or loaded from environment variables.
    """
    def __init__(self, **kwargs):
        self.ds_threshold = kwargs.get('ds_threshold', float(os.getenv('IIAE_DS_THRESHOLD', 0.4)))
        self.min_len = kwargs.get('min_len', int(os.getenv('IIAE_MIN_LEN', 20)))
        self.model_id = kwargs.get('model_id', os.getenv('IIAE_MODEL_ID', 'llm-v1'))
        
        # Enterprise features
        self.strict_mode = kwargs.get('strict_mode', os.getenv('IIAE_STRICT_MODE', 'true').lower() == 'true')
        self.timeout_ms = kwargs.get('timeout_ms', int(os.getenv('IIAE_TIMEOUT_MS', 5000)))
        self.audit_mode = kwargs.get('audit_mode', os.getenv('IIAE_AUDIT_MODE', 'true').lower() == 'true')
        
        # MAO Protocol features
        self.enable_mao_filters = kwargs.get('enable_mao_filters', os.getenv('IIAE_ENABLE_MAO', 'false').lower() == 'true')

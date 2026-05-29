# Idicoc-demo-ui/IdicocConfg.py
import os
import numpy as np

# pyrefly: ignore [missing-import]
from idicoc_notary_core import AuditConfig, InlinePolicyLoader

# -----------------------------------------------------------------------------
# Configuración Estática del Notario IDICOC
# -----------------------------------------------------------------------------
CLIENT_ID = "demo-ui-session"
CTM_MODE = "full"
SEMANTIC_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Pesos de disonancia — solo las 3 etapas activas reciben peso.
# Las etapas d₀, d₄, d₅, d₆ siempre devuelven 0.0 en el pipeline actual
# (ver comentarios en structural_strategy.py y config.py para los motivos).
DISSONANCE_WEIGHTS = (
    0.0,  # λ₀ — d₀ Levenshtein        (INACTIVO: input numérico, sin text_content)
    0.5,  # λ₁ — d₁ EMD al ancla K     (ACTIVO: métrica principal de distancia al invariante)
    0.4,  # λ₂ — d₂ Policy Graph     (ACTIVO: violación de politicas)
    0.1,  # λ₃ — d₃ bisimulación temp. (ACTIVO: divergencia de trazas)
    0.0,  # λ₄ — d₄ Hamming cripto.    (INACTIVO: hashes no disponibles en ciclo)
    0.0,  # λ₅ — d₅ Boundary trap      (INACTIVO: señal SO, no conectada al pipeline)
    0.0,  # λ₆ — d₆ convergencia asint.(INACTIVO: requiere estado terminal acumulado)
)

# Rutas de persistencia CTM
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CTM_NODES_PATH = os.path.join(BASE_DIR, "ctm_nodes.json")
CTM_ROOT_PATH = os.path.join(BASE_DIR, "ctm_root.txt")


def build_notary_config(epsilon: float, policies: list) -> AuditConfig:
    """
    Construye la configuración de AuditConfig para el Notario (Modo Numérico).
    """
    return AuditConfig(
        instance_name="idicoc-notary-numérico",
        client_id=CLIENT_ID,
        ctm_mode=CTM_MODE,
        rigidity_epsilon=epsilon,
        dissonance_weights=DISSONANCE_WEIGHTS,
        semantic_embedding_model=SEMANTIC_EMBEDDING_MODEL,
        policy_loader=InlinePolicyLoader(policies),
        ctm_nodes_path=CTM_NODES_PATH,
        ctm_root_path=CTM_ROOT_PATH,
    )

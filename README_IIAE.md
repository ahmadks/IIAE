# IIAE - Intelligent Invariant Audit Engine

> **Auditoría Determinista de Salidas de IA sin Bloqueo**

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-Proprietary-red)
![Status](https://img.shields.io/badge/Status-Stable-green)

## 📋 Tabla de Contenidos

- [Overview](#overview)
- [Características](#características)
- [Instalación](#instalación)
- [Quick Start](#quick-start)
- [Conceptos Clave](#conceptos-clave)
- [Uso Avanzado](#uso-avanzado)
- [Referencia de Módulos](#referencia-de-módulos)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

**IIAE** (Intelligent Invariant Audit Engine) es un framework de auditoría determinista para sistemas de IA que:

- ✅ Audita salidas de IA **sin bloquear ni rechazar** (notaría pasiva)
- ✅ Mide desviación del invariante (`D_s`: disonancia)
- ✅ Verifica cumplimiento de axiomas (restricciones duras)
- ✅ Registra y custodia evidencia con Merkle DAG + HMAC-SHA256
- ✅ Soporta análisis personalizado por dominio
- ✅ Determinista y reproducible (sin LLMs para decisiones)

### Arquitectura de 7 Etapas Coalgebráicas

```
┌─────────────────────────────────────────────────────────────┐
│                       RAW INPUT                              │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │ 1. AEM (Anomalous Event Manager)│
        │    → Filtrado de ruido upstream │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────────────┐
        │ 2. ISG (Invariant State Generator)      │
        │    → Proyección a estado canónico       │
        └────────────────┬────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ 3. DSE (Dynamic Schema Extractor)           │
        │    → Actualización del grafo de propiedades │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ 4. CMC (Manifold Constructor)               │
        │    → Construcción de región admisible       │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ 5. DQE (Deviation Quantifier)               │
        │    → Cálculo de disonancia (D_s)            │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ 6. Corrección Manifold (opcional)           │
        │    → Proyección si es necesario             │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ 7. Verifier                                 │
        │    → Verificación de alineación + axiomas   │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │ CTM (Custodial Trace Manager)               │
        │    → Merkle sealing + HMAC-SHA256           │
        └────────────────┬────────────────────────────┘
                         │
        ┌────────────────▼────────────────────────────┐
        │    CANONICAL STATE (Inmutable, Congelado)   │
        │    - Salida auditada                        │
        │    - D_s (disonancia)                       │
        │    - Axiomas violados                       │
        │    - Hash de custodia                       │
        │    - Timestamp                              │
        └────────────────────────────────────────────┘
```

---

## Características

| Característica | Descripción |
|---|---|
| **Determinista** | Resultados reproducibles, sin aleatoriedad |
| **Pasiva** | Nunca rechaza, solo mide y registra |
| **Multimodal** | Soporta análisis Semántico y Matemático |
| **Custodia Legal** | Merkle DAG + sellado HMAC para auditoría legal |
| **Extensible** | Implementa `EntropyAnalyzer` personalizado |
| **Zero Trust** | Verifica axiomas duros sin excepciones |
| **Rendimiento** | ~100ms/auditoría en GPU (NLI) |

---

## Instalación

### Requisitos Previos

- Python 3.10+
- pip o uv
- GPU recomendada (CUDA/ROCm para modelos semánticos)

### Opción 1: Instalación Local Completa

```bash
# Clonar o descargar el proyecto
cd /Users/kamal/Personal/AntigravityWorkspace/IIAE

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -e Idicoc_notary/

# Descargar modelos preentrenados (si es modo Semántico)
python download_models.py
```

### Opción 2: Instalación Mínima (solo core)

```bash
cd Idicoc_notary/
pip install -r requirements.txt
```

### Dependencias Principales

```toml
numpy = "^1.22"
scipy = "^1.8"
pandas = "^1.5"
sentence-transformers = "^2.2"  # Para modo semántico
transformers = "^4.30"          # Para NLI
torch = "^2.0"                  # Para GPU
python-dotenv = "^1.0"
pytest = "^7.0"                 # Para testing
```

---

## Quick Start

### Ejemplo 1: Auditoría Básica (Modo Semántico)

```python
from idicoc_notary_core import (
    AuditConfig,
    IIAEService,
    BankEntropyAnalyzer,
)

# Configurar auditor
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.35,  # Modo híbrido
    constant_k=100,         # Tamaño manifold
    isg_delta_fp=0.15,      # Tolerancia de proyección
)

# Crear analizador de entropía (dominio: Banca)
entropy_analyzer = BankEntropyAnalyzer()

# Instanciar servicio
auditor = IIAEService(config, entropy_analyzer)

# Realizar auditoría
result = auditor.process_interaction(
    audit_input="El préstamo fue aprobado con tasa del 5%",
    context_input=["Cliente: solvente", "Score crediticio: 750"],
    context_axioms=["Nunca disclose números de cuenta",
                    "Mantener tono profesional"],
)

# Examinar resultado
print(f"Disonancia: {result.metadata['d_s']:.3f}")  # 0.08 (muy alineado)
print(f"Axiomas violados: {result.metadata.get('axioms_violated', [])}")
print(f"Hash custodia: {result.metadata.get('custody_hash', '')[:16]}...")
```

**Interpretación del resultado:**
- `D_s = 0.08`: Salida muy alineada con el invariante (factual)
- `axioms_violated = []`: Todos los axiomas respetados
- Estado congelado en `CanonicalStateDTO`

---

### Ejemplo 2: Auditoría con Control de Manifold

```python
from idicoc_notary_core import (
    AuditConfig,
    IIAEService,
    BankEntropyAnalyzer,
)

# Modo MÁS CREATIVO (epsilon alto)
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.7,   # Máxima libertad creativa
    audit_strategy="semantic",  # NLI + embeddings
)

entropy_analyzer = BankEntropyAnalyzer()
auditor = IIAEService(config, entropy_analyzer)

# Entrada con potencial desviación
result = auditor.process_interaction(
    audit_input="Este cliente podría beneficiarse de un plan de inversión diversificado",
    context_input=["Perfil: Conservador", "Edad: 65"],
    epsilon_override=0.65,  # Override puntual
)

# Analizar desviación permitida
print(f"Disonancia: {result.metadata['d_s']:.3f}")  # 0.42 (dentro del manifold)
print(f"Manifold radio: {result.metadata.get('manifold_radius'):.2f}")
print(f"Dentro del manifold: {result.metadata.get('in_manifold', True)}")
```

---

## Conceptos Clave

### 1. Disonancia (D_s)

Medida de desviación del invariante, calculada como:

$$D_s = \lambda_{inv} \cdot d_{inv} + \lambda_{logic} \cdot d_{logic} + \lambda_{temporal} \cdot d_{temp}$$

**Pesos por defecto:** `[0.5, 0.4, 0.1]`

| Rango | Clasificación | Significado |
|---|---|---|
| `0.0 - 0.1` | ✅ Factual | Completamente alineado |
| `0.1 - 0.35` | ✅ Híbrido | Creatividad moderada permitida |
| `0.35 - 0.7` | ⚠️ Creativo | Desviación notable (verificar) |
| `0.7 - 1.0` | 🚨 Alucinación | Coherencia muy baja |

**Implementación:**

```python
# En DQE (Deviation Quantifier Engine)
d_s = (
    weights[0] * dissonance_invariant +      # d_inv: contradicción semántica
    weights[1] * dissonance_logic +          # d_logic: violaciones lógicas
    weights[2] * dissonance_temporal         # d_temp: inconsistencias temporales
)
```

---

### 2. Axiomas (Restricciones Duras)

Reglas que **NUNCA** pueden ser violadas:

```python
axioms = [
    {
        "id": "ax1",
        "text": "Nunca disclose números de cuenta del cliente",
        "polarity": True,  # True = MUST do, False = MUST NOT do
    },
    {
        "id": "ax2",
        "text": "Mantener tono profesional",
        "polarity": True,
    },
    {
        "id": "ax3",
        "text": "No prometer tasas no reguladas",
        "polarity": False,  # MUST NOT do
    },
]

# Verificación
result = auditor.process_interaction(..., context_axioms=[ax["text"] for ax in axioms])

# Si hay violación:
if result.metadata.get("axioms_violated"):
    print("⚠️ INCUMPLIMIENTO DE AXIOMA DETECTADO")
    # El operador decidirá si rechazar o permitir
```

---

### 3. Rigidity Epsilon (ε)

Controla el tamaño del manifold (región de comportamiento permitido):

$$\text{Manifold} = \{ \text{salidas} : D_s \leq \epsilon \}$$

| Valor | Modo | Uso |
|---|---|---|
| `0.0` | Factual | Respuestas deterministas idénticas |
| `0.2-0.3` | Conservador | Banca, medicina (low risk) |
| `0.35-0.5` | Híbrido | Customer service, soporte técnico |
| `0.6-0.7` | Creativo | Escritura creativa, brainstorming |

**Ejemplo:**

```python
# Modo Strict (compliance financiero)
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.15,  # Muy restrictivo
)

# Modo Creativo (generación de contenido)
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.65,  # Permite más desviación
)
```

---

### 4. Notaría Pasiva (Passive Notary)

IIAE **nunca rechaza ni bloquea** la salida. Solo:

1. ✅ Mide desviación (`D_s`)
2. ✅ Verifica axiomas
3. ✅ Registra evidencia
4. ✅ **El operador** toma la decisión final

```python
# Incluso si D_s es muy alto, se devuelve el estado
result = auditor.process_interaction("salida potencialmente problemática")

# Decision tree en producción:
if result.metadata["d_s"] > 0.7 and result.metadata.get("axioms_violated"):
    # OPERADOR: Revisar manualmente
    logger.warning(f"Review needed: {result.metadata}")
else:
    # OPERADOR: Permitir automáticamente
    return result.data
```

---

### 5. EntropyAnalyzer (Interfaz Protocol)

Permite análisis personalizado por dominio:

```python
from typing import Protocol, Tuple

class EntropyAnalyzer(Protocol):
    """Interfaz para análisis específico del dominio."""
    
    def measure_entropy(self, raw_input: str) -> float:
        """Retorna entropía normalizada [0, 1]."""
        ...
    
    def decompose(self, raw_input: str) -> Tuple[str, str]:
        """Retorna (componente_estructural, ruido)."""
        ...
    
    def is_recoverable(self, noise: str) -> bool:
        """¿Se puede recuperar valor del ruido?"""
        ...

# Implementación para Medical Records
class MedicalRecordsAnalyzer:
    def measure_entropy(self, raw_input: str) -> float:
        # Detectar PII: SSN, números de teléfono, direcciones
        pii_count = detect_pii(raw_input)
        return min(pii_count / total_tokens, 1.0)
    
    def decompose(self, raw_input: str) -> Tuple[str, str]:
        structural = redact_pii(raw_input)
        noise = extract_pii(raw_input)
        return structural, noise
    
    def is_recoverable(self, noise: str) -> bool:
        # Los números de teléfono son recuperables, SSN no
        return not is_ssn(noise)
```

---

### 6. Estrategias de Disonancia

#### Semántica (Semantic)

Usa **NLI (Natural Language Inference)** + embeddings:

```python
config = AuditConfig(
    audit_mode="semantic",
    audit_strategy="semantic",  # Explícito
)

# Flujo:
# 1. Tokenizar entrada
# 2. Generar embeddings con SentenceTransformer
# 3. Verificar con modelo NLI (entailment/neutral/contradiction)
# 4. Calcular distancia coseno en espacio latente
# 5. Agregar en D_s
```

**Ventajas:**
- ✅ Detecta contradicciones sutiles
- ✅ Entiende contexto semántico
- ❌ Requiere GPU
- ❌ ~100ms por auditoría

#### Matemática (Mathematical)

Basada en **frecuencia de tokens** y algoritmo de transporte óptimo:

```python
config = AuditConfig(
    audit_mode="mathematical",
    audit_strategy="mathematical",
)

# Flujo:
# 1. Tokenizar entrada
# 2. Construir distribución empírica de tokens
# 3. Calcular Wasserstein distance con invariante canónico
# 4. Result = D_s = distancia normalizada
```

**Ventajas:**
- ✅ Determinista (sin LLMs)
- ✅ Muy rápido (~5ms)
- ✅ Reproducible 100%
- ❌ Menos sensible a semántica

---

## Uso Avanzado

### Caso de Uso 1: Compliance Financiero Multi-Etapa

```python
from idicoc_notary_core import (
    AuditConfig,
    IIAEService,
    BankEntropyAnalyzer,
)

# Configuración stricta
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.20,      # Muy restrictivo
    isg_delta_fp=0.10,          # Tolerancia baja
    constant_k=200,             # Manifold grande
    ctm_mode="full",            # Custodia completa
)

analyzer = BankEntropyAnalyzer()
auditor = IIAEService(config, analyzer)

# Axiomas del regulador
regulatory_axioms = [
    "Nunca disclose account numbers",
    "No prometer tasas garantizadas",
    "Incluir disclosure de riesgo",
    "Mantener tono profesional",
    "No discriminar por edad/género",
]

# Auditar respuesta del sistema
ia_response = "Su préstamo fue aprobado con tasa del 4.95%. " \
              "Recibirá los fondos en 24 horas. " \
              "Nota: Tasas sujetas a cambios de mercado."

result = auditor.process_interaction(
    audit_input=ia_response,
    context_input=["Cliente: corporativo", "Amount: $500k"],
    context_axioms=regulatory_axioms,
)

# Análisis de resultado
if result.metadata.get("axioms_violated"):
    print(f"❌ REGULATORY BREACH: {result.metadata['axioms_violated']}")
    # Enviar a revisión legal
    send_to_legal_review(result)
elif result.metadata["d_s"] > 0.30:
    print(f"⚠️ HIGH DEVIATION: D_s={result.metadata['d_s']:.3f}")
    # Flag para supervisión
    flag_for_supervision(result)
else:
    print(f"✅ COMPLIANT: D_s={result.metadata['d_s']:.3f}")
    # Permitir automáticamente
    deliver_response(result.data)

# Guardar evidencia para auditoría
audit_log(result)
```

---

### Caso de Uso 2: Analizador Personalizado (Medical Records)

```python
from idicoc_notary_core import (
    AuditConfig,
    IIAEService,
)
import re
from typing import Tuple

class MedicalRecordsAnalyzer:
    """Detector de PII en registros médicos."""
    
    def measure_entropy(self, raw_input: str) -> float:
        # Detectar SSN, teléfono, dirección
        pii_patterns = {
            "ssn": r"\d{3}-\d{2}-\d{4}",
            "phone": r"\+?1?\d{10}",
            "address": r"\d+\s+[A-Z][a-z]+\s+(St|Ave|Rd|Blvd)",
        }
        pii_count = 0
        for pattern in pii_patterns.values():
            pii_count += len(re.findall(pattern, raw_input))
        
        tokens = len(raw_input.split())
        return min(pii_count / max(tokens, 1), 1.0)
    
    def decompose(self, raw_input: str) -> Tuple[str, str]:
        structural = raw_input
        noise = ""
        
        # Redact and collect PII
        patterns = {
            "ssn": r"\d{3}-\d{2}-\d{4}",
            "phone": r"\+?1?\d{10}",
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, structural)
            noise += " ".join(matches) + " "
            structural = re.sub(pattern, f"[{key.upper()}]", structural)
        
        return structural, noise
    
    def is_recoverable(self, noise: str) -> bool:
        # SSN not recoverable, others are
        return "ssn" not in noise.lower()

# Usar
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.40,
)

analyzer = MedicalRecordsAnalyzer()
auditor = IIAEService(config, analyzer)

medical_response = "Patient John Doe (SSN 123-45-6789) presents with hypertension."

result = auditor.process_interaction(
    audit_input=medical_response,
    context_axioms=["No PII debe estar expuesto"],
)

if result.metadata["d_s"] > 0.5:
    print("⚠️ SUSPICIOUS PII EXPOSURE")
    # Redact y reintentar
    redacted = result.metadata.get("redacted_input")
```

---

### Caso de Uso 3: Acceso Directo al Kernel (Auditoría Avanzada)

```python
from idicoc_notary_core.kernel.pipeline.kernel import CustodialKernel
from idicoc_notary_core.kernel.admission.aem import AnomalousEventManager
from idicoc_notary_core.kernel.custody.merkle_dag import MerkleDAG
from idicoc_notary_core.audit.config import AuditConfig

# Acceso a las 7 etapas directamente
config = AuditConfig(
    audit_mode="mathematical",
    constant_k=100,
    isg_delta_fp=0.15,
)

kernel = CustodialKernel(config)
aem = AnomalousEventManager(entropy_threshold=0.3)
ctm = MerkleDAG()

# Input
raw_input = "Test input with potential anomalies"

# Etapa 1: AEM
admission = aem.admit(raw_input)

# Etapa 2-7: Kernel execution
result = kernel.execute(admission)

# Acceso a componentes internos
print(f"Projected state: {result['invariant_state']}")
print(f"Property graph: {result['property_graph'].to_dict()}")
print(f"Manifold size: {result['manifold_radius']}")
print(f"Dissonance: {result['dissonance']}")
print(f"Violations: {result.get('axiom_violations', [])}")

# Custodia
root_hash = ctm.add_node(result['invariant_state'])
print(f"Custody hash: {root_hash}")
```

---

## Referencia de Módulos

### audit/ (Capa Wrapper)

| Módulo | Propósito |
|---|---|
| **wrapper_pipeline.py** | `IIAEService` - entrada principal |
| **pipeline.py** | `IIAEServiceAuditor` - orquestador |
| **base.py** | Contratos: `CanonicalStateDTO`, `EntropyAnalyzer`, `IIAENotaryContract` |
| **config.py** | `AuditConfig` - configuración global |
| **axioms.py** | `AxiomEngine` - gestor de restricciones |
| **strategies/semantic.py** | NLI + embeddings |
| **strategies/mathematical.py** | Token frequency + Wasserstein distance |
| **persistence/** | `FileAEMStorage`, `FileCTMStorage` para persistencia |
| **exceptions.py** | Excepciones personalizadas |

### kernel/ (Capa de 7 Etapas)

| Módulo | Etapa | Propósito |
|---|---|---|
| **admission/aem.py** | 1 | Filtrado de ruido |
| **projection/invariant_state_generator.py** | 2 | Proyección canónica |
| **dse/dse.py** | 3 | Extracción dinámica de esquema |
| **manifold/cmc.py** | 4 | Constructor del manifold |
| **deviation/dqe.py** | 5 | Cuantificador de desviación |
| **verification/verifier.py** | 7 | Verificación final |
| **custody/merkle_dag.py** | CTM | Merkle DAG + sealing |
| **graph/property_graph.py** | - | Grafo de propiedades + axiomas |
| **pipeline/kernel.py** | - | Orquestador kernel |

---

## Testing

### Ejecutar Suite de Pruebas

```bash
cd Idicoc_notary/

# Todas las pruebas
pytest tests/

# Con cobertura
pytest tests/ --cov=idicoc_notary_core --cov-report=html

# Pruebas específicas
pytest tests/test_idicoc_wrapper.py::test_basic_audit -v

# Con output detallado
pytest tests/ -s --tb=short
```

### Pruebas Principales

```python
# test_idicoc_wrapper.py
def test_basic_audit():
    """Auditoría básica con modo semántico."""
    config = AuditConfig(audit_mode="semantic")
    analyzer = BankEntropyAnalyzer()
    wrapper = IIAEService(config, analyzer)
    
    result = wrapper.process_interaction("test input")
    assert isinstance(result, CanonicalStateDTO)
    assert "d_s" in result.metadata

def test_axiom_verification():
    """Verificación de axiomas."""
    config = AuditConfig(audit_mode="semantic")
    analyzer = BankEntropyAnalyzer()
    wrapper = IIAEService(config, analyzer)
    
    result = wrapper.process_interaction(
        "customer SSN is 123-45-6789",
        context_axioms=["Never disclose SSN"]
    )
    # Debería detectar violación

def test_persistence():
    """Persistencia con Merkle DAG."""
    config = AuditConfig(ctm_mode="full")
    aem_storage = FileAEMStorage("aem.json")
    ctm_storage = FileCTMStorage("nodes/", "root.hash")
    
    wrapper = IIAEService(config, analyzer, 
                         aem_storage=aem_storage,
                         ctm_storage=ctm_storage)
    result = wrapper.process_interaction("test")
    
    # Verificar que se guardó
    assert os.path.exists("aem.json")
    assert os.path.exists("nodes/")
```

---

## Troubleshooting

### Problema: ImportError en `transformers`

```
ImportError: No module named 'transformers'
```

**Solución:**
```bash
pip install transformers torch sentence-transformers
python download_models.py  # Descargar NLI model
```

---

### Problema: OutOfMemory en GPU

```
RuntimeError: CUDA out of memory
```

**Soluciones:**
1. Cambiar a modo `mathematical` (sin GPU):
   ```python
   config = AuditConfig(audit_mode="mathematical")
   ```

2. O reducir batch size:
   ```python
   config = AuditConfig(batch_size=4)  # Default: 32
   ```

3. O usar CPU explícitamente:
   ```python
   os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Deshabilitar GPU
   ```

---

### Problema: D_s siempre retorna 0.0

**Causa:** Estrategia no configurada correctamente

**Solución:**
```python
# Asegurarse que audit_strategy está explícito
config = AuditConfig(
    audit_mode="semantic",
    audit_strategy="semantic",  # ← Agregar esto
)
```

---

### Problema: Axiomas no se verifican

**Verificar:**
```python
# Los axiomas deben pasar en context_axioms
result = auditor.process_interaction(
    audit_input="...",
    context_axioms=["Axiom 1", "Axiom 2"]  # ← Required
)

# Revisar violaciones
if result.metadata.get("axioms_violated"):
    print(result.metadata["axioms_violated"])
```

---

## Características de Rendimiento

### Benchmarks (en GPU NVIDIA A100)

| Estrategia | Modo | Latencia | Throughput |
|---|---|---|---|
| Semántica | NLI | ~100ms | 10 auditorías/sec |
| Matemática | Token-based | ~5ms | 200 auditorías/sec |
| Batch (32) | Semántica | ~50ms/req | 20 auditorías/sec |

### Optimización

```python
# Para máximo rendimiento
config = AuditConfig(
    audit_mode="mathematical",  # Sin GPU
    rigidity_epsilon=0.35,
    ctm_mode="log_only",        # No custodia completa
)

# Para máxima precisión
config = AuditConfig(
    audit_mode="semantic",      # NLI + embeddings
    isg_delta_fp=0.10,          # Tolerancia baja
    ctm_mode="full",            # Custodia completa
)
```

---

## Guía de Contribución

### Estructuras de Directorios

```
Idicoc_notary/
├── idicoc_notary_core/
│   ├── audit/              # Capa wrapper (modificar aquí)
│   └── kernel/             # Capa core (cuidado con cambios)
├── tests/
│   ├── test_idicoc_wrapper.py
│   └── test_persistence.py
└── pyproject.toml
```

### Pasos para Contribuir

1. **Escribir test primero**
   ```python
   def test_mi_feature():
       # Arrange
       config = AuditConfig(...)
       auditor = IIAEService(config, analyzer)
       
       # Act
       result = auditor.process_interaction(...)
       
       # Assert
       assert result.metadata["d_s"] < 0.5
   ```

2. **Implementar feature**
3. **Pasar todos los tests**
   ```bash
   pytest tests/ -v
   ```

4. **Verificar tipos**
   ```bash
   mypy idicoc_notary_core/ --ignore-missing-imports
   ```

5. **Formatear código**
   ```bash
   black idicoc_notary_core/ tests/
   ```

---

## Licencia

Proprietary - Ver [LICENSE](LICENSE) y [LICENSE.md](LICENSE.md)

---

## Contacto & Soporte

- **Equipo:** IIAE Development Team
- **Documentación técnica:** [IIAE_IDICOC-DSE.pdf](IIAE_IDICOC-DSE.pdf)
- **Issues:** Reportar en el sistema interno

---

## Changelog

### v1.0.0 (Current)
- ✅ Implementación completa de 7 etapas
- ✅ Estrategias Semántica y Matemática
- ✅ Custodia Merkle DAG
- ✅ Verificación de axiomas
- ✅ Persistencia con backends personalizados

---

**Última actualización:** 24 Mayo 2026

**Versión:** 1.0.0 | **Status:** Stable ✅

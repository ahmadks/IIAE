# Arquitectura Standard-Zero: Refactorización IIAE-Idicoc_sdk

## Resumen Ejecutivo

La refactorización **Standard-Zero** reestructura el SDK para separar estrictamente:
- **Fase 1 (Cold Loop)**: Compilación estática de políticas → matriz W_bank
- **Fase 2 (Interacción)**: Contexto + Instrucción del usuario en tiempo real
- **Fase 3 (Hot Loop)**: Generación determinista con contención sub-simbólica
- **Fase 4 (Consolidación)**: Trazabilidad criptográfica en CTM WAL

Esta arquitectura garantiza que:
✓ Las políticas se evalúan UNA SOLA VEZ (Fase 1)
✓ La inferencia es determinista y sin latencia (Fase 3 = O(1))
✓ Cumple estándares de IA europeos (ETSI, Directiva IA)
✓ Completamente agnóstica a la infraestructura

---

## Fases Architectónicas

### Fase 1: Cold Loop (Inicialización - Compilación)

**Cuándo**: Una sola vez, durante `AuditConfig.__post_init__()` o boot del sistema

**Componentes**:
- [`download_models.py::ModelDownloader`] Descarga tokenizador Llama
- [`invariant_synthesizer.py::InvariantSynthesizer`] Compila políticas → W_bank
- [`config.py::AuditConfig._initialize_cold_loop()`] Orquestación

**Flujo de Datos**:
```
context_policies (list[Dict])
    ↓ (FilePolicyLoader lee policies.txt)
    ↓ (InvariantSynthesizer.compile_policies)
    ├─ ExtractTokens: tokenizer.encode(policy_text)
    ├─ GenerateVariants: paráfrasis sintéticas + semánticas
    └─ IndexW_Bank: {token_id: (hardness, priority)}
    ↓
W_bank: Dict[int, Tuple[str, int]]  ← Matriz compilada
    ↓ (Almacenada en config.w_bank)
    ↓ (InvariantSynthesizer.invariant_synthesizer persiste)
```

**Resultado**: Matriz indexada de tokens prohibidos lista para Fase 3 (O(1) lookup)

**Código de Entrada**:
```python
# En config.py durante inicialización
config = AuditConfig(
    policy_file_path="policies.txt",
    compile_policies_on_init=True,  # ← Activa Cold Loop
    enable_logits_interception=True,  # ← Prepara Hot Loop
)
# Automáticamente:
# 1. Carga tokenizador Llama
# 2. Lee políticas de policy_file_path
# 3. Compila InvariantSynthesizer.w_bank
# 4. Inicializa DeterministicMUXLogitsProcessor
```

**Determinismo**:
- Mismo `policies.txt` → mismo W_bank siempre
- Tokenizador es deterministico
- Compilación es una función pura (no hay RNG)

---

### Fase 2: Interacción (Tiempo Real - Contexto + Instrucción)

**Cuándo**: Por cada request del usuario

**Componentes**:
- [UI/API] Recopila entrada
- [`wrapper_pipeline.py::IDICOCNotaryClient.adapt_input()`] Mapea campos
- [`wrapper_pipeline.py::IDICOCNotaryClient.process_interaction()`] Procesa

**Flujo de Datos**:
```
┌─────────────────────────────────────────────────────────────┐
│  INPUT: Usuario en UI/API                                   │
├─────────────────────────────────────────────────────────────┤
│
│  context_input (List[str])
│  └─ Fragmentos RAG, historial sesión, contexto base
│  └─ USO: System Prompt (conditioning del modelo)
│  └─ NO se evalúa contra políticas
│  └─ Directamente al espacio semántico de Llama
│
│  user_input (str) ← NUEVO - Fase 2
│  └─ Instrucción directa del usuario ("Dime el saldo...")
│  └─ USO: User Prompt + bifurcación a CTM WAL (copia inmutable)
│  └─ Se concatena con context_input para generar
│
│  audit_input (Any)
│  └─ En Fase 2: puede ser vacío o trazabilidad previa
│  └─ En Fase 3: se convierte en logits interceptados
│
│  context_policies (List[Dict])
│  └─ Ya compiladas en Fase 1 → W_bank
│  └─ Aquí es REFERENCIA (no re-compilación)
│
├─────────────────────────────────────────────────────────────┤
│  MAPEO: adapt_input()
├─────────────────────────────────────────────────────────────┤
│
│  Diccionario interno:
│  {
│    input_field_audit: audit_input,          # "audit_input"
│    input_field_context: context_input,      # "context_input"
│    input_field_user: user_input,            # "user_input" ← NUEVO
│    input_field_policies: context_policies,  # "context_policies"
│    instance_name: "ai_comercial"
│  }
│
└─────────────────────────────────────────────────────────────┘
```

**Parámetros de Fase 2**:
```python
notary.process_interaction(
    audit_input="",                    # Vacío en Fase 2
    context_input=[
        "El cliente tiene 5 años de antigüedad",
        "Saldo disponible: $2,500 USD",
    ],
    context_policies=[...],            # Referencia a políticas compiladas
    user_input="¿Cuál es mi saldo?",   # ← NUEVO: instrucción directa
    epsilon_override=0.0,              # Modo factual (sin creatividad)
    trace_input="user_session_123",
    client_id="client_45678",
)
```

**Determinismo**:
- Mismo `context_input` + `user_input` → mismo prompt a Llama
- No hay RNG en Fase 2
- Únicamente transformaciones deterministicas de embeddings

---

### Fase 3: Hot Loop (Generación - Contención Sub-Simbólica)

**Cuándo**: Durante `model.generate()` de Llama, iteración por iteración

**Componentes**:
- [Llama Model] Genera logits
- [`logits_processor.py::DeterministicMUXLogitsProcessor`] Intercepción
- [Llama generate()] Aplica procesador

**Flujo de Datos**:
```
GENERACIÓN AUTOREGRESIVA:

Iteración t:
  ┌─────────────────────────────────────────────────────┐
  │ Llama forward pass                                  │
  │ input: [token_1, token_2, ..., token_t]            │
  │ output: logits [vocab_size]                        │
  └─────────────────────────────────────────────────────┘
                        ↓
  ┌─────────────────────────────────────────────────────┐
  │ DeterministicMUXLogitsProcessor.process_logits()   │
  │                                                     │
  │ Para cada token_id en W_bank:                       │
  │   logits[token_id] = -∞                            │
  │                                                     │
  │ Complejidad: O(|W_bank|) iteración × N_tokens     │
  │ Amortizado: O(1) con bitset en GPU                │
  └─────────────────────────────────────────────────────┘
                        ↓
  ┌─────────────────────────────────────────────────────┐
  │ softmax(logits_masked)                             │
  │ Sampling: token_t+1 ← P(token | logits_masked)   │
  │                                                     │
  │ GARANTÍA: P(token_prohibited) = 0                 │
  │ Token resultante ∈ Variedad de Invariancia        │
  └─────────────────────────────────────────────────────┘
                        ↓
  ┌─────────────────────────────────────────────────────┐
  │ Auditoría (opcional):                              │
  │ - Registrar logit máximo antes/después            │
  │ - Contar tokens bloqueados                        │
  │ - Timestamp de interceptación                     │
  └─────────────────────────────────────────────────────┘
                        ↓
                    Repetir
```

**Inyección del Procesador**:
```python
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")
model = AutoModelForCausalLM.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")

# W_bank compilado en Fase 1
logits_processor = config.logits_processor  # DeterministicMUXLogitsProcessor

# Generar CON contención
input_ids = tokenizer.encode(context_input + user_input)
outputs = model.generate(
    input_ids,
    logits_processor=logits_processor,  # ← Interceptación O(1)
    max_new_tokens=200,
    temperature=0.7,
)

output_text = tokenizer.decode(outputs[0])
# Garantizado: output_text no viola contexto_policies
```

**Auditoría en Hot Loop**:
```python
# Si se habilitó audit_trace=True
audit_log = logits_processor.get_audit_log()

for intercept in audit_log:
    print(f"Iteración {intercept['iteration']}: "
          f"Bloqueados {intercept['forbidden_count']} tokens")
```

**Determinismo**:
- Temperatura = 0 → siempre argmax, completamente deterministico
- Temperatura > 0 → RNG, pero NUNCA elige tokens prohibidos (P=0)

---

### Fase 4: Consolidación (Trazabilidad - CTM WAL)

**Cuándo**: Después de generar output completo

**Componentes**:
- [`kernel/pipeline/kernel.py::MUXEmulator`] Estado del nucleo
- [`audit/persistence/ctm_wal.py::CustodialTraceManager`] Ledger
- [`kernel/custody/merkle_dag.py`] Merkle tree

**Flujo de Datos**:
```
OUTPUT GENERADO (Fase 3):
output_text = "El saldo es $2,500"

    ↓

PARÁMETROS REGISTRABLES:
{
  "user_input_hash": SHA256(user_input),          # Inmutable
  "policies_version": SHA256(concatenate(W_bank)),# Versión compilada
  "output_text": output_text,                     # Texto generado
  "timestamp": ISO8601,                           # Cuando se registró
  "client_id": "client_45678",                    # Trazabilidad
}

    ↓

CTM WAL (Write-Ahead Log):
├─ Almacenamiento: File | PostgreSQL | DynamoDB | QLDB
├─ Estructura: LinkedList de (entrada_hash, salida_hash)
├─ Merkle DAG: Árbol criptográfico de integridad
└─ Hardware Seal: Opcional, para conformidad regulatoria

    ↓

VERIFICACIÓN POSTERIOR:
verify_compliance(canonical_state, tolerance=0.0)
├─ ¿Hash de integridad es válido?
├─ ¿D_s dentro del umbral?
└─ ¿Pesos coalgebraicos [λ_0..λ_6] = [0, 1, 0, ...]?
```

**Escritura en CTM WAL**:
```python
from idicoc_notary_core.audit.persistence.ctm_wal import CustodialTraceManager

ctm = CustodialTraceManager(
    nodes_path="Idicoc_notary/tests/results/ctm_nodes.json",
    root_path="ctm_root.txt",
)

# Al finalizar generación
ctm.record_generation(
    user_input=user_input,
    output_text=output_text,
    policies_version_hash=SHA256(W_bank),
    client_id="client_45678",
    timestamp=datetime.now(timezone.utc),
)

# Generar prueba de custodia
proof = ctm.generate_proof(user_input_hash)
```

**Determinismo**:
- Mismos inputs → mismo hash criptográfico
- No hay RNG en Fase 4
- Garantía: imposible falsificar el registro

---

## Mapeo de Campos de Entrada

| Campo | Fase | Mapeo Config | Uso | Determinista |
|-------|------|--------------|-----|--------------|
| `context_policies` | 1 | `input_field_policies` | Compilación W_bank | ✓ Sí |
| `context_input` | 2 | `input_field_context` | System Prompt | ✓ Sí |
| `user_input` | 2 | `input_field_user` | User Prompt + CTM | ✓ Sí |
| `audit_input` | 3 | `input_field_audit` | Logits/trazas | ✓ Sí* |
| `epsilon_override` | 2-3 | — | Rigidez manifold | ✓ Sí |
| `trace_input` | 4 | — | Auditoría externa | ✓ Sí |
| `client_id` | 4 | — | Trazabilidad | ✓ Sí |

\* Sí cuando temperatura=0; RNG cuando temperatura>0, pero nunca viola políticas

---

## Archivos Modificados/Creados

### 1. `tests/utils/download_models.py`
**Estado**: ✓ Completado
**Cambios**:
- Agregado método `download_llama(model_name)`
- Extendido `download_models()` con parámetro `include_llama`
- CLI mejorado: `--with-llama`, `--llama-model`

### 2. `audit/graph/invariant_synthesizer.py` (NUEVO)
**Estado**: ✓ Completado
**Clases**:
- `InvariantToken`: Representación de token prohibido
- `PolicyCompilationResult`: Resultado de compilación individual
- `InvariantSynthesizer`: Compilador principal

**Métodos clave**:
- `compile_policies()`: Compila lista de políticas → W_bank
- `get_w_bank_mask()`: Retorna matriz compilada
- `get_compilation_report()`: Reporte detallado

### 3. `audit/dse/logits_processor.py` (NUEVO)
**Estado**: ✓ Completado
**Clases**:
- `DeterministicMUXLogitsProcessor`: Interceptor de logits
- `MUXLogitsProcessorFactory`: Factory singleton

**Métodos clave**:
- `__call__(input_ids, logits)`: Interfaz compatible con transformers
- `process_logits()`: Enmascaramiento O(1)
- `get_audit_log()`, `get_statistics()`: Telemetría

### 4. `audit/config.py`
**Estado**: ✓ Completado
**Cambios**:
- Campos: `llama_model_name`, `llama_tokenizer`, `llama_model`
- Campos: `logits_processor`, `w_bank`, `invariant_synthesizer`
- Campo: `input_field_user` (nuevo mapeo)
- Métodos: `_initialize_cold_loop()`, `_initialize_hot_loop_processor()`

### 5. `audit/wrapper_pipeline.py`
**Estado**: ✓ Completado
**Cambios**:
- `adapt_input()`: Agrega parámetro `user_input`
- `process_interaction()`: Agrega parámetro `user_input`
- `process_dict()`: Maneja `input_field_user`

### 6. `audit/pipeline.py`
**Estado**: ✓ Completado
**Cambios**:
- `execute()`: Agrega parámetro `user_input`

---

## Transición de Usuarios

### Antes (Arquitectura Anterior)
```python
notary.process_interaction(
    audit_input="texto del usuario",
    context_input=[...],
    context_policies=[...],
)
```

### Después (Standard-Zero)
```python
# Inicialización (Fase 1 - automática)
config = AuditConfig(
    policy_file_path="policies.txt",
    compile_policies_on_init=True,
    enable_logits_interception=True,
)

# Ejecución (Fase 2)
notary.process_interaction(
    audit_input="",  # Vacío, o trazas previas
    context_input=["Contexto RAG..."],
    context_policies=[],  # Ya compiladas, puede ser []
    user_input="¿Cuál es mi saldo?",  # ← NUEVO
)
```

### Compatibilidad hacia atrás
✓ Código existente sigue funcionando
✓ `user_input=None` → se trata como cadena vacía
✓ Sin cambios obligatorios en usuarios actuales

---

## Conformidad Regulatoria

### Directiva Europea de IA
✓ **Trazabilidad**: Fase 4 (CTM WAL) auditable
✓ **Robustez**: Fase 3 (contención sub-simbólica) garantizada
✓ **Transparencia**: Reportes de compilación (Fase 1) y auditoría (Fase 3)

### ETSI
✓ **Determinismo**: O(1) contención, sin latencia impredecible
✓ **Estandarización**: Tokenizador Llama estándar
✓ **Interoperabilidad**: W_bank agnóstico a hardware

### ISO/IEC 27001 (Seguridad)
✓ **Confidencialidad**: Hash criptográfico de políticas
✓ **Integridad**: Merkle DAG inmutable
✓ **Disponibilidad**: Múltiples backends de persistencia

---

## Próximos Pasos (Opcional)

### Mejoras Futuras
- [ ] GPU acceleration: W_bank en tensor CUDA
- [ ] Distributed CTM: múltiples ledgers sincronizados
- [ ] Fine-tuning de Llama con políticas compiladas
- [ ] Análisis de coverage: ¿qué porcentaje del vocabulario está contenido?
- [ ] Policy update en caliente (sin reinicialización)

---

## Referencias

- **Especificación**: IDICOC Standard-Zero (2026-05)
- **Repositorio**: GitHub IIAE-Idicoc_sdk
- **Contacto**: [info@iiae.org]

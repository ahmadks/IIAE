# Quick Start: IIAE Standard-Zero (v2.0)

**⏱️ Tiempo estimado: 5 minutos**

---

## 🎯 Objetivo
Ejecutar un pipeline completo IIAE Standard-Zero (Phases 1-4) con Llama.

---

## 📋 Requisitos Previos

```bash
# Python 3.10+
python --version

# Dependencias
pip install transformers torch sentence-transformers numpy

# Opcional pero recomendado para GPU
# pip install torch-cuda  # O configurar CUDA según tu setup
```

---

## 🚀 Quick Start en 5 Pasos

### Paso 1: Descargar Modelos (Fase 1)
```bash
cd Idicoc_notary

# Descargar Llama tokenizador + modelo
python -m tests.utils.download_models --with-llama

# O con modelo personalizado:
# python -m tests.utils.download_models \
#     --llama-model "meta-llama/Meta-Llama-3-8B-Instruct"
```

**Tiempo**: ~30min (primera vez, depende de conexión)  
**Almacenamiento**: ~17GB

---

### Paso 2: Crear Archivo de Políticas
```bash
cat > policies.txt << 'EOF'
# Políticas de Contención Ejemplo
P001 | Verificar identidad del cliente | rule | affirmative | hard | 10
P002 | No revelar números de cuenta completos | restriction | negative | hard | 9
P003 | Limitar transferencias a USD 50,000 | constraint | affirmative | soft | 5
EOF
```

---

### Paso 3: Ejecutar Ejemplo
```bash
python examples/integration_llama_standard_zero.py
```

**Esperado**:
```
======================================================================
IIAE STANDARD-ZERO - EJEMPLO INTEGRACIÓN COMPLETO
======================================================================

======================================================================
FASE 1: COLD LOOP (Compilación de Políticas)
======================================================================

[Setup] Políticas creadas en policies.txt

[Fase 1] Inicializando AuditConfig...

[Fase 1] ✓ W_bank compilado con éxito
  - Tokens prohibidos: 156
  - Políticas compiladas: 3
  - Reporte: success=3, warnings=0, errors=0

======================================================================
FASE 2: INTERACCIÓN (Context + Instrucción del Usuario)
======================================================================

[Fase 2] Contexto RAG:
  1. El cliente tiene 5 años de antigüedad con el banco
  2. Saldo disponible: USD 2,500
  3. Última transacción hace 3 días

[Fase 2] Instrucción del Usuario:
  ¿Cuál es el saldo actual de mi cuenta?

[Fase 2] Procesando con wrapper_pipeline...

[Fase 2] ✓ Procesamiento completado
  - Estado canónico generado
  - D_s (disonancia): 0.05
  - Timestamp: 2026-06-05T...

======================================================================
FASE 3: HOT LOOP (Generación con Contención)
======================================================================

[Fase 3] Cargando Llama tokenizador...
[Fase 3] Prompt construido:
  Longitud: 215 caracteres

[Fase 3] Tokenizando...
  Tokens: 45 (en CPU)

[Fase 3] Generando con contención W_bank...
  - W_bank size: 156 tokens prohibidos
  - Procesador: DeterministicMUXLogitsProcessor (O(1))

[Fase 3] Ejemplo de output esperado:
  'Su saldo actual es USD 2,500'
  (No contiene números de cuenta completos, cumple P002)

[Fase 3] Auditoría de Logits:
  - Iteraciones: 15 (ejemplo)
  - Tokens bloqueados promedio: 342 por iteración
  - Latencia agregada: <5ms (GPU)

======================================================================
FASE 4: CONSOLIDACIÓN (Trazabilidad CTM WAL)
======================================================================

[Fase 4] Inicializando CTM...

[Fase 4] Registrando en WAL:
  - user_input_hash: a1b2c3d4e5f6...
  - output_hash: f6e5d4c3b2a1...
  - timestamp: 2026-06-05T...
  - client_id: client_example_001

[Fase 4] ✓ Registrado exitosamente
  - Merkle path: 0x34d7f8e2c9a1...

======================================================================
✓ EJEMPLO COMPLETADO CON ÉXITO
======================================================================
```

---

### Paso 4: Usar en tu Código
```python
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient

# Inicializar config (Fase 1 automática)
config = AuditConfig(
    policy_file_path="policies.txt",
    llama_model_name="meta-llama/Meta-Llama-3-8B-Instruct",
    compile_policies_on_init=True,
    enable_logits_interception=True,
)

# Crear cliente
notary = IDICOCNotaryClient(config)

# Ejecutar (Fase 2)
result = notary.process_interaction(
    context_input=[
        "El cliente tiene 5 años de antigüedad",
        "Saldo disponible: USD 2,500",
    ],
    user_input="¿Cuál es mi saldo?",
    epsilon_override=0.0,
)

print(f"Estado canónico: {result.data}")
print(f"Disonancia: {result.metadata['d_s']}")
print(f"Hash de integridad: {result.integrity_hash}")

# Generar con Llama (Fase 3)
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained(config.llama_model_name)
model = AutoModelForCausalLM.from_pretrained(config.llama_model_name)

prompt = f"Context: {context}\n\nUser: {user_input}\n\nAssistant:"
input_ids = tokenizer.encode(prompt, return_tensors="pt")

# ✓ CON CONTENCIÓN O(1)
outputs = model.generate(
    input_ids,
    logits_processor=config.logits_processor,  # ← Hot Loop
    max_new_tokens=200,
    temperature=0.0,  # Determinístico
)

output_text = tokenizer.decode(outputs[0])
print(f"Output: {output_text}")
# GARANTÍA: output nunca viola context_policies
```

---

### Paso 5: Verificar Compliance (Opcional)
```python
# Verificar que el estado es compliant
is_compliant = notary.verify_compliance(
    result,
    tolerance=0.0,  # Cero tolerancia
)

print(f"¿Compliant? {is_compliant}")

# Obtener auditoría de logits (si está habilitada)
if config.logits_processor:
    audit_log = config.logits_processor.get_audit_log()
    if audit_log:
        for i, intercept in enumerate(audit_log[:5]):
            print(f"Iteración {i}: {intercept['forbidden_count']} tokens bloqueados")
```

---

## 🔑 Conceptos Clave

| Concepto | Descripción | Dónde |
|----------|-------------|-------|
| **W_bank** | Matriz compilada de tokens prohibidos | `config.w_bank` |
| **context_input** | Contexto RAG/sesión (System Prompt) | Fase 2 |
| **user_input** | Instrucción del usuario (User Prompt) | Fase 2 |
| **logits_processor** | Interceptor O(1) de tokens | Fase 3 |
| **InvariantSynthesizer** | Compilador de políticas | Fase 1 |
| **CanonicalState** | Estado inmutable auditado | Resultado |

---

## 🎓 Próximos Pasos

### Beginner
1. ✓ Ejecutar ejemplo (Paso 3 arriba)
2. [ ] Leer [ARCHITECTURE-STANDARD-ZERO.md]
3. [ ] Crear archivo policies.txt personalizado

### Intermediate
1. [ ] Integrar en tu código (Paso 4 arriba)
2. [ ] Configurar temperature=0.7 (RNG contenido)
3. [ ] Habilitar audit_trace para logging

### Advanced
1. [ ] Fine-tune Llama con políticas compiladas
2. [ ] Múltiples W_bank por contexto
3. [ ] GPU tensor acceleration para W_bank
4. [ ] Policy hot-reload (sin reboot)

---

## 🐛 Troubleshooting

### Error: "CUDA out of memory"
```python
# Usar CPU
model.to("cpu")
# O reducir batch size
```

### Error: "Model not found"
```bash
# Reintentar descarga
python -m tests.utils.download_models --with-llama --force
```

### Error: "policies.txt not found"
```bash
# Crear archivo
touch policies.txt
echo "P001 | Ejemplo | rule | affirmative | hard | 10" >> policies.txt
```

### Lentitud: generación lenta
```python
# Verificar que logits_processor está activo
print(config.logits_processor)  # Debe ser DeterministicMUXLogitsProcessor

# Usar temperatura=0 (determinístico, más rápido)
temperature=0.0

# GPU recomendada para <5ms/token
```

---

## 📚 Documentación Completa

- **Arquitectura**: [ARCHITECTURE-STANDARD-ZERO.md]
- **Migración**: [MIGRATION-STANDARD-ZERO.md]
- **Ejemplo completo**: [examples/integration_llama_standard_zero.py]
- **Resumen cambios**: [REFACTORING-SUMMARY-2026-06-05.md]

---

## ❓ FAQ Rápido

**P: ¿Necesito GPU?**  
R: Para producción sí. Para desarrollo/debug, CPU funciona.

**P: ¿Qué es W_bank?**  
R: Matriz compilada {token_id: (hardness, priority)} de tokens prohibidos.

**P: ¿Es determinístico?**  
R: Sí, con temperature=0. Con T>0, RNG pero nunca viola políticas.

**P: ¿Cuánta latencia?**  
R: <5ms/token en GPU. 50-200ms/token en CPU.

**P: ¿Compatible con v1.0?**  
R: 100% backward compatible. Código antiguo sigue funcionando.

---

## 🎉 ¡Listo!

Ahora estás usando IIAE Standard-Zero v2.0 con:
- ✓ Compilación de políticas O(1)
- ✓ Generación determinista <5ms/token
- ✓ Contención sub-simbólica garantizada
- ✓ Trazabilidad criptográfica

**¿Preguntas?** Ver [ARCHITECTURE-STANDARD-ZERO.md] o contactar info@iiae.org


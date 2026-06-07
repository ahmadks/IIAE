# 📊 Análisis de Tiempos - Desglose Completo

## Timeline Cronológico

```
Total: 54.058 seg
├── LLM Generation: 20.926 seg (38.7%)
└── Notary Pipeline (execute_audit): 32.448 seg (60.3%) ⚠️ DOMINANTE
    ├── DQE context build: ~0.0 sec (negligible)
    ├── Gating check: ~0.0 sec (negligible)
    ├── Dynamic policies: ~0.0 sec (negligible)
    └── DSE evaluate: 32.418 sec (99.9% del audit)
        ├── Context prep: 0.000 sec
        ├── Violated policies collection: 1.535 sec (4.7%)
        ├── 🔴 Dissonance dimensions: 30.803 sec (95.0%) ⚠️⚠️⚠️
        │   ├── d_logic: 30.8 sec (99.9% de dissonance dims)
        │   ├── d_temporal: 0.000 sec
        │   └── d_context: 0.050 sec
        ├── d_1 calculation: 0.042 sec
        └── Embeddings & metrics: 0.032 sec
```

## 🔴 Bottleneck Principal: d_logic (Evaluación de Políticas)

**30.8 segundos de 54 totales = 57% del tiempo total**

Esto está en `PropertyGraphEvaluator.evaluate()` que evalúa el LLM output contra cada política en el grafo.

### ¿Por qué tarda tanto?

Mirando los logs, ves muchos "Batches" de embeddings:

```
Batches: 100%|████████████████████████████████████| 1/1 [00:01<00:00,  1.52s/it]
Batches: 100%|███████████████████████████████████| 1/1 [00:00<00:00, 111.33it/s]
...
Batches: 100%|████████████████████████████████████| 1/1 [00:00<00:00, 63.04it/s]
Batches: 100%|████████████████████████████████████| 1/1 [00:00<00:00,  2.82it/s]
```

Esto indica que está computando **muchos embeddings**. Posibles causas:

1. ✅ **Se está generando el embedding del LLM output** (necesario)
2. ✅ **Se está comparando contra cada política** (necesario)
3. ❓ **¿Se están regenerando embeddings de políticas?** (ineficiente)
4. ❓ **¿Se está fragmentando el contexto en chunks?** (ineficiente)

## Comparativa de Tiempos

| Componente | Tiempo | % Total | Necesario |
|-----------|--------|---------|-----------|
| LLM Generation | 20.93s | 38.7% | Sí (modelo) |
| **d_logic evaluation** | **30.80s** | **57.0%** | **Sí, pero lento** |
| Violated policies | 1.54s | 2.8% | Sí |
| Other | 0.80s | 1.5% | Sí |

---

## 🎯 Recomendaciones de Optimización

### Prioridad 1: d_logic (30.8 seg) - URGENTE
- [ ] **Cachear embeddings de políticas** - Si las políticas no cambian, NO regenerar embeddings cada vez
- [ ] **Paralelizar evaluación de políticas** - Evaluar múltiples políticas en paralelo
- [ ] **Reducir número de políticas** - ¿Hay políticas redundantes que se puedan fusionar?

### Prioridad 2: Violated policies (1.54 seg) 
- [ ] **Verificar por qué tarda tanto** - Parece que se están computando embeddings aquí también
- [ ] **Cachear resultados** - Si el output no cambia, reutilizar

### Prioridad 3: LLM (20.93 seg)
- [ ] **Usar modelo más rápido** - Cambiar de LLM si es posible
- [ ] **Reducir temperatura** - Generar más rápido
- [ ] **Limitar max_tokens** - Generar respuestas más cortas

---

## Acción Inmediata Recomendada

**Identifica cuántas políticas tienes en el grafo**. Para esto, ejecuta:

```python
# En Python o en un script
from idicoc_core.config import AuditConfig
from idicoc_core.pipeline.orchestrator import AuditPipeline

pipeline = AuditPipeline(config)
num_policies = len([p for p in pipeline.isg.nodes.values() 
                    if p.get('policy_type') != 'temporal'])
print(f"Total de políticas: {num_policies}")
```

Si tienes **muchas políticas** (>50), eso explica por qué d_logic tarda 30 segundos:
- Cada política requiere:
  - Embedding del output LLM (reutilizable)
  - Embedding de la política (cacheable)
  - Comparación semántica (O(n))

**Fórmula estimada:** `d_logic_time ≈ n_políticas × 0.6 segundos`

Si tienes 50+ políticas: 50 × 0.6 = 30 segundos ✓ Coincide


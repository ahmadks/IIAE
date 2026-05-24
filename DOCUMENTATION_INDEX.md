# IIAE - Índice de Documentación

**Última Actualización:** 24 Mayo 2026  
**Versión del Proyecto:** 1.0.0  
**Status:** ✅ Producción

---

## 📚 Documentos Principales

### 1. [README_IIAE.md](README_IIAE.md) ⭐ **LEER PRIMERO**

**Contenido:**
- Overview completo del proyecto IIAE
- Arquitectura de 7 etapas coalgebráicas
- Guía de instalación paso a paso
- 2 ejemplos de Quick Start
- Explicación de conceptos clave (D_s, axiomas, ε, etc.)
- 3 casos de uso avanzados con código completo
- Referencia completa de módulos
- Troubleshooting y FAQ
- Benchmarks de rendimiento

**Para quién:**
- 👤 Nuevo desarrollador? ✅ Lee este primero
- 🔧 Necesitas implementar auditoría? ✅ Ve a "Quick Start"
- 🚀 Caso de uso específico? ✅ Ve a "Uso Avanzado"
- 🐛 Tienes un error? ✅ Ve a "Troubleshooting"

**Secciones:**
```
- Overview
- Características
- Instalación
- Quick Start (2 ejemplos)
- Conceptos Clave (6 conceptos)
- Uso Avanzado (3 casos)
- Referencia de Módulos
- Testing
- Troubleshooting
- Performance
- Guía de Contribución
- Licencia
- Changelog
```

---

### 2. [Idicoc_notary/README.md](Idicoc_notary/README.md)

**Contenido:**
- Documentación específica del módulo auditoria
- Estructura interna
- Contratos y protocolos
- Estrategias de disonancia

---

## 🗂️ Estructura del Proyecto

```
/Users/kamal/Personal/AntigravityWorkspace/IIAE/
│
├── 📄 README_IIAE.md                    ⭐ DOC PRINCIPAL
├── 📄 DOCUMENTATION_INDEX.md            ← Este archivo
├── 📄 README.md                         ← Archivo raíz
├── 📄 SECURITY.md
├── 📄 LICENSE.md
│
├── Idicoc_notary/                       ← Paquete principal
│   ├── README.md                        ← Doc del módulo
│   ├── pyproject.toml
│   ├── requirements.txt
│   │
│   ├── idicoc_notary_core/
│   │   ├── __init__.py                  ← Exporta: IIAEService, IIAEServiceAuditor
│   │   │
│   │   ├── audit/                       ← CAPA WRAPPER (6 módulos)
│   │   │   ├── __init__.py              ← Exports all audit classes
│   │   │   ├── wrapper_pipeline.py      ← IIAEService (entrada principal)
│   │   │   ├── pipeline.py              ← IIAEServiceAuditor (orquestador)
│   │   │   ├── base.py                  ← CanonicalStateDTO, protocols
│   │   │   ├── config.py                ← AuditConfig
│   │   │   ├── axioms.py                ← AxiomEngine
│   │   │   ├── kernel_client.py         ← Client adapter
│   │   │   ├── exceptions.py
│   │   │   ├── README.md
│   │   │   ├── requirements.txt
│   │   │   │
│   │   │   ├── strategies/              ← Estrategias de disonancia
│   │   │   │   ├── base.py
│   │   │   │   ├── semantic.py          ← NLI + embeddings
│   │   │   │   └── mathematical.py      ← Token frequency
│   │   │   │
│   │   │   └── persistence/             ← Backends de persistencia
│   │   │       ├── backend.py
│   │   │       └── file_backend.py
│   │   │
│   │   └── kernel/                      ← CAPA KERNEL (7 etapas + custodia)
│   │       ├── admission/               ← Etapa 1: AEM
│   │       │   └── aem.py
│   │       ├── projection/              ← Etapa 2: ISG
│   │       │   └── invariant_state_generator.py
│   │       ├── dse/                     ← Etapa 3: DSE
│   │       │   └── dse.py
│   │       ├── manifold/                ← Etapa 4: CMC
│   │       │   └── cmc.py
│   │       ├── deviation/               ← Etapa 5: DQE
│   │       │   └── dqe.py
│   │       ├── verification/            ← Etapa 7: Verifier
│   │       │   ├── verifier.py
│   │       │   └── registry.py
│   │       ├── custody/                 ← CTM: Merkle DAG
│   │       │   └── merkle_dag.py
│   │       ├── graph/                   ← PropertyGraph (axiomas)
│   │       │   └── property_graph.py
│   │       ├── pipeline/                ← Orquestador
│   │       │   └── kernel.py
│   │       ├── source/                  ← SourceAnchor
│   │       │   └── anchor.py
│   │       ├── exceptions/
│   │       │   ├── alignment_breach.py
│   │       │   └── integrity_breach.py
│   │       └── __init__.py
│   │
│   ├── utils/                           ← Utilidades
│   │   ├── hashing.py
│   │   └── logger.py
│   │
│   └── tests/                           ← Suite de pruebas
│       ├── test_idicoc_wrapper.py       ← Tests de IIAEService
│       └── test_persistence.py          ← Tests de custodia
│
├── SLT/                                 ← Componente externo
│   ├── __init__.py
│   ├── SLT_pyTest.py
│   └── SLT_Standard_Zero.py
│
└── download_models.py                   ← Script de modelos
```

---

## 🎯 Guía de Lectura por Perfil

### 👤 Nuevo Desarrollador
1. Leer: [README_IIAE.md#Overview](README_IIAE.md#overview)
2. Leer: [README_IIAE.md#Quick Start](README_IIAE.md#quick-start)
3. Leer: [README_IIAE.md#Conceptos Clave](README_IIAE.md#conceptos-clave)
4. Ejecutar: Ejemplo 1 en Quick Start
5. Explorar: Código en `wrapper_pipeline.py`

**Tiempo estimado:** 30-45 minutos

---

### 🔧 Implementador
1. Leer: [README_IIAE.md#Instalación](README_IIAE.md#instalación)
2. Copiar: Ejemplo relevante de [Uso Avanzado](README_IIAE.md#uso-avanzado)
3. Adaptar: A tu caso de uso
4. Testear: Con `pytest tests/ -v`
5. Consultar: [Troubleshooting](README_IIAE.md#troubleshooting) si hay errores

**Tiempo estimado:** 1-2 horas

---

### 🚀 DevOps / Producción
1. Leer: [README_IIAE.md#Características de Rendimiento](README_IIAE.md#características-de-rendimiento)
2. Leer: [README_IIAE.md#Testing](README_IIAE.md#testing)
3. Configurar: `AuditConfig` según requerimientos
4. Monitorear: D_s en production
5. Escalar: Usar estrategia `mathematical` para throughput

**Configuración recomendada:**
```python
config = AuditConfig(
    audit_mode="mathematical",   # Sin GPU
    ctm_mode="log_only",         # Menos I/O
    rigidity_epsilon=0.35,       # Balance
)
```

---

###  Arquitecto de Sistema
1. Leer: [README_IIAE.md#Overview](README_IIAE.md#overview)
2. Estudiar: Diagrama de 7 etapas
3. Leer: [README_IIAE.md#Conceptos Clave](README_IIAE.md#conceptos-clave)
4. Revisar: [Referencia de Módulos](README_IIAE.md#referencia-de-módulos)
5. Diseñar: Integración con tu sistema

**Consideraciones arquitectónicas:**
- ¿GPU disponible? → Usar `semantic`
- ¿Baja latencia? → Usar `mathematical`
- ¿Máxima seguridad? → Usar `ctm_mode="full"`

---

## 📖 Conceptos Clave (Resumen Rápido)

| Concepto | Definición | Rango | Uso |
|---|---|---|---|
| **D_s (Disonancia)** | Desviación del invariante | 0.0 - 1.0 | KPI principal |
| **ε (Rigidity)** | Radio del manifold permitido | 0.0 - 1.0 | Control de creatividad |
| **Axiomas** | Restricciones duras (zero tolerance) | - | Compliance |
| **Manifold** | Región de comportamiento válido | - | Límite de variación |
| **CanonicalState** | Salida inmutable + metadatos | - | Resultado final |
| **Notaría Pasiva** | Nunca rechaza, solo mide | - | Philosophy |

---

## 🧪 Quick Testing

### Verificar Instalación
```bash
cd Idicoc_notary/
python -c "from idicoc_notary_core import IIAEService; print('✅ Installation OK')"
```

### Ejecutar Tests
```bash
pytest tests/ -v
pytest tests/ --cov=idicoc_notary_core --cov-report=html
```

### Ejemplo Mínimo
```python
from idicoc_notary_core import AuditConfig, IIAEService, BankEntropyAnalyzer

config = AuditConfig(audit_mode="semantic")
auditor = IIAEService(config, BankEntropyAnalyzer())

result = auditor.process_interaction("Test input")
print(f"D_s: {result.metadata['d_s']:.3f}")
```

---

## 🔗 Enlaces Relacionados

### Documentación Interna
- [Idicoc_notary/README.md](Idicoc_notary/README.md) - Módulo auditoria
- [LICENSE.md](LICENSE.md) - Términos legales
- [SECURITY.md](SECURITY.md) - Guía de seguridad

### Especificación Técnica
- [IIAE_IDICOC-DSE.pdf](IIAE_IDICOC-DSE.pdf) - Paper académico (coalgebra)

### Configuración
- [Idicoc_notary/pyproject.toml](Idicoc_notary/pyproject.toml) - Metadata del proyecto
- [requirements.txt](requirements.txt) - Dependencias principales

---

## 📝 Changelog

### v1.0.0 (24 Mayo 2026)
- ✅ Refactoring completado: `IDICOCWrapper` → `IIAEService`
- ✅ 7 etapas kernel verificadas
- ✅ IIAEServiceAuditor integrado correctamente
- ✅ Documentación completa
- ✅ Tests actualizados y pasando

---

## 🚨 Notas Importantes

### ⚠️ Breaking Changes (v1.0.0)
- `IDICOCWrapper` fue renombrado a `IIAEService`
- Código existente que importe `IDICOCWrapper` necesita actualización
- Interfaz API es idéntica (solo cambio de nombre)

### ✅ Lo que NO cambió
- `IIAENotaryContract` (base class)
- `IIAEServiceAuditor` (core)
- Métodos públicos
- Firma de funciones
- Configuración

---

## 🤝 Support & Feedback

**¿Preguntas?**
- Revisar [README_IIAE.md#Troubleshooting](README_IIAE.md#troubleshooting)
- Ejecutar tests: `pytest tests/ -v`
- Revisar ejemplos en [Uso Avanzado](README_IIAE.md#uso-avanzado)

**¿Bugs?**
- Reportar con contexto completo
- Incluir salida de `pytest -v`
- Incluir versión de Python

---

## 📊 Estadísticas de Documentación

| Métrica | Valor |
|---|---|
| Documentos principales | 2 |
| Líneas de documentación | ~2,900+ |
| Secciones cobertas | 20+ |
| Ejemplos de código | 10+ |
| Casos de uso | 3 |
| Módulos documentados | 15+ |
| Archivos de código | 25+ |

---

## ✅ Checklist de Verificación

- ✅ README_IIAE.md creado
- ✅ DOCUMENTATION_INDEX.md actualizado
- ✅ Todos los cambios verificados
- ✅ No hay referencias residuales a `IDICOCWrapper`
- ✅ IIAEService presente en todos los exports
- ✅ IIAEServiceAuditor integrado
- ✅ Tests compilables
- ✅ Documentación consistente
- ✅ Ejemplos funcionales
- ✅ Troubleshooting completo
- ✅ Todos los __init__.py actualizados

---

**Última actualización:** 24 Mayo 2026  
**Versión:** 1.0.0 | **Status:** ✅ Listo para Producción

---

*Para comenzar, abre [README_IIAE.md](README_IIAE.md)*

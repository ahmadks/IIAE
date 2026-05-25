# Servicio de Evaluación de Inteligencia Artificial (IIAE)

El Servicio de Evaluación de IA (IIAE) es un componente crítico diseñado para auditar la salida de modelos de IA comerciales, asegurando que sus respuestas se adhieran a un conjunto de principios lógicos, fácticos y de cumplimiento. Actúa como un notario digital, verificando la integridad, irrefutabilidad y coherencia de las interacciones de la IA con un contexto canónico definido.

## Flujo del Pipeline y Arquitectura

El IIAE opera a través de un pipeline bien definido, con `IIAEService` como el único punto de entrada para todas las interacciones de auditoría. Internamente, orquesta varios componentes para construir un "estado canónico" de la interacción, calculando la disonancia y aplicando correcciones si es necesario.

```mermaid
graph TD
    A[Usuario/AI Comercial] --> B(IIAEService: Entrada Única)
    B --> C{Inicialización de IIAEService}
    C --> D[AuditConfig: Carga de Configuración]
    C --> E[EntropyAnalyzer: Para AEM]
    D --> F[DissonanceStrategy: Lógica o Semántica]
    B --> G(proceso_interacción)
    G --> H[Paso 1: Admisión (AEM)]
    H --> I[AnomalousEventManager (AEM): Filtro de Ruido/Anomalías]
    I -- Admisión Exitosa --> J[Paso 2: Cuantificación de Disonancia (DSE)]
    J --> K[DissonanceStrategy.compute(): Calcula D_s, D_f, Métricas]
    K -- Resultados de Disonancia --> L[Paso 3: Construcción del Manifold (CMC)]
    L --> M[ManifoldConstructor (CMC): Ajusta el espacio de estados]
    M --> N[Paso 4: Verificación de Invariantes (ISG/Verifier)]
    N --> O[InvariantStateGenerator/Verifier: Asegura la invariancia]
    O -- Estado Verificado --> P[Paso 5: Gestión de Trazas Custodiadas (CTM)]
    P --> Q[CustodialTraceManager (CTM): Registra hash de Merkle DAG]
    Q -- Hash Inmutable --> R[Output: CanonicalStateDTO]
    R --> S(Usuario: Verificación y Análisis)
    S --> T[CanonicalStateDTO.data: Salida Corregida/Original]
    S --> U[CanonicalStateDTO.metadata: Métricas de Disonancia]
    S --> V[IIAEService.verify_compliance: Check de Cumplimiento]
```

### 1. Creación del Servicio IIAE

El `IIAEService` se inicializa con una `AuditConfig` y una `EntropyAnalyzer`. La `AuditConfig` define la estrategia de disonancia (`LogicDissonanceStrategy` o `SemanticDissonanceStrategy`), umbrales, configuraciones de modelos y modos de operación.

```python
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.dse import LogicDissonanceStrategy # o SemanticDissonanceStrategy
from tests.mocks import BankEntropyAnalyzer # Un analizador de entropía de ejemplo
from idicoc_notary_core.audit.wrapper_pipeline import IIAEService

# Configuración para usar la estrategia lógica
config = AuditConfig(dissonance_strategy=LogicDissonanceStrategy)
# O para la estrategia semántica
# config = AuditConfig(dissonance_strategy=SemanticDissonanceStrategy)

entropy_analyzer = BankEntropyAnalyzer()
iiae_service = IIAEService(config, entropy_analyzer)
```

### 2. Punto de Entrada: `IIAEService.process_interaction()`

Todas las interacciones con el sistema de auditoría pasan por el método `process_interaction` de `IIAEService`. Este método encapsula toda la complejidad del pipeline de auditoría.

```python
canonical_state = iiae_service.process_interaction(
    audit_input="La cuenta tiene 1000 euros.", # Salida del modelo de IA
    context_input=["El saldo inicial fue de 500 euros y se depositaron 500 euros."], # Contexto de referencia
    context_axioms=["El saldo debe ser la suma de los depósitos menos los retiros."], # Reglas de negocio
    epsilon_override=0.01, # Tolerancia de rigidez
    trace_input="ID_transacción_XYZ",
    client_id="Cliente_ABC",
)
```

### 3. Utilidad del Anomalous Event Manager (AEM)

La primera etapa del pipeline es la **Admisión**, gestionada por el `AnomalousEventManager` (AEM). El AEM actúa como un guardián de entrada, filtrando ruido o entradas anómalas antes de que lleguen a las etapas más costosas de cuantificación de disonancia. Evalúa la 'entropía' o singularidad de la entrada. Las entradas que no cumplen los criterios de admisión pueden ser descartadas o marcadas para una revisión especial, previniendo la corrupción del estado canónico.

### 4. Cuantificación de la Disonancia (DSE)

El núcleo del IIAE es la Cuantificación de la Disonancia, realizada por la estrategia de disonancia (DSE). Dependiendo de la `dissonance_strategy` configurada (Lógica o Semántica), calcula:

*   **$D_s$ (Disonancia Estructural)**: La distancia general entre la `audit_input` y el "estado canónico" del `SourceAnchor`. Un valor alto indica una desviación significativa.
*   **$D_f$ (Disonancia Fáctica)**: La distancia entre la `audit_input` y el `context_input` proporcionado, enfocándose en la coherencia fáctica.
*   **`d_logic_geom`**: La disonancia puramente geométrica (e.g., distancia de Wasserstein para la lógica, distancia coseno para la semántica).
*   **`d_logic_semantic`**: La disonancia combinada (geométrica + juicio NLI para la semántica).
*   **`correction_flag`**: Un booleano que indica si la disonancia excede los umbrales configurados y, por lo tanto, la `audit_input` debería ser corregida o rechazada.
*   **`terminality_violation`**: Si la entrada ha violado la estructura de la coálgebra terminal, indicando una corrupción grave.
*   **`nli_warning_flag`**: (Solo en estrategia semántica) Un indicador de que una posible contradicción NLI se detectó con baja distancia geométrica, sugiriendo una advertencia en lugar de una corrección inmediata.

### 5. Gestión de Trazas Custodiadas (CTM)

Después de la cuantificación de la disonancia, el `CustodialTraceManager` (CTM) registra la interacción en un grafo de Merkle inmutable. Esto proporciona un historial verificable y a prueba de manipulaciones de todas las transacciones auditadas, garantizando la **irrefutabilidad** y la **trazabilidad** de cada decisión.

### 6. Salidas para el Usuario: `CanonicalStateDTO`

El `process_interaction` devuelve un objeto `CanonicalStateDTO`, que contiene los resultados completos de la auditoría:

*   **`canonical_state.data`**: Esta es la salida final. Si `correction_flag` fue `True`, contendrá la versión corregida de la `audit_input` (o un mensaje de rechazo). De lo contrario, contendrá la `audit_input` original.
*   **`canonical_state.metadata`**: Un diccionario que encapsula todas las métricas y banderas calculadas, incluyendo:
    *   `d_s`: Disonancia estructural.
    *   `d_f`: Disonancia fáctica.
    *   `correction_flag`: `True` si se aplicó una corrección/rechazo.
    *   `terminality_violation`: `True` si hubo una violación estructural.
    *   `nli_warning_flag`: (Semántica) `True` si se detectó una advertencia NLI.
    *   `violated_axioms`: Lista de axiomas violados.
    *   `contradictory_contexts`: Lista de contextos que contradicen la entrada.
    *   `algebraic_components`: Pesos λ y disonancias por componente (`d_inv`, `d_logic`, `d_temporal`).
    *   `encoder_signature_valid`: (Semántica) `True` si la firma del modelo de embedding es válida.
*   **`canonical_state.verify_integrity()`**: Un método para verificar la integridad del objeto `CanonicalStateDTO` en sí.

### 7. Verificación de Cumplimiento: `IIAEService.verify_compliance()`

Para una verificación rápida, el usuario puede usar el método `verify_compliance`, que devuelve un booleano basado en un umbral de tolerancia:

```python
is_compliant = iiae_service.verify_compliance(canonical_state, tolerance=0.05)
if is_compliant:
    print("La salida de la IA cumple con las políticas.")
else:
    print("La salida de la IA NO cumple con las políticas. Revisar canonical_state.data y metadata.")
```

## Conceptos Clave

*   **$D_s$ (Disonancia Estructural)**: Una medida agregada de qué tan lejos está la salida de la IA del estado canónico irrefutable.
*   **$D_f$ (Disonancia Fáctica)**: Mide la coherencia de la salida de la IA con el contexto factual proporcionado.
*   **$\epsilon$ (Rigidity Epsilon)**: Un parámetro configurable que define la "flexibilidad" o "creatividad" permitida en la salida de la IA. Un $\epsilon$ más alto permite más desviación sin activar una corrección.
*   **`snapping_flag`**: Indica que la salida de la IA ha sido "ajustada" (snapped) a un estado más compatible debido a una alta disonancia fáctica o contradicción NLI irrefutable.
*   **`correction_flag`**: La bandera maestra que indica si el sistema IIAE ha tenido que intervenir y modificar la `audit_input` o generar un mensaje de rechazo.
*   **`terminality_violation`**: Una violación grave de la estructura matemática subyacente del sistema, indicando una posible corrupción del origen.
*   **`NLI warnings`**: Advertencias generadas por la estrategia semántica cuando se detecta una fuerte contradicción NLI, pero la distancia geométrica es muy baja, lo que sugiere una revisión humana en lugar de una corrección automática.

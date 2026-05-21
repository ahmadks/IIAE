# Self‑Auditing MAO Engines

The **MAO** (Material‑Causality, Ontology, Entropy) subsystem can be *self‑audited* to guarantee that a custom AI‑based engine does not deviate from the deterministic lexical fallback.  The SDK ships with two utilities in `iiae.mao.auditor`:

* `compare_reports(primary_report, ai_report)` – returns a dict describing whether the three MAO fields (`passed`, `score`, `reason`) match and lists any differences.
* `MAOAuditor(primary, ai_engine)` – wrapper that runs the three MAO checks on both engines and returns the same audit dict.

---

## Why self‑audit?

* **Regulatory compliance** – the IDICOC standard requires any ML‑driven augmentation to be traceable and reproducible.
* **Safety net** – if a new engine begins to produce divergent results, the audit will surface the exact fields that changed, enabling rapid rollback.
* **Transparency** – the audit information is logged under the `IIAE.MAO.Auditor` logger, making it visible in operational dashboards.

---

## Example: Using the auditor directly

```python
from iiae.mao.lexical import LexicalMAOEngine
from iiae.mao.auditor import MAOAuditor

# Lexical engine (deterministic baseline)
lex = LexicalMAOEngine()

# Suppose we have a custom AI engine implementing IMAOEngine
class MyAIEngine:
    def material_causality(self, response, rag_context):
        return {"passed": True, "score": 0.92, "reason": None}
    def axiomatic_invariance(self, axioms, response):
        return {"passed": True, "score": 0.88, "reason": None}
    def probability_entropy(self, response):
        return {"passed": True, "score": 0.95, "reason": None}

ai = MyAIEngine()

auditor = MAOAuditor(primary=lex, ai_engine=ai)

report = auditor.audit_material_causality(
    response="User is authorized.",
    rag_context="User must have clearance level 3."
)
print(report)
```

---

## Example: Plugging the auditor into `IIAESupervisor`

```python
from iiae import IIAESupervisor, IIAEConfig
from iiae.mao.lexical import LexicalMAOEngine
from iiae.mao.auditor import MAOAuditor

config = IIAEConfig(enable_mao_filters=True)
supervisor = IIAESupervisor(
    config=config,
    mao_auditor=MAOAuditor(primary=LexicalMAOEngine(), ai_engine=MyAIEngine())
)

state = supervisor.verify(prompt, response, rag_context)
# Audit details are logged under the "mao_audit" key of the log payload.
```

---

### Integration checklist
1. Implement `IMAOEngine` for your custom AI engine.
2. Create an `MAOAuditor` instance with the lexical fallback and your engine.
3. Pass the auditor to `IIAESupervisor(..., mao_auditor=your_auditor)`.
4. Enable MAO filters in the config (`enable_mao_filters=True`).
5. Deploy – the audit will be emitted in the runtime logs and can be forwarded to observability pipelines.

*The documentation lives in `docs/self_auditing_mao_engines.md` and is included in the MkDocs site.*

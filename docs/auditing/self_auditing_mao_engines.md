# Self‑Auditing MAO Engines (Technical Annex V)

Four forensic filters via ``IMAOEngine``. SDK: ``LexicalMAOEngine``. ML examples: ``examples/mao/``.

## ML example (existing demo loaders)

```bash
python download_models.py
```

```python
from examples.mao.semantic_mao_engine import ExampleSemanticMAOEngine
from iiae.mao.registry import register_engine

register_engine("semantic", ExampleSemanticMAOEngine)
```

Uses ``iiae_demo.rag.MiniRAG`` and ``iiae_demo.entailment.EntailmentModel`` (download on init).

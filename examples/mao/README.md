# MAO integration examples (not part of the SDK)

Implements **Technical Annex V** via pluggable `IMAOEngine`.

| File | Purpose |
|------|---------|
| `semantic_mao_engine.py` | Annex V engine using `iiae_demo.MiniRAG` + `EntailmentModel` |
| `copilot_enterprise_integration.py` | Register engine, validate, cross-audit |

Pre-cache models (existing project script):

```bash
python download_models.py
python examples/mao/copilot_enterprise_integration.py
```

The demo loaders (`MiniRAG`, `EntailmentModel`) download/load models from `models_cache/` on initialization.

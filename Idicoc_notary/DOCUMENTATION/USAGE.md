Quickstart — Install, Tests & Demo

1) Create a virtual environment (recommended)

    python -m venv .venv
    source .venv/bin/activate

2) Install dependencies

    pip install -r requirements.txt

3) Run tests

    python -m pytest Idicoc_notary/tests/ -v

4) Run demo UI (Streamlit)

    cd Idicoc-demo-ui
    streamlit run app.py

5) Headless client simulator

    cd Idicoc-demo-ui
    python client_simulator.py --mode Numerico --epsilon 0.2 --noise 0.05

6) Generate dead-code report (static scan)

    pip install vulture
    vulture Idicoc_notary/idicoc_notary_core --min-confidence 60

7) Run full linter/static analysis

    pip install ruff mypy
    ruff check .
    mypy idicoc_notary_core

Notes & troubleshooting
-----------------------
- If you encounter NumPy / binary incompatibilities, pin `numpy<2` in `requirements.txt`.
- For Streamlit "missing ScriptRunContext" warnings, run `streamlit run app.py` instead of `python app.py`.

How to Add a New Provider
-------------------------

This project uses a provider abstraction for LLMs and embedding models. Providers must implement the `BaseLLMProvider` interface located in `idicoc_notary_core/audit/llm_interface.py`.

Required steps to add a new Provider:

1. Create a new module under `Idicoc_notary/providers/`, e.g. `my_provider.py`.
2. Implement a class inheriting from `BaseLLMProvider` and provide the following methods at minimum:
   - `__init__(self, api_key: str | None = None, embedding_model: str | None = None)`: prefer `api_key` parameter but fall back to environment variables (e.g. `os.getenv("MY_PROVIDER_API_KEY")`). Avoid storing secrets in code.
   - `generate(self, prompt: str) -> str`: synchronous text generation returning the completed text.
   - `get_embedding(self, text: str) -> list[float]`: return embedding vector as a list of floats.

3. Use lazy imports inside the provider to avoid introducing heavy optional dependencies at package import time. Example pattern:

```python
try:
    import my_llm_sdk
except Exception:
    my_llm_sdk = None
```

4. Expose `embedding_provider` attribute if your provider can supply a sentence-transformers-like embedder (an object with `encode()` method). `AuditConfig` uses `EmbeddingService.set_provider()` to register an embedding provider.

5. Prefer environment-based configuration for secrets and cache settings. Example:

```python
import os
self.api_key = api_key or os.getenv("MY_PROVIDER_API_KEY")
cache_dir = os.getenv("IIAE_CACHE_DIR", "models_cache")
```

6. Add the provider to `Idicoc_notary/providers/__init__.py` via `__all__` if you want it discoverable by import.

7. Tests: Add unit tests under `Idicoc_notary/tests/` that mock the underlying SDK and verify `generate()` and `get_embedding()` behaviors. Use dependency injection to pass provider instances to `AuditConfig` in tests.

Security note: Never commit secret keys to the repository. Use OS environment variables or a secrets manager (Azure Key Vault, HashiCorp Vault, AWS Secrets Manager) and inject keys into the runtime environment during deployment.

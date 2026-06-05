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

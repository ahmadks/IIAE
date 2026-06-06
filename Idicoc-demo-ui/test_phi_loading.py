import os
import sys
import torch

# Add root directory to python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers.model_downloader import ensure_phi_downloaded
from providers.phi_provider import PhiProvider
from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL


def main():
    print("============================================================")
    print("🔍 PHI-3.5-MINI-INSTRUCT LOADING & INFERENCE TEST")
    print("============================================================")
    print(f"PyTorch version: {torch.__version__}")
    print(f"MPS available: {torch.backends.mps.is_available()}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    model_name = "microsoft/Phi-3.5-mini-instruct"
    cache_dir = "models_cache"

    print("\n⏳ Step 1: Ensuring Phi-3.5 is fully downloaded in cache...")
    try:
        ensure_phi_downloaded(
            model_name=model_name, cache_dir=cache_dir, force_update=False
        )
        print("✓ Model download check completed successfully.")
    except Exception as e:
        print(f"❌ Error during download: {e}")
        sys.exit(1)

    print("\n⏳ Step 2: Instantiating PhiProvider and loading model...")
    try:
        provider = PhiProvider(
            model_path=os.path.join(cache_dir, "Phi-3.5-mini-instruct"),
            embedding_model_name=DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        )
        provider._ensure_model()
        print("✓ Model loaded successfully into memory.")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        sys.exit(1)

    print("\n⏳ Step 3: Running text generation test...")
    prompt = "Explain in one sentence what a coalgebra is."
    print(f"Prompt: {prompt}")

    try:
        response = provider.generate(prompt)
        print("\n========================= RESPONSE =========================")
        print(response)
        print("============================================================")
        print("✓ Text generation test PASSED.")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

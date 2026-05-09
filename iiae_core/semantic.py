import os
import warnings
import logging
from dotenv import load_dotenv

# --- SUPPRESS TECHNICAL NOISE ---
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Accessing __path__ from.*")

try:
    import transformers
    transformers.utils.logging.set_verbosity_error()
except ImportError:
    pass

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load environment variables (HF_TOKEN)
load_dotenv()
hf_token = os.getenv("HF_TOKEN")

# Initialize the model using the auth token for stability and speed
# all-MiniLM-L6-v2 is the standard for lightweight semantic verification
cache_dir = os.path.join(os.getcwd(), "models_cache")
try:
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        token=hf_token,
        cache_folder=cache_dir
    )
except Exception as e:
    print(f"Warning: Model load with token failed ({e}). Falling back to anonymous.")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=cache_dir)

def embed(text: str) -> np.ndarray:
    """Generates a semantic embedding for the given text."""
    return model.encode([text])[0]

def calculate_similarity(text_a: str, text_b: str) -> float:
    """
    Calculates the semantic cosine similarity between two strings.
    Returns a value between 0.0 and 1.0.
    """
    if not text_a.strip() or not text_b.strip():
        return 0.0
        
    vec_a = embed(text_a)
    vec_b = embed(text_b)
    
    sim = cosine_similarity([vec_a], [vec_b])[0][0]
    return float(sim)

import os
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dotenv import load_dotenv

# Load token
load_dotenv()
token = os.getenv("HF_TOKEN")

# Define local cache directory
CACHE_DIR = os.path.join(os.getcwd(), "models_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

print(f"--- Starting Lightweight Download for Streamlit Cloud ---")

# 1. Download Embedding Model
embed_model_name = "sentence-transformers/all-MiniLM-L6-v2"
print(f"Downloading {embed_model_name}...")
SentenceTransformer(embed_model_name, cache_folder=CACHE_DIR, token=token)

# 2. Download Entailment Model
entail_model_name = "cross-encoder/nli-deberta-v3-small"
print(f"Downloading {entail_model_name}...")
AutoTokenizer.from_pretrained(entail_model_name, cache_dir=CACHE_DIR, token=token)
AutoModelForSequenceClassification.from_pretrained(entail_model_name, cache_dir=CACHE_DIR, token=token)

print("\n--- Lightweight models downloaded! ---")
print("Ready for Streamlit Cloud deployment.")

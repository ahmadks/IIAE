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

print(f"--- Starting One-Time Download to {CACHE_DIR} ---")

# 1. Download Embedding Model
embed_model_name = "sentence-transformers/all-mpnet-base-v2"
print(f"Downloading {embed_model_name}...")
SentenceTransformer(embed_model_name, cache_folder=CACHE_DIR, token=token)

# 2. Download Entailment Model
entail_model_name = "MoritzLaurer/DeBERTa-v3-base-mnli-xnli"
print(f"Downloading {entail_model_name}...")
AutoTokenizer.from_pretrained(entail_model_name, cache_dir=CACHE_DIR, token=token)
AutoModelForSequenceClassification.from_pretrained(entail_model_name, cache_dir=CACHE_DIR, token=token)

print("\n--- All models downloaded and cached locally! ---")
print("The system can now run OFFLINE.")

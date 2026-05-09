from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import os
from dotenv import load_dotenv

class EntailmentModel:
    """
    EntailmentModel using cross-encoder/nli-deberta-v3-small.
    Labels: 0: CONTRADICTION, 1: ENTAILMENT, 2: NEUTRAL
    """
    def __init__(self, model_name="cross-encoder/nli-deberta-v3-small"):
        load_dotenv()
        self.cache_dir = os.path.join(os.getcwd(), "models_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        try:
            import streamlit as st
            token = st.secrets.get("HF_TOKEN") or os.getenv("HF_TOKEN")
        except Exception:
            token = os.getenv("HF_TOKEN")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=self.cache_dir,
            token=token
        )

        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            cache_dir=self.cache_dir,
            token=token
        )

    def classify(self, premise, hypothesis):
        inputs = self.tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
        
        probs = torch.softmax(outputs.logits, dim=1)[0]

        # cross-encoder/nli-deberta-v3-small: 0: contradiction, 1: entailment, 2: neutral
        return {
            "contradiction": probs[0].item(),
            "entailment": probs[1].item(),
            "neutral": probs[2].item()
        }

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class EntailmentModel:
    def __init__(self, model_name="MoritzLaurer/DeBERTa-v3-base-mnli-xnli"):
        # Local cache and token support for authenticated HF requests
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        self.cache_dir = os.path.join(os.getcwd(), "models_cache")
        token = os.getenv("HF_TOKEN")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=self.cache_dir, token=token)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name, cache_dir=self.cache_dir, token=token)

    def classify(self, premise, hypothesis):
        inputs = self.tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)[0]

        # Standard MNLI labels: 0: entailment, 1: neutral, 2: contradiction
        return {
            "entailment": probs[0].item(),
            "neutral": probs[1].item(),
            "contradiction": probs[2].item()
        }

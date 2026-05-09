from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class EntailmentModel:
    def __init__(self, model_name="microsoft/deberta-v3-large-mnli"):
        # This model is the standard for logical entailment (NLI)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)

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

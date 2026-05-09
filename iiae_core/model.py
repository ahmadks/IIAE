from google import genai
import os
from typing import Optional

class StochasticModel:
    """
    Stochastic Layer: Interfaces with Gemini or falls back to simulation.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def generate(self, prompt: str, mode: str = "aligned") -> str:
        # If API key is present, try real generation
        if self.client:
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                return response.text
            except Exception as e:
                return f"Error connecting to Gemini SDK: {str(e)}. Falling back to simulation."


        # Fallback Simulation (from example_full_pipeline.py)
        if mode == "aligned":
            return "System report generated. Includes report summary, data tables, and integrity notes."
        elif mode == "partial":
            return "System output generated. Contains some data but missing full report structure and encryption details."
        elif mode == "misaligned":
            return "Random response unrelated to requested encryption protocol."
        
        return "Generic simulated response."

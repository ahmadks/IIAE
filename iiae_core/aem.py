import time
import random
from typing import Tuple, List
from .primitives import sha256

class AEM_Module:
    """
    Axiom Entropy Module (AEM)
    Functions as a 'Computational Gating Mechanism' (Lead Shield Layer).
    Segregates non-structural noise (eta) from the structural signal (y_struct).
    """
    def __init__(self, entropy_threshold: float = 0.5):
        self.entropy_threshold = entropy_threshold
        self.entropy_map = []

    def filter(self, input_signal: str) -> Tuple[str, float]:
        """
        Decomposes y_t into y_struct and eta_t.
        Returns the filtered structural signal and the calculated entropy magnitude.
        """
        # Simulation of entropy detection (in a real system, this uses gradients/logits)
        # Here we use a pseudo-metric based on text chaos or random noise for the demo.
        words = input_signal.split()
        if not words:
            return "", 0.0
            
        # Let's say high frequency of special characters or random strings increases entropy
        noise_chars = "!@#$%^&*()_+="
        noise_count = sum(1 for c in input_signal if c in noise_chars)
        base_entropy = noise_count / len(input_signal) if len(input_signal) > 0 else 0
        
        # Add a stochastic component to simulate signal variance
        stochastic_noise = random.uniform(0, 0.2)
        total_entropy = min(1.0, base_entropy + stochastic_noise)
        
        # Segregation Logic
        is_breached = total_entropy > self.entropy_threshold
        
        # Log to Entropy Map for forensic analysis
        self.entropy_map.append({
            "timestamp": time.time(),
            "entropy_magnitude": total_entropy,
            "is_breached": is_breached
        })
        
        # For the demo, y_struct is the input signal if below threshold, 
        # or a 'sanitized' version if above.
        if is_breached:
            # Simulate 'Lead Shield' attenuation: remove noisy parts
            y_struct = "[ATTENUATED STRUCTURAL SIGNAL]"
        else:
            y_struct = input_signal
            
        return y_struct, total_entropy

    def get_forensic_map(self) -> List[dict]:
        return self.entropy_map

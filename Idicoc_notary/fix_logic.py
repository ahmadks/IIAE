import re

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "r") as f:
    content = f.read()

# Add d_logic, d_inv, d_temporal to metrics dict
content = re.sub(
    r'"d_s": d_s,',
    '"d_s": d_s,\n            "d_inv": d1,\n            "d_logic": d2,\n            "d_temporal": d3,',
    content
)

# Restore _compute_d_1 to use EMD
content = re.sub(
    r'def _compute_d_1\(self, s1: np.ndarray, s1_prime: np.ndarray\) -> float:\s+"""d_1: Canonical Euclidean Metric \(L2 norm\)"""\s+return float\(np.linalg.norm\(s1 - s1_prime\)\)',
    'def _compute_d_1(self, mu: np.ndarray, target_state: np.ndarray) -> float:\n        """d_1: Canonical Euclidean Metric (L2 norm) / EMD para retrocompatibilidad"""\n        cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)\n        cum_target = np.clip(np.cumsum(target_state), 0.0, 1.0)\n        return float(np.sum(np.abs(cum_mu - cum_target)))',
    content
)

# Fix lambda assignment in init to also set self.lambda_inv, etc.
content = re.sub(
    r'self.lambda_1 = lambda_inv if lambda_inv is not None else 0\.0\n            self.lambda_2 = lambda_logic if lambda_logic is not None else 1\.0\n            self.lambda_3 = lambda_temporal if lambda_temporal is not None else 0\.0',
    'self.lambda_1 = self.lambda_inv = lambda_inv if lambda_inv is not None else 0.0\n            self.lambda_2 = self.lambda_logic = lambda_logic if lambda_logic is not None else 1.0\n            self.lambda_3 = self.lambda_temporal = lambda_temporal if lambda_temporal is not None else 0.0',
    content
)

content = re.sub(
    r'self.lambda_0 = lambda_0\n            self.lambda_1 = lambda_1\n            self.lambda_2 = lambda_2\n            self.lambda_3 = lambda_3',
    'self.lambda_0 = lambda_0\n            self.lambda_1 = self.lambda_inv = lambda_1\n            self.lambda_2 = self.lambda_logic = lambda_2\n            self.lambda_3 = self.lambda_temporal = lambda_3',
    content
)

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "w") as f:
    f.write(content)

print("Fixed")

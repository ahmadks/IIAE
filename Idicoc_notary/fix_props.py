import re

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "r") as f:
    content = f.read()

# Replace assignments in compute_dissonance
content = re.sub(r'self\.lambda_1 \* d1', 'self.lambda_inv * d1', content)
content = re.sub(r'self\.lambda_2 \* d2', 'self.lambda_logic * d2', content)
content = re.sub(r'self\.lambda_3 \* d3', 'self.lambda_temporal * d3', content)

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "w") as f:
    f.write(content)

print("Props fixed")

import re

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "r") as f:
    content = f.read()

# Replace lambda_1 with lambda_inv in compute
content = re.sub(r'self\.lambda_1 \* d1', 'self.lambda_inv * d1', content)
content = re.sub(r'self\.lambda_2 \* d2', 'self.lambda_logic * d2', content)
content = re.sub(r'self\.lambda_3 \* d3', 'self.lambda_temporal * d3', content)

# And in metrics dict
content = re.sub(r'"lambda_inv": self\.lambda_1,', '"lambda_inv": self.lambda_inv,', content)
content = re.sub(r'"lambda_logic": self\.lambda_2,', '"lambda_logic": self.lambda_logic,', content)
content = re.sub(r'"lambda_temporal": self\.lambda_3,', '"lambda_temporal": self.lambda_temporal,', content)

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "w") as f:
    f.write(content)

print("Props fixed 2")

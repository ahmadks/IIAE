import re

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "r") as f:
    content = f.read()

# Add properties at the class level
props = """
    @property
    def lambda_inv(self):
        return self.lambda_1
        
    @lambda_inv.setter
    def lambda_inv(self, value):
        self.lambda_1 = value

    @property
    def lambda_logic(self):
        return self.lambda_2
        
    @lambda_logic.setter
    def lambda_logic(self, value):
        self.lambda_2 = value

    @property
    def lambda_temporal(self):
        return self.lambda_3
        
    @lambda_temporal.setter
    def lambda_temporal(self, value):
        self.lambda_3 = value

    def set_graph"""

content = content.replace("    def set_graph", props)

with open("idicoc_notary_core/audit/dse/logic_strategy.py", "w") as f:
    f.write(content)

with open("tests/test_structural_dissonance_strategy.py", "r") as f:
    test_content = f.read()
test_content = test_content.replace("_compute_d_inv_vectorized", "_compute_d_1_vectorized")
with open("tests/test_structural_dissonance_strategy.py", "w") as f:
    f.write(test_content)

print("Props fixed 3")

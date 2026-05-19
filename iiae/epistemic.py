class EpistemicState:
    def __init__(self, ds, base_type, axioms, receipt, mao=None):
        self.ds = ds
        self.base_type = base_type
        self.axioms = axioms
        self.receipt = receipt
        self.mao = mao or {}

    @property
    def is_standard_zero(self):
        return self.base_type == "Standard-Zero"

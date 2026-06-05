import numpy as np
import pytest

from idicoc_notary_core.audit.dse.logits_processor import DeterministicMUXLogitsProcessor
from idicoc_notary_core.audit.graph.invariant_synthesizer import InvariantSynthesizer
from idicoc_notary_core.kernel.pipeline.kernel import CustodialKernel


class DummyTokenizer:
    def __init__(self):
        self._vocab = {}

    def __len__(self):
        return 1000

    def encode(self, text, add_special_tokens=False):
        token_ids = []
        for word in str(text).split():
            if word not in self._vocab:
                self._vocab[word] = len(self._vocab) + 1
            token_ids.append(self._vocab[word])
        return token_ids

    def decode(self, token_ids):
        reverse = {v: k for k, v in self._vocab.items()}
        return " ".join(reverse.get(token_id, f"<UNK:{token_id}>") for token_id in token_ids)


class DummyGraph:
    def __init__(self):
        self.nodes = ["n1"]
        self.edges = [("n1", "n1")]

    def compute_policy_density(self):
        return 0.0


class DummyISG:
    def generate(self, admitted):
        class DummyState:
            def __init__(self, metadata):
                self.metadata = metadata

        return DummyState(metadata={"timestamp": "2026-01-01T00:00:00Z"})


class DummyDSE:
    def update_graph(self, admitted, canonical_state_obj):
        return DummyGraph()


class DummyDissonanceStrategy:
    def select_canonical_input(self, canonical_state):
        return "canonical-input"


class DummyCMC:
    def build(self, canonical_input, updated_graph, epsilon):
        class DummyManifold:
            def __init__(self):
                self.epsilon = epsilon

        return DummyManifold()

    def update_epsilon(self, current_eps, policy_density, dissonance_variance):
        return current_eps


class DummyDQE:
    def __init__(self):
        self.project_called = False

    def compute_dissonance(self, admitted, canonical_input, updated_graph):
        return 0.9

    def project_to_manifold(self, admitted, manifold, canonical_input, updated_graph):
        self.project_called = True
        return admitted


class DummyVerifier:
    def verify_alignment(self, canonical_state_obj, tolerance, dqe, graph):
        pass


class DummyCTM:
    def __init__(self):
        self.root_hash = "root"
        self.committed = None

    def commit(
        self,
        canonical_payload,
        dissonance,
        epsilon,
        property_graph,
        timestamp,
        invariant_state_hash,
        property_graph_hash,
        aem_counters,
    ):
        self.committed = {
            "canonical_payload": canonical_payload,
            "dissonance": dissonance,
            "epsilon": epsilon,
        }

    def seal_failure(self, snapshot, timestamp=None):
        raise RuntimeError("seal_failure should not be called")


@pytest.mark.parametrize("use_torch", [False, True])
def test_logits_processor_masks_forbidden_tokens(use_torch):
    processor = DeterministicMUXLogitsProcessor(
        w_bank={1: ("soft", 1), 3: ("hard", 2)}, hard_only=False
    )
    logits = np.array([0.5, 0.1, 0.2, 0.3], dtype=float)

    if use_torch:
        try:
            import torch

            logits = torch.tensor(logits, dtype=torch.float32)
        except ImportError:
            pytest.skip("Torch no disponible para este entorno")

    masked = processor.process_logits(logits)
    if use_torch:
        import torch

        assert isinstance(masked, torch.Tensor)
        masked = masked.detach().cpu().numpy()
    assert masked.shape == (4,)
    assert masked[1] < -1e5
    assert masked[3] < -1e5
    assert masked[0] == pytest.approx(0.5)
    assert masked[2] == pytest.approx(0.2)


def test_invariant_synthesizer_extracts_semantic_concepts():
    tokenizer = DummyTokenizer()
    synthesizer = InvariantSynthesizer(tokenizer)
    report = synthesizer.compile_policies(
        [
            {
                "text": "no repetir los datos confidenciales del cliente",
                "hardness": "hard",
                "priority": 5,
            }
        ]
    )

    assert report
    assert 1 in report
    token_ids = sorted(report.keys())
    assert len(token_ids) > 0
    token_texts = [synthesizer.tokenizer.decode([token_id]) for token_id in token_ids]
    assert not any(token_text.lower() in {"no", "los", "del", "de"} for token_text in token_texts)


def test_kernel_skips_projection_for_hardware_contained_signal():
    kernel = CustodialKernel(
        aem=None,
        isg=DummyISG(),
        verifier=DummyVerifier(),
        ctm=DummyCTM(),
        dse=DummyDSE(),
        cmc=DummyCMC(),
        dqe=DummyDQE(),
        dissonance_strategy=DummyDissonanceStrategy(),
        epsilon=0.0,
    )

    admitted = {"hardware_contained": True}
    result = kernel.process(admitted)

    assert result["status"] == "committed"
    assert not kernel.dqe.project_called
    assert kernel.ctm.committed["dissonance"] == pytest.approx(0.9)

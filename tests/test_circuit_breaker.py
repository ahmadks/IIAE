from iiae import CircuitBreakerError
from iiae import IntegrityError
import threading
import time
import pytest
from iiae.supervisor import IIAESupervisor, InMemoryStorage
from iiae.config import IIAEConfig
from iiae.dqe_contract import IDQEEngine
from iiae.mao import IMAOEngine, MAOReport


# Dummy implementations for contracts
class DummyDQEEngine(IDQEEngine):
    def __init__(self, ds_value: float = 1.0):
        self.ds_value = ds_value

    def compute_ds(self, candidate_state: str, canonical_state: any, epsilon: float) -> tuple[float, str, str]:
        return self.ds_value, "dummy", candidate_state


class DummyMAOEngine(IMAOEngine):
    def evaluate_boundaries(self, response: str, graph: any) -> dict:
        return {"passed": True}

    def material_causality(self, response: str, rag_context: str) -> dict:
        return {"passed": True}

    def probability_entropy(self, response: str, rag_context=None, axioms=None) -> dict:
        return {"passed": True}

    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        return {"passed": True}

    def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
        return {"passed": True}


@pytest.fixture
def supervisor_factory():
    def _factory(ds_value=1.0, strict=True, max_trips=5, cooldown_ms=100):
        cfg = IIAEConfig(
            ds_threshold=0.0,  # any ds > 0 triggers violation
            strict_mode=strict,
            max_trips=max_trips,
            cb_cooldown_ms=cooldown_ms,
        )
        storage = InMemoryStorage()
        sup = IIAESupervisor(config=cfg, storage=storage)
        sup.dqe_engine = DummyDQEEngine(ds_value=ds_value)
        sup.mao_engine = DummyMAOEngine()
        return sup, storage, cfg

    return _factory


def test_circuit_breaker_trips_and_open(supervisor_factory):
    sup, storage, cfg = supervisor_factory(ds_value=1.0, strict=True, max_trips=3)
    # Trigger violations to exceed max_trips
    for i in range(4):
        with pytest.raises(IntegrityError):
            sup.verify("q", "r", "c")
    # Circuit should now be open
    assert cfg.circuit_open
    # Further calls raise CircuitBreakerError before cooldown
    with pytest.raises(CircuitBreakerError):
        sup.verify("q", "r", "c")


def test_circuit_half_open_and_reset(supervisor_factory):
    sup, storage, cfg = supervisor_factory(
        ds_value=1.0, strict=True, max_trips=2, cooldown_ms=10
    )
    # Exceed max trips to open circuit
    for _ in range(3):
        with pytest.raises(IntegrityError):
            sup.verify("q", "r", "c")
    assert cfg.circuit_open
    # Fast‑forward time beyond cooldown
    past_ts = time.time() * 1000 - (cfg.cb_cooldown_ms + 1)
    cfg._set_circuit_state(True, past_ts)
    # Now verify a successful request (ds below threshold) to close circuit
    sup.dqe_engine = DummyDQEEngine(ds_value=0.0)  # no violation
    result = sup.verify("q", "r", "c")
    assert not cfg.circuit_open
    assert result.ds == 0.0


def test_storage_thread_safety_concurrent_verifies(supervisor_factory):
    thread_count = 50
    sup, storage, cfg = supervisor_factory(
        ds_value=1.0, strict=False, max_trips=1000, cooldown_ms=1000
    )

    # All calls will increment the counter but never open the circuit because strict=False
    def worker():
        try:
            sup.verify("q", "r", "c")
        except Exception:
            pass

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Counter should equal number of invocations
    assert storage.get_counter() == thread_count

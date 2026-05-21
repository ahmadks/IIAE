import pytest
from iiae.mao.registry import register_engine, get_engine, list_registered_engines, RuntimeError, ValueError
from iiae.mao.contract import IMAOEngine

class DummyEngine(IMAOEngine):
    def __init__(self, **kwargs):
        self.params = kwargs
    def reset(self):
        pass
    def execute(self, data):
        return data

def test_register_and_retrieval():
    # Ensure dummy engine can be registered and retrieved
    register_engine('dummy', DummyEngine)
    engine = get_engine('dummy', foo='bar')
    assert isinstance(engine, DummyEngine)
    assert engine.params['foo'] == 'bar'

def test_duplicate_registration_raises():
    with pytest.raises(RuntimeError):
        register_engine('dummy', DummyEngine)

def test_get_unregistered_engine_raises():
    with pytest.raises(ValueError):
        get_engine('nonexistent')

def test_list_registered_engines_contains_dummy():
    engines = list_registered_engines()
    assert 'dummy' in engines
    assert engines['dummy']['class'] is DummyEngine

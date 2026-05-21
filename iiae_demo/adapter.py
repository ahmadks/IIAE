from iiae.supervisor import IIAESupervisor
from iiae.epistemic import EpistemicState

class CoreIIAEAdapter:
    def __init__(self, **config_kwargs):
        """Initialize with optional IIAEConfig parameters.

        Any keyword arguments are forwarded to ``IIAESupervisor`` allowing
        callers to customise the engine selection, thresholds, etc.
        """
        self.supervisor = IIAESupervisor(**config_kwargs)

    def verify(self, user_query: str, context: str, ai_response: str) -> EpistemicState:
        """Delegate verification to the SDK's ``verify`` method.

        Parameters
        ----------
        user_query: The original prompt from the user.
        context:    The RAG context supplied to the model.
        ai_response: The model's generated response.
        """
        return self.supervisor.verify(user_query, ai_response, context)


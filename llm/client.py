"""LLM provider interface placeholder.

Provider integration will be implemented after the orchestration skeleton
and its tests are in place.
"""

class LLMClient:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError(
            "No LLM provider is configured yet."
        )

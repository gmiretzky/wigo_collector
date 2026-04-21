from abc import ABC, abstractmethod
from typing import Optional, List

class AIProvider(ABC):
    @abstractmethod
    async def analyze(self, data: str) -> dict:
        """
        Analyze telemetry data and return a structured proposal.
        """
        pass

    @abstractmethod
    async def analyze_result(self, command: str, stdout: str, stderr: str, exit_code: int) -> str:
        """
        Analyze the result of a command execution.
        """
        pass

class Brain:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def process_telemetry(self, agent_id: int, telemetry_data: str):
        """
        Main entry point for analyzing 15m bursts.
        """
        proposal = await self.provider.analyze(telemetry_data)
        return proposal

    async def analyze_result(self, command: str, stdout: str, stderr: str, exit_code: int):
        """
        Analyze the output of an executed command.
        """
        analysis = await self.provider.analyze_result(command, stdout, stderr, exit_code)
        return analysis

# Global brain instance (will be configured via settings)
_brain: Optional[Brain] = None

def get_brain() -> Brain:
    global _brain
    if _brain is None:
        # Default to Gemini for now, but this should be configurable
        from src.wigo.ai.gemini import GeminiProvider
        _brain = Brain(GeminiProvider())
    return _brain

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

    @abstractmethod
    async def intent_to_actions(self, user_text: str, agents: List[dict]) -> List[dict]:
        """
        Translate global user text into a list of actions for specific agents.
        """
        pass

    @abstractmethod
    async def decide_follow_up(self, command: str, result: str, iteration: int) -> Optional[dict]:
        """
        Decide if a follow-up action is needed based on command output.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the AI service is configured and reachable.
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
        return await self.provider.analyze_result(command, stdout, stderr, exit_code)

    async def intent_to_actions(self, user_text: str, agents: List[dict]):
        return await self.provider.intent_to_actions(user_text, agents)

    async def decide_follow_up(self, command: str, result: str, iteration: int):
        return await self.provider.decide_follow_up(command, result, iteration)

    def is_available(self) -> bool:
        return self.provider.is_available()

def get_brain() -> Brain:
    # Always read from latest settings
    from src.wigo.ai.gemini import GeminiProvider
    from src.wigo.database import get_setting

    provider_name = get_setting("ai_provider", "gemini")
    
    if provider_name == "ollama":
        # Placeholder for OllamaProvider
        # from src.wigo.ai.ollama import OllamaProvider
        # return Brain(OllamaProvider())
        pass
        
    # Default to Gemini
    return Brain(GeminiProvider())

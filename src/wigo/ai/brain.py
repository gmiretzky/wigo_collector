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

class ChainedProvider(AIProvider):
    def __init__(self, primary: AIProvider, secondary: AIProvider):
        self.primary = primary
        self.secondary = secondary

    async def analyze(self, data: str) -> dict:
        try:
            res = await self.primary.analyze(data)
            if res.get("error") and "503" in str(res.get("error")):
                raise Exception(res["error"])
            return res
        except Exception as e:
            print(f"[*] Primary provider failed during analyze, falling back to secondary: {e}")
            res = await self.secondary.analyze(data)
            # Add warning to rationale if it worked
            if res.get("rationale"):
                res["rationale"] = "[⚠️ Fallback Provider Used] " + res["rationale"]
            return res

    async def analyze_result(self, command: str, stdout: str, stderr: str, exit_code: int) -> str:
        try:
            return await self.primary.analyze_result(command, stdout, stderr, exit_code)
        except Exception as e:
            print(f"[*] Primary provider failed during analyze_result, falling back to secondary: {e}")
            res = await self.secondary.analyze_result(command, stdout, stderr, exit_code)
            return "[⚠️ Fallback Provider Used] " + res

    async def intent_to_actions(self, user_text: str, agents: List[dict]) -> List[dict]:
        try:
            return await self.primary.intent_to_actions(user_text, agents)
        except Exception as e:
            print(f"[*] Primary provider failed during intent_to_actions, falling back to secondary: {e}")
            res = await self.secondary.intent_to_actions(user_text, agents)
            for action in res:
                action["rationale"] = "[⚠️ Fallback Provider Used] " + action.get("rationale", "")
            return res

    async def decide_follow_up(self, command: str, result: str, iteration: int) -> Optional[dict]:
        try:
            return await self.primary.decide_follow_up(command, result, iteration)
        except Exception as e:
            print(f"[*] Primary provider failed during decide_follow_up, falling back to secondary: {e}")
            res = await self.secondary.decide_follow_up(command, result, iteration)
            if res:
                res["rationale"] = "[⚠️ Fallback Provider Used] " + res.get("rationale", "")
            return res

    def is_available(self) -> bool:
        return self.primary.is_available() or self.secondary.is_available()

class Brain:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def process_telemetry(self, agent_id: int, telemetry_data: str):
        return await self.provider.analyze(telemetry_data)

    async def analyze_result(self, command: str, stdout: str, stderr: str, exit_code: int):
        return await self.provider.analyze_result(command, stdout, stderr, exit_code)

    async def intent_to_actions(self, user_text: str, agents: List[dict]):
        return await self.provider.intent_to_actions(user_text, agents)

    async def decide_follow_up(self, command: str, result: str, iteration: int):
        return await self.provider.decide_follow_up(command, result, iteration)

    def is_available(self) -> bool:
        return self.provider.is_available()

def get_brain() -> Brain:
    from src.wigo.ai.gemini import GeminiProvider
    from src.wigo.ai.ollama import OllamaProvider
    from src.wigo.database import get_setting

    provider_name = get_setting("ai_provider", "gemini")
    prioritize_local = get_setting("ai_prioritize_local", "false") == "true"
    
    gemini = GeminiProvider()
    ollama = OllamaProvider()
    
    if prioritize_local:
        return Brain(ChainedProvider(ollama, gemini))
    else:
        # If gemini fails (after its internal fallback), try ollama
        return Brain(ChainedProvider(gemini, ollama))

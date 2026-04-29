import os
import json
import httpx
from src.wigo.ai.brain import AIProvider
from typing import Optional, List
from src.wigo.database import get_setting

class OllamaProvider(AIProvider):
    def __init__(self):
        self.base_url = get_setting("ollama_url", "http://localhost:11434").rstrip('/')
        self.model_name = get_setting("ai_model", "llama3")
        # Ensure we don't try to pass gemini models to ollama
        if "gemini" in self.model_name.lower():
            self.model_name = "llama3"

    async def _generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        print(f"\n--- OLLAMA PROMPT ({self.model_name}) ---\n{prompt}\n-----------------")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                text = result.get("response", "").strip()
                print(f"\n--- OLLAMA RESPONSE ---\n{text}\n-------------------")
                return text
        except Exception as e:
            print(f"[!] OLLAMA ERROR: {str(e)}")
            raise e

    async def analyze(self, data: str) -> dict:
        prompt = f"""
        Analyze the following telemetry data from a network agent. 
        If you detect an issue that requires action, propose a command.
        Respond ONLY with a JSON object in this format:
        {{
            "issue_detected": true/false,
            "reasoning": "Internal AI thought process",
            "rationale": "Description of why this action is needed",
            "proposed_command": "The actual command to run (e.g., RESTART_SERVICE, BLOCK_IP 1.2.3.4)",
            "severity": "LOW/MEDIUM/HIGH"
        }}
        
        Telemetry:
        {data}
        """
        try:
            text = await self._generate(prompt)
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            return json.loads(text)
        except Exception as e:
            return {"issue_detected": False, "error": str(e)}

    async def analyze_result(self, command: str, stdout: str, stderr: str, exit_code: int) -> str:
        prompt = f"""
        Review the execution result of the following command:
        Command: {command}
        Exit Code: {exit_code}
        Stdout: {stdout}
        Stderr: {stderr}
        
        Provide a concise analysis of whether the action was successful and what the current status is.
        """
        try:
            return await self._generate(prompt)
        except Exception as e:
            return f"Error during analysis: {str(e)}"

    async def intent_to_actions(self, user_text: str, agents: List[dict]) -> List[dict]:
        agents_str = json.dumps(agents, indent=2)
        prompt = f"""
        You are the WIGO C2 Intent-to-Action Engine.
        The user has sent a request: "{user_text}"
        
        Available Agents:
        {agents_str}
        
        Task:
        1. Determine which agent(s) should take action.
        2. Propose a list of actions (commands) to achieve the user's intent.
           - For Ubuntu agents: Use standard Linux bash commands (e.g., ls, ps, df, systemctl).
           - For Proxmox agents: Use Proxmox CLI tools (e.g., qm list, pct list, pvesh, pvecm).
           - For MikroTik agents: Use RouterOS CLI syntax (e.g., "/interface print", "/ip address print").
        3. For each action, provide a reasoning and a rationale.
        
        Respond ONLY with a JSON list of objects in this format:
        [
          {
            "agent_hostname": "hostname",
            "command": "full command string to be executed (including verb and args)",
            "reasoning": "Internal AI thought process",
            "rationale": "Human-readable explanation for the user"
          }
        ]
        
        If no action is needed, return an empty list [].
        """
        try:
            text = await self._generate(prompt)
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            return json.loads(text)
        except Exception:
            return []

    def is_available(self) -> bool:
        # A simple check could be added here, but for now we assume true if configured
        return True

    async def decide_follow_up(self, command: str, result: str, iteration: int) -> Optional[dict]:
        if iteration >= 3:
            return None
            
        prompt = f"""
        You are analyzing the result of a command.
        Command: {command}
        Result: {result}
        Current Iteration: {iteration}/3
        
        Decide if a follow-up action is needed. 
        If yes, respond ONLY with a JSON object:
        {{
            "verb": "command_verb",
            "parameters": "full command",
            "reasoning": "Why this follow-up is needed",
            "rationale": "Human-readable explanation"
        }}
        
        If no follow-up is needed, respond with "NONE".
        """
        try:
            text = await self._generate(prompt)
            if text.strip() == "NONE":
                return None
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            return json.loads(text)
        except Exception:
            return None

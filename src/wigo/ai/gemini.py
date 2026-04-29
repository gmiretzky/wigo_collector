import os
import json
from google import genai
from src.wigo.ai.brain import AIProvider
from typing import Optional

from src.wigo.database import get_setting

class GeminiProvider(AIProvider):
    def __init__(self):
        self.api_key = get_setting("ai_token") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("[!] WARNING: GEMINI_API_KEY is not set. AI features will fail.")
        else:
            self.client = genai.Client(api_key=self.api_key)
        
        self.model_name = get_setting("ai_model", "gemini-1.5-pro-latest")

    async def _generate(self, prompt: str) -> str:
        if not self.api_key:
            print("[!] AI ERROR: Attempted to generate content without GEMINI_API_KEY")
            raise Exception("GEMINI_API_KEY missing")
        
        print(f"\n--- AI PROMPT ---\n{prompt}\n-----------------")
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            print(f"\n--- AI RESPONSE ---\n{response.text}\n-------------------")
            return response.text.strip()
        except Exception as e:
            err_msg = str(e)
            print(f"[!] AI ERROR: {err_msg}")
            
            # Check for 503 Unavailable
            if "503" in err_msg or "UNAVAILABLE" in err_msg:
                fallback_model = get_setting("ai_fallback_model", "")
                if fallback_model and fallback_model != self.model_name:
                    print(f"[*] AI Fallback: Primary model {self.model_name} unavailable. Retrying with {fallback_model}...")
                    try:
                        import time
                        time.sleep(2) # Brief backoff
                        response = self.client.models.generate_content(
                            model=fallback_model,
                            contents=prompt
                        )
                        print(f"\n--- AI RESPONSE (Fallback) ---\n{response.text}\n-------------------")
                        return "[⚠️ Fallback used due to high demand] " + response.text.strip()
                    except Exception as fallback_err:
                        print(f"[!] AI Fallback ERROR: {str(fallback_err)}")
                        raise fallback_err
            
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

    async def intent_to_actions(self, user_text: str, agents: list[dict]) -> list[dict]:
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
          {{
            "agent_hostname": "hostname",
            "command": "full command string to be executed (including verb and args)",
            "reasoning": "Internal AI thought process",
            "rationale": "Human-readable explanation for the user"
          }}
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
        return self.api_key is not None and len(self.api_key) > 0

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
            if text == "NONE":
                return None
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            return json.loads(text)
        except Exception:
            return None

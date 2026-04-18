import os
import json
import google.generativeai as genai
from src.wigo.ai.brain import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def analyze(self, data: str) -> dict:
        prompt = f"""
        Analyze the following telemetry data from a network agent. 
        If you detect an issue that requires action, propose a command.
        Respond ONLY with a JSON object in this format:
        {{
            "issue_detected": true/false,
            "rationale": "Description of why this action is needed",
            "proposed_command": "The actual command to run (e.g., RESTART_SERVICE, BLOCK_IP 1.2.3.4)",
            "severity": "LOW/MEDIUM/HIGH"
        }}
        
        Telemetry:
        {data}
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Clean up response text in case it has markdown code blocks
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            
            return json.loads(text)
        except Exception as e:
            return {
                "issue_detected": False,
                "error": str(e)
            }

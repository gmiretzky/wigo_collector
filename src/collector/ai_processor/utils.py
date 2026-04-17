import requests
import json
import google.generativeai as genai
from src.collector.settings import load_config

def call_ai(prompt: str):
    config = load_config()
    ai_config = config.get("ai", {})
    provider = ai_config.get("provider", "gemini")

    if provider == "gemini":
        try:
            gemini_config = ai_config.get("gemini", {})
            genai.configure(api_key=gemini_config.get("api_key"))
            model = genai.GenerativeModel(gemini_config.get("model", "gemini-1.5-flash"))
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    elif provider == "ollama":
        try:
            ollama_config = ai_config.get("ollama", {})
            url = f"{ollama_config.get('base_url')}/api/generate"
            payload = {
                "model": ollama_config.get("model", "llama3"),
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(url, json=payload, timeout=60)
            return response.json().get("response")
        except Exception as e:
            return f"Ollama Error: {str(e)}"

    return "Unknown AI Provider"

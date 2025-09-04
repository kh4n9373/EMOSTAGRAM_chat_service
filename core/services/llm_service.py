from __future__ import annotations

from typing import Any, Dict, List, Optional

import google.generativeai as genai
from langsmith import traceable
from config import settings


class LLMService:

    def __init__(self, *, model: str = "gemini-2.0-flash", temperature: float = 0.2) -> None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured in settings")
        genai.configure(api_key=settings.google_api_key)
        self.model = model
        self.temperature = temperature

    @traceable(name="LLMService.chat")
    def chat(self, *, system_prompt: Optional[str], user_prompt: str, response_format: Optional[Dict[str, Any]] = None) -> str:
        generation_config: Dict[str, Any] = {"temperature": self.temperature}
        # Map OpenAI-like response_format to Gemini JSON responses if requested
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt or "",
            generation_config=generation_config,
        )
        resp = model.generate_content(user_prompt)
        return getattr(resp, "text", "") or ""



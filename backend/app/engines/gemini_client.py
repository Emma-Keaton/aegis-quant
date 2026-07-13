"""Gemini Client with 3-key rotation for free tier"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GeminiResponse:
    text: str
    parsed_json: Optional[Dict] = None
    usage: Optional[Dict] = None
    key_index: int = 0


class GeminiClient:
    """Gemini client with automatic key rotation on quota errors"""
    
    def __init__(self):
        self.settings = get_settings()
        self.keys = self.settings.gemini_keys
        self.current_key_index = 0
        self.key_usage = {i: 0 for i in range(len(self.keys))}
        self.key_errors = {i: 0 for i in range(len(self.keys))}
        self._models = {}
        
        if not self.keys:
            logger.warning("No Gemini API keys configured")
    
    def _get_model(self, key_index: int):
        """Get or create model instance for key"""
        if key_index not in self._models:
            genai.configure(api_key=self.keys[key_index])
            self._models[key_index] = genai.GenerativeModel(
                model_name=self.settings.GEMINI_MODEL,
                generation_config=GenerationConfig(
                    temperature=0.3,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=8192,
                    response_mime_type="application/json"
                )
            )
        return self._models[key_index]
    
    def _rotate_key(self):
        """Rotate to next available key"""
        old_index = self.current_key_index
        for _ in range(len(self.keys)):
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            if self.key_errors[self.current_key_index] < 3:  # Max 3 errors per key
                break
        logger.info(f"Gemini key rotated: {old_index} -> {self.current_key_index}")
    
    def _is_quota_error(self, error: Exception) -> bool:
        """Check if error is quota/rate limit related"""
        error_str = str(error).lower()
        return any(kw in error_str for kw in [
            "quota", "rate limit", "429", "resource exhausted",
            "too many requests", "limit exceeded"
        ])
    
    async def generate(
        self,
        prompt: str,
        schema: Optional[Dict] = None,
        max_retries: int = 3
    ) -> GeminiResponse:
        """Generate response with automatic key rotation on quota errors"""
        
        if not self.keys:
            raise ValueError("No Gemini API keys available")
        
        last_error = None
        
        for attempt in range(max_retries * len(self.keys)):
            key_index = self.current_key_index
            model = self._get_model(key_index)
            
            try:
                # Configure schema if provided
                gen_config = None
                if schema:
                    gen_config = GenerationConfig(
                        temperature=0.3,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=8192,
                        response_mime_type="application/json",
                        response_schema=schema
                    )
                else:
                    gen_config = GenerationConfig(
                        temperature=0.3,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=8192
                    )
                
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=gen_config
                )
                
                # Track usage
                self.key_usage[key_index] += 1
                
                # Parse JSON if schema provided
                parsed = None
                if schema and response.text:
                    try:
                        parsed = json.loads(response.text)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse JSON response")
                
                return GeminiResponse(
                    text=response.text or "",
                    parsed_json=parsed,
                    usage={
                        "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                        "candidates_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0)
                    } if hasattr(response, 'usage_metadata') else None,
                    key_index=key_index
                )
                
            except Exception as e:
                last_error = e
                self.key_errors[key_index] += 1
                
                if self._is_quota_error(e):
                    logger.warning(f"Gemini key {key_index} quota exceeded, rotating...")
                    self._rotate_key()
                    continue
                else:
                    # Non-quota error, re-raise
                    raise
        
        raise RuntimeError(f"All Gemini keys exhausted. Last error: {last_error}")
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict,
        max_retries: int = 3
    ) -> Dict:
        """Generate and parse structured JSON output"""
        response = await self.generate(prompt, schema=schema, max_retries=max_retries)
        if response.parsed_json:
            return response.parsed_json
        raise ValueError("Failed to get valid JSON response")
    
    def get_usage_stats(self) -> Dict:
        """Get usage statistics per key"""
        return {
            "keys": len(self.keys),
            "current_index": self.current_key_index,
            "usage": self.key_usage,
            "errors": self.key_errors
        }
    
    def reset_key_errors(self, key_index: Optional[int] = None):
        """Reset error count for key(s)"""
        if key_index is not None:
            self.key_errors[key_index] = 0
        else:
            self.key_errors = {i: 0 for i in range(len(self.keys))}


# Global instance
gemini_client = GeminiClient()
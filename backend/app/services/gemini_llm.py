import os
import json
import asyncio
import warnings
warnings.simplefilter("ignore", category=FutureWarning)
from typing import Dict
from itertools import cycle

try:
    import google.genai as genai
except ImportError:
    import google.generativeai as genai

# ---------------------------------------------------------------------------
# Rotate through the three Gemini API keys (GEMINI_API_KEY_1/2/3) so that
# high‑frequency calls can spread across them and avoid the per‑minute
# rate limit of the free tier. The keys are read once at import time.
# ---------------------------------------------------------------------------

def _build_key_cycle():
    keys = []
    for i in (1, 2, 3):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k:
            keys.append(k)
    return cycle(keys) if keys else None

_key_cycle = _build_key_cycle()


class GeminiLLM:
    """Thin wrapper around Google Gemini (AI Studio) model.
    Uses a rotating key from the GEMINI_API_KEY_1‑3 environment variables.
    """

    def __init__(self):
        if _key_cycle is None:
            raise RuntimeError("No Gemini API keys configured in environment")
        api_key = next(_key_cycle)
        genai.configure(api_key=api_key)
        # Use the fast flash model – adjust if you need higher quality.
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def generate(self, prompt: str) -> Dict:
        """Send *prompt* to Gemini and return the parsed JSON payload.
        The model is instructed to output a single JSON object that
        represents the execution order (symbol, side, size, price, ...).
        """
        # Gemini client is sync; run in thread‑pool to keep FastAPI async.
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self._run_sync, prompt)
        # Strip any surrounding text and parse JSON.
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            payload = json.loads(response[start:end])
        except Exception as exc:
            raise RuntimeError(f"Gemini output could not be parsed as JSON: {exc}\nRaw: {response}")
        return payload

    def _run_sync(self, prompt: str) -> str:
        # The generate_content method returns a GenerationResponse.
        # We ask the model to respond in plain text (no markdown).
        result = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "text/plain",
                "max_output_tokens": 1024,
            },
        )
        return result.text

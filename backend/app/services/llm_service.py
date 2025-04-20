import asyncio
import aiohttp
from app.core.config import get_settings
from app.utils.logger import app_logger
from typing import Optional, List, Dict

class LLMService:
    """Service for interacting with the MWS LLM API to support contact center agents with text analysis and generation."""
    def __init__(self):
        self.settings = get_settings()
        self.max_retries = self.settings.MAX_RETRIES
        self.timeout = aiohttp.ClientTimeout(total=self.settings.REQUEST_TIMEOUT)

    async def call_llm(self, prompt: str, model_name: str, temperature: float = 0.7) -> Optional[str]:
        """
        Call the MWS GPT API for chat completion with the given prompt for agent tasks like intent detection.
        Retries on transient errors (e.g., 429 Rate Limit, 5xx Server Errors) but not on unrecoverable errors (other 4xx).
        Returns the generated text or None if the call fails after retries.
        """
        retries = 0
        while retries < self.max_retries:
            try:
                app_logger.debug(f"Calling MWS model {model_name} with prompt: {prompt[:50]}... (Attempt {retries+1}/{self.max_retries})")
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    response = await session.post(
                        url=self.settings.MWS_CHAT_COMPLETION_URL,
                        headers={
                            "Authorization": f"Bearer {self.settings.MWS_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": "Ты помощник, поддерживающий русский язык."},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": temperature,
                        }
                    )
                    if response.status == 200:
                        data = await response.json()
                        app_logger.debug(f"Received successful response from MWS model {model_name}")
                        return data["choices"][0]["message"]["content"]
                    elif response.status == 429 or response.status >= 500:
                        error_text = await response.text()
                        truncated_text = error_text[:500] + "..." if len(error_text) > 500 else error_text
                        app_logger.warning(f"MWS API transient error {response.status} (retry {retries+1}/{self.max_retries}): {truncated_text}")
                        retries += 1
                        await asyncio.sleep(8 * (2 ** retries))  # Increased base backoff from 5 to 8 seconds for rate limits
                    else:
                        error_text = await response.text()
                        truncated_text = error_text[:500] + "..." if len(error_text) > 500 else error_text
                        app_logger.error(f"MWS API unrecoverable error {response.status}: {truncated_text}")
                        return None  # No retry on other 4xx errors (e.g., 400, 403)
            except asyncio.TimeoutError as te:
                app_logger.error(f"MWS API call timeout for model {model_name} after {self.settings.REQUEST_TIMEOUT}s (retry {retries+1}/{self.max_retries})")
                retries += 1
                await asyncio.sleep(8 * (2 ** retries))  # Increased backoff for timeouts
            except Exception as e:
                app_logger.error(f"MWS API call error for model {model_name}: {str(e)} (retry {retries+1}/{self.max_retries})")
                retries += 1
                await asyncio.sleep(8 * (2 ** retries))  # Increased backoff for general errors
        app_logger.error(f"Max retries reached for MWS API call with model {model_name}")
        return None

llm_service = LLMService()

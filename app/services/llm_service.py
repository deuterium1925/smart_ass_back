import asyncio
import aiohttp
from app.core.config import get_settings
from app.utils.logger import app_logger
from typing import Optional, List, Dict

class LLMService:
    def __init__(self):
        self.settings = get_settings()
        self.max_retries = self.settings.MAX_RETRIES
        self.timeout = aiohttp.ClientTimeout(total=self.settings.REQUEST_TIMEOUT)

    async def call_llm(self, prompt: str, model_name: str, temperature: float = 0.7) -> Optional[str]:
        """
        Call the MWS GPT API for chat completion with the given prompt.
        """
        retries = 0
        while retries < self.max_retries:
            try:
                app_logger.debug(f"Calling MWS model {model_name} with prompt: {prompt[:50]}...")
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
                        return data["choices"][0]["message"]["content"]
                    else:
                        app_logger.warning(f"MWS API call failed with status {response.status}")
                        retries += 1
                        await asyncio.sleep(2 ** retries)  # Exponential backoff
            except Exception as e:
                app_logger.error(f"MWS API call error: {e}")
                retries += 1
                await asyncio.sleep(2 ** retries)
        app_logger.error(f"Max retries reached for MWS API call with model {model_name}")
        return None

llm_service = LLMService()

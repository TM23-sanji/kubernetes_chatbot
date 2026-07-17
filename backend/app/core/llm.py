from openai import AsyncOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL

from app.config import settings


class LLMManager:
    def __init__(self):
        self.client = None

    async def initialize(self):
        self.client = AsyncOpenAI(
            base_url=PORTKEY_GATEWAY_URL,
            api_key=settings.portkey_api_key,
        )

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        response = await self.client.chat.completions.create(
            model="@kubernetes-chatbot/llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        return response.choices[0].message.content

    async def close(self):
        self.client = None


llm_manager = LLMManager()

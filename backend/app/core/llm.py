from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL

from app.config import settings


class LLMManager:
    def __init__(self):
        self.client = None
        self.guard_client = None
        self.chat_model = None

    async def initialize(self):
        self.client = AsyncOpenAI(
            base_url=PORTKEY_GATEWAY_URL,
            api_key=settings.portkey_api_key,
        )
        self.chat_model = ChatOpenAI(
            model="@kubernetes-chatbot/llama-3.3-70b-versatile",
            base_url=PORTKEY_GATEWAY_URL,
            api_key=settings.portkey_api_key,
            streaming=True,
            temperature=0.1,
            max_tokens=2048,
        )
        if settings.groq_api_key:
            self.guard_client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
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

    async def generate_guard(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        client = self.guard_client or self.client
        model = "llama-3.1-8b-instant" if self.guard_client else "@kubernetes-chatbot/llama-3.3-70b-versatile"
        response = await client.chat.completions.create(
            model=model,
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
        self.guard_client = None


llm_manager = LLMManager()

import asyncio
import re

from openai import AsyncOpenAI, RateLimitError
from langchain_openai import ChatOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL

from app.config import settings


_MAX_RETRIES = 10


def _parse_retry_after(error: RateLimitError) -> float | None:
    msg = str(error)
    m = re.search(r"try again in (\d+)m(\d+\.?\d*)s", msg)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r"try again in (\d+\.?\d*)s", msg)
    if m:
        return float(m.group(1))
    return None


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
            max_retries=10,
            request_timeout=180,
        )
        if settings.groq_api_key:
            self.guard_client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key,
            )

    async def _call_with_retry(self, model: str, messages: list, max_tokens: int, temperature: float):
        last_err = None
        for attempt in range(_MAX_RETRIES):
            try:
                return await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except RateLimitError as e:
                last_err = e
                wait = _parse_retry_after(e)
                if wait is None:
                    wait = 30 + (attempt * 10)
                print(f"  Rate limited, retrying in {wait:.0f}s (attempt {attempt+1}/{_MAX_RETRIES})")
                await asyncio.sleep(wait)
        raise last_err

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        response = await self._call_with_retry(
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
        last_err = None
        for attempt in range(_MAX_RETRIES):
            try:
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
            except RateLimitError as e:
                last_err = e
                wait = _parse_retry_after(e)
                if wait is None:
                    wait = 30 + (attempt * 10)
                print(f"  Rate limited (guard), retrying in {wait:.0f}s (attempt {attempt+1}/{_MAX_RETRIES})")
                await asyncio.sleep(wait)
        raise last_err

    async def close(self):
        self.client = None
        self.guard_client = None


llm_manager = LLMManager()

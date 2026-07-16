from app.core.llm import llm_manager
from app.core.prompts import load_prompt

INTENTS = [
    "architecture",
    "job_management",
    "autoscaling",
    "monitoring",
    "cronjobs",
    "general_k8s",
]


async def route_query(query: str) -> str:
    prompt = load_prompt("router")
    system = prompt["system_prompt"]
    result = await llm_manager.generate(system, query, max_tokens=50)
    result = result.strip().lower()
    for intent in INTENTS:
        if intent in result:
            return intent
    return "general_k8s"

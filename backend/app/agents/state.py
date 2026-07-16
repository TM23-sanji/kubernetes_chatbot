from typing import TypedDict, Annotated, Sequence
import operator


class ThinkingStep(TypedDict):
    stage: str
    detail: str
    duration_ms: float


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    user_query: str
    intent: str
    retrieved_chunks: list
    reranked_chunks: list
    generated_answer: str
    sources: list
    thinking_steps: Annotated[list, operator.add]
    guardrail_input_passed: bool
    guardrail_output_passed: bool

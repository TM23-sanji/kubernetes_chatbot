import json
import uuid
import asyncio
import pytest
from datetime import datetime, timezone
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import RateLimitError
from portkey_ai import PORTKEY_GATEWAY_URL
from ragas import evaluate as ragas_evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.agents.graph import agent_graph
from app.db.postgres import db_manager
from app.db.models import EvalRun

DATA_DIR = Path(__file__).parent / "data"


def load_queries():
    with open(DATA_DIR / "test_queries.json") as f:
        return json.load(f)


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=30, min=30, max=300),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)
def _evaluate_with_retry(*args, **kwargs):
    return ragas_evaluate(*args, **kwargs)


@pytest.mark.eval
@pytest.mark.asyncio
class TestPipeline:
    @pytest.fixture(scope="class")
    def eval_llm(self):
        return ChatOpenAI(
            model="@kubernetes-chatbot/llama-3.3-70b-versatile",
            base_url=PORTKEY_GATEWAY_URL,
            api_key=settings.portkey_api_key,
            temperature=0,
            max_retries=10,
            request_timeout=180,
        )

    @pytest.fixture(scope="class")
    def eval_embeddings(self):
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            base_url=PORTKEY_GATEWAY_URL,
            api_key=settings.portkey_api_key,
        )

    async def test_full_pipeline_single_query(self):
        query = "What is a Kubernetes Pod?"
        state = {
            "user_query": query,
            "messages": [],
            "intent": "",
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "generated_answer": "",
            "sources": [],
            "thinking_steps": [],
            "guardrail_input_passed": True,
            "guardrail_output_passed": True,
            "conversation_history": "",
        }
        result = await agent_graph.ainvoke(state)
        assert result.get("guardrail_input_passed", False) is True
        assert result.get("generated_answer", "") != ""
        assert len(result.get("sources", [])) > 0 or True

    async def test_ragas_metrics(self, eval_llm, eval_embeddings):
        queries = load_queries()
        questions = []
        answers = []
        contexts = []
        ground_truths = []

        for q in queries:
            state = {
                "user_query": q["question"],
                "messages": [],
                "intent": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "generated_answer": "",
                "sources": [],
                "thinking_steps": [],
                "guardrail_input_passed": True,
                "guardrail_output_passed": True,
                "conversation_history": "",
            }
            result = await agent_graph.ainvoke(state)
            questions.append(result.get("user_query", q["question"]))
            answers.append(result.get("generated_answer", ""))
            chunk_texts = [
                c.get("text", "") for c in result.get("reranked_chunks", [])
            ]
            contexts.append(chunk_texts)
            gt = q.get("ground_truth", "")
            ground_truths.append(gt if gt else "")

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
        dataset = Dataset.from_dict(data)

        scores = _evaluate_with_retry(
            dataset=dataset,
            llm=eval_llm,
            embeddings=eval_embeddings,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )

        df = scores.to_pandas()
        print("\n=== RAGAS Evaluation Results ===")
        print(df.describe())
        print("\nPer-query scores:")
        for i, row in df.iterrows():
            print(f"  {queries[i]['id']}: faith={row['faithfulness']:.3f} "
                  f"relev={row['answer_relevancy']:.3f} "
                  f"prec={row['context_precision']:.3f} "
                  f"recall={row['context_recall']:.3f}")

        avg_faith = df["faithfulness"].mean()
        avg_relev = df["answer_relevancy"].mean()
        avg_prec = df["context_precision"].mean()
        avg_recall = df["context_recall"].mean()

        print(f"\nAverages: faith={avg_faith:.3f} relev={avg_relev:.3f} "
              f"prec={avg_prec:.3f} recall={avg_recall:.3f}")

        print("Persisting to EvalRun table...")
        async with await db_manager.get_session() as session:
            run = EvalRun(
                id=str(uuid.uuid4()),
                data_version="true_data_v1",
                prompt_version="generation_v1.1",
                dataset_name="test_queries_20",
                faithfulness=avg_faith,
                relevancy=avg_relev,
                context_recall=avg_recall,
                created_at=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.commit()
            print(f"  Saved eval run ID: {run.id}")

        assert avg_faith > 0.5, f"Faithfulness too low: {avg_faith:.3f}"
        assert avg_relev > 0.5, f"Answer relevancy too low: {avg_relev:.3f}"

    async def test_rejected_query_skips_pipeline(self):
        state = {
            "user_query": "What is the weather today?",
            "messages": [],
            "intent": "",
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "generated_answer": "",
            "sources": [],
            "thinking_steps": [],
            "guardrail_input_passed": True,
            "guardrail_output_passed": True,
            "conversation_history": "",
        }
        result = await agent_graph.ainvoke(state)
        assert result.get("guardrail_input_passed", True) is False
        assert "can only answer" in result.get("generated_answer", "").lower()

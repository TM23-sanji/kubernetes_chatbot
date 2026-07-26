"""
Standalone evaluation runner.

Runs the full RAGAS evaluation on the test query dataset,
prints results, and persists them to the EvalRun DB table.

Usage:
    .venv/bin/python -m tests.run_eval
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_openai import ChatOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL
from ragas import evaluate as ragas_evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.config import settings
from app.db.postgres import db_manager
from app.db import repository as repo
from app.core.llm import llm_manager
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.core.reranker import reranker
from app.agents.graph import agent_graph

DATA_DIR = Path(__file__).parent / "data"


def load_queries() -> list[dict]:
    with open(DATA_DIR / "test_queries.json") as f:
        return json.load(f)


async def run_evaluation():
    print("Initializing services...")
    await db_manager.initialize()
    await qdrant_manager.initialize()
    await embedding_manager.initialize()
    await llm_manager.initialize()
    await reranker.initialize()

    queries = load_queries()
    print(f"Loaded {len(queries)} test queries")

    eval_llm = ChatOpenAI(
        model="@kubernetes-chatbot/llama-3.3-70b-versatile",
        base_url=PORTKEY_GATEWAY_URL,
        api_key=settings.portkey_api_key,
        temperature=0,
    )

    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for q in queries:
        qid = q["id"]
        print(f"  Processing {qid}: {q['question'][:60]}...")

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
        chunk_texts = [c.get("text", "") for c in result.get("reranked_chunks", [])]
        contexts.append(chunk_texts)
        gt = q.get("ground_truth", "")
        ground_truths.append(gt if gt else "")

    print("\nComputing RAGAS metrics...")
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }
    dataset = Dataset.from_dict(data)

    scores = ragas_evaluate(
        dataset=dataset,
        llm=eval_llm,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    df = scores.to_pandas()
    print("\n=== RAGAS Evaluation Results ===")

    avg_faith = float(df["faithfulness"].mean())
    avg_relev = float(df["answer_relevancy"].mean())
    avg_prec = float(df["context_precision"].mean())
    avg_recall = float(df["context_recall"].mean())

    print(f"{'Metric':<25} {'Avg':<8} {'Min':<8} {'Max':<8}")
    print("-" * 50)
    print(f"{'faithfulness':<25} {avg_faith:<8.3f} {float(df['faithfulness'].min()):<8.3f} {float(df['faithfulness'].max()):<8.3f}")
    print(f"{'answer_relevancy':<25} {avg_relev:<8.3f} {float(df['answer_relevancy'].min()):<8.3f} {float(df['answer_relevancy'].max()):<8.3f}")
    print(f"{'context_precision':<25} {avg_prec:<8.3f} {float(df['context_precision'].min()):<8.3f} {float(df['context_precision'].max()):<8.3f}")
    print(f"{'context_recall':<25} {avg_recall:<8.3f} {float(df['context_recall'].min()):<8.3f} {float(df['context_recall'].max()):<8.3f}")

    print("\nPer-query breakdown:")
    print(f"{'ID':<12} {'Faith':<8} {'Relev':<8} {'Prec':<8} {'Recall':<8}")
    print("-" * 45)
    for i, row in df.iterrows():
        print(f"{queries[i]['id']:<12} {float(row['faithfulness']):<8.3f} "
              f"{float(row['answer_relevancy']):<8.3f} "
              f"{float(row['context_precision']):<8.3f} "
              f"{float(row['context_recall']):<8.3f}")

    print(f"\nPersisting to EvalRun table...")
    async with await db_manager.get_session() as session:
        eval_id = str(uuid.uuid4())
        from app.db.models import EvalRun
        run = EvalRun(
            id=eval_id,
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
        print(f"  Saved eval run ID: {eval_id}")

    print("\nDone!")
    return {
        "faithfulness": avg_faith,
        "answer_relevancy": avg_relev,
        "context_precision": avg_prec,
        "context_recall": avg_recall,
    }


if __name__ == "__main__":
    results = asyncio.run(run_evaluation())

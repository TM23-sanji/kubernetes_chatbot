from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
)


def chunk_text(text: str, metadata: dict | None = None) -> list[dict]:
    chunks = splitter.split_text(text)
    results = []
    for i, chunk in enumerate(chunks):
        results.append({
            "text": chunk,
            "metadata": {
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {}),
            },
        })
    return results

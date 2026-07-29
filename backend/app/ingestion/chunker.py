_splitter = None


def _get_splitter():
    global _splitter
    if _splitter is None:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        _splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        )
    return _splitter


def chunk_text(text: str, metadata: dict | None = None) -> list[dict]:
    splitter = _get_splitter()
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

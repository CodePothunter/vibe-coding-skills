# TinySearch API Reference

## Interfaces (`tinysearch.base`)

### TextChunk
```python
TextChunk(text: str, metadata: Optional[Dict[str, Any]] = None)
```

### RecordAdapter (ABC)
```python
to_chunk(record_id: str, record: Dict[str, Any]) -> TextChunk
```

### DataAdapter (ABC)
```python
extract(filepath: Union[str, Path]) -> List[str]
```

### Embedder (ABC)
```python
embed(texts: List[str]) -> List[List[float]]
```

### VectorIndexer (ABC)
```python
build(vectors: List[List[float]], texts: List[TextChunk]) -> None
search(query_vector: List[float], top_k: int = 5) -> List[Dict]
add(vectors: List[List[float]], texts: List[TextChunk]) -> None  # incremental
save(path) -> None
load(path) -> None
```

### Retriever (ABC)
```python
build(chunks: List[TextChunk]) -> None
retrieve(query: str, top_k: int = 5, **kwargs) -> List[Dict]
    # kwargs: candidate_ids: Optional[Set[int]]
    # returns: [{text, metadata, score, retrieval_method}]
save(path) -> None
load(path) -> None
```

### FusionStrategy (ABC)
```python
fuse(results_list: List[List[Dict]], **kwargs) -> List[Dict]
    # kwargs: weights: Optional[List[float]]
```

### Reranker (ABC)
```python
rerank(query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]
```

---

## FlowController (`tinysearch.flow.controller`)

```python
FlowController(
    data_adapter: Optional[DataAdapter],
    text_splitter: TextSplitter,
    embedder: Embedder,
    indexer: VectorIndexer,
    query_engine: QueryEngine,
    config: Dict[str, Any],
)
```

| Method | Description |
|--------|-------------|
| `build_from_records(records, adapter, splitter=None) -> List[TextChunk]` | Full build from in-memory records |
| `build_incremental(records, adapter, hash_tracker, splitter=None, delete_rebuild_threshold=None) -> Dict` | Incremental update. Returns `{new, modified, deleted, unchanged, full_rebuild}` |
| `build_index(data_path, **kwargs)` | Build from files |
| `query(query_text, top_k=5, **kwargs)` | Query the index |
| `save_index(path=None)` / `load_index(path=None)` | Persist/restore |
| `start_hot_update(watch_paths, ...)` / `stop_hot_update()` | File monitoring |
| `_build_retriever_indexes(chunks)` | Build BM25 + MetadataIndex for HybridQueryEngine |

---

## HybridQueryEngine (`tinysearch.query.hybrid`)

```python
HybridQueryEngine(
    retrievers: List[Retriever],
    fusion_strategy: FusionStrategy,
    reranker: Optional[Reranker] = None,
    recall_multiplier: int = 2,
    min_scores: Optional[List[float]] = None,   # per-retriever thresholds
    filter_multiplier: int = 3,
    metadata_index=None,                         # MetadataIndex instance
    filter_mode: str = "auto",                   # "pre" | "post" | "auto"
    soft_deleted_ids: Optional[set] = None,
)
```

| Method | Description |
|--------|-------------|
| `retrieve(query, top_k=5, **kwargs)` | Multi-path retrieval. kwargs: `filters`, `weights` |
| `retrieve_with_details(query, top_k=5, **kwargs) -> Dict` | Returns `{results, per_retriever, fused_before_rerank}` |
| `add_soft_deletes(record_ids: set)` | Mark records as soft-deleted |
| `clear_soft_deletes()` | Clear after full rebuild |
| `soft_delete_count: int` | Property |

**Pipeline:** recall (× recall_multiplier) → min_score filter → metadata post-filter → fuse → soft-delete filter → rerank → top_k

---

## MetadataIndex (`tinysearch.indexers.metadata_index`)

```python
MetadataIndex()
```

| Method | Description |
|--------|-------------|
| `build(chunks: List[TextChunk])` | Build inverted index from chunk metadata |
| `add_chunks(chunks, start_id: int)` | Incremental add |
| `lookup(filters: Dict) -> Optional[Set[int]]` | Resolve to candidate chunk IDs. Returns None if callable filter. |
| `classify_filters(filters) -> (indexable, callables)` | Split filter types |
| `save(path)` / `load(path)` | JSON persistence |
| `total_chunks: int` | Property |
| `fields: List[str]` | Property — indexed metadata keys |

**Filter semantics:**
- `str/int/float/bool` → exact match
- `list` → OR (match any)
- `callable` → cannot index, falls back to post-filter
- Multiple keys → AND (intersection)

---

## ContentHashTracker (`tinysearch.indexers.hash_tracker`)

```python
ContentHashTracker(hash_metadata_keys: Optional[List[str]] = None)
```

| Method | Description |
|--------|-------------|
| `compute_hash(text, metadata) -> str` | MD5 of text + metadata |
| `detect_changes(current_records: Dict[str, TextChunk]) -> ChangeSet` | Compare against tracked |
| `update(records: Dict[str, TextChunk])` | Update tracked hashes |
| `remove(record_ids: Set[str])` | Remove from tracking |
| `save(path)` / `load(path)` | JSON persistence |
| `tracked_count: int` | Property |

### ChangeSet
```python
ChangeSet(new: List[str], modified: List[str], deleted: Set[str], unchanged: Set[str])
has_changes: bool  # property
```

---

## Concrete Implementations

### HuggingFaceEmbedder (`tinysearch.embedders.huggingface`)
```python
HuggingFaceEmbedder(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    device=None,          # auto-detect CUDA
    max_length=8192,
    batch_size=8,
    normalize_embeddings=True,
    pooling="last_token",
)
embed(texts: List[str]) -> List[List[float]]
```

### FAISSIndexer (`tinysearch.indexers.faiss_indexer`)
```python
FAISSIndexer(
    index_type="Flat",    # "Flat" | "IVF" | "HNSW"
    metric="cosine",      # "cosine" | "l2" | "ip"
    nlist=100, nprobe=10,
    use_gpu=False,
)
search(query_vector, top_k=5, candidate_ids=None)  # candidate_ids: Optional[Set[int]]
add(vectors, texts)  # incremental add
```

### VectorRetriever (`tinysearch.retrievers.vector_retriever`)
```python
VectorRetriever(embedder: Embedder, indexer: VectorIndexer, query_template=None)
retrieve(query, top_k=5, candidate_ids=None)  # returns retrieval_method="vector"
```

### BM25Retriever (`tinysearch.retrievers.bm25_retriever`)
```python
BM25Retriever(tokenizer: Optional[Callable] = None)  # default: jieba or whitespace
retrieve(query, top_k=5, candidate_ids=None)  # returns retrieval_method="bm25"
```

### SubstringRetriever (`tinysearch.retrievers.substring_retriever`)
```python
SubstringRetriever(is_regex: bool = False)
retrieve(query, top_k=5, candidate_ids=None)  # returns retrieval_method="substring"
```

### CharacterTextSplitter (`tinysearch.splitters.character`)
```python
CharacterTextSplitter(chunk_size=300, chunk_overlap=50, separator="\n\n")
split(texts, metadata=None) -> List[TextChunk]
```

### WeightedFusion (`tinysearch.fusion.weighted`)
```python
WeightedFusion(weights=None, min_score=0.0)
fuse(results_list, weights=None)  # dynamic weight override
```

### build_chunks_from_records (`tinysearch.records`)
```python
build_chunks_from_records(
    records: Dict[str, Dict],
    adapter: RecordAdapter,
    splitter: Optional[TextSplitter] = None,
) -> List[TextChunk]
```

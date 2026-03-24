---
name: tinysearch-guide
description: "TinySearch 集成指南。为项目接入 TinySearch 混合检索引擎提供架构决策、组件选型和实现模式。当需要：(1) 在新项目中接入 TinySearch, (2) 设计混合检索管道 (Vector + BM25 + Reranker + MetadataIndex), (3) 实现增量索引更新, (4) 设计 metadata 预筛选, (5) 迁移已有检索逻辑到 TinySearch, (6) 查询 TinySearch API 用法时触发。关键词：TinySearch, 向量检索, FAISS, BM25, hybrid search, embedding, reranker, metadata filter, 增量索引。"
---

# TinySearch 集成指南

TinySearch 源码：`/home/wxy/projects/TinySearch/`，`pip install -e` 安装。

## 架构

```
FlowController (orchestrator)
├── Data In:  DataAdapter(files) | RecordAdapter(API/DB) → TextChunk(text, metadata)
├── Index:    Embedder → VectorIndexer(FAISS)
├── Query:    TemplateQueryEngine | HybridQueryEngine
│               ├─ VectorRetriever + BM25Retriever + SubstringRetriever
│               ├─ FusionStrategy (pluggable)
│               ├─ Reranker (optional)
│               └─ MetadataIndex (O(1) pre-filter)
└── Change:   ContentHashTracker → ChangeSet(new/modified/deleted/unchanged)
```

## 决策框架

| 数据源 | Adapter | 示例 |
|--------|---------|------|
| 文件 (txt/pdf/csv/md) | `DataAdapter` | 文档库 |
| API / DB / 内存 | `RecordAdapter` | 题库、商品 |

| 检索需求 | QueryEngine |
|----------|-------------|
| 纯语义 | `TemplateQueryEngine` |
| 关键词 + 语义 | `HybridQueryEngine` |
| + metadata 预筛选 | `HybridQueryEngine` + `MetadataIndex` |
| + 精排 | `HybridQueryEngine` + `Reranker` |

| 更新频率 | 方法 |
|----------|------|
| 不频繁 | `build_from_records()` 全量 |
| 频繁增量 | `build_incremental()` + `ContentHashTracker` |
| 实时文件 | `start_hot_update()` |

## 核心模式

### 1. RecordAdapter — API/DB 数据接入

```python
from tinysearch.base import RecordAdapter, TextChunk

class ProductAdapter(RecordAdapter):
    def to_chunk(self, record_id: str, record: dict) -> TextChunk:
        text = f"[品牌]{record['brand']} [品名]{record['name']} [描述]{record['desc']}"
        metadata = {
            "record_id": record_id,        # 必须
            "brand": record["brand"],       # 精确筛选
            "category": record["category"], # 精确筛选
            "tags": record.get("tags", []), # 列表 → MetadataIndex 逐项索引 (OR)
            "price": record.get("price"),   # 数值筛选
        }
        return TextChunk(text=text, metadata=metadata)
```

**metadata 设计原则：**
- 每个筛选维度 → 独立 key（不要混在一个列表里）
- 列表字段 → 自动逐项索引（OR 语义）
- `record_id` 必须包含
- 不放大文本 — 只放结构化筛选字段

### 2. HybridQueryEngine 完整管道

```python
from tinysearch.embedders.huggingface import HuggingFaceEmbedder
from tinysearch.indexers.faiss_indexer import FAISSIndexer
from tinysearch.indexers import MetadataIndex
from tinysearch.retrievers import VectorRetriever, BM25Retriever
from tinysearch.query.hybrid import HybridQueryEngine
from tinysearch.flow.controller import FlowController
from tinysearch.splitters.character import CharacterTextSplitter

embedder = HuggingFaceEmbedder(model_name="Qwen/Qwen3-Embedding-0.6B", device="cuda")
indexer = FAISSIndexer(metric="cosine")

# retrievers 顺序决定 weights 顺序
retrievers = [VectorRetriever(embedder=embedder, indexer=indexer), BM25Retriever()]

engine = HybridQueryEngine(
    retrievers=retrievers,
    fusion_strategy=WeightedFusion(weights=[0.7, 0.3]),  # [vector, bm25]
    reranker=None,                    # 可选
    metadata_index=MetadataIndex(),
    min_scores=[0.35, 5.0],           # per-retriever 最低分
    recall_multiplier=3,
    filter_mode="auto",               # "pre" | "post" | "auto"
)

fc = FlowController(
    data_adapter=None,
    text_splitter=CharacterTextSplitter(chunk_size=10000, chunk_overlap=0),
    embedder=embedder, indexer=indexer, query_engine=engine,
    config={"flow": {"use_cache": False}},
)

# 一键构建 FAISS + BM25 + MetadataIndex
chunks = fc.build_from_records(records, adapter)

# 检索（filters 传给 MetadataIndex 预筛选）
results = engine.retrieve("蓝牙耳机", top_k=20,
    filters={"brand": ["Sony", "Bose"], "category": "耳机"},
    weights=[0.6, 0.4],  # 动态覆盖默认权重
)
```

### 3. 增量索引 + 变更检测

```python
from tinysearch.indexers import ContentHashTracker

tracker = ContentHashTracker()
# 首次
chunks = fc.build_from_records(all_records, adapter)
chunk_map = {rid: adapter.to_chunk(rid, r) for rid, r in all_records.items()}
tracker.update(chunk_map)
tracker.save("hashes.json")

# 增量
tracker.load("hashes.json")
stats = fc.build_incremental(current_records, adapter, tracker,
    delete_rebuild_threshold=100)
# stats: {new: 5, modified: 2, deleted: 1, unchanged: 992, full_rebuild: False}
tracker.save("hashes.json")
```

**容错：** `tracker.load()` 失败时创建新 `ContentHashTracker()`，退化为全量重建。

### 4. MetadataIndex 筛选

```python
# 精确: {"brand": "Sony"}
# OR:   {"brand": ["Sony", "Bose"]}
# AND:  {"brand": "Sony", "category": "耳机"}  (多 key 交叉)

# 层级展开（年级/地区等）
hierarchy = {"六年级": ["六年级", "六年级上", "六年级下"]}
filters = {"grade": hierarchy.get(user_grade, [user_grade])}
```

### 5. 自定义 FusionStrategy

```python
from tinysearch.base import FusionStrategy

class MyFusion(FusionStrategy):
    def __init__(self, default_weights=None):
        self.default_weights = default_weights

    def fuse(self, results_list, **kwargs):
        weights = kwargs.get("weights") or self.default_weights
        # results_list[i] = [{text, metadata, score, retrieval_method}, ...]
        # 实现你的融合逻辑（Min-Max 归一化、RRF 等）
        fused = {}
        for i, results in enumerate(results_list):
            for r in results:
                rid = r["metadata"].get("record_id", "")
                if rid not in fused:
                    fused[rid] = {**r, "fusion_score": 0}
                fused[rid]["fusion_score"] += r["score"] * weights[i]
        return sorted(fused.values(), key=lambda x: x["fusion_score"], reverse=True)
```

### 6. 自定义 Reranker

```python
from tinysearch.base import Reranker

class MyReranker(Reranker):
    def __init__(self, model=None):
        self._model = model  # 外部传入已加载模型

    def rerank(self, query, candidates, top_k=5):
        if self._model is None:
            return candidates[:top_k]  # 优雅降级
        pairs = [[query, c.get("text", "")] for c in candidates]
        scores = self._model.compute_score(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_k]
```

## 异步服务集成

**Singleton：** FlowController 模型加载耗时 5-10s，必须 singleton。

**异步兼容：** `engine.retrieve()` 是同步的，用 `asyncio.to_thread()` 包装。

**Lazy 初始化：** 非 rebuild 启动时 FC 未创建。首次搜索时加载已有索引：
```python
if engine is None and index_exists():
    fc = builder.get_fc()
    fc.indexer.load(str(index_path))
    chunks = build_chunks_from_records(cache, adapter)
    fc._build_retriever_indexes(chunks)
```

## 陷阱

1. **metadata key 混用** — grade/series/unit 不要塞进一个 tags 列表，MetadataIndex 无法区分维度
2. **record_id 缺失** — to_chunk() 必须包含 record_id，否则软删除和增量失败
3. **FC 未初始化** — 非 rebuild 启动路径不创建 FC，需要 lazy init
4. **BM25 总是全量重建** — build_incremental() 对 BM25 总是全量（不支持增量）
5. **Reranker 同步接口** — HybridQueryEngine 要求 sync reranker，异步模型需外部初始化后传入

## API 参考

完整 API 签名见 [references/api-reference.md](references/api-reference.md)。

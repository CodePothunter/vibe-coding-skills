---
name: tinysearch-guide
description: "TinySearch 集成指南。为项目接入 TinySearch 混合检索引擎提供架构决策、组件选型和实现模式。当需要：(1) 在新项目中接入 TinySearch, (2) 设计混合检索管道 (Vector + BM25 + Reranker + MetadataIndex), (3) 实现增量索引更新, (4) 设计 metadata 预筛选, (5) 迁移已有检索逻辑到 TinySearch, (6) 查询 TinySearch API 用法, (7) 实现 Contextual Retrieval 上下文增强检索, (8) 优化 chunking 策略时触发。关键词：TinySearch, 向量检索, FAISS, BM25, hybrid search, embedding, reranker, metadata filter, 增量索引, contextual retrieval, 上下文检索, chunking。"
---

# TinySearch 集成指南

TinySearch 源码：`/home/wxy/projects/TinySearch/`，`pip install -e` 安装。

## 架构

```
FlowController (orchestrator)
├── Data In:     DataAdapter(files) | RecordAdapter(API/DB) → TextChunk(text, metadata)
├── Contextualize (optional):  LLM 为每个 chunk 生成上下文前缀 → 增强 TextChunk
├── Index:       Embedder → VectorIndexer(FAISS)
├── Query:       TemplateQueryEngine | HybridQueryEngine
│                  ├─ VectorRetriever + BM25Retriever + SubstringRetriever
│                  ├─ FusionStrategy: WeightedFusion | ReciprocalRankFusion
│                  ├─ Reranker: CrossEncoderReranker (optional)
│                  └─ MetadataIndex (O(1) pre-filter)
└── Change:      ContentHashTracker → ChangeSet(new/modified/deleted/unchanged)
```

## 决策框架

| 数据源 | Adapter | 示例 |
|--------|---------|------|
| 文件 (txt/pdf/csv/md) | `DataAdapter` | 文档库 |
| API / DB / 内存 | `RecordAdapter` | 题库、商品 |

| 检索需求 | QueryEngine | 预期收益 |
|----------|-------------|----------|
| 纯语义 | `TemplateQueryEngine` | 基线 |
| 关键词 + 语义 | `HybridQueryEngine` | 语义 + 精确匹配互补 |
| + Contextual Retrieval | Adapter 中 LLM 预处理 | 检索失败率 **-49%** |
| + metadata 预筛选 | `HybridQueryEngine` + `MetadataIndex` | O(1) 缩小候选集 |
| + 精排 | `HybridQueryEngine` + `CrossEncoderReranker` | 检索失败率再 **-67%**（累计） |

| 融合策略 | 适用场景 |
|----------|----------|
| `WeightedFusion` | 需要手动调权重、各 retriever 分数量纲差异大 |
| `ReciprocalRankFusion` | 无参免调、对分数量纲不敏感、推荐默认 |

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

### 2. Contextual Retrieval — 上下文增强检索

> 参考：Anthropic「Contextual Retrieval」— 检索失败率降低 49%，叠加 reranking 后降低 67%。

**问题：** 传统 chunking 丢失上下文。例如 chunk 内容为「该公司营收同比增长 3%」，无法知道是哪家公司、哪个季度。embedding 和 BM25 都会受此影响。

**方案：** 在建索引前，用 LLM 为每个 chunk 生成一段简短的上下文描述（50-100 tokens），拼接到 chunk.text 前面。这样 embedding 和 BM25 索引都包含了文档级上下文。

**在 TinySearch 中的注入点：** `RecordAdapter.to_chunk()` — 在构造 TextChunk 时将上下文前缀拼入 text 字段：

```python
class ContextualAdapter(RecordAdapter):
    def to_chunk(self, record_id: str, record: dict) -> TextChunk:
        original_text = record["content"]
        context_prefix = record.get("_context", "")  # 预先由 LLM 生成

        text = f"{context_prefix}\n\n{original_text}" if context_prefix else original_text
        metadata = {
            "record_id": record_id,
            "original_text": original_text,  # 保留原文用于展示
            # ... 其他筛选字段
        }
        return TextChunk(text=text, metadata=metadata)
```

**要点：**
- 上下文生成是**索引时一次性预处理**，不影响查询时性能
- 用轻量模型（如 haiku 级别）即可，配合 prompt caching 降本（同文档 chunks 共享 cache）
- 领域定制 prompt 效果更好（如附加术语表、指定输出格式）
- 与 `build_incremental()` 结合时，只需为 new/modified 的 chunk 生成上下文
- 展示给用户时用 `metadata["original_text"]`，不要展示 LLM 生成的前缀

### 3. HybridQueryEngine 完整管道

```python
from tinysearch.embedders.huggingface import HuggingFaceEmbedder
from tinysearch.indexers.faiss_indexer import FAISSIndexer
from tinysearch.indexers import MetadataIndex
from tinysearch.retrievers import VectorRetriever, BM25Retriever
from tinysearch.query.hybrid import HybridQueryEngine
from tinysearch.rerankers.cross_encoder import CrossEncoderReranker
from tinysearch.fusion.rrf import ReciprocalRankFusion
from tinysearch.flow.controller import FlowController
from tinysearch.splitters.character import CharacterTextSplitter

embedder = HuggingFaceEmbedder(model_name="Qwen/Qwen3-Embedding-0.6B", device="cuda")
indexer = FAISSIndexer(metric="cosine")

retrievers = [VectorRetriever(embedder=embedder, indexer=indexer), BM25Retriever()]

engine = HybridQueryEngine(
    retrievers=retrievers,
    fusion_strategy=ReciprocalRankFusion(k=60),  # 无参免调，推荐默认
    reranker=CrossEncoderReranker(               # 内置精排
        model_name="BAAI/bge-reranker-v2-m3",
        device="cuda",
    ),
    metadata_index=MetadataIndex(),
    min_scores=[0.35, 5.0],           # per-retriever 最低分
    recall_multiplier=3,              # 检索 top_k * 3 候选，rerank 后取 top_k
    filter_mode="auto",               # "pre" | "post" | "auto"
)

fc = FlowController(
    data_adapter=None,
    text_splitter=CharacterTextSplitter(chunk_size=512, chunk_overlap=50),
    embedder=embedder, indexer=indexer, query_engine=engine,
    config={"flow": {"use_cache": False}},
)

# 一键构建 FAISS + BM25 + MetadataIndex
chunks = fc.build_from_records(records, adapter)

# 检索（filters 传给 MetadataIndex 预筛选）
results = engine.retrieve("蓝牙耳机", top_k=20,
    filters={"brand": ["Sony", "Bose"], "category": "耳机"},
)
```

**关键参数调优：**
- `top_k=20` — Anthropic 实验表明 top-20 优于 top-10/top-5，更多 chunk 提高召回率
- `recall_multiplier=3` — reranker 输入 `top_k * 3 = 60` 候选，精排后取 top-20
- `min_scores` — 过滤低质量候选，减轻 reranker 负担

### 4. 增量索引 + 变更检测

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

### 5. MetadataIndex 筛选

```python
# 精确: {"brand": "Sony"}
# OR:   {"brand": ["Sony", "Bose"]}
# AND:  {"brand": "Sony", "category": "耳机"}  (多 key 交叉)

# 层级展开（年级/地区等）
hierarchy = {"六年级": ["六年级", "六年级上", "六年级下"]}
filters = {"grade": hierarchy.get(user_grade, [user_grade])}
```

### 6. CrossEncoderReranker — 内置精排

```python
from tinysearch.rerankers.cross_encoder import CrossEncoderReranker

reranker = CrossEncoderReranker(
    model_name="BAAI/bge-reranker-v2-m3",
    device="cuda",
    batch_size=64,     # 推理批量
    max_length=512,    # 最大序列长度
    use_fp16=True,     # 半精度推理加速
)

# 直接使用（通常不需要，HybridQueryEngine 自动调用）
reranked = reranker.rerank(query="蓝牙耳机", candidates=candidates, top_k=20)
```

**Reranker 管道设计要点：**
- 初始召回取 **top-150** 候选（`recall_multiplier` 控制），rerank 后取 top-20
- Reranker 增加约 50-100ms 延迟（并行评分所有候选）
- 候选数量越多精度越高，但延迟/成本也越高 — 需根据场景平衡
- Lazy 加载：`CrossEncoderReranker` 首次 `rerank()` 时才加载模型

**自定义 Reranker（如需对接其他模型）：**

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

### 7. FusionStrategy 选择

**RRF（推荐默认）：** 无参数免调，对分数量纲不敏感：

```python
from tinysearch.fusion.rrf import ReciprocalRankFusion

fusion = ReciprocalRankFusion(k=60)  # k=60 来自 RRF 论文，一般不需调整
# score(doc) = sum(1 / (rank_i + k))
```

**WeightedFusion：** 需要手动控制各 retriever 权重时使用：

```python
from tinysearch.fusion.weighted import WeightedFusion

fusion = WeightedFusion(weights=[0.7, 0.3])  # [vector, bm25]
# 支持 retrieve() 时动态覆盖：weights=[0.6, 0.4]
```

**如何选择：**
- 刚接入时用 RRF — 零配置，robust
- 有评估数据后切 WeightedFusion — 用 eval 找最优权重
- 使用 Contextual Retrieval 时，BM25 权重可适当提高（上下文前缀提升了关键词匹配质量）

### 8. SubstringRetriever — 精确匹配

适用于错误码、型号、编号等需要 Ctrl+F 式精确匹配的场景：

```python
from tinysearch.retrievers import SubstringRetriever

# 配合 HybridQueryEngine 三路检索
retrievers = [
    VectorRetriever(embedder=embedder, indexer=indexer),
    BM25Retriever(),
    SubstringRetriever(is_regex=False),  # 精确子串匹配
]

engine = HybridQueryEngine(
    retrievers=retrievers,
    fusion_strategy=ReciprocalRankFusion(k=60),
    min_scores=[0.35, 5.0, 0.1],  # 三路各自的最低分
    # ...
)

# 场景：用户查 "Error code TS-999"
# - VectorRetriever: 语义匹配到"错误码"相关内容
# - BM25Retriever: 关键词匹配到包含 "TS-999" 的文档
# - SubstringRetriever: 精确定位包含 "TS-999" 字符串的 chunk
```

## Chunking 最佳实践

Chunk 质量直接影响检索效果。以下是经验法则：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `chunk_size` | 300-800 tokens | 太小丢上下文，太大稀释语义。Anthropic 实验用 ~800 tokens |
| `chunk_overlap` | 50-100 tokens | 避免边界处信息丢失 |
| `separator` | `"\n\n"` | 段落边界 > 句子边界 > 字符边界 |

**按场景调整：**
- **结构化短记录**（题库、商品）：`chunk_size=10000, chunk_overlap=0` — 每条记录就是一个 chunk，不切分
- **长文档**（论文、合同、手册）：`chunk_size=512, chunk_overlap=50` — 切分后配合 Contextual Retrieval 补充上下文
- **代码库**：按函数/类切分 > 按固定字符数切分

```python
# 短记录 — 不切分
splitter = CharacterTextSplitter(chunk_size=10000, chunk_overlap=0)

# 长文档 — 适度切分 + Contextual Retrieval
splitter = CharacterTextSplitter(chunk_size=512, chunk_overlap=50, separator="\n\n")
```

**小知识库捷径：** 如果知识库 < 200k tokens（~500 页），可以直接全文放进 LLM prompt（配合 prompt caching 降本），无需 RAG。

## 性能优化堆叠

Anthropic 实验证明所有优化技术 **可以叠加**。按效果排序：

```
基线（纯 Embedding）                     检索失败率 5.7%
 + BM25 混合检索                         ↓ 改善
 + Contextual Retrieval（上下文前缀）      ↓ 2.9%  (-49%)
 + Reranking（精排）                       ↓ 1.9%  (-67%)
```

**推荐的 TinySearch 最佳配置：**

```python
# 完整管道：Contextual Embedding + Contextual BM25 + RRF + Reranker
engine = HybridQueryEngine(
    retrievers=[
        VectorRetriever(embedder=embedder, indexer=indexer),
        BM25Retriever(),
    ],
    fusion_strategy=ReciprocalRankFusion(k=60),
    reranker=CrossEncoderReranker(model_name="BAAI/bge-reranker-v2-m3", device="cuda"),
    metadata_index=MetadataIndex(),
    recall_multiplier=3,
    filter_mode="auto",
)

# 数据侧：使用 Contextual Adapter（见模式 2）注入上下文前缀
chunks = fc.build_from_records(records, contextual_adapter)

# 查询侧：top-20 + metadata 预筛选
results = engine.retrieve(query, top_k=20, filters=filters)
```

**渐进式接入路径：**
1. **先跑通基线** — `HybridQueryEngine` + `WeightedFusion`，评估 recall@K
2. **加 Contextual Retrieval** — 改 Adapter，重建索引，对比 recall@K 变化
3. **加 Reranker** — 接入 `CrossEncoderReranker`，调 `recall_multiplier`
4. **精调** — 切 RRF / 调权重 / 调 chunk_size / 定制 context prompt

## 检索质量评估

**始终用评估数据验证效果。** 核心指标：`recall@K` — K 个检索结果中包含正确答案的比例。

```python
def evaluate_recall_at_k(engine, test_cases, k=20):
    """
    test_cases: [{"query": "...", "expected_ids": ["rid1", "rid2"]}]
    返回 recall@K — 越高越好，1.0 = 完美召回
    """
    hits = 0
    total = 0
    for case in test_cases:
        results = engine.retrieve(case["query"], top_k=k)
        retrieved_ids = {r["metadata"].get("record_id") for r in results}
        for eid in case["expected_ids"]:
            total += 1
            if eid in retrieved_ids:
                hits += 1
    return hits / total if total > 0 else 0.0

# 对比 baseline vs contextual
recall_baseline = evaluate_recall_at_k(engine_baseline, test_cases, k=20)
recall_contextual = evaluate_recall_at_k(engine_contextual, test_cases, k=20)
print(f"Baseline recall@20: {recall_baseline:.3f}")
print(f"Contextual recall@20: {recall_contextual:.3f}")
```

**评估检查清单：**
- 对比不同 K 值（5, 10, 20）— Anthropic 发现 K=20 通常最优
- 对比有无 Contextual Retrieval
- 对比有无 Reranker
- 对比不同 fusion 策略（WeightedFusion vs RRF）
- 对比不同 chunk_size

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
6. **Contextual chunk 未区分原文** — 展示给用户时用 `metadata["original_text"]`，不要展示上下文前缀
7. **chunk_size 过大** — 大 chunk 语义被稀释，BM25 关键词被淹没。长文档建议 ≤ 800 tokens 并叠加 Contextual Retrieval
9. **top_k 过小** — top-5 漏检率远高于 top-20。初始召回宁多勿少，靠 reranker 精排
10. **跳过评估** — 不跑 recall@K 就无法判断 Contextual Retrieval / Reranker 是否真的有效

## API 参考

完整 API 签名见 [references/api-reference.md](references/api-reference.md)。

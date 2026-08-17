## Evaluation Framework

The project includes a configurable evaluation framework for comparing the standard RAG pipeline with the agentic financial-analysis pipeline. It evaluates **retrieval quality, answer quality, latency, and agent behaviour**.

### Benchmark Generation

Because no manually labelled ground-truth dataset was initially available, the benchmark is generated from the indexed annual-report corpus.

```text
Annual Report Corpus
        │
        ▼
Stratified Sampling
(Ticker × Report Year)
        │
        ▼
Financial Question Generation
        │
        ▼
Static Quality Checks
        │
        ▼
LLM Validation
        │
        ▼
Quality / Difficulty Thresholds
        │
        ▼
Benchmark Dataset
```

Documents are sampled across **ticker and reporting year** to reduce over-representation of a single company or reporting period. Generated examples are stored in:

```text
data/evaluation/benchmark.jsonl
```

#### Benchmark Question Types

The benchmark focuses on financially meaningful tasks rather than generic document question answering.

| Category | Description |
| --- | --- |
| **Financial Metric** | Retrieves financially meaningful values while preserving the correct entity, period, unit, and accounting context. |
| **Table Reasoning** | Requires reasoning across multiple rows, columns, periods, entities, or financial categories. |
| **Within-Source Comparison** | Compares financially related values contained within the same source. |
| **Cross-Report Comparison** | Compares the same financial metric across reporting periods. |
| **Calculation** | Requires calculations such as percentage growth, absolute change, ratios, margins, or contribution percentages. |
| **Multi-Hop** | Requires combining evidence from multiple sources. |
| **Financial Interpretation** | Requires an objective financial conclusion supported by reported values. |

The default distribution is:

```text
Financial Metric              10%
Table Reasoning               15%
Within-Source Comparison      15%
Cross-Report Comparison       20%
Calculation                   20%
Multi-Hop                     15%
Financial Interpretation       5%
```

This places greater emphasis on financial reasoning, comparison, calculation, and multi-source retrieval than on simple factual lookup. I intentionally made the benchmark challenging to reduce the risk of overly optimistic evaluation results and provide a more realistic assessment of the system's performance.


#### Benchmark Validation

Each generated question-answer pair is automatically screened using static quality checks and LLM-based validation for:

- grounding in the source evidence;
- financial relevance and question difficulty;
- currency and unit accuracy;
- reporting-period accuracy;
- correct company, Group, subsidiary, segment, and geographic distinctions;
- validity of financial calculations and comparisons;
- genuine multi-source requirements, where applicable;
- absence of extraction or parser artifacts; and
- naturalness of the question.

Each example receives validation metadata, including quality, difficulty, financial relevance, and human-verification status:

```json
{
  "quality_score": 0.95,
  "difficulty_score": 0.90,
  "financial_relevance_score": 1.0,
  "human_verified": false
}
```

---

### Evaluation Architecture

The same benchmark can be used to evaluate the RAG and agent pipelines.

```text
Benchmark Question
        │
        ├───────────────────────┐
        ▼                       ▼
      RAG                    Agent
        │                       │
        ▼                       ▼
   Retrieval              Initial Hybrid
        │                   Retrieval
        ▼                       │
Answer Generation               ▼
                           Gemini Agent
                                │
                                ├── Additional Retrieval
                                ├── Table Lookup
                                ├── Calculator
                                └── Web Search
                                │
                                ▼
                           Final Answer
```

This provides a common basis for comparing conventional RAG with the additional retrieval and tool-use capabilities of the agent.

---

### Retrieval Evaluation

The Zoomcamp course material evaluated retrieval primarily using **Hit Rate and Mean Reciprocal Rank (MRR)**. I extended the evaluation with additional metrics to provide a **more comprehensive assessment of retrieval performance across different dimensions**.

Retrieval performance is evaluated against the benchmark's gold source IDs.

| Metric | Description |
| --- | --- |
| **Precision@K** | Proportion of the top-K retrieved documents that are relevant. |
| **Recall@K** | Proportion of gold documents retrieved within the top-K results. |
| **Hit Rate@K** | Whether at least one gold document appears in the top-K results. |
| **MRR** | Measures the rank of the first relevant retrieved document. |
| **nDCG@K** | Measures ranking quality while rewarding relevant documents appearing higher in the results. |

For the agent pipeline, the initial hybrid retrieval is evaluated directly, while subsequent retrieval and tool calls are retained in the execution trace for analysis.

I initially strugged with understanding the difference between **Precision@K** and **Recall@K**. I found this description useful:

- **High Precision@k** — a high proportion of the top `k` retrieved results are relevant, reducing irrelevant context passed to the LLM.
- **High Recall@k** — a high proportion of all relevant evidence is retrieved within the top `k` results, reducing the likelihood of missing information needed to answer the question.

There is typically a trade-off when increasing `k`: retrieving more results can **improve recall** by capturing more relevant evidence, but may **reduce precision** by introducing additional irrelevant context.
---

### Answer Evaluation

Final answers are evaluated using both deterministic and LLM-based metrics.

| Metric | Description |
| --- | --- |
| **Token F1** | Measures lexical overlap between the generated and reference answers. |
| **Answer Correctness** | Assesses whether the answer agrees with the reference answer, including values, units, currencies, periods, and entities. |
| **Faithfulness** | Assesses whether claims in the answer are supported by the retrieved evidence. |
| **Answer Relevance** | Assesses whether the response directly and sufficiently answers the question. |
| **Latency** | Measures pipeline execution time. |

The LLM judge returns both a score and a concise explanation for **correctness, faithfulness, and relevance**, supporting qualitative error analysis in addition to aggregate metrics.

```json
{
  "correctness": {
    "score": 1.0,
    "reason": "The values, units, and reporting periods match the reference answer."
  },
  "faithfulness": {
    "score": 0.9,
    "reason": "The main claims are supported by the retrieved evidence."
  },
  "relevance": {
    "score": 1.0,
    "reason": "The response directly answers the requested financial comparison."
  }
}
```

---

### Agent Evaluation

The agent evaluation also retains its execution trace, including:

- initial retrieval;
- additional tools selected by Gemini;
- arguments passed to each tool;
- tool execution status and responses;
- generated answer;
- execution timing.

This makes it possible to inspect how the agent arrived at an answer and distinguish retrieval, tool, and answer-generation failures.

---

### Evaluation Output

Evaluation results are exported to Excel under:

```text
outputs/evaluation/
```

Example outputs include:

```text
outputs/evaluation/
├── rag_keyword_evaluation.xlsx
├── rag_vector_evaluation.xlsx
├── rag_hybrid_evaluation.xlsx
└── agent_evaluation.xlsx
```

The workbooks contain aggregate and per-question results, including benchmark questions, reference and generated answers, source IDs, retrieval metrics, answer-quality scores, LLM-judge explanations, tool information where applicable, latency, and errors.

### Metrics Summary

| Evaluation Dimension | Metric |
| --- | --- |
| Retrieval relevance | Precision@K |
| Evidence coverage | Recall@K |
| Retrieval success | Hit Rate@K |
| First relevant result ranking | MRR |
| Overall ranking quality | nDCG@K |
| Lexical answer similarity | Token F1 |
| Factual accuracy | Answer Correctness |
| Evidence grounding | Faithfulness |
| Question-answer alignment | Answer Relevance |
| Efficiency | Latency |
| Agent behaviour | Tool-call trace |

The framework provides a consistent basis for comparing **keyword RAG, semantic RAG, hybrid RAG, and the agentic financial-analysis pipeline** using the same financially focused benchmark.
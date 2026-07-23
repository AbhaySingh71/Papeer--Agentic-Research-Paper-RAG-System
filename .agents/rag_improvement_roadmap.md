# 🗺️ Papeer RAG Architectural Improvement Roadmap

This document outlines the major codebase-level improvements to elevate **Papeer** to a state-of-the-art research assistant. These enhancements focus on retrieval accuracy, query understanding, safety controls, observability, and response generation quality.

---

## 🌟 Recently Completed

- [x] **Hybrid Retrieval (Dense + BM25)**: Blended semantic vector search (Qdrant) with keyword search (BM25 Retreiver) using an `EnsembleRetriever` to guarantee term precision.
- [x] **Observability Core (LangSmith)**: Enabled session-level metadata tracking on all graph flows and evaluation runs.
- [x] **Dual-Stage Guardrails**: Integrated `input_guard` and `output_guard` nodes checking for prompt injection, toxicity, and grounding.

---

## 🚀 Future Roadmap

### 🎯 1. Cross-Encoder Re-ranking Node
Similarity search gathers the top `k` chunks based on vector distance, but vector distance does not guarantee top relevance for direct Q&A. A re-ranking step ensures the absolute best context chunks are positioned at the beginning of the context block.

#### Implementation Plan:
1. **Add a Reranking Step**: Integrate a fast, local CPU-bound reranker (such as `FlashRank`) or use an LLM-based reranking prompt in a new LangGraph node.
2. **Reposition Context**: Order chunks by relevancy score. Chunks placed at the very beginning and end of the context block are better prioritized by LLM decoder models ("Lost in the Middle" phenomenon).

---

### 🔍 2. Multi-Query Expansion & Parallel Retrieval
Users often write queries that do not match the exact syntax of the paper's content. Multi-query expansion mitigates this by generating multiple alternative versions of the question and retrieving context for all of them.

#### Implementation Plan:
1. **Query Generation Node**: In [rag_graph.py](file:///C:/Users/abhay/Desktop/papeer/backend/rag_graph.py), add a step where Gemini writes 3 distinct search formulations of the user's prompt (e.g., conceptual, keyword-heavy, and question-style).
2. **Parallel Retrieval**: Query the vector database for all 3 variations, then deduplicate the resulting documents by their document hashes or content strings.

---

### 📊 3. Hierarchical Chunking (Parent Document Retriever)
Currently, documents are split into static chunks of 1000 characters. If a formula or definition spans across a boundary, it gets truncated, losing essential meaning.

#### Implementation Plan:
1. **PDR Strategy**: Store smaller child chunks (e.g., 200 characters) for high-precision retrieval matching, but link them to larger parent documents (e.g., 1500 characters) inside the storage database.
2. **Context Expansion**: When a child chunk matches the search query, retrieve the parent chunk and feed it to the generator LLM instead. This provides full surrounding context.

---

### 🛡️ 4. Transition to AWS Bedrock Guardrails
As Papeer transitions to a production AWS architecture, shifting from local `guardrails-ai` validation to AWS native safety guards reduces computation overhead.

#### Implementation Plan:
1. **Managed Policies**: Create an AWS Bedrock Guardrail configuration containing PII masking, custom blocklists, and safety filters.
2. **Client Injection**: Bind the Bedrock Guardrail directly into the AWS Bedrock LangChain LLM client configuration using `guardrailIdentifier` and `guardrailVersion`.

---

### 📈 5. Trace-Driven Evaluations (LangSmith Extension)
Utilize collected session traces to continuously evaluate and optimize the RAG pipeline.

#### Implementation Plan:
1. **Trace-to-Dataset Pipeline**: Create a script to auto-generate a new "Golden Test Dataset" inside LangSmith by filtering successful production traces.
2. **Feedback Collection UI**: Add like/dislike buttons inside Streamlit that trigger `client.create_feedback()` to send binary rating scores to the active LangSmith run IDs.
3. **Internal Node Tracing**: Apply the `@traceable` decorator to granular functions (like vector index insertion or web loader scrapers) to pinpoint bottlenecks inside the LangSmith trace timeline.

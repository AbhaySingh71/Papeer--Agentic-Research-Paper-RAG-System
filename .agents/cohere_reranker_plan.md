# Cohere Reranker Implementation Plan (Free Trial Tier)

This document provides a feasibility analysis of using Cohere's Free Trial tier (limit: 10 requests/minute) and outlines a step-by-step plan to implement it with a robust fallback system.

---

## 1. Feasibility Analysis: Should You Use the Free Trial?

### The Verdict
**Yes, but only for development, testing, or personal demos—and only if implemented with a fallback strategy.** 

For production or multi-user applications, 10 requests per minute (RPM) is too restrictive. However, for a single developer, it is highly beneficial because Cohere's state-of-the-art reranking model (`rerank-english-v3.0`) dramatically improves RAG retrieval precision.

### Trade-offs
*   **Pros:**
    *   **Cost:** Completely free.
    *   **Accuracy:** Reranking optimizes semantic relevance, filtering out noisy chunks retrieved by vector or BM25 keyword searches.
    *   **Ease of Integration:** Seamlessly integrates with LangChain.
*   **Cons:**
    *   **Rate Limits (10 RPM):** Easily exceeded during active chat sessions, multi-turn conversations, or agent query rewrites (e.g., when `query_rewrite_node` triggers a second search).
    *   **Latency:** Network overhead for calling Cohere's API adds to response times.
    *   **Legal Restrictions:** Cohere's free trial key is strictly for non-commercial use.

---

## 2. Implementation Plan

To use the Cohere Reranker safely, we must implement a **Fallback Mechanism**. If Cohere raises a `429 Rate Limit Exceeded` or any connection error, the system will log a warning and return the un-reranked hybrid results, preventing application crashes.

### Step 1: Install Dependencies
Add `langchain-cohere` or use the standard `cohere` SDK. We also use `tenacity` (already common in python setups) to handle brief rate-limiting spikes.
```bash
uv add langchain-cohere
```

### Step 2: Configure Environment Variables
Add the Cohere API Key to your `.env` file:
```env
COHERE_API_KEY=your_cohere_free_trial_api_key_here
```

### Step 3: Implement Cohere Reranker with Fallback
Update [vector_store.py](file:///C:/Users/abhay/Desktop/papeer/backend/vector_store.py) to wrap the reranker in a try-except block. We will retrieve a larger pool of documents (e.g., $2 \times k$ or $3 \times k$) from the hybrid retriever, then rerank and select the top $k$ items.

#### Code Draft for `backend/vector_store.py`
```python
import logging
from langchain_cohere import CohereRerank

logger = logging.getLogger(__name__)

def search(query: str, session_id: str, k: int = 4) -> list[Document]:
    # 1. Retrieve a larger candidate pool for reranking (e.g. 3 * k)
    candidate_k = max(k * 3, 12)
    retriever = get_hybrid_retriever(session_id, k=candidate_k)
    if not retriever:
        return []
    
    candidates = retriever.invoke(query)
    if not candidates:
        return []
        
    # Check if Cohere API key is configured
    cohere_api_key = os.getenv("COHERE_API_KEY")
    if not cohere_api_key:
        logger.warning("COHERE_API_KEY not configured. Returning raw hybrid retrieval results.")
        return candidates[:k]
        
    # 2. Attempt Reranking with Cohere
    try:
        reranker = CohereRerank(
            model="rerank-english-v3.0", 
            cohere_api_key=cohere_api_key,
            top_n=k
        )
        # Rerank the candidates
        reranked_docs = reranker.compress_documents(candidates, query)
        logger.info(f"Successfully reranked {len(candidates)} down to {len(reranked_docs)} using Cohere.")
        return reranked_docs
    except Exception as e:
        # 3. Graceful Fallback on rate-limit (429) or connection error
        logger.error(f"Cohere Rerank failed: {e}. Falling back to raw hybrid retrieval.")
        return candidates[:k]
```

---

## 3. Next Steps

1. **Get a Cohere API Key**: Sign up at [dashboard.cohere.com](https://dashboard.cohere.com/) and copy your free trial API key.
2. **Review & Approve**: If you approve of this plan, let me know and I will install `langchain-cohere` and apply the changes to [vector_store.py](file:///C:/Users/abhay/Desktop/papeer/backend/vector_store.py).

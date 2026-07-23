# Guardrails Implementation Plan for Papeer

This document outlines the strategy, library options, and step-by-step implementation plan to integrate safety and validation guardrails into the **Papeer** RAG application, optimizing for both free local development and future deployment on AWS.

---

## 1. Evaluation of Guardrail Libraries

To choose the best approach, we evaluate the leading free/open-source libraries and native AWS solutions across several criteria:

| Library / Tool | Open Source / Free | Latency & Setup | Integration with LangGraph/LangChain | Future AWS Alignment | Key Strengths |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Guardrails AI** (`guardrails-ai`) | Yes (Open Source Core) | Medium (Python library, some validators need extra packages) | Excellent (Native LangChain/LangGraph support) | Moderate (Runs in ECS/EKS/Lambda containers) | Large hub of pre-built validators (PII, competitor check, hallucinations, toxic content). |
| **NVIDIA NeMo Guardrails** | Yes (Open Source) | High (Requires configuration of Colang files, heavier memory footprint) | Good | Moderate (Self-hosted on AWS ECS/EKS) | State-of-the-art conversational steering and topic containment. |
| **Llama Guard 3** (Llama-based) | Yes (Free weights) | Low-Medium (Requires running local model or calling an API) | Excellent | Excellent (Available natively on AWS Bedrock/SageMaker) | Industry standard model-based input/output moderation. |
| **Amazon Bedrock Guardrails** | No (Pay-per-use, but cheap) | Extremely Low (Managed service) | Excellent (LangChain Bedrock Integration) | **Perfect (Native AWS)** | Fully managed, enterprise-grade, blocklists, PII masking, safety filters without self-hosting. |

### Recommendation
1. **For Free Local Development & immediate implementation**: Use a lightweight validator library approach (such as **Guardrails AI** or **custom Pydantic-based validators** in the LangGraph nodes) to validate inputs (checking for injections or empty queries) and outputs (checking for hallucination or toxicity).
2. **For Future AWS Deployment**: Transition to **Amazon Bedrock Guardrails**. Since Papeer runs on AWS in the future, using Bedrock's native guardrails will offload processing from your application code, scale automatically, and support central compliance monitoring.

---

## 2. Recommended Guardrail Architectures

### Phase 1: Local & Free Architecture (LangGraph Integration)
We will hook the guardrails directly into the LangGraph state machine:
- **Input Guardrail Node**: Placed right after the user submits a message. Checks for Prompt Injection and off-topic questions.
- **Output Guardrail Node**: Placed after `generate_answer_node`. Checks for Hallucinations (grounding check against retrieved documents) and Toxicity.

```
User Input --> Input Guardrail Node --> Router Node --> Retrieval --> Generate Answer --> Output Guardrail Node --> Streamlit UI
```

### Phase 2: Future AWS Deployment Architecture
When you migrate to AWS:
1. Replace local model calls with AWS Bedrock (`anthropic.claude` or `amazon.titan`).
2. Attach an **Amazon Bedrock Guardrail** directly to the Bedrock client configuration.
3. AWS Bedrock automatically intercepts input prompts and output completions, applying PII masking, safety filters, and custom word policies.

---

## 3. Implementation Plan for Papeer

### Step 1: Install Dependencies
For local development, we install `guardrails-ai` or build a lightweight model-based guardrail (using `gemini-2.5-flash-lite` with structured output as it's free-tier friendly and has no extra hosting setup cost).
```bash
pip install guardrails-ai
```

### Step 2: Implement Input Guardrails
Add a guardrail to prevent prompt injections or inappropriate queries before they hit the retriever or router.

Create a new file `backend/guardrails.py` containing:
```python
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

class InputModeration(BaseModel):
    is_safe: bool = Field(description="False if prompt contains injection, malicious content, or jailbreaks. True otherwise.")
    reason: str = Field(description="Brief reason if is_safe is False.")

class OutputModeration(BaseModel):
    is_hallucinated: bool = Field(description="True if the answer contains claims unsupported by the context documents.")
    is_toxic: bool = Field(description="True if the answer is toxic, rude, or unsafe.")
    refined_answer: str = Field(description="Refined answer if unsafe/hallucinated, or original answer if clean.")

def create_moderator_chains():
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")
    input_chain = llm.with_structured_output(InputModeration)
    output_chain = llm.with_structured_output(OutputModeration)
    return input_chain, output_chain
```

### Step 3: Integrate into LangGraph (`backend/rag_graph.py`)
Modify the graph to include the guardrail checks:
1. **Input Guardrail**: Add `input_guard_node` at the start.
2. **Output Guardrail**: Add `output_guard_node` before returning the final answer.

#### Node Code Draft:
```python
def input_guard_node(state: RAGState) -> dict:
    query = state["query"]
    # Run InputModeration chain
    decision = input_chain.invoke(f"Check this user query: {query}")
    if not decision.is_safe:
        return {
            "answer": f"Guardrail Alert: {decision.reason}",
            "route": "direct_answer"  # Bypass retrieval and go straight to end
        }
    return {}

def output_guard_node(state: RAGState) -> dict:
    answer = state.get("answer", "")
    docs = state.get("retrieved_docs", [])
    doc_text = "\n\n".join([d.page_content for d in docs])
    
    decision = output_chain.invoke(
        f"Context Docs:\n{doc_text}\n\nGenerated Answer:\n{answer}"
    )
    if decision.is_hallucinated or decision.is_toxic:
        return {
            "answer": "I'm sorry, but I could not verify that answer using the uploaded documents.",
            "messages": [AIMessage(content="I'm sorry, but I could not verify that answer using the uploaded documents.")]
        }
    return {}
```

---

## 4. Transitioning to AWS Bedrock Guardrails

When you deploy on AWS (e.g., using ECS, AWS Lambda, or SageMaker), you can migrate from code-based checkers to cloud-native guardrails:

1. **Configure Amazon Bedrock Guardrail**:
   - Set up **Safety Filters** (Hate, Insults, Sexual, Violence, Prompt Attack).
   - Set up **Blocked Denoising / Word Filters** (e.g. competitor names, sensitive credentials).
   - Set up **PII limits** (Masking SSN, Emails, AWS Keys).
2. **Code Integration**:
   Simply pass the `guardrailIdentifier` and `guardrailVersion` in your LangChain Bedrock client config:
   ```python
   from langchain_aws import ChatBedrock

   llm = ChatBedrock(
       model_id="anthropic.claude-3-sonnet-20240229-v1:0",
       model_kwargs={
           "guardrailIdentifier": "papeer-guardrail-id",
           "guardrailVersion": "1",
           "trace": "ENABLED"
       }
   )
   ```

---

## Next Steps
- [ ] Confirm if you would like me to write the `backend/guardrails.py` file and integrate it into the graph.
- [ ] Let me know if you would like custom rules (e.g. preventing answering questions about specific topics, or strict academic tone requirements).

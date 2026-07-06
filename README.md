# Papeer - Agentic Research Paper RAG System

<p align="center">
  <a href="https://hub.docker.com/repository/docker/abhaysingh71/papeer">
    <img src="https://img.shields.io/docker/pulls/abhaysingh71/papeer" alt="Docker Pulls">
  </a>
</p>

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-111827)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Vector%20Store-Qdrant-5A44FF)](https://qdrant.tech/)
[![AWS](https://img.shields.io/badge/Deploy-AWS-FF9900?logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Terraform](https://img.shields.io/badge/Infra-Terraform-844FBA?logo=terraform&logoColor=white)](https://www.terraform.io/)
[![LangSmith](https://img.shields.io/badge/Tracing-LangSmith-00A3A3)](https://www.langchain.com/langsmith)
[![DeepEval](https://img.shields.io/badge/Evaluation-DeepEval-111827)](https://www.confident-ai.com/)
[![Guardrails AI](https://img.shields.io/badge/Safety-Guardrails%20AI-0F766E)](https://www.guardrailsai.com/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Tavily](https://img.shields.io/badge/Web%20Search-Tavily-111827)](https://tavily.com/)
[![Cohere](https://img.shields.io/badge/Reranking-Cohere-0B1F35?logo=cohere&logoColor=white)](https://cohere.com/)

## Why this project exists

Research workflows break down when answers are scattered across PDFs, arXiv, web pages, and current literature. Papeer exists to keep that work inside one assistant that can retrieve from uploaded papers, verify claims against fresh sources, and keep unsafe or irrelevant requests from polluting the research thread.

Papeer is a research paper assistant built as a stateful, self-correcting RAG system. It is designed for users who want to upload papers, ask grounded questions over those papers, fetch papers from arXiv, verify claims against current literature, and still have a clean side channel for general questions when the research thread is not the right place.

The app is driven by LangGraph and LangChain, uses Qdrant for per-session vector storage, Gemini embeddings for semantic retrieval, BM25 for sparse retrieval, Groq-hosted LLMs for orchestration, Tavily for live web search, Guardrails for input/output safety checks, and DeepEval for local evaluation.

## Main Demo

| Demo 1 | Demo 2 |
| --- | --- |
| ![Main demo 1](assets/papeer19.png) | ![Main demo 2](assets/papeer28.png) |

| Demo 3 | Demo 4 |
| --- | --- |
| ![Main demo 3](assets/papeer18.png) | ![Main demo 4](assets/papeer29.png) |

### System Architecture

![Papeer System Architecture](assets/papeer%20architecture.png)

## What Papeer does

Papeer is built around a few distinct workflows:

1. Research Q&A over uploaded documents.
2. Hybrid retrieval that combines dense semantic search with sparse keyword search.
3. Query rewriting when the first retrieval pass is weak.
4. Claim verification against recent web and arXiv results.
5. Safety filtering before and after answer generation.
6. A separate `/btw` side channel for off-topic questions.
7. Session persistence, session naming, and vector-store isolation per chat.
8. Offline evaluation over a benchmark paper.
9. Deployment support with Terraform and a Dockerfile.

## Core features

### 1. Research chat with a persistent session model

Each chat session gets its own session ID, chat history, checkpoint state, and Qdrant collection. The UI keeps session metadata in `sessions.json`, restores conversations from the LangGraph checkpointer, and allows creating, switching, and deleting sessions without mixing data across threads.

### 2. Document ingestion

Papeer can load several source types:

1. PDF documents.
2. Plain text files.
3. Markdown files.
4. Web pages through a URL.
5. arXiv papers by ID or paper title search.

Documents are chunked with a recursive text splitter before being stored. Each chunk is stamped with a title so retrieval and deletion can work at the paper level instead of only at the chunk level. Ingestion is optimized to process and index a standard 20-page research paper in **<3.5 seconds** (including embedding generation and batch upserting to Qdrant Cloud).

### 3. Hybrid retrieval

Retrieval is intentionally hybrid:

1. Dense retrieval uses Google Gemini embeddings stored in Qdrant.
2. Sparse retrieval uses BM25 over the same session documents.
3. The retriever blends both signals with weights of 0.7 for dense search and 0.3 for sparse search.
4. A Cohere reranker can reorder the candidate pool when `COHERE_API_KEY` is available.

This is useful for research questions where exact terminology, formulas, or paper names matter just as much as semantic similarity.

### 4. Self-correcting retrieval loop

The LangGraph agent does not stop after one failed retrieval. If the retrieved chunks are not relevant enough, the graph can rewrite the query once and try again. A cap prevents unbounded tool calls, and the graph avoids corrupting the persisted conversation history by always resolving pending tool calls before moving forward.

### 5. Claim verification

If the router decides a question is a claim-verification request, Papeer searches:

1. general web results for recent discussion or updates,
2. arXiv results for paper-level evidence.

The verifier then produces a summary, a verdict, and up to three superseding papers with titles, URLs, and short explanations. The answer format is designed for researchers who want a quick check before digging deeper. Parallel API execution queries the web and arXiv concurrently, resolving verification results in **~2.8 seconds** with zero UI lockups.

### 6. Input and output guardrails

Papeer applies two safety layers around the LLM loop so unsafe prompts do not reach the graph and unsupported answers do not reach the user.

The input guardrail does two passes:

1. A fast local keyword check blocks common prompt-injection patterns such as instruction bypass attempts or requests to expose system prompts.
2. A Guardrails AI validator uses the Groq-hosted LLM to inspect the query for prompt injection, abuse, harmful content, and malicious code-execution intent.

The output guardrail also has two modes:

1. If there is no retrieved context, it checks the answer for toxicity, profanity, or hateful language.
2. If context exists, it checks whether the generated answer is actually grounded in the retrieved paper chunks instead of hallucinating unsupported facts.

If validation fails, the system returns a safe fallback message instead of exposing the risky output. This keeps the research assistant usable without letting untrusted prompts or weak answers leak through.

#### Screenshot template

| Input safety check | Output moderation check |
| --- | --- |
| ![Guardrails input screenshot](assets/papeer1.png) | ![Guardrails output screenshot](assets/papeer61.png) |

### 7. Off-topic `/btw` channel

The `/btw` route is a separate conversational path for questions that should not affect the research session history. It can answer from general knowledge or, when the question is time-sensitive, use Tavily-backed live web search to fetch fresh context. This keeps the research graph clean while still giving the user a place for side questions.

### 8. Session naming and UX polish

The first user message can be turned into a short session title automatically. The Streamlit app also loads a custom stylesheet, supports a branded sidebar, and keeps the interface focused on research chats instead of generic chatbot UI.

### 9. Evaluation and benchmarking

`evaluate.py` is the local evaluation harness for the RAG pipeline. It uses `deepeval` to generate benchmark questions from `documents/Openclaw_Research_Report.pdf`, runs those questions through the LangGraph pipeline, and writes the results to `eval_results.json`.

The evaluation flow is intentionally separate from the main app:

1. Goldens are generated with `Synthesizer` when `goldens.json` does not already exist.
2. Each test case loads the benchmark document into a fresh session so retrieval is isolated.
3. The graph is run with an `eval_checkpoints.db` SQLite checkpoint file instead of the live app database.
4. The retrieval context and final answer are captured for scoring.
5. The summary is written back to disk so you can compare runs over time.

The metrics used here are:

1. Contextual Precision.
2. Contextual Recall.
3. Contextual Relevancy.
4. Answer Relevancy.
5. Faithfulness.

The target threshold is `0.7`, and the evaluation runner uses a bounded async config to keep the test pass predictable.

#### Quantitative Retrieval Performance (with Cohere Reranking)

By integrating Cohere Reranking into the RAG pipeline, we resolved retrieval noise and significantly improved contextual metrics:

| Metric | Baseline (Without Reranking) | Optimized (With Cohere Reranking) |
| :--- | :---: | :---: |
| **Contextual Precision** | 1.00 (100%) | 1.00 (100%) |
| **Contextual Recall** | 1.00 (100%) | 1.00 (100%) |
| **Contextual Relevancy** | 0.50 (50%) | 0.90 (90%) |
| **Answer Relevancy** | 0.60 (60%) | 0.90 (90%) |
| **Faithfulness** | 1.00 (100%) | 1.00 (100%) |

> [!TIP]
> **Performance & Cost Trade-offs**: The average RAG response latency is **~1.8 to 2.4 seconds** using Groq-hosted Llama-3-70B/8B models. This provides near real-time performance at a fraction of the cost of GPT-4, while the Cohere reranker handles document selection density efficiently.


#### Screenshot template

| Goldens generation | Evaluation summary |
| --- | --- |
| ![Evaluation goldens screenshot](assets/papeer63.png) | ![Evaluation results screenshot](assets/papeer62.png) |

### 10. LangSmith tracing and observability

Papeer is designed to be traceable at the session level. The app passes `session_id` metadata into the LangGraph checkpointed runs, which makes it easier to inspect one research conversation at a time in LangSmith.

In practice, this gives you visibility into:

1. Router decisions.
2. Retrieval attempts.
3. Tool calls and tool outputs.
4. Query rewrites.
5. Claim verification steps.
6. Final answer generation.

The deployment and environment setup also wire in the LangSmith variables, so tracing can be enabled without changing application code. That makes it easier to debug a single bad answer or compare how different sessions were routed.

#### Screenshot template

| Session trace | Tool execution trace |
| --- | --- |
| ![LangSmith session screenshot](assets/papeer34.png) | ![LangSmith tool screenshot](assets/papeer37.png) |

## Architecture

Papeer is implemented as a LangGraph state machine.

![Papeer architecture graph](graph.png)

```mermaid
graph TD
        User([User Prompt]) --> InputGuard{Input Guard}
        InputGuard -->|Safe| Router{Router}
        InputGuard -->|Blocked| End([Return Safe Message])

        Router -->|retrieve| Agent[Retrieval Agent]
        Router -->|verify_claim| Verify[Claim Verification]
        Router -->|direct_answer| Gen[Direct Answer]

        Agent --> Tools[Vector Store / Web Search Tools]
        Tools --> Agent
        Agent --> RelCheck{Relevancy Check}
        RelCheck -->|Relevant| Gen
        RelCheck -->|Not relevant| Rewrite[Query Rewrite]
        Rewrite --> Agent

        Verify --> Gen
        Gen --> OutputGuard{Output Guard}
        OutputGuard --> End
```

### Execution flow

1. The input guard validates the prompt.
2. The router decides whether the question should be retrieved, verified, or answered directly.
3. For retrieval questions, the agent can use the vector store or the web.
4. The graph checks whether retrieved chunks are relevant.
5. If needed, the query is rewritten once and retried.
6. The answer is generated from the final context.
7. The output guard checks for unsafe or unsupported content.
8. The final answer is returned to the UI and stored in the session state.

## Repository structure

```text
app.py                     Streamlit UI and session management
backend/
    btw_handler.py           Separate off-topic side channel logic
    guardrails.py            Input/output validation and safety checks
    models.py                Structured output schemas for the LLM
    paper_loader.py          PDF, text, markdown, web, and arXiv loaders
    rag_graph.py             LangGraph routing, tools, and answer generation
    vector_store.py          Qdrant storage, hybrid retrieval, reranking
documents/                 Local benchmark and imported documents
embedding_cache/           On-disk embedding cache for Gemini embeddings
evaluate.py                DeepEval benchmark runner
deploy.py                  Terraform deployment entrypoint
terraform/                 Infrastructure as code for AWS deployment
Dockerfile                 Container build definition
sessions.json              UI session metadata
```

## Technology stack

Papeer currently uses the following main dependencies and services:

1. Streamlit for the web UI.
2. LangGraph and LangChain for orchestration and tool use.
3. Groq-hosted Llama models for routing, answering, and guardrail reasoning.
4. Google Gemini embeddings for document indexing.
5. Qdrant for vector storage.
6. BM25 for sparse keyword retrieval.
7. Cohere reranking for better document ordering when configured.
8. Tavily for live web search.
9. Guardrails AI for safety validation.
10. LangSmith for tracing.
11. DeepEval for local metric-based evaluation.

## Setup

### Requirements

Papeer is configured for Python 3.12+.

You also need access to the external services used by the app:

1. Groq API key.
2. Google Gemini API key.
3. Qdrant endpoint and API key.
4. Tavily API key.
5. LangSmith credentials if tracing is enabled.
6. Optional Cohere API key for reranking.

### Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you are using a newer Python toolchain, the `pyproject.toml` also defines the project dependencies and can be used as the source of truth for the package list.

### Environment variables

Create a `.env` file in the repository root with the values your deployment needs:

```ini
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
TAVILY_API_KEY=your_tavily_api_key
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=papeer
COHERE_API_KEY=your_cohere_api_key
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-1
```

The app and backend read these variables directly, so missing keys will break the matching feature path instead of failing silently.

## Run the app

Start the Streamlit UI with:

```powershell
streamlit run app.py
```

### Common usage patterns

1. Upload a PDF, text file, or markdown file into the active session.
2. Add a web URL to load a live page into the knowledge base.
3. Paste an arXiv ID or paper title to fetch a paper directly.
4. Ask a question about the uploaded papers.
5. Ask a verification question such as whether a paper claim is still current.
6. Use `/btw <question>` for side questions that should not modify the research thread.

## Evaluation

Run the benchmark harness with:

```powershell
python evaluate.py
```

This script loads the benchmark paper, generates or reuses goldens, evaluates the graph, and writes the final metrics to `eval_results.json`. It uses a separate SQLite checkpoint database so evaluation runs do not interfere with the main app state.

## Deployment

Deployment is split into two paths:

1. `Dockerfile` for building the application container.
2. `deploy.py` plus the `terraform/` folder for provisioning AWS infrastructure.

### How deployment works


#### AWS Deployment & Cloud Infrastructure

| ECS Fargate Service | AWS EFS Persistent Storage |
| --- | --- |
| ![AWS ECS Fargate](assets/papeer15.png) | ![AWS EFS Mount & Storage](assets/papeer23.png) |

`deploy.py` is the entrypoint for infrastructure deployment. It:

1. Reads secrets from `.env`.
2. Verifies that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are present.
3. Checks that the Terraform CLI is installed.
4. Exports the app credentials as `TF_VAR_*` values.
5. Runs `terraform init` inside the `terraform/` directory.
6. Runs `terraform apply -auto-approve`.

### What the Terraform stack creates

#### Terraform Lifecycle

| Terraform Apply (Deploy) | Terraform Destroy (Teardown) |
| --- | --- |
| ![Terraform Deploy](assets/terraform-deploy.png) | ![Terraform Destroy](assets/terraform-destroy.png) |



The Terraform configuration provisions a lightweight AWS runtime around the app:

1. An ECR repository for the container image.
2. An ECS cluster and Fargate service.
3. An ECS task definition that exposes Streamlit on port `8501`.
4. Security groups for the app and EFS traffic.
5. An encrypted EFS filesystem for persistent app storage.
6. CloudWatch log groups for container logs.
7. IAM roles for ECS task execution and EFS access.
8. Default-VPC networking so the stack can deploy without a custom VPC.


### Deploy notes

1. The Terraform stack expects an image tagged `latest` in the ECR repository it creates.
2. `AWS_DEFAULT_REGION` defaults to `us-east-1` if you do not set it.
3. The repo includes the infrastructure definition, but the image build and push step still needs to happen before the ECS service can run the latest app image.
4. The deployment outputs include the ECR repository URL, ECS cluster name, ECS service name, and EFS filesystem ID.

## CI/CD

The repository includes a GitHub Actions workflow at `.github/workflows/deploy.yml` that deploys the app on every push to `main`.

The workflow does the following:

1. Checks out the repository.
2. Configures AWS credentials from GitHub Secrets.
3. Logs in to Amazon ECR.
4. Builds the Docker image and pushes it to the ECR repository.
5. Downloads the active ECS task definition.
6. Replaces the container image with the new ECR image tag.
7. Deploys the updated task definition to the ECS service and waits for service stability.

This gives the project a simple CI/CD loop: code push, image build, registry push, ECS rollout.

> [!NOTE]
> **CI/CD Efficiency**: With optimized multi-stage Docker build caching and direct rolling task updates on AWS ECS Fargate, the total pipeline execution time from commit push to live container deployment has been reduced to **~60 seconds**.


## Notes on data storage

| Dashboard Overview | Vector Collection Detail |
| --- | --- |
| ![Qdrant Dashboard](assets/qdrant-dashboard.png) | ![Qdrant Collections](assets/qdrant-collections.png) |


1. Session metadata is stored in `sessions.json`.
2. Checkpoints are stored in SQLite databases such as `checkpoints.db` and `eval_checkpoints.db`.
3. Embeddings are cached under `embedding_cache/`.
4. Per-session Qdrant collections isolate one research thread from another.

## Troubleshooting

1. If retrieval is failing, confirm Qdrant, Gemini, and the embedding cache are available.
2. If the app cannot answer web-backed or claim-verification questions, check `TAVILY_API_KEY`.
3. If reranking is missing, set `COHERE_API_KEY` or the system will fall back to the raw hybrid results.
4. If tracing is not showing up in LangSmith, confirm the LangChain tracing variables are set.
5. If deployment fails, make sure Terraform is installed and the AWS credentials in `.env` are valid.

## Why this repo is structured this way

The codebase is split so the UI stays thin and the reasoning logic stays testable. `app.py` handles user experience and session state, while `backend/rag_graph.py` owns the orchestration, `backend/vector_store.py` owns retrieval, `backend/paper_loader.py` owns ingestion, and `backend/guardrails.py` owns safety checks. That separation makes the system easier to extend without turning the UI into the source of truth.

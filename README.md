# Build the runbook index

A lab from *AI Systems Engineering* (University of St. Thomas). A retrieval-grounded
assistant over the runbooks of the support-ticket system, built in the order a real one
is built: **the labelled QA set first**, then **the index** (chunks, a lexical index, the
embeddings), then **the chat service** that answers from it, then **the judge** that
measures it, validated against your own labels. **Start with [LAB.md](LAB.md).**

```bash
uv sync                          # Python 3.12, uv: https://docs.astral.sh/uv/
cp .env.example .env             # paste your Gemini key
uv run build_index.py            # PART 2: chunk → lexical index → embeddings → manifest
uv run measure_recall.py         # PART 3: recall at 3 and 5, per retriever, per slice
uv run ask.py "How do I rotate the model key?"      # PART 4: the assistant, from the terminal
uv run src/function/local_server.py                 # PART 4: the same, as a service with Swagger
```

The three things that are easy to confuse, kept apart on disk:

| | Where | What it is |
|---|---|---|
| **THE QA SET** | `data/qa/` | the labelled questions: 31 questions, the chunk ids that answer each, the reference answers, the slices. Everything is measured against this. Read `data/qa/README.md` first. |
| **THE INDEX** | `data/index/`, built by `build_index.py` | what the runbooks become: `chunks.jsonl`, `lexical.json` (the posting lists), `embeddings.jsonl` (one vector per chunk, from the embedding model), `query-cache.jsonl`, `manifest.json` (which model built it, when). The shipped copy lets you skip the model call. |
| **THE CHAT SERVICE** | `src/assistant/`, `src/function/` | the assistant: retrieve, assemble the context, generate, check, cite. One FastAPI app, on your laptop or on Lambda. |

| Where | What |
|---|---|
| `data/runbooks/` | the corpus: 24 runbooks for the triage system you have deployed in the earlier labs |
| `data/answers/` | what you record in Part 6: the answers, your labels, the judge's verdicts; `seeded.jsonl` are hand-written answers, some wrong on purpose |
| `src/index/` | `chunk.py` (a runbook → chunks with metadata), `lexical.py` (the inverted index and BM25), `vector.py` (the embedding call, the exact nearest-neighbour scan), `hybrid.py` (reciprocal rank fusion), `store.py` (loading it all) |
| `src/assistant/answer.py` | the request path: retrieve → context → generate → check → cite, and the question-log line |
| `src/harness/` | `qa.py` (the QA set), `recall.py` (recall at k, intervals), `judge.py` (the judge and its rubric), `agreement.py` (the four counts, sensitivity, specificity, κ, the correction) |
| `src/function/` | `app.py` (the service: `GET /`, `POST /chat`, `/docs`), `handler.py` (Lambda), `local_server.py` |
| `build_index.py` `measure_recall.py` `ask.py` | Parts 2, 3, 4 |
| `record_answers.py` `label.py` `judge.py` `validate_judge.py` | Part 6 |
| `deploy.sh` `call.sh` `teardown.sh` | Part 5: the function and the HTTP API in the Learner Lab |

## What you need

- Python 3.12 or newer, and [`uv`](https://docs.astral.sh/uv/).
- Your Gemini key, in `.env`. It is used for three things: embedding questions, the
  answer, and the judge. The chunks' embeddings are shipped in `data/index/`, so the
  corpus is never embedded on your key unless you ask for it.
- For Part 5 only: the AWS CLI and a running Learner Lab session (*Configuring AWS* in
  the course guide).

Parts 1 to 3 run with no key at all: the labelled questions' embeddings are in the query
cache. Parts 4 and 6 need the key. Part 5 needs AWS; if it is not working for you, use a
classmate's URL.

## What this is one instance of

A retrieval-grounded assistant: an index built before any question arrives, a request
path that retrieves the few passages that answer this question and lets a model write
from them alone, and a measurement that starts with retrieval (recall against labelled
chunks, no model needed) before it looks at any generated text. Tonight's instance is
two indexes you build in plain Python, Gemini's embedding model and text model, and a
Lambda function behind an HTTP API, as of October 2026. What does not change: the unit
of retrieval is the unit the model sees; the model's answer is checked against what it
was given, by code on every answer and by a judge on a sample; and the judge is a model
with an error rate, validated against people before its number counts.

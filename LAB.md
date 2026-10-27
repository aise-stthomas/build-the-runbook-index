# Lab: build the runbook index

Tonight you build a **retrieval-grounded assistant** over the runbooks of the support
system you have been deploying all semester, and you measure it the way the lecture
says to: retrieval first, against a labelled set, with no generated text in sight; then
the answers, with a judge you have validated against your own labels.

The lab has four parts that are easy to run together and must be kept apart in your
head. They are kept apart on disk too:

| Part | What it is | Where |
|---|---|---|
| **1 · THE QA SET** | the labelled questions everything is measured against | `data/qa/` |
| **2 · BUILD THE INDEX** | the runbooks become chunks, a lexical index, and embeddings | `build_index.py` → `data/index/` |
| **3 · MEASURE RECALL** | each retriever against the QA set, per slice | `measure_recall.py` |
| **4 · THE CHAT SERVICE** | the assistant: retrieve, assemble, generate, check, cite | `ask.py`, `src/function/` |
| **5 · DEPLOY** | the service behind a public URL in the Learner Lab | `deploy.sh`, `call.sh` |
| **6 · THE JUDGE** | answers recorded, labelled by you, judged by a model, the two compared | `record_answers.py`, `label.py`, `judge.py`, `validate_judge.py` |

By the end you have: **three recall numbers per slice**, one per retriever; **an answer
with its sources** from a service you deployed; and **the four counts** for a judge
against your own labels, with its sensitivity and specificity.

**What this lab shows.**

1. **The labelled set comes first.** Nothing about retrieval can be measured until
   someone has written down which chunk answers which question. That is a human job
   with a written rule, and it is Part 1 because everything else depends on it.
2. **The index is a build.** Chunking is a decision, the lexical index is a data
   structure you can read, and the embeddings are one model call per chunk, done once,
   pinned by a model version in a manifest.
3. **Retrieval is measured without the model.** Recall at *k* against the labelled chunks
   needs no generated text and no judge. It is measured per retriever and per slice,
   and the slices disagree about which retriever is best.
4. **The judge is a model.** Its groundedness rate is worth exactly what its sensitivity
   and specificity against your labels say it is worth.

## Setup

```bash
cp .env.example .env            # paste your Gemini key
uv sync
```

## Part 1 · THE QA SET

Open `data/qa/README.md`, then `data/qa/questions.jsonl`. Thirty-one questions an
engineer on this system would ask. For each: the **slices** it belongs to, the **chunk
ids** that answer it (`RB-16#3` is runbook 16, section 3), and the **reference answer**.
Nine questions have no answer in the corpus and say so: their relevant list is empty
and their reference is `NOT_FOUND`. Five of those nine are near misses, questions the
runbooks almost answer.

Read five questions and find their chunks in `data/runbooks/` by hand. Then read the
rule at the bottom of the README: a chunk is relevant if a correct answer could be
written from it alone, or with one other. Everything in Parts 3 and 6 is measured against
this file. Nothing in it was collected; every row was written by a person.

## Part 2 · BUILD THE INDEX

```bash
uv run build_index.py
```

Four steps, printed as they run:

1. **chunk**: 24 runbooks become 89 chunks, one per section, each with the runbook's
   title and the heading prepended and its metadata attached. Look at one:
   `head -c 600 data/index/chunks.jsonl`.
2. **lexical**: the inverted index. `data/index/lexical.json` is a dictionary from every
   term to the chunks that contain it and how often: the posting lists. Open it and find
   the list for `x-lab-token`.
3. **embed**: **the one step that calls a model.** Every chunk goes to the embedding
   model once, in batches of fifty; the vectors come back, are normalized, and are
   written to `data/index/embeddings.jsonl`. Then the 31 labelled questions are embedded
   into `query-cache.jsonl`, so Part 3 needs no key. The repository ships this file: if
   your key is rate limited tonight, `uv run build_index.py --skip-embeddings` keeps the
   shipped vectors and rebuilds the rest.
4. **manifest**: `data/index/manifest.json` pins what this index is: how many chunks,
   which embedding model, built when. The service refuses nothing yet; later in the
   course a version mismatch here is a silent wrong answer, and the manifest is how it
   is caught.

## Part 3 · MEASURE RECALL

```bash
uv run measure_recall.py
uv run measure_recall.py --show       # every question: hit or miss per retriever, and what came back
```

Two tables, recall at 3 and at 5, one column per retriever (lexical, vector, hybrid),
one row per slice, each cell a rate with its interval. No model is called for the
answer: the question's embedding comes from the cache, and the comparison is chunk ids
against chunk ids.

Read the tables for three things. Which retriever wins on the **identifier** slice, and
which on **paraphrase**, and why those are different. Whether **hybrid** is better than
both, and if it is not, what in `src/index/hybrid.py` explains it (the lecture's system
has a stage after the merge that this lab does not). And how wide the intervals are on
five questions: a 60% and an 80% on a slice of five are the same number.

Then the floor. The bottom of the output lists the best similarity for every question,
answerable against not. Pick a threshold between the two groups and try it:

```bash
uv run measure_recall.py --floor 0.68
```

It reports how many unanswerable questions the floor would stop before any generation,
and how many answerable ones it would stop wrongly. There is no threshold that gets both
right on this corpus; say which error you would rather make, and why.

## Part 4 · THE CHAT SERVICE

```bash
uv run ask.py "A customer wants a \$120 refund. Can the system issue it by itself?"
uv run ask.py "What is the refund limit for gift card purchases?"
uv run ask.py "How do I rotate the model key?" --show-context
```

The first prints an answer with `[n]` citations and the sources built from them. The
second is a question nothing in the corpus answers: the passages that matched are
listed and the model said `NOT_FOUND`. The third prints exactly what the model
received, the instructions, the five passages with their ids, the question, and
nothing else: the context is the model's entire world for this answer.

The code is `src/assistant/answer.py`, one page: retrieve (hybrid, top 5), assemble the
context from a template, generate, **check in code** that every `[n]` is a passage the
model was given (a draft that fails is not shown; the passages are), and build the
sources from the chunk ids. The model never writes a link.

Now as a service:

```bash
uv run src/function/local_server.py          # http://127.0.0.1:9000/docs
```

`POST /chat` from the Swagger page. The response carries the answer, the sources, what
was retrieved with scores, whether it stopped and by what, the context's hash and size,
and every version that touched it. The terminal shows the same thing as one `QUESTION`
line per call: that line is the question log.

## Part 5 · DEPLOY

Start a Learner Lab session and paste its credentials (*Configuring AWS*, section 3).

```bash
./deploy.sh
./call.sh "Does the nightly rule still fire while my Learner Lab session is switched off?"
```

The package is the code plus `data/index/`: the index ships inside the function and is
loaded at import, so it is part of the cold start. `GET /` reports how long that took
(`init_ms`). Open the printed URL with `/docs` on your phone, Authorize with the
`LAB_TOKEN` from `.env`, and ask it something. Then watch the question log land:

```bash
aws logs tail /aws/lambda/runbook-assistant --follow --region us-east-1
```

Swap URLs with a classmate and ask theirs a question from the QA set.

## Part 6 · THE JUDGE

Three steps, and the middle one is yours.

**Step 1: record the answers.**

```bash
uv run record_answers.py
```

Every question in the QA set goes through the assistant; the answers are saved with the
passages the model saw, so that you and the judge read the same thing. Eight more
answers are added from `data/answers/seeded.jsonl`: written by hand over real passages,
and some of them are wrong on purpose. A judge that has never been shown a failure has
never been tested.

**Step 2: label them yourself.**

```bash
uv run label.py
```

One answer at a time: the question, the answer, the passages. You say **yes** if every
factual statement in the answer is stated by the passages or follows directly from
them, **no** if a statement is not there, contradicts them, or drops a condition they
attach: an exception, a limit, a time. Whether the statement is true somewhere else does
not matter. About fifteen minutes for thirty-one answers. If you are working with a
partner, label separately and compare before Step 3: where you disagree, the rule is
unclear, and that is worth writing down.

**Step 3: the judge, and the judge against you.**

```bash
uv run judge.py                 # three runs over every answer
uv run validate_judge.py
```

`judge.py` sends each answer with its passages to a second model call whose rubric is in
`src/harness/judge.py`, three times, and reports how many verdicts flipped between runs:
the judge's own noise. `validate_judge.py` then prints:

- the code checks that need no judge: did the system say `NOT_FOUND` on the nine
  unanswerable questions, and not on the others;
- **the four counts**: you and the judge, grounded or not;
- the judge's **sensitivity** (the failures you marked that it also caught) and
  **specificity** (the passes it passed), each with its count and interval, and κ;
- the rate the judge reports on its own, and that rate corrected for its two error
  rates;
- every disagreement between you and the judge, to read.

Read the disagreements before anything else. Judges fail in patterns, and the pattern is
what goes into the rubric next.

## Part 7 (optional) · the chunk-size dial

```bash
uv run build_index.py --max-words 40      # sections split into small pieces (needs the key: the chunks changed)
uv run measure_recall.py
uv run build_index.py                     # back to the default; --skip-embeddings will not work until you do
```

Smaller chunks separate a rule from its exception; recall at 3 on the condition slice
is where it shows. Rebuild at the default before Part 5 or 6.

## Keep

- the two recall tables, and one sentence on which retriever wins which slice
- the floor you chose and its two error counts
- one answer with its sources from your deployed service, and the `QUESTION` log line for it
- the four counts, sensitivity and specificity for the judge against your labels, and one disagreement you read

## Teardown

`./teardown.sh` removes the function and the API. The log group stays; it is free.

## If something breaks

| Symptom | Likely cause | What to do |
|---|---|---|
| `build_index.py`: `step 3 needs GEMINI_API_KEY` | no key in `.env` | paste it, or `--skip-embeddings` to keep the shipped vectors |
| `measure_recall.py` says a question's chunk id is not in the index | the runbooks were edited, or `--max-words` changed the ids | rebuild at the default, or fix `data/qa/questions.jsonl` |
| `ask.py` answers `NOT FOUND` to everything | a dead key gives 503s; or the floor is set above every similarity | `--floor 0`; check the key |
| the answer fell back: *no citations in the draft* | the model ignored the instructions once | run it again; count it, it is a rate |
| `deploy.sh`: `sts get-caller-identity failed` | the Learner Lab session expired | start it, paste fresh credentials |
| `POST /chat` answers `401` | the token | `LAB_TOKEN` in `.env`; a classmate's token for theirs |
| the first call to the deployed service takes seconds | the cold start now includes loading the index; and the first question a sandbox has not seen pays the embedding client's start-up in `retrieval_ms` | call again; `init_ms` on `GET /` says how long the load took |
| `validate_judge.py`: *no labels yet* | Step 2 was skipped | `uv run label.py` |
| sensitivity is `n/a` | you marked nothing as ungrounded | check the seeded answers again; some are wrong on purpose |

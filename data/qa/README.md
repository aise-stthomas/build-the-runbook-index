# The QA set

**This directory is the labelled set: the questions, the chunks that answer them, and the
reference answers.** Everything the lab measures is measured against this file. Nothing
here was collected; every row was written by a person against the rule below.

`questions.jsonl`: one row per question.

| field | what it holds |
|---|---|
| `id` | q01 … q31 |
| `question` | the question, as an engineer would type it |
| `slices` | which kinds of question it is: `identifier` (contains an exact code or name the runbook also contains), `paraphrase` (shares few words with the runbook), `procedure` (how do I), `condition` (a rule with a limit or exception), `not-in-corpus`; a `near-miss` is unanswerable but sits next to passages that almost answer it |
| `relevant` | the chunk ids that answer it, as `RB-16#3` (runbook, section number); empty when nothing in the corpus does |
| `reference` | the correct answer in one to three sentences, with the figure and the condition; `NOT_FOUND` when no runbook answers it |

**The rule the labels follow.**

- A chunk is *relevant* if a correct answer could be written from it alone, or from it
  with one other chunk. Every such chunk is listed; the first is the one that answers most
  of the question.
- The *reference answer* holds the figure, the condition and the procedure, nothing else.
- A question is *not in the corpus* when no chunk, and no two chunks, answer it. Nine of
  the thirty-one are, on purpose, and five of those are near misses, questions the passages almost answer: a system that is never asked what it cannot answer is
  never measured on saying so.

**What is measured against it.** Recall at *k* per retriever and per slice (`measure_recall.py`);
the stop rate on the unanswerable questions and the wrong-stop rate on the rest
(`validate_judge.py`); and your own groundedness labels, which you write in
`data/answers/labels.jsonl` after `record_answers.py` has produced the answers.

**When it expires.** The chunk ids point at sections of the runbooks as they are now. Edit a
runbook and the ids may move: rerun `build_index.py` and check that every `relevant` id still
exists (`measure_recall.py` refuses to run if one does not).

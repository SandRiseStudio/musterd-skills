---
name: cross-family-review
description: Before a change merges, have it judged by a model of a different family than the one that wrote it — four questions (intent, principles, usable, feel), each answered with what the reviewer checked, and the accept or decline IS the verdict. Grades the pairing honestly — cross-family, cross-model, or same-model — and refuses to call a pairing diverse on a model nobody observed. Use when an agent's change is ready for review, when choosing who reviews it, or when a review came back as "LGTM".
---

# cross-family-review

Two agents running the same model tend to agree for the same reasons. They were
trained the same way, so they tend to share blind spots and to prefer their own
kind of answer. So when one reviews the other's work, the approval is weaker
evidence than it looks: the reviewer is likely to miss what the author missed.

The fix is not a better prompt. A stance prompt ("be critical", "you are a
security reviewer") helps least. What helps, roughly strongest
first in our experience:

1. **Different evidence.** The reviewer reads whole files and runs the thing, not
   just the diff the author chose to show.
2. **A different model.** It is the only fix for a blind spot the model family
   shares.
3. **A different stance.** It helps a little and is never enough on its own.

This skill is the second one, done carefully enough that you can trust the label
on it.

## The rule

> **Before a change merges, a model of a different family than the author's
> judges it.**
>
> **The accept or the decline is the verdict. There is no third state.**

"Approve with changes" is a decline with a note. "LGTM, one nit" is an accept.
Pick one. The change moves on the verdict, and nobody closes it separately
afterwards.

## The grade

The pairing is graded, not assumed:

| Grade | When | Counts as |
| --- | --- | --- |
| `cross_family` | different families: `claude-*` reviewing `gpt-*` | the goal |
| `cross_model` | same family, different model: `claude-opus-5` reviewing `claude-opus-4-8` | accepted; different checkpoints make different mistakes |
| `same_model` | identical after dropping a trailing date stamp | **refused**; it proves nothing |
| `human` | a person reviewed it | cross-family by construction, and reported beside the model grade, never inside it |
| *cannot tell* | either model is unknown | no grade, and no diversity claim |

**Family is the leading run of letters** in the model id: `claude-opus-5` is
`claude`, `gpt-6` is `gpt`, `grok-4` is `grok`. It is crude on purpose. A rule
you can apply by eye beats a lookup table that goes stale. Strip a provider
prefix first (`us.anthropic.claude-…`, `openai/gpt-…`): the script does not, and
would read the family as `us` or `openai`.

**A person on the team does not make the agents diverse.** One human reviewer
plus five Claude agents is still a Claude monoculture among the agents. The
human is a separate kind of review, not a diversity substitute.

## Where the model name comes from

This is the part that decides whether the grade means anything.

| Source | What it is | Trust it for a grade? |
| --- | --- | --- |
| **observed** | the harness reported which model ran: its model setting, a status line, a log | yes |
| **environment** | the runtime set it: an env var or a config the harness reads | yes |
| **declared** | the model said so, or someone typed it in | **no** |
| *unrecorded* | nobody wrote it down | **no** |

A model asked "what model are you?" often answers wrong. It names its training
predecessor, or the model its system prompt mentions. A seat's *name* is worse:
it is a label somebody chose.

> **A false "diverse" label is worse than no label.** It turns weak evidence into
> strong-looking evidence, so the reader stops discounting exactly when they
> should discount most. When either side is only declared, report the pairing as
> **diversity unverifiable**, never as diverse.

## The four questions

Each question is answered with **what you checked**, not what you concluded:

| | Asks | A bad answer | A good answer |
| --- | --- | --- | --- |
| **intent** | Does it do what was asked? | "Matches the ticket." | "The issue asked for retries on 5xx only; it also retries 409." |
| **principles** | Does it break a written rule? | "Follows conventions." | "CONTRIBUTING.md 'no silent retries on a conflict', violated at upload.ts:88." |
| **usable** | Does it work when exercised? | "Tests pass." | "Ran the upload against the stub: 3 retries on 503, and 3 on 409, which is the bug." |
| **feel** | Does it read right to a person? | "Looks good." | "Read it at phone width; the line wraps once and still reads as one thought." |

`feel` may be `n/a`, but only with the reason: "n/a: no user-facing output".

**Read whole files, not the diff.** A diff shows what changed. An omission, such
as the missing check or the caller that was never updated, shows up only in the
code around it. Reviewers who read only the diff approve omissions.

A **decline** carries a note that says what to change and where. A decline with
no note sends the author back with nothing to act on.

## The script

```sh
./review.py check <verdict.json>...    # validate a verdict and grade the pairing
./review.py grade <author> <reviewer>  # grade two model ids
./review.py template                   # a blank verdict
```

Python 3.8+, stdlib only. Exit codes:

| Exit | Meaning |
| --- | --- |
| 0 | well formed, graded `cross_family`, `cross_model` or `human` |
| 1 | refused: an answer with nothing checked behind it, a decline with no note, a third verdict, or a same-model pairing |
| 2 | the file cannot be read |
| 3 | **cannot tell**: well formed, but a model is unknown or only declared |

Exit 3 is not a pass. It is the script declining to certify a diversity claim it
cannot check, and keeping "I could not tell" apart from "it is fine". A refusal
outranks it: a verdict with an unchecked answer *and* an unverified model exits 1.

`verdicts.example.json` holds one of each: a cross-family decline with its note, a
human accept, and an accept whose reviewer model was only declared. The last one
exits 3, which is the point.

## What a file cannot do

**Nothing attests that the reviewer's model actually differed from the author's.**
The `source` field is the reviewer's own word about where the model name came
from. The script can refuse a *declared* model, but it cannot tell an honest
`observed` from a copied one. A verdict file is a claim, not a record.

It also cannot pick the reviewer. Choosing the best-graded reviewer who is
actually around right now, and not the author or someone already busy, needs a
roster of who is live on which model.

## The falsifier

Twenty-two cases run on 2026-09-29:

| Case | Expected |
| --- | --- |
| claude author, gpt reviewer, all four answered | exit 0, `cross_family` |
| `claude-opus-5` reviewing `claude-opus-4-8` | exit 0, `cross_model` |
| a human reviewer | exit 0, `human` |
| `claude-haiku-4-5-20251001` reviewing `claude-haiku-4-5` | exit 1, same model (the date stamp is dropped) |
| identical model ids | exit 1, same model |
| reviewer model `declared` | exit 3, "diversity UNVERIFIABLE" |
| reviewer source missing | exit 3, "unrecorded" |
| reviewer model `unknown` | exit 3, "cannot be graded" |
| `usable: "LGTM"` / `"not checked"` | exit 1, "a verdict with nothing behind it" |
| `usable: "tests pass"` | exit 1, "too short" (a different message) |
| `feel: "n/a"` with no reason | exit 1 |
| an answer missing | exit 1 |
| decline with no note | exit 1 |
| decline with a concrete note | exit 0 |
| `verdict: "approve-with-changes"` | exit 1, "no third state" |
| no `change` named | exit 1 |
| an unchecked answer *and* a declared model | exit 1: the refusal outranks "cannot tell" |
| an unreadable file | exit 2 |
| `grade gpt-6 claude-opus-5` / date-stamped pair / `unknown` | 0 / 1 / 3 |

---

*From the musterd team — the coordination layer where agents and humans are
peers. This skill is the practice; musterd is where it has a name, a roster, and
a record. Everything above works on one machine with no server; what a file
cannot do is attest which model actually did the review, or find the right
reviewer among the ones live now. musterd.io.*

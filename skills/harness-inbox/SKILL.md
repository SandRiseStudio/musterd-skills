---
name: harness-inbox
description: The coordination loop between agent sessions (and the person running them), minimally — a small vocabulary of acts instead of free-text chatter, the inbox checked at every task boundary, a status line on start and finish, and asks to a human that carry a tier and a clock. One append-only file on one machine, and a stdlib script whose read cursor never skips a message. Use when two or more agent sessions share a machine or a repo and need to hand work, ask for help, or ask the human something without either stalling or guessing.
---

# harness-inbox

Two agents in two terminals can already talk: each can write a file the other
reads. The trouble is that "a message" means nothing in particular. Was that a
question? Is it still open? Did anyone answer? Did the asker give up and go
ahead? Everyone reads the prose and guesses.

This skill replaces the guessing with three things:

1. **A few acts, each with one meaning**, so the kind of message is a field and
   not a tone of voice.
2. **A loop**: when to check, when to report.
3. **A clock on questions to a person**, so an agent neither waits forever on
   someone who is away nor quietly goes ahead with nothing written down.

It is the smallest version of the protocol musterd runs, and deliberately no more
than that.

## The acts

| Act | Means | Needs |
| --- | --- | --- |
| `message` | plain talk; asks nothing | — |
| `status_update` | what I am doing, or just did | — |
| `request_help` | unblock me | an answer: `accept` or `decline` |
| `handoff` | this work is yours now | an answer: `accept` or `decline` |
| `challenge` | justify this, or reconsider it | an answer, with evidence |
| `steer` | change direction; the newest steer to you replaces older ones | — |
| `ask` | a question for a **person**, with a species and a tier | an answer, or the clock runs out |
| `accept` / `decline` | answer one specific act | `--reply-to` that act; a decline says why |
| `wait` | paused; on an ask, "I'm deciding, check back" | — |
| `resolve` | this thread is **done** | `--thread` it closes |

`accept` is not "finished". Accepting a handoff means *I have it*. `resolve` is
what says the work landed. Keeping the two apart is the difference between a
thread that is taken and one that is done.

## The loop

- **Check at every task boundary**: when you start, when you finish a unit of
  work, and after a long heads-down stretch. `./inbox.py check --as you`.
- **Report on start and on finish.** A `status_update` each time. It costs one
  line, and it is how the other session knows you are not stuck.
- **Answer what is addressed to you before starting anything new.**
  `./inbox.py open --as you` lists what is still waiting on your answer.
- **Blocked? `request_help`, named.** Say what would unblock you. "Help" asks
  nothing anyone can do.

## Asking a person

An `ask` picks a **species**:

- `consult`: I would like your view.
- `escalate`: this is past me.
- `approve`: may I?

It also picks a **tier**, and the tier sets the clock:

| Tier | Clock | When it runs out |
| --- | --- | --- |
| `blocking` | none | **hold**. The asker waits, however long. Use it for the irreversible. |
| `standard` | 5 min | the asker may go ahead, and **records that it did** |
| `advisory` | 3 min | same |

Going ahead is a recorded act, not a silence:
`./inbox.py proceed --as you <ask-id> "what you did"` writes a `status_update`
tied to the ask, saying it went ahead without an answer. The person comes back to
a record of what happened, not to a mystery.

A person who replies `wait` ("deciding, back in ten") stops the clock. They are
on it, so the agent keeps waiting.

## The cursor never passes what you did not see

A long-running session can fall behind by hundreds of lines. The easy way to
catch up is to read the newest twenty and move your cursor to the end. That
silently drops everything in between, including the one question that was
addressed to you.

`check` reads **oldest first** and moves your cursor only past the lines it
actually printed. With `--limit 20`, a backlog takes several checks, each one
says how many are still waiting, and every line is reached in order.

## The script

```sh
./inbox.py send --as ada --to bo --act request_help "need the 409 fixture"
./inbox.py send --as bo  --to ada --act accept "test/stub/409.json" --reply-to A0002
./inbox.py send --as ada --to nick --act ask "retry 409s?" --species consult --tier standard
./inbox.py check   --as bo [--limit N]   # new for me, oldest first; the cursor stops where I stopped
./inbox.py open    --as bo               # directed acts still waiting on my answer   (exit 3 if any)
./inbox.py due     --as ada              # my asks whose clock has run out            (exit 3 if any)
./inbox.py proceed --as ada A0004 "surfaced 409 to the caller"
./inbox.py validate                      # every line well formed
```

`--file` points at a file other than `./INBOX.jsonl`. Each reader keeps its
cursor in `INBOX.jsonl.cursor-<name>`. Python 3.8+, stdlib only.
`INBOX.example.jsonl` is one short exchange: a status line, a request answered,
an ask whose clock ran out, the recorded proceed, and the finish.

| Exit | Meaning |
| --- | --- |
| 0 | done; or `check` ran, whether or not anything was new |
| 1 | refused: an accept of nothing, a decline with no reason, an ask with no tier, a `proceed` before the clock ran out or on a blocking ask |
| 2 | the file cannot be read, or a line in it is not JSON |
| 3 | `open` / `due`: something is waiting on you |

**Hook it in.** If your harness can run a command at the end of each turn or
before each tool call, run `./inbox.py open --as you` there and show the agent
what it prints. A rule the agent meets while it is working holds better than
one written in its instructions.

## What a file cannot do

**There is no roster, no presence, and no delivery receipt.** Nobody can tell
whether `bo` is running at all, or whether the line was read. Silence in this
file is not a recorded fact. It might mean "not yet read" or "nobody there".

**There is no attestation of who wrote a line.** `--as nick` is whatever name was
typed. An `ask` answered as `nick` might not have been answered by nick.

**It does not reach a person who is away.** The clock is honest about that: it
lets the agent move on and write down that it did. But nothing rings the
person's phone.

## The falsifier

Thirty-three cases run on 2026-09-29, in sequence, against one file:

| Case | Expected |
| --- | --- |
| `check` on an empty inbox | exit 0, "nothing new" |
| an act to yourself / an unknown act | exit 1 |
| `accept` with no `--reply-to` | exit 1, "agreement nobody asked for" |
| `accept` answering a `status_update` | exit 1, "which asks nothing" |
| `accept` of an act addressed to someone else | exit 1 |
| `decline` with no reason | exit 1 |
| `ask` with no species or tier | exit 1, both named |
| `open` with a request_help pending | exit 3 |
| `check --limit 1` on two new lines | shows the older one, "1 more waiting … nothing was skipped" |
| the next `check` | shows the second; the one after, "nothing new" |
| `open` after the accept | exit 0 |
| `proceed` before a standard ask's 300 s | exit 1, time left shown |
| `due` after 300 s | exit 3, DUE; then `proceed` records `proceeded_unanswered` |
| a blocking ask, days old | never DUE, shown HOLDING; `proceed` refused |
| an advisory ask the person answered with `wait` | DECIDING; `proceed` refused |
| `resolve` on a handoff's thread | the handoff no longer shows in `open` |
| `validate` on a clean file / a corrupt line | exit 0 / exit 2 |

---

*From the musterd team — the coordination layer where agents and humans are
peers. This skill is the practice; musterd is where it has a name, a roster, and
a record. Everything above works on one machine with no server; what a file
cannot do is say who is present, prove who wrote a line, or reach a person who
is away. musterd.io.*

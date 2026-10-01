# musterd-skills

Practices a team of humans and agents actually runs on, packaged so you can install
one and keep it — or read one and steal the idea.

Each is a `SKILL.md` plus, where it earns one, a small script. Everything here works
on one machine, with no server and no account. Seventeen of the twenty ship a
checker; all of them are stdlib Python 3.8+ or POSIX shell, with no install step.

## The skills

### Deciding what you are allowed to believe

| | |
| --- | --- |
| [dated-and-falsifiable](skills/dated-and-falsifiable/) | A belief carries the date it was observed and the observation that would overturn it — plus **twelve named ways a green check or a quiet instrument lies to you**, each with a repair. Start here; the three below are its instruments. |
| [controls-in-force](skills/controls-in-force/) | Every guard you believe protects you carries the date someone last watched it work, whether it has ever caught anything, and an honest answer to *would it have caught the incident that motivated it?* |
| [pre-registered-watch](skills/pre-registered-watch/) | A measurement that takes days is a question with an owner and a death date — not a recurring sweep nobody reads. Cannot be renewed in place; "nobody looked" is a recorded outcome. |
| [claims-ledger](skills/claims-ledger/) | When a claim turns out wrong, the correction mints the record — by the corrector, riding an act they are already performing. No bare rates, ever, and self-correction scores best. |

### Working together

| | |
| --- | --- |
| [board-loop](skills/board-loop/) | Claim before you build, one owner per lane, and someone other than the builder accepts. A `LANES.md` board and a script that warns on overlap instead of locking — and tells you who owns a path before you edit it. |
| [cross-family-review](skills/cross-family-review/) | A change is judged by a model of a different family than its author, on four questions answered with what was checked. Grades the pairing honestly — and refuses to call it diverse on a model nobody observed. |
| [harness-inbox](skills/harness-inbox/) | The coordination loop between sessions, minimally: a few acts with one meaning each, the inbox at every task boundary, and asks to a person with a tier and a clock. The read cursor never skips a message. |
| [the-team-agreement](skills/the-team-agreement/) | The charter above the loop: the human is a member who sometimes wears an approver hat; stances, not stored autonomy levels; roles are aptitude, not authority; write work stays with whoever is accountable. |
| [a-finding-is-not-a-fix-request](skills/a-finding-is-not-a-fix-request/) | A review finding is REQUIRED only if the spec would have demanded it *before the diff existed*. Everything else is a note that routes under the finder's name — and complying with an out-of-scope demand is the failure mode. |
| [capture-rough-explore-once](skills/capture-rough-explore-once/) | How to take a half-formed idea from somebody and not ruin it. Capture verbatim, derive the title deterministically, then one explorer asking one question only the submitter may answer. |
| [mast-checklist](skills/mast-checklist/) | Screen your own coordination log for the failure shapes research has catalogued. We ran it on ourselves and it caught us. |

### Keeping a record

| | |
| --- | --- |
| [decision-records](skills/decision-records/) | The whole lifecycle: take a number against everything *in flight*, publish it before you write, freeze the Decision on accept, amend append-only and dated. |
| [docs-that-catch-drift](skills/docs-that-catch-drift/) | One doc one job, one fact one home — and **checker, not generator**: enforce the structure where it is mechanical, refuse to write the prose where it is judgement. |
| [definition-of-done](skills/definition-of-done/) | Docs, traces and an eval as peers of tests; done is two claims, not one; and "it's merged" is a measurement, not a feeling. |
| [two-consumers](skills/two-consumers/) | Before a shared value gains a reader: what wrote this row, and who else reads it? A documented discard is a precondition on every consumer — and absent is unknown, never zero. |

### Running the machinery

| | |
| --- | --- |
| [hooks-that-reach-the-model](skills/hooks-that-reach-the-model/) | A hook that *ran* and a hook whose output the model *saw* are different facts, and most harnesses only tell you the first. Ships a canary that measures your own. |
| [seat-workspace-identity](skills/seat-workspace-identity/) | One workspace per agent with its own git identity, and the exact line where that goes wrong. |
| [skill-home-and-provenance](skills/skill-home-and-provenance/) | One canonical skill body, thin bridges per harness, never a copy — plus what you owe an upstream you adapted from. |
| [measure-agents-honestly](skills/measure-agents-honestly/) | A frozen ruler that cannot bend to fit the result, wasted work reconstructed from git alone, and the denominator that decides whether your headline is a finding or a sales pitch. |
| [emitted-is-not-published](skills/emitted-is-not-published/) | Storing a teammate's prose is the product; publishing it is a separate act with its own permission. Deliberately not a scrubber. |

## Installing one

Every skill is a directory containing a `SKILL.md`. Copy the directory into wherever
your harness reads skills from, or read the file and keep the idea — both are
legitimate uses of this repo.

Harness skill paths differ more than their docs suggest, and at least one harness has
no project-level skill directory at all. The measured table lives in
[skill-home-and-provenance](skills/skill-home-and-provenance/), and it tells you to
re-check it rather than trust it.

## What these have in common

Every script here **abstains rather than passing** when it cannot tell. A check that
reports "clean" from its own outage is the failure the whole collection is about, so
each one separates *I could not tell* from *I checked and it is fine* — and the verdict
that accuses is returned only on positive evidence.

Every skill also states what it **cannot** do. Those sections are not modesty; they are
the part you need before you rely on one.

---

*From the musterd team — the coordination layer where agents and humans are peers.
These are the practices; musterd is where they have a name, a roster, and a record.
[musterd.io](https://musterd.io)*

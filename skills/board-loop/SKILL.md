---
name: board-loop
description: Claim before you build, one owner per surface, and someone other than the builder accepts. A LANES.md convention plus a stdlib script that opens, claims, releases, submits, accepts and declines lanes, warns when two claimed lanes may touch the same files, and tells you who owns a path before you edit it. Use when two or more agents (or an agent and a person) work in one repo, when work is being duplicated or thrown away, or when "done" keeps meaning "I think I finished".
---

# board-loop

Put three agents on one repo with a list of tasks and they will each read the
list, each pick the most obvious task, and each build it. Two of those three
changes get thrown away. Nobody did anything wrong; they all read the same list.

A task list is a menu. What stops the collision is a **claim**: a line that says
*this work is mine, and these are the files it touches*, written *before* anyone
starts editing.

## The loop

1. **Look at the board.** `./lanes.py board`. Review debt comes first, because
   work waiting for acceptance is work that is finished but not yet trusted.
2. **Claim one lane before you touch the code.** `./lanes.py claim L-004 --as you`,
   or `open "<title>" --surface <globs> --claim --as you` if it is not on the
   board. Reading the board is not claiming.
3. **Build only inside your surface.** Before editing a file you are unsure about,
   `./lanes.py who <path>`.
4. **Submit with evidence.** `./lanes.py submit L-004 --as you --evidence "PR #9 @ abc123"`.
   Evidence is what landed, not "done".
5. **Someone else accepts.** They judge the landed outcome, not your intentions:
   `accept`, or `decline --note "<what to change, where>"`, which sends it back to
   you.
6. **Stopped carrying it? Release it.** `./lanes.py release L-004 --as you`. A
   claimed lane nobody is working on reserves work nobody is doing. Releasing is
   not failing; it is the honest state of the board.

## The rules, and why each one

**One owner per lane.** A claim on a lane someone else holds is refused. Take a
different lane, or ask them to hand it off. "We both own it" means nobody is
accountable for the merge.

**Every lane names its surface**, the globs of the files it owns. Without one, you
cannot tell two lanes apart, and `who` has nothing to answer with.

**Overlap is a warning, never a lock.** When a claim may touch files another
claimed lane covers, the script says so and still lets you claim:

```
WARNING: L-002 (src/upload/*.test.ts) may overlap L-001 owned by ada (src/upload/**)
-- talk to them before you edit it
```

A lock would be wrong half the time, because globs overlap on paper far more often
than edits collide in practice. A warning at claim time costs a message. A
collision found at merge time costs one person's afternoon.

**The builder does not accept their own work.** `accept` on your own lane is
refused. When nobody else can accept it, `accept --self` is allowed and writes
`unconfirmed: yes` on the lane, so the board keeps two kinds of *done* apart: the
kind someone else checked, and the kind that is only the builder's word. Removing
that line by hand makes `check` fail.

**A decline carries a note.** Declining with nothing to act on is refused. A
declined lane goes back to `claimed`, with its owner and the note.

**Moves carry a name.** Every move takes `--as`. A move with no name is a move
nobody made.

## The file

```markdown
## L-003 Rate-limit the export endpoint
- state: claimed
- owner: claude-a
- surface: src/api/export.ts
- story: Exports stop timing out for everyone when one team exports a year of data
```

States: `open` → `claimed` → `awaiting_acceptance` → `done`, or back to `claimed`
on a decline, or back to `open` on a release. `abandoned` is for work nobody will
do. `story` is optional: one line an outsider would understand.

Everything outside the `## L-nnn` sections, and any line in a section the script
does not recognise, is kept as written. Edit by hand if you like, and run
`check` afterwards. The script refuses to move anything on a board that fails
`check`, so a bad hand edit is caught at the next move, not at merge time.
`LANES.example.md` is a board with one lane in each state.

## The script

```sh
./lanes.py board                        # review debt first, then in progress, then open
./lanes.py check                        # validate; prints overlaps as WARNINGs
./lanes.py who src/api/export.ts        # which claimed lane covers this path
./lanes.py open "<title>" --surface "src/a.ts,src/b/**" [--claim --as you]
./lanes.py claim | release  <id> --as you
./lanes.py submit  <id> --as you --evidence "PR #9 @ abc123"
./lanes.py accept  <id> --as them [--self]
./lanes.py decline <id> --as them --note "what to change, where"
```

`--file` points at a board other than `./LANES.md`. Python 3.8+, stdlib only.
Writes are atomic: a crash mid-write leaves the old file, never half of one.

| Exit | Meaning |
| --- | --- |
| 0 | done, or the board is valid (warnings do not change this) |
| 1 | refused: a rule stops the move, or `check` found the board invalid |
| 2 | the file is missing or unreadable, or the command is malformed |
| 3 | `who`: **nobody has claimed this path**, which is not the same as "you may edit it" |

**Hook it in.** An agent that ignores "claim before you build" in its
instructions cannot ignore a tool call that fails. If your harness runs a command
before each edit, run `./lanes.py who "$FILE"` there and show the output to the
agent. That turns the rule into something the agent meets at the moment it acts.

## What a file cannot do

**Nothing stops two sessions claiming the same lane.** Both read the file, both
see `open`, both write `claimed`. The second write wins and the first owner never
finds out. The script narrows this window and cannot close it: there is one file,
no identity, and no gate. `--as` is whatever name you type.

The same goes for the acceptor. `accept --as nick` does not mean nick accepted
it. It means somebody typed "nick".

## The falsifier

Twenty-seven cases run on 2026-09-29, in sequence, against one board:

| Case | Expected |
| --- | --- |
| a move on a board that does not exist | exit 2, "`open` creates it" |
| `open` with no `--surface` | exit 1 |
| claiming a lane whose surface may overlap a claimed one | exit 0, WARNING naming the other owner |
| claiming a lane someone else owns | exit 1, "take a different lane, or ask them to hand it off" |
| any move with no `--as` | exit 1, "a move nobody made" |
| `who` on a path two claimed lanes cover | exit 0, both owners listed |
| `who` on an unclaimed path | exit 3 |
| releasing someone else's lane | exit 1 |
| `submit --evidence none` | exit 1 |
| accepting your own lane | exit 1, pointing at `--self` |
| `accept --self` | exit 0, lane written `unconfirmed: yes` |
| declining with a note under 16 characters | exit 1 |
| declining with a note | exit 0, lane back to its owner, note recorded |
| resubmit after a decline, accepted by someone else | exit 0, `done` |
| a hand-edited self-accept with no `unconfirmed: yes` | `check` exit 1 |
| any move on a board that fails `check` | exit 1, "fix it first" |

---

*From the musterd team — the coordination layer where agents and humans are
peers. This skill is the practice; musterd is where it has a name, a roster, and
a record. Everything above works on one machine with no server; what a file
cannot do is stop two sessions claiming the same lane, or prove who accepted it.
musterd.io.*

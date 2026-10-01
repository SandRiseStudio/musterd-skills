#!/usr/bin/env python3
"""An inbox two sessions on one machine can share: the acts, the loop, and the ask clock.

    ./inbox.py [--file INBOX.jsonl] send --as <me> --to <name|@team> --act <act> "<body>"
                                         [--reply-to <id>] [--thread <id>]
                                         [--species consult|escalate|approve --tier advisory|standard|blocking]
    ./inbox.py [--file INBOX.jsonl] check --as <me> [--limit N]   what is new for me, oldest first
    ./inbox.py [--file INBOX.jsonl] open  --as <me>               directed acts still waiting on my answer
    ./inbox.py [--file INBOX.jsonl] due   --as <me>               my asks whose clock has run out
    ./inbox.py [--file INBOX.jsonl] proceed --as <me> <ask-id> "<what you did>" --risk "<what could go wrong>"
    ./inbox.py [--file INBOX.jsonl] validate                      check every line

Exit 0 on success, 1 when a rule refuses the send, 2 when the file cannot be read or
the command is malformed. `check` exits 0 whether or not anything was new; `open` and
`due` exit 3 when something is waiting, so a hook can branch on it. Python 3.8+,
stdlib only.

THE CURSOR NEVER PASSES WHAT YOU DID NOT SEE. `check` reads the OLDEST unread lines
first and advances your cursor only past the lines it printed. With --limit, a deep
backlog takes several checks and reaches every line in order; it never jumps to the
newest and skips the middle.
"""

import json
import os
import re
import sys
import time

ACTS = ("message", "status_update", "request_help", "handoff", "accept", "decline",
        "wait", "resolve", "steer", "challenge", "ask")
ANSWERABLE = ("request_help", "handoff", "challenge", "ask")
ANSWERS = ("accept", "decline", "resolve", "wait")
SPECIES = ("consult", "escalate", "approve")
# The tier owns the clock. Blocking holds: the asker waits, however long. Below it,
# the asker proceeds when the clock runs out -- and writes down that it did.
TIER_SECONDS = {"advisory": 180, "standard": 300, "blocking": None}
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
NEGATION = re.compile(r"^\W*(none|n/?a|tbd|todo|nothing|ok|-+)\W*$", re.I)


class Refused(Exception):
    pass


def good_ts(row):
    """A timestamp is whole seconds since the epoch. Anything else, the clock cannot be read."""
    ts = row.get("ts")
    return isinstance(ts, int) and not isinstance(ts, bool) and ts >= 0


def load(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                raise ValueError("line %d is not JSON" % n)
    return rows


def append(path, row):
    # One write per line, opened for append: on a local filesystem a short line lands whole.
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def cursor_path(path, me):
    return "%s.cursor-%s" % (path, me)


def read_cursor(path, me):
    try:
        with open(cursor_path(path, me), encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def write_cursor(path, me, n):
    tmp = cursor_path(path, me) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(n))
    os.replace(tmp, cursor_path(path, me))


def for_me(row, me):
    return row.get("from") != me and row.get("to") in (me, "@team")


def by_id(rows):
    return {r.get("id"): r for r in rows}


def answered(rows, target):
    """The act that settled `target`, or None. A `wait` on an ask is a 'deciding' reply:
    it stops the clock but does not settle the ask."""
    for r in rows:
        if r.get("reply_to") == target.get("id") and r.get("act") in ("accept", "decline", "resolve"):
            return r
        if r.get("act") == "resolve" and r.get("thread") in (target.get("id"), target.get("thread")) \
                and r.get("thread"):
            return r
        if r.get("act") == "status_update" and (r.get("meta") or {}).get("ask_ref") == target.get("id"):
            return r
    return None


def deciding(rows, ask):
    return any(r.get("act") == "wait" and r.get("reply_to") == ask.get("id") for r in rows)


def problems(row, rows_before):
    errs = []
    for k in ("id", "ts", "from", "to", "act", "body"):
        if row.get(k) in (None, ""):
            errs.append("%s is missing" % k)
    if row.get("ts") not in (None, "") and not good_ts(row):
        errs.append("ts %r is not whole seconds since the epoch" % (row.get("ts"),))
    if row.get("act") not in ACTS:
        errs.append("act %r is not one of %s" % (row.get("act"), ", ".join(ACTS)))
    to = row.get("to")
    if to and to != "@team" and not NAME.match(to):
        errs.append("to %r is not a name or @team" % to)
    if row.get("from") and not NAME.match(row["from"]):
        errs.append("from %r is not a name" % row["from"])
    if row.get("from") and row.get("from") == to:
        errs.append("an act to yourself is a note, not coordination")
    act, meta = row.get("act"), row.get("meta") or {}
    known = by_id(rows_before)
    if act in ("accept", "decline"):
        ref = known.get(row.get("reply_to"))
        if ref is None:
            errs.append("%s must name the act it answers with --reply-to; an accept of nothing "
                        "is agreement nobody asked for" % act)
        elif ref.get("act") not in ANSWERABLE:
            errs.append("%s answers a %s, which asks nothing" % (act, ref.get("act")))
        elif ref.get("to") not in (row.get("from"), "@team"):
            errs.append("%s answers an act addressed to %s, not you" % (act, ref.get("to")))
    if act == "decline" and len((row.get("body") or "").strip()) < 12:
        errs.append("a decline says why -- the asker needs it to route elsewhere")
    if act == "resolve" and not row.get("thread") and not row.get("reply_to"):
        errs.append("resolve closes a thread: name it with --thread or --reply-to")
    if act == "ask":
        if meta.get("species") not in SPECIES:
            errs.append("an ask needs --species (%s)" % ", ".join(SPECIES))
        if meta.get("tier") not in TIER_SECONDS:
            errs.append("an ask needs --tier (%s): the tier owns the clock" % ", ".join(TIER_SECONDS))
    if act == "status_update" and meta.get("ask_outcome") == "proceeded_unanswered":
        if meta.get("risk_accepted") is not True:
            errs.append("proceeding without an answer accepts a risk: meta.risk_accepted must be true")
        for k in ("risk", "chosen_approach"):
            if not str(meta.get(k) or "").strip():
                errs.append("proceeding without an answer records meta.%s" % k)
    if act == "wait" and row.get("reply_to") and row.get("reply_to") not in known:
        errs.append("wait names an act that is not in the inbox")
    if row.get("body") and NEGATION.match(row["body"]) and act not in ("accept", "wait"):
        errs.append("body %r says nothing" % row["body"])
    return errs


def show(row, rows=None):
    meta = row.get("meta") or {}
    extra = ""
    if row.get("act") == "ask":
        extra = " [%s/%s]" % (meta.get("species"), meta.get("tier"))
    if row.get("reply_to"):
        extra += " (re %s)" % row["reply_to"]
    when = time.strftime("%H:%M", time.localtime(row["ts"])) if good_ts(row) else "??:??"
    return "%s %s  %s -> %s  %s%s: %s" % (row.get("id"), when, row.get("from"), row.get("to"),
                                          row.get("act"), extra, row.get("body"))


def parse_argv(argv):
    opts, args, i = {"file": "INBOX.jsonl"}, [], 0
    valued = {"--file": "file", "--as": "as", "--to": "to", "--act": "act", "--reply-to": "reply_to",
              "--thread": "thread", "--species": "species", "--tier": "tier", "--limit": "limit",
              "--risk": "risk"}
    while i < len(argv):
        a = argv[i]
        if a in valued:
            if i + 1 >= len(argv):
                raise Refused("%s needs a value" % a)
            opts[valued[a]] = argv[i + 1]
            i += 1
        else:
            args.append(a)
        i += 1
    return opts, args


def new_id(rows):
    return "A%04d" % (len(rows) + 1)


def main(argv):
    try:
        opts, args = parse_argv(argv[1:])
    except Refused as e:
        print(e, file=sys.stderr)
        return 2
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if args else 2
    cmd, args = args[0], args[1:]
    path, me = opts["file"], opts.get("as")
    try:
        rows = load(path)
    except (OSError, ValueError) as e:
        print("cannot read %s: %s" % (path, e), file=sys.stderr)
        return 2
    if cmd != "validate" and not me:
        print("%s needs --as <name>" % cmd, file=sys.stderr)
        return 2

    if cmd == "validate":
        bad = 0
        for i, row in enumerate(rows):
            for e in problems(row, rows[:i]):
                bad += 1
                print("%s: %s" % (row.get("id", "line %d" % (i + 1)), e))
        print("ok -- %d acts" % len(rows) if not bad else "%d problem(s)" % bad)
        return 1 if bad else 0

    if cmd in ("send", "proceed"):
        if cmd == "proceed":
            if len(args) != 2:
                print("proceed needs <ask-id> \"<what you did>\" --risk \"<what could go wrong>\"",
                      file=sys.stderr)
                return 2
            ask = by_id(rows).get(args[0])
            try:
                if not ask or ask.get("act") != "ask" or ask.get("from") != me:
                    raise Refused("%s is not an ask you sent" % args[0])
                if answered(rows, ask):
                    raise Refused("%s was answered -- act on the answer" % args[0])
                limit = TIER_SECONDS[ask["meta"]["tier"]]
                if limit is None:
                    raise Refused("%s is blocking: it holds until a person answers. Proceeding is "
                                  "not yours to decide" % args[0])
                if not good_ts(ask):
                    raise Refused("%s has no readable ts, so its clock cannot be read -- "
                                  "run validate" % args[0])
                if not (opts.get("risk") or "").strip():
                    raise Refused("going ahead without an answer accepts a risk: name it with "
                                  "--risk \"<what could go wrong>\"")
                if deciding(rows, ask):
                    raise Refused("%s has a 'deciding' reply -- the person is on it; wait" % args[0])
                left = ask["ts"] + limit - time.time()
                if left > 0:
                    raise Refused("%s's clock has %ds left" % (args[0], int(left)))
            except Refused as e:
                print("REFUSED: %s" % e, file=sys.stderr)
                return 1
            row = {"id": new_id(rows), "ts": int(time.time()), "from": me, "to": ask["to"],
                   "act": "status_update", "body": "proceeded without an answer: " + args[1],
                   "meta": {"ask_ref": ask["id"], "ask_outcome": "proceeded_unanswered",
                            "risk_accepted": True, "risk": opts["risk"].strip(),
                            "chosen_approach": args[1]},
                   "thread": ask.get("thread") or ask["id"]}
        else:
            if len(args) != 1:
                print("send needs exactly one body argument", file=sys.stderr)
                return 2
            row = {"id": new_id(rows), "ts": int(time.time()), "from": me, "to": opts.get("to"),
                   "act": opts.get("act"), "body": args[0]}
            for k in ("reply_to", "thread"):
                if opts.get(k):
                    row[k] = opts[k]
            if row.get("reply_to") and not row.get("thread"):
                ref = by_id(rows).get(row["reply_to"])
                if ref:
                    row["thread"] = ref.get("thread") or ref["id"]
            if opts.get("species") or opts.get("tier"):
                row["meta"] = {"species": opts.get("species"), "tier": opts.get("tier")}
        errs = problems(row, rows)
        if errs:
            for e in errs:
                print("REFUSED: %s" % e, file=sys.stderr)
            return 1
        append(path, row)
        print("sent %s" % row["id"])
        if row["act"] == "ask":
            t = TIER_SECONDS[row["meta"]["tier"]]
            print("  blocking: HOLD until answered" if t is None else
                  "  %s: if nobody answers in %ds, `proceed` and record what you did" % (row["meta"]["tier"], t))
        return 0

    if cmd == "check":
        start = read_cursor(path, me)
        pending = [(i, r) for i, r in enumerate(rows) if i >= start]
        try:
            limit = int(opts.get("limit") or 0)
        except ValueError:
            print("--limit takes a number", file=sys.stderr)
            return 2
        shown_to = len(rows)
        mine = [(i, r) for i, r in pending if for_me(r, me)]
        if limit and len(mine) > limit:
            mine = mine[:limit]
            shown_to = mine[-1][0] + 1  # stop the cursor at the last line shown, never past it
        for _, r in mine:
            print(show(r))
        left = sum(1 for i, r in enumerate(rows) if i >= shown_to and for_me(r, me))
        if not mine:
            print("nothing new")
        elif left:
            print("… %d more waiting -- check again; nothing was skipped" % left)
        write_cursor(path, me, shown_to)
        return 0

    if cmd == "open":
        waiting = [r for r in rows if r.get("act") in ANSWERABLE and r.get("to") in (me, "@team")
                   and r.get("from") != me and not answered(rows, r)]
        for r in waiting:
            print(show(r))
        if not waiting:
            print("nothing waiting on you")
        return 3 if waiting else 0

    if cmd == "due":
        now, due = time.time(), []
        for r in rows:
            if r.get("act") != "ask" or r.get("from") != me or answered(rows, r):
                continue
            t = TIER_SECONDS.get((r.get("meta") or {}).get("tier"))
            if t is None:
                print("HOLDING  %s (blocking -- no clock; it waits for a person)" % show(r))
            elif not good_ts(r):
                print("UNREADABLE %s (ts is not a timestamp -- run validate; not counted as due)"
                      % show(r))
            elif deciding(rows, r):
                print("DECIDING %s (a person said they are on it)" % show(r))
            elif now >= r["ts"] + t:
                due.append(r)
                print("DUE      %s -- `proceed %s \"<what you did>\" --risk \"<what could go wrong>\"`"
                      % (show(r), r["id"]))
        if not due:
            print("no ask has run out its clock")
        return 3 if due else 0

    print("unknown command %r" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

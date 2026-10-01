#!/usr/bin/env python3
"""A lane board in one Markdown file: claim before you build, one owner per lane,
someone else accepts.

    ./lanes.py [--file LANES.md] check                 validate the board
    ./lanes.py [--file LANES.md] board                 render it, review debt first
    ./lanes.py [--file LANES.md] who <path>            which claimed lane covers a path
    ./lanes.py [--file LANES.md] open "<title>" --scope <glob>[,<glob>...] [--claim --as <name>]
    ./lanes.py [--file LANES.md] claim <id> --as <name>
    ./lanes.py [--file LANES.md] release <id> --as <name>
    ./lanes.py [--file LANES.md] submit <id> --as <name> --evidence "<PR / commit / link>"
    ./lanes.py [--file LANES.md] accept <id> --as <name> [--self]
    ./lanes.py [--file LANES.md] decline <id> --as <name> --note "<what to change>"

Exit 0 on success, 1 when a rule refuses the move or the board is invalid, 2 when
the file cannot be read or the command is malformed. `who` exits 3 when no claimed
lane covers the path: "nobody owns this", which is not the same as "you own it".
Overlap between claimed lanes is printed as a WARNING and never changes the exit
code: it is a prompt to talk, not a lock. Python 3.8+, stdlib only.

THE FILE. One `## <id> <title>` heading per lane, then `- key: value` lines:
state, owner, scope, and -- as the lane moves -- evidence, accepted_by, note.
Anything else in the file (a preamble, your own notes) is kept as written.
"""

import os
import re
import sys
import tempfile

STATES = ("open", "claimed", "awaiting_acceptance", "done", "abandoned")
KEYS = ("state", "owner", "scope", "story", "evidence", "accepted_by", "unconfirmed", "note")
HEAD = re.compile(r"^## (L-\d+)\s+(.+?)\s*$")
FIELD = re.compile(r"^- ([a-z_]+):\s*(.*?)\s*$")
NEGATION = re.compile(r"^\W*(none|n/?a|tbd|todo|nothing|-+)\W*$", re.I)
PREAMBLE = "# Lanes\n\nOne lane per unit of work. Claim before you build; someone else accepts.\n"


class Refused(Exception):
    pass


# ---------- parsing ----------------------------------------------------------------------

def parse(text):
    """(preamble, [lane]) where a lane is {id, title, fields, extra} in file order."""
    lines = text.splitlines()
    pre, lanes, cur = [], [], None
    for line in lines:
        h = HEAD.match(line)
        if h:
            cur = {"id": h.group(1), "title": h.group(2), "fields": {}, "extra": []}
            lanes.append(cur)
            continue
        if cur is None:
            pre.append(line)
            continue
        f = FIELD.match(line)
        if f and f.group(1) in KEYS and f.group(1) not in cur["fields"]:
            cur["fields"][f.group(1)] = f.group(2)
        elif line.strip():
            cur["extra"].append(line)
    return "\n".join(pre).rstrip() + "\n", lanes


def render_file(pre, lanes):
    out = [pre.rstrip(), ""]
    for l in lanes:
        out.append("## %s %s" % (l["id"], l["title"]))
        for k in KEYS:
            if l["fields"].get(k):
                out.append("- %s: %s" % (k, l["fields"][k]))
        out.extend(l["extra"])
        out.append("")
    return "\n".join(out)


def scopes(lane):
    return [s.strip() for s in lane["fields"].get("scope", "").split(",") if s.strip()]


# ---------- globs --------------------------------------------------------------------------

def glob_re(glob):
    """`**` spans directories, `*` and `?` stay inside one path segment."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile("^" + out + "$")


def literal_prefix(glob):
    """The part of the glob before its first wildcard."""
    m = re.search(r"[*?\[]", glob)
    return glob if m is None else glob[: m.start()]


def may_overlap(a, b):
    """True when some path could match both globs. Errs toward True: a false warning costs a
    message, a missed one costs a collision."""
    pa, pb = literal_prefix(a), literal_prefix(b)
    if glob_re(a).match(pb) or glob_re(b).match(pa):
        return True
    return pa.startswith(pb) or pb.startswith(pa)


def overlaps(lanes, lane):
    """[(other lane, glob pair)] for every claimed-or-awaiting lane whose scope may overlap."""
    found = []
    for o in lanes:
        if o is lane or o["fields"].get("state") not in ("claimed", "awaiting_acceptance"):
            continue
        for a in scopes(lane):
            for b in scopes(o):
                if may_overlap(a, b):
                    found.append((o, a, b))
    return found


# ---------- validation ---------------------------------------------------------------------

def problems(lanes):
    errs, seen = [], set()
    for l in lanes:
        f, lid = l["fields"], l["id"]
        if lid in seen:
            errs.append("%s: the id is used twice" % lid)
        seen.add(lid)
        st = f.get("state")
        if st not in STATES:
            errs.append("%s: state %r is not one of %s" % (lid, st, ", ".join(STATES)))
            continue
        if not scopes(l):
            errs.append("%s: no scope -- a lane with no scope cannot be told apart from any other" % lid)
        if st in ("claimed", "awaiting_acceptance", "done") and not f.get("owner"):
            errs.append("%s: %s with no owner" % (lid, st))
        if st == "open" and f.get("owner"):
            errs.append("%s: open but names an owner -- release clears the owner" % lid)
        if st in ("awaiting_acceptance", "done"):
            ev = f.get("evidence", "")
            if not ev or NEGATION.match(ev):
                errs.append("%s: %s with no evidence of what landed" % (lid, st))
        if st == "done":
            by = f.get("accepted_by")
            if not by:
                errs.append("%s: done with no accepted_by" % lid)
            elif by == f.get("owner") and f.get("unconfirmed") != "yes":
                errs.append("%s: accepted by its own owner but not marked `unconfirmed: yes`" % lid)
    return errs


# ---------- moves --------------------------------------------------------------------------

def find(lanes, lid):
    for l in lanes:
        if l["id"] == lid:
            return l
    raise Refused("%s: no such lane" % lid)


def need_state(l, *states):
    st = l["fields"].get("state")
    if st not in states:
        raise Refused("%s is %s; this move needs %s" % (l["id"], st, " or ".join(states)))


def need_owner(l, name):
    if l["fields"].get("owner") != name:
        raise Refused("%s is owned by %s, not %s" % (l["id"], l["fields"].get("owner"), name))


def warn_overlaps(lanes, l):
    for o, a, b in overlaps(lanes, l):
        print("WARNING: %s (%s) may overlap %s owned by %s (%s) -- talk to them before you edit it"
              % (l["id"], a, o["id"], o["fields"].get("owner"), b), file=sys.stderr)


def do_claim(lanes, l, name):
    need_state(l, "open")
    l["fields"]["state"], l["fields"]["owner"] = "claimed", name
    warn_overlaps(lanes, l)


def move(lanes, cmd, args, opts):
    name = opts.get("as")
    if cmd != "open" and not args:
        raise Refused("%s needs a lane id" % cmd)
    if cmd in ("claim", "release", "submit", "accept", "decline") and not name:
        raise Refused("%s needs --as <name>: a move with no name is a move nobody made" % cmd)
    if cmd == "open":
        if not args:
            raise Refused("open needs a title")
        if not opts.get("scope"):
            raise Refused("open needs --scope: which files does this lane own?")
        nums = [int(l["id"][2:]) for l in lanes]
        l = {"id": "L-%03d" % (max(nums, default=0) + 1), "title": args[0],
             "fields": {"state": "open", "scope": opts["scope"]}, "extra": []}
        lanes.append(l)
        if opts.get("claim"):
            if not name:
                raise Refused("--claim needs --as <name>")
            do_claim(lanes, l, name)
        return "%s opened%s" % (l["id"], " and claimed by %s" % name if opts.get("claim") else "")
    l = find(lanes, args[0])
    f = l["fields"]
    if cmd == "claim":
        if f.get("state") == "claimed" and f.get("owner") != name:
            raise Refused("%s is already claimed by %s -- take a different lane, or ask them to hand it off"
                          % (l["id"], f.get("owner")))
        do_claim(lanes, l, name)
        return "%s claimed by %s" % (l["id"], name)
    if cmd == "release":
        need_state(l, "claimed")
        need_owner(l, name)
        f["state"] = "open"
        f.pop("owner", None)
        return "%s released -- back on the board" % l["id"]
    if cmd == "submit":
        need_state(l, "claimed")
        need_owner(l, name)
        ev = opts.get("evidence", "")
        if len(ev.strip()) < 6 or NEGATION.match(ev):
            raise Refused("submit needs --evidence naming what landed: a PR, a commit, a link")
        f["state"], f["evidence"] = "awaiting_acceptance", ev
        return "%s submitted -- now someone other than %s accepts it" % (l["id"], name)
    if cmd == "accept":
        need_state(l, "awaiting_acceptance")
        if name == f.get("owner"):
            if not opts.get("self"):
                raise Refused("%s is yours: someone else accepts it. If nobody else can, "
                              "`accept --self` records it as unconfirmed" % l["id"])
            f["unconfirmed"] = "yes"
        f["state"], f["accepted_by"] = "done", name
        return "%s done, accepted by %s%s" % (l["id"], name, " (unconfirmed)" if opts.get("self") else "")
    if cmd == "decline":
        need_state(l, "awaiting_acceptance")
        note = opts.get("note", "")
        if len(note.strip()) < 16 or NEGATION.match(note):
            raise Refused("decline needs --note saying what to change, and where")
        if name == f.get("owner"):
            raise Refused("you cannot decline your own lane -- release it or keep working")
        f["state"], f["note"] = "claimed", "declined by %s: %s" % (name, note)
        return "%s sent back to %s" % (l["id"], f.get("owner"))
    raise Refused("unknown command %r" % cmd)


# ---------- views --------------------------------------------------------------------------

def board(lanes):
    order = [("awaiting_acceptance", "Waiting for someone to accept (review debt first)"),
             ("claimed", "In progress"), ("open", "Open -- claim one before you build")]
    out = []
    for st, label in order:
        rows = [l for l in lanes if l["fields"].get("state") == st]
        if not rows:
            continue
        out.append(label)
        for l in rows:
            who = l["fields"].get("owner", "")
            out.append("  %s  %-40s %-12s %s" % (l["id"], l["title"][:40], who, ", ".join(scopes(l))))
            if st == "awaiting_acceptance":
                out.append("        evidence: %s" % l["fields"].get("evidence"))
        out.append("")
    done = sum(l["fields"].get("state") == "done" for l in lanes)
    unconf = sum(l["fields"].get("unconfirmed") == "yes" for l in lanes)
    out.append("done: %d%s" % (done, " (%d unconfirmed)" % unconf if unconf else ""))
    return "\n".join(out)


def who(lanes, path):
    owners = [l for l in lanes if l["fields"].get("state") in ("claimed", "awaiting_acceptance")
              and any(glob_re(g).match(path) for g in scopes(l))]
    return owners


# ---------- main ---------------------------------------------------------------------------

def parse_argv(argv):
    opts, args, i = {"file": "LANES.md"}, [], 0
    flags = {"--self": "self", "--claim": "claim"}
    valued = {"--file": "file", "--as": "as", "--scope": "scope", "--evidence": "evidence", "--note": "note"}
    while i < len(argv):
        a = argv[i]
        if a in flags:
            opts[flags[a]] = True
        elif a in valued:
            if i + 1 >= len(argv):
                raise Refused("%s needs a value" % a)
            opts[valued[a]] = argv[i + 1]
            i += 1
        else:
            args.append(a)
        i += 1
    return opts, args


def write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".lanes-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


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
    path = opts["file"]
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                pre, lanes = parse(f.read())
        except OSError as e:
            print("cannot read %s: %s" % (path, e), file=sys.stderr)
            return 2
    elif cmd == "open":
        pre, lanes = PREAMBLE, []
    else:
        print("%s does not exist -- `open` creates it" % path, file=sys.stderr)
        return 2

    if cmd == "check":
        errs = problems(lanes)
        for e in errs:
            print("INVALID: %s" % e)
        for l in lanes:
            if l["fields"].get("state") == "claimed":
                for o, a, b in overlaps(lanes, l):
                    if o["id"] > l["id"]:
                        print("WARNING: %s (%s) may overlap %s (%s)" % (l["id"], a, o["id"], b))
        if not errs:
            print("ok -- %d lanes" % len(lanes))
        return 1 if errs else 0
    if cmd == "board":
        print(board(lanes))
        return 0
    if cmd == "who":
        if not args:
            print("who needs a path", file=sys.stderr)
            return 2
        owners = who(lanes, args[0])
        if not owners:
            print("nobody has claimed %s -- claim a lane that covers it before you edit it" % args[0])
            return 3
        for l in owners:
            print("%s  %s  owned by %s" % (l["id"], l["title"], l["fields"].get("owner")))
        return 0
    try:
        errs = problems(lanes)
        if errs:
            raise Refused("the board is already invalid; fix it first (`check`):\n  " + "\n  ".join(errs))
        msg = move(lanes, cmd, args, opts)
    except Refused as e:
        print("REFUSED: %s" % e, file=sys.stderr)
        return 1
    write_atomic(path, render_file(pre, lanes))
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

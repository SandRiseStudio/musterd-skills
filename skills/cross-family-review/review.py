#!/usr/bin/env python3
"""Check a cross-family review verdict -- and grade the pairing without flattering it.

    ./review.py check <verdict.json>...   validate one or more verdicts
    ./review.py grade <author> <reviewer> grade two model ids
    ./review.py template                  print a blank verdict

Exit 0 when every verdict is well formed AND its pairing is graded cross-family or
cross-model; 1 when one is refused; 2 when the input cannot be read; 3 when the
verdict is well formed but the pairing CANNOT BE GRADED -- a model the reviewer only
declared, or one nobody recorded. Exit 3 is "cannot tell", never a pass: a review
flagged diverse on a declared model converts weak evidence into strong-looking
evidence, which is worse than no flag at all. Python 3.8+, stdlib only.

THE GRADE. Family is the leading run of letters in the model id (claude-opus-5 ->
claude, gpt-6 -> gpt). Different families -> cross_family; same family, different
model -> cross_model; identical after trimming one trailing 8-digit date stamp ->
same_model, which proves nothing and is refused. A human reviewer grades `human`:
cross-family by construction, and it rides beside the model grade, never inside it.

THE VERDICT. Four questions -- intent, principles, usable, feel -- each answered with
what the reviewer CHECKED, not what they concluded. `feel` may be "n/a" only with a
reason (no user-facing surface in the change). The accept or decline IS the verdict;
there is no separate close. A decline carries a concrete note: what to change, where.
"""

import json
import re
import sys

QUESTIONS = ("intent", "principles", "usable", "feel")
VERDICTS = ("accept", "decline")
SOURCES = ("observed", "environment", "declared")
DATE_STAMP = re.compile(r"-\d{8}$")
NEGATION = re.compile(
    r"^\W*(none|n/?a|tbd|todo|nothing|lgtm|looks good|ok|fine|yes|no|not (?:checked|run|yet))\W*$",
    re.I,
)
NA = re.compile(r"^\W*n/?a\b", re.I)

TEMPLATE = {
    "change": "what was reviewed -- a PR, a commit range, a file",
    "author": {"model": "claude-opus-5", "source": "observed"},
    "reviewer": {"model": "gpt-6", "source": "observed"},
    "verdict": "accept",
    "answers": {
        "intent": "what you compared the change against, and what matched or did not",
        "principles": "which written rule you checked it against, and the result",
        "usable": "what you ran or exercised, and what it did",
        "feel": "what you looked at -- or 'n/a: <why there is no surface>'",
    },
    "note": "for a decline: what to change, and where",
}


def normalize(model):
    m = (model or "").strip().lower()
    if not m or m == "unknown":
        return None
    return DATE_STAMP.sub("", m)


def family(model):
    m = normalize(model)
    if m is None:
        return None
    match = re.match(r"[a-z]+", m)
    return match.group(0) if match else None


def grade(author, reviewer):
    """cross_family | cross_model | same_model, or None when either side is unknown."""
    a, r = normalize(author), normalize(reviewer)
    if a is None or r is None:
        return None
    if family(a) != family(r):
        return "cross_family"
    return "cross_model" if a != r else "same_model"


def evidence_problem(field, value):
    v = (value or "").strip() if isinstance(value, str) else ""
    if not v:
        return "%s is missing. Answer with what you checked, not what you concluded." % field
    if field == "feel" and NA.match(v):
        reason = NA.sub("", v, count=1).strip(" :-—")
        if len(reason) < 8:
            return "feel says n/a with no reason. Name why there is no surface to judge " \
                   "(no UI, no copy, no output a person reads)."
        return None
    if NEGATION.match(v):
        return "%s is a verdict with nothing behind it (%r). Name the command, the file, " \
               "or the thing you exercised." % (field, v[:40])
    if len(v) < 16:
        return "%s is too short to be something the next reader can repeat (%r)." % (field, v[:40])
    return None


def side(v, who):
    """(model, source, is_human, problems)."""
    probs = []
    s = v.get(who)
    if not isinstance(s, dict):
        return None, None, False, ["%s is missing: {\"model\": ..., \"source\": ...} or {\"human\": true}" % who]
    if s.get("human") is True:
        return None, "human", True, probs
    model, source = s.get("model"), s.get("source")
    if source is not None and source not in SOURCES:
        probs.append("%s.source %r is not one of %s" % (who, source, ", ".join(SOURCES)))
    return model, source, False, probs


def check(v):
    """(errors, abstain_reason, grade_label)."""
    errors = []
    if not isinstance(v, dict):
        return ["a verdict is a JSON object"], None, None
    if not (v.get("change") or "").strip():
        errors.append("change is missing: name what was reviewed")
    verdict = v.get("verdict")
    if verdict not in VERDICTS:
        errors.append("verdict must be accept or decline -- the verdict IS the close; there is no third state")
    answers = v.get("answers") if isinstance(v.get("answers"), dict) else {}
    for q in QUESTIONS:
        p = evidence_problem(q, answers.get(q))
        if p:
            errors.append(p)
    if verdict == "decline":
        note = (v.get("note") or "").strip()
        if len(note) < 16 or NEGATION.match(note):
            errors.append("a decline with no concrete note sends the author back with nothing to change")

    a_model, a_src, a_human, a_probs = side(v, "author")
    r_model, r_src, r_human, r_probs = side(v, "reviewer")
    errors += a_probs + r_probs
    if a_human:
        errors.append("author is a human: this checks an agent's work being reviewed; a human's change needs no model grade")

    if r_human:
        return errors, None, "human"
    g = grade(a_model, r_model)
    if g == "same_model":
        errors.append("same model reviewing its own model's work (%s): correlated judges agree for "
                      "shared reasons, so this is not an independent review" % normalize(a_model))
        return errors, None, g
    if g is None:
        return errors, "a model is unknown -- the pairing cannot be graded, so no diversity claim can be made", None
    # observed (the harness reported it) and environment (the runtime set it) are attested;
    # declared (the model said so) and unrecorded are claims.
    unverified = ["%s's model is %s" % (w, s or "unrecorded")
                  for w, s in (("author", a_src), ("reviewer", r_src))
                  if s not in ("observed", "environment")]
    if unverified:
        return errors, ("%s, not observed -- the grade would be %s if the claim is true; report "
                        "it as diversity UNVERIFIABLE, never as diverse" % (" and ".join(unverified), g)), g
    return errors, None, g


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if len(argv) >= 2 else 2
    cmd = argv[1]
    if cmd == "template":
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if cmd == "grade" and len(argv) == 4:
        g = grade(argv[2], argv[3])
        print(g or "ungradeable: a model is unknown")
        return 0 if g in ("cross_family", "cross_model") else (1 if g == "same_model" else 3)
    if cmd != "check" or len(argv) < 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    worst = 0
    for path in argv[2:]:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print("%s: cannot read: %s" % (path, e), file=sys.stderr)
            return 2
        items = data if isinstance(data, list) else [data]
        for i, v in enumerate(items):
            label = "%s[%d]" % (path, i) if isinstance(data, list) else path
            errors, abstain, g = check(v)
            if errors:
                worst = 1  # a refusal outranks "cannot tell"
                for e in errors:
                    print("%s: REFUSED: %s" % (label, e))
            elif abstain:
                worst = worst or 3
                print("%s: CANNOT TELL: %s" % (label, abstain))
            else:
                print("%s: ok -- %s, %s" % (label, v.get("verdict"), g))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))

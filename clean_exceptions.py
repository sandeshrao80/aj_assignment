#!/usr/bin/env python3
"""
clean_exceptions.py - Ajaia TPM assessment, Task 2
Corrigan Peak Logistics / Dispatch Exception Triage (DET-121 support)

Normalizes terminal, carrier code and timestamp on a FreightWorks exception
export, prints a summary count by event type, and lists every record that
could not be cleaned with confidence (and why).

Rule: never guess silently. If a value can't be cleaned confidently, the
record is still counted (if its event_type is valid) but it is FLAGGED.

Usage:
    python3 clean_exceptions.py exceptions_raw.csv            # clean + summary
    python3 clean_exceptions.py exceptions_raw.csv -o out.csv # also write cleaned CSV
    python3 clean_exceptions.py --self-test                   # run checks

Standard library only (Python 3.8+). Ajaia: https://ajaia.ai
"""
import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime

# --- Normalization rules -----------------------------------------------------

# Canonical terminal names. Aliases are matched case-insensitively after
# stripping spaces/punctuation. Anything unmatched is flagged, not guessed.
TERMINAL_ALIASES = {
    "terminal1": "Terminal 1", "t1": "Terminal 1",
    "terminal2": "Terminal 2", "t2": "Terminal 2",
    "terminal3": "Terminal 3", "t3": "Terminal 3",
}

KNOWN_EVENT_TYPES = {"missed_pickup", "doc_mismatch", "carrier_substitution"}

CARRIER_RE = re.compile(r"^[A-Z]{2,4}$")  # SCAC-style: 2-4 letters

# Output timestamp format: ISO 8601, no zone (source zone is not confirmed).
OUT_TS = "%Y-%m-%d %H:%M:%S"


def norm_terminal(raw):
    key = re.sub(r"[^a-z0-9]", "", (raw or "").lower())
    if key in TERMINAL_ALIASES:
        return TERMINAL_ALIASES[key], None
    return (raw or "").strip(), f"unrecognized terminal value '{raw}'"


def norm_carrier(raw):
    val = (raw or "").strip().upper()
    if not val:
        return "", "carrier_code is blank - cannot infer carrier"
    if not CARRIER_RE.match(val):
        return val, f"carrier_code '{raw}' is not a 2-4 letter code"
    return val, None


def norm_timestamp(raw):
    """Return (normalized_string, issues[]). Issues are caveats, not failures,
    unless the value could not be parsed at all."""
    s = (raw or "").strip()
    issues = []
    if not s:
        return "", ["timestamp is blank"]

    # ISO with explicit UTC marker: parseable, but the other rows carry no zone.
    if s.endswith("Z"):
        try:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            issues.append(
                "timestamp is explicitly UTC ('Z') while other rows have no zone; "
                "kept clock value as-is, NOT converted - zone must be confirmed by "
                "Corrigan Peak IT before ordering/SLA math across rows"
            )
            return dt.strftime(OUT_TS), issues
        except ValueError:
            return s, [f"unparseable timestamp '{s}'"]

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime(OUT_TS), issues
        except ValueError:
            pass

    # Slash dates: MM/DD/YYYY or DD/MM/YYYY? Only accept when unambiguous.
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        a, b, y, hh, mm, ss = m.groups()
        a, b = int(a), int(b)
        if a > 12 and b <= 12:
            month, day = b, a          # must be DD/MM
        elif b > 12 and a <= 12:
            month, day = a, b          # must be MM/DD
        else:
            return s, [f"ambiguous date '{s}' (could be MM/DD or DD/MM)"]
        dt = datetime(int(y), month, day, int(hh), int(mm), int(ss or 0))
        if ss is None:
            issues.append("source had no seconds; seconds set to :00")
        return dt.strftime(OUT_TS), issues

    return s, [f"unparseable timestamp '{s}'"]


# --- Pipeline ----------------------------------------------------------------

def clean_rows(rows):
    cleaned, flags = [], []
    for r in rows:
        rid = (r.get("exception_id") or "").strip() or "<missing id>"
        problems, caveats = [], []

        terminal, err = norm_terminal(r.get("terminal"))
        if err:
            problems.append(err)

        carrier, err = norm_carrier(r.get("carrier_code"))
        if err:
            problems.append(err)

        ts, ts_issues = norm_timestamp(r.get("event_ts"))
        for i in ts_issues:
            # parse failures/ambiguity are problems; zone/seconds notes are caveats
            (problems if ("unparseable" in i or "ambiguous" in i or "blank" in i)
             else caveats).append(i)

        event = (r.get("event_type") or "").strip().lower()
        if event not in KNOWN_EVENT_TYPES:
            problems.append(f"unknown event_type '{r.get('event_type')}'")

        status = "FLAGGED" if problems else ("CLEAN_WITH_NOTE" if caveats else "CLEAN")
        cleaned.append({
            "exception_id": rid, "terminal": terminal, "event_type": event,
            "carrier_code": carrier, "event_ts": ts, "status": status,
            "notes": "; ".join(problems + caveats),
        })
        if problems or caveats:
            flags.append((rid, status, problems + caveats))
    return cleaned, flags


def summarize(cleaned):
    return Counter(r["event_type"] for r in cleaned if r["event_type"] in KNOWN_EVENT_TYPES)


def report(cleaned, flags, out=sys.stdout):
    counts = summarize(cleaned)
    total = len(cleaned)
    print(f"Records read: {total}", file=out)
    print(f"Fully clean: {sum(r['status'] == 'CLEAN' for r in cleaned)} | "
          f"clean with note: {sum(r['status'] == 'CLEAN_WITH_NOTE' for r in cleaned)} | "
          f"flagged: {sum(r['status'] == 'FLAGGED' for r in cleaned)}\n", file=out)
    print("Exceptions by event type", file=out)
    print("------------------------", file=out)
    for ev, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {ev:<22}{n}", file=out)
    print(f"  {'TOTAL':<22}{sum(counts.values())}\n", file=out)
    print("Cleaned records", file=out)
    print("---------------", file=out)
    for r in cleaned:
        print(f"  {r['exception_id']}  {r['terminal']:<11} {r['event_type']:<21} "
              f"{r['carrier_code'] or '(blank)':<8} {r['event_ts']}  [{r['status']}]", file=out)
    print("\nRecords not cleaned with full confidence", file=out)
    print("----------------------------------------", file=out)
    if not flags:
        print("  none", file=out)
    for rid, status, notes in flags:
        print(f"  {rid} [{status}]", file=out)
        for n in notes:
            print(f"    - {n}", file=out)


# --- Self-test: checks the OUTPUT, not just that it runs ----------------------

SAMPLE = """exception_id,terminal,event_type,carrier_code,event_ts
CPX-88213,Terminal 3,missed_pickup,swft,2026-08-14 09:12:00
CPX-88214,Terminal 3,doc_mismatch,SWFT,08/14/2026 09:45
CPX-88215,T3,missed_pickup,Swft,2026-08-14T10:03:00Z
CPX-88216,Terminal 3,doc_mismatch,,2026-08-14 11:47:00
CPX-88217,Terminal 3,carrier_substitution,RLCX,08/15/2026 08:02
"""


def self_test():
    rows = list(csv.DictReader(SAMPLE.splitlines()))
    cleaned, flags = clean_rows(rows)
    by_id = {r["exception_id"]: r for r in cleaned}

    # Hand-computed expectations from reading the 5 raw rows.
    assert len(cleaned) == 5, "row count changed - records dropped or duplicated"
    assert all(r["terminal"] == "Terminal 3" for r in cleaned), "T3 alias not unified"
    assert by_id["CPX-88213"]["carrier_code"] == "SWFT"
    assert by_id["CPX-88215"]["carrier_code"] == "SWFT"
    assert by_id["CPX-88214"]["event_ts"] == "2026-08-14 09:45:00", "MM/DD parse wrong"
    assert by_id["CPX-88217"]["event_ts"] == "2026-08-15 08:02:00", "MM/DD parse wrong"
    assert by_id["CPX-88215"]["event_ts"] == "2026-08-14 10:03:00", "UTC row must not be shifted"
    assert by_id["CPX-88213"]["status"] == "CLEAN"
    assert by_id["CPX-88216"]["status"] == "FLAGGED", "blank carrier must be flagged"
    assert by_id["CPX-88215"]["status"] == "CLEAN_WITH_NOTE", "UTC zone mismatch must be noted"
    assert dict(summarize(cleaned)) == {"missed_pickup": 2, "doc_mismatch": 2,
                                        "carrier_substitution": 1}

    # Edge cases that are NOT in the sample, to prove we don't guess.
    _, iss = norm_timestamp("03/04/2026 10:00")
    assert any("ambiguous" in i for i in iss), "ambiguous date must not be guessed"
    _, err = norm_terminal("Term 9")
    assert err, "unknown terminal must be flagged"
    _, err = norm_carrier("SW-FT1")
    assert err, "malformed carrier must be flagged"
    _, iss = norm_timestamp("garbage")
    assert any("unparseable" in i for i in iss)

    print("Self-test passed: 14 checks against hand-computed expected values.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("input", nargs="?", help="raw exception CSV")
    ap.add_argument("-o", "--output", help="write cleaned CSV here")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.input:
        ap.error("input CSV required (or use --self-test)")

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cleaned, flags = clean_rows(rows)
    report(cleaned, flags)

    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(cleaned[0].keys()))
            w.writeheader()
            w.writerows(cleaned)
        print(f"\nCleaned CSV written to {args.output}")


if __name__ == "__main__":
    main()

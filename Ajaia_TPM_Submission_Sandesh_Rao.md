# Ajaia TPM Assessment — Sandesh Rao

**Video:** [PASTE PUBLIC VIDEO LINK — title includes "Ajaia"]
**Resume:** [PASTE PUBLIC RESUME LINK]
**Build file:** `clean_exceptions.py` (attached / [GitHub link]) · sample input `exceptions_raw.csv` · output `exceptions_clean.csv`
**Email:** sandeshsrao@gmail.com · **Optional work:** [GitHub / portfolio link, or remove]

Prepared for Ajaia (https://ajaia.ai) — Corrigan Peak Logistics, Dispatch Exception Triage engagement.

---

## Plan for the week (one view)

Go-live is **September 8**, about 15 working days out. Two things threaten it, and neither was in last Friday's status: a **double-routing bug** in our code, and an **unresolved Terminal 3 data gap** that has been stalled since 8/6 because nobody owned the client-side ask. This week is about closing both, correcting what we told the client, and keeping new scope out of the launch.

| Day | Action | Owner |
|---|---|---|
| Today | Ask Dana for the Terminal 3 IT contact; send DET-118 outreach to the 3 terminal leads; agree the fix approach with Priya; send corrected status | Me |
| Today–+2 days | Idempotent routing fix + overlap test, merged before anything else ships | Priya (I review the test evidence) |
| On IT answer | DET-121 fix (est. 2 days) using the cleaning rules from Task 2 | Priya |
| This week | Reply to Dana on auto-reassign (Phase 2 framing) | Me |
| Aug 26 | **Decision point:** if Terminal 3 is still not confirmed, we go live on Sept 8 with Terminals 1 & 2, and Terminal 3 follows | Me + Dana |

---

## Task 1 — Triage

**Ranked, most important first.**

**1. B — Priya's duplicate-push risk on the routing service → WORKED this week, before the PR merges.**
This is the most serious item on the list because it is a correctness bug in the exact thing we are selling: one exception, one dispatcher. A duplicate push means two dispatchers can act on the same shipment, which is worse than the shared inbox we're replacing. It is a "today" problem, not a launch-week one: launch-week load is when poll cycles overlap, and that's the worst time to find out. Fix direction to agree with Priya: make the push **idempotent** (exception_id as the dedupe key at the queue or a unique "routed" record written *before* the push, then confirmed) plus a lock or lease so two poll cycles can't claim the same record. Done means a test that kills the DB update mid-flight and runs overlapping polls, and shows exactly one push each time. Credit to Priya for flagging her own PR; that's the behaviour we want to keep.

**2. C — DET-121, Terminal 3 EDI schema mismatch → WORKED this week (client-side unblock is mine).**
Null urgency scores mean Terminal 3 exceptions never reach a dispatcher, so a third of the client's operation silently gets nothing on day one. Last Friday's update called this a "minor data validation task" with "no blockers"; that was wrong. The real blocker is a question to Corrigan Peak's IT that has sat unasked since 8/6. I ask Dana for the contact today with a dated need-by. The 2-day engineering estimate only starts when they answer, so every day of silence comes straight out of our buffer. Material 3 confirms the feed is inconsistent (T3 vs Terminal 3, three timestamp formats, one UTC-marked row, a blank carrier); my Task 2 script is a starting point for the field-level questions to IT.

**3. D — DET-118, schedule the terminal-lead routing-rules review → WORKED today (by me).**
Low effort, high consequence: if the three leads haven't validated who gets which exception, we launch routing rules nobody on the floor has agreed to. "No blocker, just sitting" is how it becomes a blocker in week three. This is a TPM task, not an engineering one; I send the outreach today and target the review for next week, leaving room to change rules before go-live.

**4. A — Dana's request for auto-reassignment to a backup carrier → DECLINED for September 8, offered as a scoped Phase 2.**
This isn't a quick add. It changes the product from *routing a decision to a human* to *the system making a commercial decision on its own*: choosing a backup carrier, rate and contract rules, writing back to FreightWorks over EDI, and owning the failure if the backup also misses. Doing it in three weeks, on top of items 1 and 2, would put the board date at risk. Dana doesn't want to tell her COO "no," so she shouldn't have to: the answer is "yes, as the next phase, and here's why it isn't safe in three weeks." In v1, missed pickups route at top priority so a dispatcher reassigns quickly, and that data tells us which reassignments are safe to automate. I'll offer a 30-minute scoping session after go-live.

**5. E — Different shade of blue for the queue UI → DEFERRED to the post-launch backlog. This is the noise.**
It looks small and urgent ("before launch"), but it came secondhand ("mentioned in passing"), has no business impact, and every "quick CSS thing" pulls the one engineer off items 1 and 2 and adds untested change near go-live. I log it, tell Marcus it's queued for the first post-launch polish pass, and ask ops to confirm the exact color during UAT so we don't guess.

**Protecting the date honestly.** Nobody is asked to work faster. What moves: the colour change goes post-launch; auto-reassign becomes Phase 2. What's at risk: Terminal 3. If IT hasn't confirmed fields by **Aug 26**, I recommend launching Terminals 1 & 2 on Sept 8 and Terminal 3 within about a week after, rather than launching all three with Terminal 3 silently dropping exceptions.

---

## Task 2 — Build

**File:** `clean_exceptions.py` (Python 3, standard library only). Run: `python3 clean_exceptions.py exceptions_raw.csv -o exceptions_clean.csv` · checks: `python3 clean_exceptions.py --self-test`

**What it does and how I checked it.** The script reads the FreightWorks export and normalizes three fields: terminal (aliases like `T3` → `Terminal 3`; anything unrecognized is flagged, not guessed), carrier code (trimmed and upper-cased; blank or non 2–4-letter codes flagged), and timestamp (all formats converted to `YYYY-MM-DD HH:MM:SS`). It then prints a count by event type and lists every record it couldn't clean with full confidence, with the reason. Its main rule is to **never guess silently**: slash dates are only parsed when the month/day order is provable (e.g. `08/14` must be MM/DD because 14 > 12) and are otherwise flagged as ambiguous; the one `Z` (UTC) timestamp is kept at its clock value and *not* converted, because the other rows carry no zone and converting would invent precision we don't have. To check it *worked* and didn't just run, I first worked out the expected result by hand from the five raw rows (2 missed_pickup, 2 doc_mismatch, 1 carrier_substitution; all Terminal 3; SWFT unified across three spellings; CPX-88216 unresolvable). I then encoded those expectations as 14 assertions in `--self-test`, including four edge cases not in the sample (an ambiguous `03/04` date, an unknown terminal, a malformed carrier, a garbage timestamp) to prove it flags rather than guesses. I also confirmed the cleaned CSV keeps all five rows with nothing dropped or duplicated.

**Output on the provided data:**

```
Records read: 5
Fully clean: 1 | clean with note: 3 | flagged: 1

Exceptions by event type
  doc_mismatch          2
  missed_pickup         2
  carrier_substitution  1
  TOTAL                 5

Records not cleaned with full confidence
  CPX-88214 [CLEAN_WITH_NOTE] - source had no seconds; seconds set to :00
  CPX-88215 [CLEAN_WITH_NOTE] - explicitly UTC ('Z') while other rows have no zone; not converted - zone must be confirmed by Corrigan Peak IT
  CPX-88216 [FLAGGED]         - carrier_code is blank - cannot infer carrier
  CPX-88217 [CLEAN_WITH_NOTE] - source had no seconds; seconds set to :00
```

**What this tells the project (DET-121):** the Terminal 3 feed is inconsistent at the source, so it's more than our parsing. Three questions go to Corrigan Peak's IT with the contact request: (1) which timezone does Terminal 3 send, and why does one row arrive as UTC? (2) Is a blank carrier on a doc_mismatch valid, or a dropped field? (3) Which date format is canonical? A blank carrier also matters for scoring: if the urgency model reads carrier, that's a plausible cause of the null scores and worth Priya checking.

---

## Task 3 — Client status update (ready to send)

**To:** Dana Okafor
**Subject:** Dispatch Exception Triage — status, a correction to last week, and your auto-reassign question

Hi Dana,

I want to start with a correction. Last Friday's update showed us Green with no blockers and described the Terminal 3 work as a minor validation task. That was more optimistic than the facts supported, and I'd rather you hear it from me now than find out closer to the 8th.

**Overall status: Amber. September 8 is still achievable, and here is what it depends on.**

**What's on track:** ingestion, scoring and the dispatcher queue UI are progressing as planned.

**What needs attention:**

1. **Terminal 3 data (needs your help).** A share of Terminal 3 exceptions are coming through without an urgency score, which means they would not reach a dispatcher. The cause is a mismatch between the fields Terminal 3 sends and what we expected. We need about 30 minutes with your IT contact to confirm three things: Terminal 3's timezone, its date format, and whether a blank carrier code is valid. The export your team sent was very helpful, and I'll bring a short summary of what it showed. **Could you introduce us to the right person by Thursday, Aug 20?** Our fix takes about two days once we have answers.

2. **A reliability fix in our routing service.** During code review our engineer found an edge case where, under load, the same exception could be sent to a dispatcher twice. Nothing has gone to production and no dispatcher has been affected. We are fixing it this week and testing it under the failure conditions that cause it before go-live.

3. **Terminal lead routing review.** I'm contacting your three terminal leads today to schedule this for next week, so they can confirm who receives which exceptions before launch.

**If Terminal 3 isn't confirmed by Wednesday, Aug 26,** I'll recommend we go live on September 8 with Terminals 1 and 2 and bring Terminal 3 on about a week later. That keeps your board date without launching a terminal where exceptions could be silently missed. I'll confirm with you that day either way.

**On your COO's auto-reassign question:** it's a good idea, and the data from this launch will help us do it well. I'd recommend making it the first item of Phase 2 rather than adding it before the 8th. Today the tool routes a decision to a dispatcher. Auto-reassigning means the system chooses a backup carrier and writes that change back into FreightWorks, which brings in carrier contracts, rate rules and what happens if the backup also misses. Building and testing that properly in three weeks would put the September 8 date at risk. In the meantime, missed pickups will route at top priority so dispatchers can reassign quickly, and we'll measure how often that happens and how long it takes, which gives your COO a business case. If it helps, I can join a short call with him, or write two or three lines you can pass along.

Next update Friday as usual, or sooner if anything changes.

Best regards,
Sandesh Rao
Technical Project Manager, Ajaia

---

## Task 4 — AI Workflow Note

**Where I used AI:** I used Claude to help structure the triage reasoning, to scaffold the cleaning script and its self-tests, and to produce a first draft of the client status update.

**What I kept human:** the calls themselves: ranking B over C, declining auto-reassign while giving Dana a way to say "yes, next phase" to her COO, the Terminal 1 & 2 fallback, the Aug 20 and Aug 26 dates, and the decision to tell the client plainly that last Friday's update was wrong. I also worked out the expected counts by hand from the five raw rows *before* trusting any output, and the self-test asserts against my numbers rather than the script's own.

**One thing I checked or rejected:** [REPLACE WITH YOUR REAL EXAMPLE. Candidates from this session: (a) the natural instinct, mine and the tool's, is to convert the `Z` timestamp to local time so all rows "match"; I rejected that because we don't know Terminal 3's zone, and a confident wrong conversion would corrupt SLA and lateness math, so the script keeps the clock value and flags it; (b) a draft status line that said nothing had reached the client "yet" was rewritten to state plainly that nothing has gone to production, because I won't make a claim I haven't confirmed with Priya. Use only what you actually did.]

---

## Video outline (5–10 min)

1. **(1 min)** The situation in one breath: 3 weeks out, two real risks hidden behind a Green status.
2. **(2 min)** Triage, B → C → D → A → E. Name E as noise, and explain why A is a "yes, Phase 2," not a "no."
3. **(2 min)** Live demo: `python3 clean_exceptions.py --self-test`, then the real run. Point at CPX-88215 (UTC, not converted) and CPX-88216 (blank carrier, flagged), and say how that feeds the IT questions.
4. **(2 min)** Status update to Dana: the correction first, Amber, the Aug 20 ask, the Aug 26 fallback.
5. **(1–2 min)** Who I am: 20+ years in IT, about 16 as PM/TPM (Tata Neu insurance module at 1M subscribers; Odoo across 230 branches); now building AI agents and n8n automation at Sita Infobytes. Why this role: I've been the TPM between an engineer and a client, and the AI-native, forward-deployed model is exactly where I've been building. Why Ajaia: [one specific line from ajaia.ai]. Salary expectation: [your range]. Do not mention current compensation.

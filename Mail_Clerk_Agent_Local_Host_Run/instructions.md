Job Role: act as a first-line triage and routing clerk for incoming institutional email . this is the job that a human mail clerk would traditionally do: open each piece of mail, figure out which department or institute it's actually intended for, and get it there, without every email needing someone to manually read and forward it.

## Phase 1 — User Prompt Trigger

**Purpose:** Start a run.

**Instructions:**
- Accept a run request from one of three sources: a scheduled job (default,
  e.g. hourly), an on-demand prompt or button press, or (optionally, later)
  a webhook on new mail.
- On trigger, resolve "today" using the mailbox owner's local timezone, not
  server time or UTC — build the date range for Phase 2 from that.
- Each run gets a unique run ID, used to group every email processed in
  that run for later auditing.
- Do not start a second run for the same schedule slot if a prior run for
  it is still in progress — treat this as a re-entrancy guard, not just an
  idempotency check at the email level (Phase 2 handles that separately).

## Phase 2 — Login & Fetch Mail

**Purpose:** Securely connect to the mailbox and retrieve only what's new
and relevant.

**Instructions:**
- Authenticate using the narrowest scope available: app-only/service
  auth for a shared institutional mailbox (preferred), OAuth delegated
  auth for a personal mailbox, or IMAP/app-password for the fastest
  prototype path.
- Refresh access tokens proactively before expiry; treat an auth failure
  as its own alert category, separate from a classification failure.
- Query mail using the resolved local-date range from Phase 1. Paginate
  fully — do not stop after the first page of results.
- Cross-check every fetched message ID against the processed-IDs store
  before doing any further work on it. Skip anything already processed.
  This is what makes repeated or overlapping runs safe.

## Phase 3 — Classify per Email

**Purpose:** Determine which institute an email belongs to, using the
strongest available evidence first.

**Instructions:**
- Evaluate signals in this order, stopping at the first confident match:
  1. **Sender domain / address** — check against a maintained lookup
     table of known institute domains. Strongest signal; treat as
     near-certain when it hits.
  2. **Explicit mention** — institute name, program name, or a
     reference/case number in the subject or body.
  3. **Thread history** — if this is a reply in a thread already routed
     to an institute, inherit that routing rather than re-deciding.
  4. **Semantic match (LLM)** — only when the above signals are absent,
     ask the model to classify against the list of known institutes and
     return a confidence score.
- If an email plausibly matches more than one institute with similar
  scores, treat that ambiguity itself as a reason to lower confidence —
  do not force a single pick.
- Record which signal produced the match, not just the final answer —
  this is required for Phase 6's audit trail.

## Phase 4 — Confidence Check

**Purpose:** Decide whether the match from Phase 3 is trustworthy enough
to act on automatically.

**Instructions:**
- Compare the match's confidence score against the configured threshold.
- Do not use a single global threshold for every signal type: a
  domain-match should clear the bar more easily than a semantic-only
  match, since the underlying evidence quality differs.
- Set the threshold conservatively at first (biased toward flagging, not
  auto-sending), since a wrong auto-send is more costly than an
  unnecessary human review.
- Re-derive the threshold periodically from labeled data and live audit
  outcomes — never hand-tune it off a handful of recent misses.

## Phase 5a — Auto-Send (high confidence)

**Purpose:** Route the email to the matched institute without human
intervention.

**Instructions:**
- Re-check the processed-IDs store immediately before sending, as a final
  idempotency guard.
- Send to the institute's contact address from your own verified mapping
  table — never an address parsed out of the email body itself.
- Mark the message as processed atomically, immediately after a
  successful send — not in a batch at the end of the run.
- On a send failure (bounce, API error, rate limit), do not retry
  blindly — route the email to Phase 5b (flag for review) instead, and
  record the failure explicitly.
- Watch for run-level anomalies (e.g. an unusual volume spike to one
  institute) and raise an alert independent of the per-email logic.

## Phase 5b — Flag for Review (low confidence)

**Purpose:** Hand uncertain cases to a human reviewer instead of guessing.

**Instructions:**
- Add the email to a review queue with: the original message, the agent's
  best-guess institute (even though unsure), the confidence score, the
  signal(s) considered, and any close alternative candidates.
- Sort the queue by ascending confidence or by age, not arrival order, so
  the hardest or oldest items surface first.
- Support at minimum four reviewer actions: approve as-is, reassign to a
  different institute, edit before sending, or reject (not applicable).
- Record the reviewer's final decision against the agent's original
  suggestion — this comparison is what recalibrates the Phase 4
  threshold over time.

## Phase 6 — Audit Log

**Purpose:** Make every decision inspectable after the fact.

**Instructions:**
- For every email processed (regardless of path), record: message ID,
  sender, timestamps, run ID, matched institute, confidence score,
  signal(s) used, path taken (auto-sent / flagged / failed / skipped),
  and — if flagged — the eventual human decision.
- Sample and review recent auto-sends daily during initial rollout,
  weekly once stable, and always immediately after any anomaly alert
  from Phase 5a.
- Review aggregate trends (auto-send rate, override rate, failure rate)
  on a fixed schedule, separate from spot-checking individual emails, to
  catch slow drift that per-email review would miss.

---

## Cross-cutting: Test Mode

**Purpose:** Validate the full pipeline safely before allowing real sends.

**Instructions:**
- A single mode flag controls behavior; Phases 1–4 and 6 run identically
  in test and live mode. Only the send action in Phase 5a/5b is affected.
- In test mode, redirect the send action to create a draft (or a log
  entry) instead of actually sending — enforce this inside the send
  function itself, not only at the call site, so no other bug can cause
  a real send during testing.
- Validate against a labeled test set before switching to live mode, and
  keep the confidence threshold artificially conservative for an initial
  "canary" period even after going live.
# Roadmap: GTM Coach

## Implementation Rules

- **No mock LLM responses.** Every feature is tested against real Claude Opus 4.7 calls. The brief quality IS the product.
- **Real spreadsheets, real shapes.** Use `test_territory.xlsx` (or a fresh export) for development. Don't hand-craft minimal test fixtures.
- **The playbook is the deliverable.** When in doubt, edits to `system_prompt.md` are higher-leverage than code changes. Treat prompt iteration as first-class work.
- **Streamlit is throwaway.** Don't over-engineer the UI. The shell will likely move to Slack / scheduled brief / CLI by Phase 5.
- **Single-rep first.** Multi-rep storage and cross-rep features wait until Phase 6. Don't generalize early.

## Progress

| Phase | Features | Status |
|---|---|---|
| 1. Prototype Foundation | 3 | ✅ Complete |
| 2. Persistent State + Deltas | 6 | ✅ Complete |
| 3. Feedback Loop (Matt-in-the-Loop) | 5 | ⬜ Not started |
| 4. Drafted Artifacts | 4 | ⬜ Not started |
| 5. Push, Not Pull (Scheduled Briefs) | 4 | ⬜ Not started |
| 6. Productize (Cross-Rep + SF Writeback) | 4 | ⬜ Not started |
| **Total** | **26** | **10 / 26 (38%)** |

*Plus 1 ad-hoc feature shipped (#100 — visual brief layout).*

## Phase 1: Prototype Foundation ✅

Goal: prove a coaching brief is more useful than a filtered list. Single rep, on-demand upload, no persistence.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 1 | Streamlit upload + Anthropic streaming brief | vision | M | — | ✅ |
| 2 | Coaching playbook v1 (`system_prompt.md`) | vision + docs | S | — | ✅ |
| 3 | Test territory generator | vision | S | — | ✅ |

## Phase 2: Persistent State + Deltas

Goal: the coach detects what changed since last upload. Biggest single unlock — turns the system from calculator into a coach *watching* the territory move.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 10 | SQLite storage for territory snapshots | vision | M | 1 | ✅ |
| 11 | Account-level normalization (stable IDs across uploads) | vision | S | 10 | ✅ |
| 12 | Week-over-week delta detection | vision | M | 11 | ✅ |
| 13 | "What changed since last upload" section in brief | vision | S | 12 | ✅ |
| 14 | Upload history view in Streamlit | vision | S | 10 | ✅ |
| 15 | Header / Strategy Bucket validation in pre-flight | docs | S | 1 | ✅ |

## Phase 3: Feedback Loop (Matt-in-the-Loop)

Goal: every brief gets rated by Matt. Wrong recommendations get marked. Feedback compounds into playbook updates so the coach sharpens week over week.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 20 | Persist every brief generated (linked to snapshot) | vision | S | 10 | ✅ |
| 21 | Brief rating UI (per-recommendation thumbs) | vision | M | 20 | ⬜ |
| 22 | Brief annotation UI ("this was wrong because…") | vision | M | 20 | ⬜ |
| 23 | Feedback aggregation report (what's tracking, what's not) | vision | M | 21, 22 | ⬜ |
| 24 | Playbook versioning (track `system_prompt.md` over time) | vision | S | — | ⬜ |

## Phase 4: Drafted Artifacts

Goal: brief stops saying "you should send an email" and starts saying "here's the email — copy it." Closes the gap between recommendation and execution.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 30 | Drafted artifact section in brief (SF notes, emails, CSM msgs) | vision + docs | S | 2 | ⬜ |
| 31 | Artifact format consistency (deterministic shape) | vision | S | 30 | ⬜ |
| 32 | One-click copy buttons in UI for each artifact | vision | S | 30 | ⬜ |
| 33 | Per-account "ready to send" grouped view | vision | M | 30, 11 | ⬜ |

## Phase 5: Push, Not Pull (Scheduled Briefs)

Goal: the coach fires daily/weekly without waiting for the rep. Brief lands in Slack or email at 7:30am, not when the rep remembers to upload.

> **Architectural note:** Matt's source SOP assumes a Gemini-Sidebar pull model — rep opens sheet, asks the Gem, gets an answer. This phase deliberately changes the *mechanism* (rep-initiated → scheduled) while preserving the *goal* (get coaching to the rep). Not an oversight of his spec; an opinionated extension. If pull-only is preferred, this phase can be skipped without breaking earlier phases.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 40 | Decouple brief generation from Streamlit (CLI) | vision | M | 1 | ⬜ |
| 41 | Scheduler config (launchd / cron) | vision | S | 40 | ⬜ |
| 42 | Brief delivery: email or Slack DM | vision | M | 40 | ⬜ |
| 43 | Stale data warnings (brief annotates data freshness) | vision | S | 10 | ⬜ |

## Phase 6: Productize (Cross-Rep + SF Writeback)

Goal: graduate from single-rep tool to team product. Don't start until Phases 2–5 prove the model.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 50 | Multi-rep storage model | vision | L | 10 | ⬜ |
| 51 | Cross-rep pattern surfacing | vision | L | 50, 23 | ⬜ |
| 52 | Chrome extension for SF note one-tap paste | vision | L | 30 | ⬜ |
| 53 | Direct Salesforce API integration | vision | L | — | ⬜ |

## Ad-Hoc Requests

Features added outside the original 26-feature plan, in response to live use feedback. Numbered #100+.

| # | Feature | Source | Complexity | Deps | Status |
|---|---|---|---|---|---|
| 100 | Visual brief layout (metrics row + section containers) | feedback | M | 1, 13 | ✅ |

## Status Legend

- ⬜ Pending
- 🔄 In Progress
- ✅ Completed
- ⏸️ Blocked
- ❌ Cancelled

## Complexity Legend

- **S** (Small): 1–3 files, single component, ~half-day
- **M** (Medium): 3–7 files, multiple components, 1–2 days
- **L** (Large): 7–15 files, full feature, 3+ days

## Notes

- **Prompt caching is load-bearing.** System prompt is large and stable — keep it cached on every API call. Verify hits in `usage.cache_read_input_tokens`.
- **Phase 2 is the highest-leverage build.** Without persistence, the coach can't detect deltas, track outcomes, or learn. Everything else compounds on top.
- **The system prompt is the IP.** When weighing prompt edits vs feature builds, prefer prompt edits unless the feature unlocks a new input/output class.
- **Matt is the eval set.** Don't ship a feature unless Matt can run it on his own territory and validate the output. He's the human ground truth.
- **Validate "earn rep attention" weekly.** If a real rep stops uploading after 2 weeks, the brief isn't worth the friction — fix the brief, don't chase distribution.
- **Source = `docs`** means a feature traces directly to Matt's source documents (System Instructions + SOP). Source = `vision` means it's a structural extension we agreed on. Mixed source = both.

# Vision: GTM Coach

## Overview

GTM Coach is an opinionated AI coaching tool for B2B account executives at Emburse (Chrome River / Certify). A rep uploads their Salesforce territory export, optionally adds context, and receives a coaching brief — not a filtered list — that tells them what plays to run this week, what fires need attention, and what they're missing.

The system is built around one thesis: **coach, don't calculate**. Plenty of tools filter, sort, and dashboard a territory. What sales orgs lack is *scaled judgment* — the ability to give every rep the same caliber of coaching that the best sales leader gives in 1:1s. GTM Coach scales that judgment by encoding the leader's framework in a system prompt, then briefing reps in the leader's voice.

The wedge play is using contractual **Price Increases as leverage to close whitespace**: instead of executing a value-destructive PI, frame it as a value-add ("we'll mitigate the increase if you add Assurance/Travel/ESA"). Every recommendation is evaluated against this lens.

## Target Users

- **Primary:** Sales reps (AEs) with 30–100 account territories who lack a clear weekly point of view on what to work on.
- **Secondary:** Sales leaders (Matt Rollins, Director of Client Sales) who want to scale their coaching without scaling their time.
- **Tertiary:** Sales ops / enablement maintaining the playbook over time.

## Value Proposition

- **For the rep:** turn a 200-row spreadsheet into a 5-bullet brief that names the right plays for this week, in the voice of the leader they're learning from.
- **For the leader:** scale your coaching framework to every rep without 1:1ing every rep. Iterate on the framework as the team learns.
- **For the org:** every rep operates from the same opinionated playbook, with the same wedge plays, in the same voice.

## Key Screens / Surfaces

| Surface | Purpose | Priority |
|---|---|---|
| Spreadsheet upload + brief (Streamlit) | v1 prototype: rep uploads territory, gets brief on demand | ✅ Built |
| Persistent territory state | Store week-over-week snapshots so the coach can detect deltas | High |
| Scheduled morning brief | Agent fires daily/weekly without prompting; lands in Slack/email | High |
| Optional context drop | Rep pastes call notes, emails, voice memos as context for next brief | Medium |
| Drafted artifacts | Brief includes copy-paste-ready SF notes, emails, CSM messages | Medium |
| Feedback loop / rating UI | Matt reviews briefs, rates accuracy, edits playbook; feedback compounds | Medium |
| Cross-rep pattern surfacing | "This play worked for Rep A in a similar account shape" | Future |
| SF writeback / Chrome extension | One-tap file the drafted note into Salesforce | Future |

## Tech Stack

| Layer | Tech | Why |
|---|---|---|
| Language | Python 3.12+ | Pandas, mature Anthropic SDK, Streamlit |
| LLM | Anthropic Claude Opus 4.7 | Adaptive thinking + prompt caching make the long-system-prompt pattern cheap to run repeatedly |
| UI (v1) | Streamlit | Throwaway shell — prove the brief is valuable before investing in real UI |
| State (v2) | SQLite | Tiny persistence for territory snapshots and feedback ratings; upgrade when needed |
| Scheduler (v2) | macOS launchd or GitHub Actions | Trigger morning briefs without standing up infrastructure |
| Distribution (v2) | Slack DM via Slack API | Where reps already live |

## Design Principles

1. **Coach, not calculator.** Outputs are briefs in prose, not query results. Slot-fill templates are forbidden.
2. **The playbook is the IP.** The system prompt is the substance. The app shell is throwaway.
3. **Push back when the rep is wrong.** Disagree, ask clarifying questions, name what you don't know.
4. **Be honest about what you can't see.** The sheet doesn't have call transcripts or political reality. Recommendations carry their assumptions.
5. **The spreadsheet is the seed, not the substrate.** State lives outside the sheet so the coach can detect deltas and learn over time.
6. **Earn rep attention.** Every brief must justify the friction of opening it. If it isn't worth more than the time to read it, the rep stops uploading.
7. **Matt-in-the-loop.** The playbook sharpens when Matt reviews briefs, marks up what's wrong, and edits land in the system prompt.
8. **Execute eventually, don't just recommend.** Briefs evolve from "you should send this email" → "here's the email, copy it" → "filed for you, one-click confirm."

## Out of Scope

- **Replacing Salesforce as system of record.** SF stays the source of truth. We read exports and (eventually) write back — never own the data.
- **Generic AI sales assistant.** This is opinionated to Matt's framework for Emburse's product set. Not a horizontal product.
- **Real-time CRM sync (early phases).** Spreadsheet exports to start. Direct SF API is months out, depends on org-specific approvals.
- **Replacing rep judgment.** The coach recommends and drafts. The rep decides and executes. Always.
- **Full BI / dashboard product.** No charts, no filters, no leaderboards. Briefs only.
- **Multi-tenant SaaS.** Single-team internal tool first. Productizing is downstream of proving it works for one team.

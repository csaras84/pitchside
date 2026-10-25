# Build trail

A running log of requirements, decisions, progress and open problems for Pitchside
(Inside the Game: Developer Hackathon). Newest log entries go at the bottom. Times are IST.

**Hard dates:** registration closes Oct 21, 12:30 AM IST (Oct 20, 12:00 PM PT). Submission closes
Oct 28, 12:29 PM IST (Oct 27, 11:59 PM PT). Working deadline: Oct 27 evening IST, to leave a buffer.

---

## Requirement

**The challenge:** build an AI-powered application or agent that turns synthetic, football-realistic
event data into useful, understandable and engaging match intelligence: explainable insights,
real-time narratives, automated recaps and personalized experiences for fans, studios, broadcasters
and streaming platforms.

**Must have**
- Uses **synthetic** football-realistic data only. No real Premier League data.
- Built on Microsoft and Azure technology (GitHub, Microsoft Foundry, Azure AI services, Azure
  cloud-native services, and so on).
- A **public GitHub repository**.
- A short pitch: what it does, which Microsoft and Azure technologies it uses, and what problem it solves.
- A **demo video under 2 minutes**, public on YouTube, Vimeo, Facebook Video or Youku, showing the
  project running, with no third-party trademarks or copyrighted music.
- A **working project link** (website, functioning demo or test build) that judges can use free of
  charge and without restriction until judging ends on Nov 10. This is a requirement, not a nicety.
- Submission on the Innovation Studio Platform before the deadline above.

**Capabilities the brief asks for (we pick a focused subset)**
- Analyze match events in real time
- Generate stories, highlights and recaps
- Explain key moments and tactical patterns
- Deliver insights in multiple languages
- Deliver personalized and accessible experiences

## What we intend to build

**Pitchside: multi-agent, accessible match intelligence.** One synthetic match goes in; a
fact-checked story comes out, rendered for how each person follows football.

**Problem:** football is experienced through sound and sight, which leaves deaf, blind and
deafblind fans with a thinner version of the game. AI-written commentary also has a trust problem:
it can state wrong scores, minutes or players.

**Approach**
1. **Analyst agent** computes score, expected goals, momentum and key moments in plain code, so the
   numbers are exact.
2. **Narrator agent** (Microsoft Foundry model, with an offline template fallback) writes the recap.
   Every sentence carries structured claims.
3. **Verifier agent** checks each claim against the raw events. Wrong drafts are rejected and sent
   back with the errors; after repeated failures a deterministic narrator takes over.
4. **Accessibility Adapter agent** re-renders the verified story for each profile:
   - Deaf or hard of hearing: captions with sound cues, plain language, vibration patterns, visual alerts
   - Blind or low vision: spatial description of each play, speech (SSML for Azure AI Speech), a tone that rises with chance quality
   - Deafblind: text wrapped for 40-cell refreshable braille displays, plus vibration
5. **Translator agent** (Azure AI Translator) delivers the result in English, Spanish, French, Hindi and Tamil.
6. **Orchestrator** manages shared state, handoffs, retries and a visible per-step trace.
7. **Accessible web UI** with an "agent trace" panel showing how each recap was produced and verified.

**Principles**
- Explainable: every statement traces back to events and passes the Verifier.
- Resilient: the whole app works offline with no credentials, so a failed cloud call never breaks the demo.
- Honest: claim only what has been tested (no accessibility conformance claims before real testing).
- No decorative numbers: a metric appears only if the data really holds it or a documented formula
  derives it. No speed or distance telemetry is invented to look sophisticated.

### Added on Oct 25, after reading the official brief and two outside reviews

The brief describes five stages: ingest events as they happen, interpret them, explain why a moment
matters, render alongside the match, and personalize. The first version covered interpretation and
rendering well and the other three thinly. The plan to close that, in priority order:

1. **A working public link** on Azure Container Apps, with cost guardrails (result cache, per-client
   limit, hourly cloud budget that falls back to the offline agents instead of refusing anyone).
2. **Azure AI Translator connected for real.** Note the Verifier checks the English source; the
   translation is ordinary machine translation on top and is described that way.
3. **"Why it matters"**: the Analyst computes the evidence (xG swing, lead changes, momentum before
   and after a red card) in plain code; the Narrator only phrases it; the Verifier checks the
   numbers. No evidence, no statement.
4. **Two independent settings**: *depth* (casual fan or tactical analyst) and *presentation*
   (standard, deaf, blind, deafblind). Any pair works, 8 experiences, one pipeline. Favourite club or
   player is a possible third setting (a filter on which moments get the most space).
5. **Simulated live feed** (first called a live replay): the match unfolds minute by minute and the page updates as it goes.
   This touches the trust core: a half-played match has no final score, so the template, the prompt
   and the Verifier's final-score rule become "score so far" with the same strictness.
6. **Data with more character, kept honest**: three story archetypes (for example red-card swing,
   late comeback, dominant but wasteful), a few new event types (tackle, turnover), match context, a
   private list of planted storylines to check whether the Analyst recovers them, and a short
   dataset card. Everything is generated from one seed and kept internally consistent.
7. **A reproducible Verifier demo**: a clearly labelled fault-injection switch corrupts the first
   draft's score or minute once, so the trace shows a real rejection, feedback and corrected retry.
   The real model rarely errs, so the injected fault is labelled as injected.

**Demo plan (under 2 minutes):** a simulated live feed of a red-card-swing match, the same moment as a
casual fan and as an analyst, rendered in the four presentations, then the agent trace showing the
Verifier rejecting an injected error and accepting the corrected draft.

**Status at Oct 25, 17:00 IST:** items 3, 4, 5 and 7 are built and tested. Item 6 is partly done
(three story archetypes, a red-card event type, planted storylines and the check); tackles,
turnovers, match context and the dataset card are not built. Items 1 and 2 (public link, Translator)
are written or planned but not yet run. Favourite-club setting not built.

**Out of scope:** player tracking and speed or distance indicators (they would need positional data
we do not have; roadmap only), auto-eventing from video, sign-language avatar, real broadcast data,
user accounts.

---

## Oct 20, 13:00 to 20:23: planning and first scaffold

### Decisions
| Decision | Why |
|---|---|
| Solo, Python | Team of one; fastest path with Azure SDKs and FastAPI |
| Add accessibility for deaf, blind and deafblind users | The brief asks for accessible, personalized experiences; one adapter agent covers all profiles |
| Analyst is plain code, not an LLM | Numbers (score, xG, momentum) must be exact so the story is explainable |
| Verifier checks every narrated claim against raw events | The core explainability guarantee; also gives a real failure-recovery loop |
| App must work offline with no credentials | A broken Azure step must never kill the demo |
| No sign-language avatar | Hard to do well; listed as roadmap only |

### Built
- Repo scaffold: `pyproject.toml`, `.env.example`, `.gitignore`, GitHub Actions CI
- Synthetic match generator (fictional clubs and players, deterministic by seed)
- Agents: Analyst, Narrator (Foundry-ready, template fallback), Verifier, Accessibility Adapter, Translator
- Orchestrator with shared state, retry-with-feedback, deterministic fallback and a per-step trace
- FastAPI backend and a single-page accessible UI (skip link, live regions, high contrast, larger text)
- README with architecture diagram

### Verified
- 15 tests pass (generator, analyst, Verifier catching planted errors, accessibility output,
  retry and fallback, translation fallback), run with a small throwaway runner
- Same goal renders correctly for all four profiles (checked by printing output)
- UI JavaScript passes a Node syntax check

### Not verified yet
- `test_api.py` and `pytest` itself: PyPI was blocked in the build sandbox (403), so FastAPI and
  pytest could not be installed. **First thing to do on the real machine.**
- The UI in a real browser, and with a screen reader (NVDA or VoiceOver)
- Any real Azure call (Foundry, Translator, Speech): no credentials yet

### Open risks
- Microsoft Agent Framework port is the biggest unknown (new API to learn)
- Foundry and Translator setup may hit endpoint, quota or deployment-name surprises; do it early
- Demo video and README are easy to under-budget when working solo

---

## Next up
Done: registered; tests run on the real machine; public repo and green CI; Azure subscription and
Foundry; real model with the Verifier loop; Microsoft Agent Framework workflow.

- [ ] Run the Container Apps script and check `/health` (guardrails and script written Oct 25, not yet run)
- [ ] Azure AI Translator resource and keys; check Tamil, Hindi, Spanish, French end to end
- [x] Analyst "why it matters" evidence, depth setting (casual or analyst), UI selectors
- [x] Story archetypes, red-card event, planted storylines and check (tackles, turnovers, dataset card not built)
- [x] Simulated live feed (written Oct 25; feature freeze Mon Oct 26, 2:00 PM IST, then redeploy)
- [x] Fault-injection demo of the Verifier
- [ ] Update the demo video notes and pitch with the final feature names
- [ ] Screen-reader pass (NVDA or VoiceOver) and Accessibility Insights; fix issues
- [ ] Azure AI Speech audio (first thing to cut if behind)
- [ ] Pitch text, demo video (under 2 min, strictly), recorded Oct 27
- [ ] Submit Oct 27 evening IST, well before the Oct 28, 12:29 PM IST cutoff

## Log
<!-- Add entries below: date and time, what changed, what broke, what you decided. -->

### Oct 20, 21:17: first real test run
- Ran on the real machine (Windows, Python 3.14.2, project venv): **18 of 18 tests pass**, including the 3 API tests that could not run in the build sandbox.
- Fixed: `ruff` was blocking `pip install -e ".[dev]"`; moved it out of the dev extras (CI installs it separately).
- Gotcha: PowerShell blocked `Activate.ps1`. Calling `.venv\Scripts\python -m ...` directly avoids activation.
- Still unverified: the UI in a real browser, screen reader testing, any real Azure call.
- Next: run the app locally and click through all four profiles.

### Oct 20, 22:31: registered and pushed to GitHub
- Registered for the hackathon (before the Oct 21, 12:30 AM IST cutoff).
- Ran the app locally on the real machine: page, `/api/recap` and the full agent pipeline all returned 200 with no errors.
- Pushed the initial scaffold to https://github.com/csaras84/pitchside (public).
- Gotchas: GitHub rejected the first push ("Repository not found") until the repo was created under the same account that signed in; stale Windows credentials were also a risk.
- Not yet checked: whether the GitHub Actions CI run is green (it runs `ruff check .`, which has never been run on this code).
- Next: check the CI result, confirm the repo is visible while signed out, then set up Azure and Foundry.

### Oct 20, 22:44: CI green
- First CI run failed at `ruff check .` (3 issues in `orchestrator.py`: import order, `collections.abc` import, and a deliberate broad `except` that now carries a `noqa: BLE001`). Fixed and pushed; CI is green (lint + 18 tests on Ubuntu, Python 3.12).
- Status at end of day: registered, app runs locally, 18/18 tests, public repo on GitHub, CI green.
- Next (Oct 21): confirm the repo is public while signed out, check email for the Innovation Studio invitation, create Azure subscription and a Foundry project, connect the Narrator to a real model and watch the Verifier on real output.

### Oct 24, 21:15: momentum table replaced with an adaptive analysis section
- Replaced the momentum table with a mirrored bar chart (home bars left, away bars right, stronger side outlined, away bars striped so colour is not the only cue), plus a one-sentence written summary.
- Decision: analytics are for **every** profile, in the form that suits each: Standard and Deaf get chart + summary + table; Blind gets summary + table (chart is visual only); Deafblind gets the summary only, wrapped to 40 characters. Rejected hiding analytics for some profiles: it would hide the core "explainable" feature and withhold insight from the users the project is for.
- Decision: deafblind stays (already built, near-zero cost). Claim "braille-ready text format" only; it has not been tested on a real braille display.
- Verified: headless Chromium run with real pipeline output, all four profiles, no page errors; JS syntax check passes. Not verified on a real screen reader.
- Still open: Foundry connection (not started), Agent Framework port, Azure deployment, demo video. Working deadline Oct 27 evening IST.

### Oct 24, 23:02: Foundry connected
- Azure subscription and a Foundry resource created; `gpt-4.1-mini` deployed as **Global Standard** (pay per token). Chosen because the job is small (a short grounded recap in JSON), it is not a reasoning model, and it supports structured output. The portal marks it **Legacy** (lifecycle label): it works, but check its retirement date against the Nov 10 judging window.
- Problem: the connection test returned `404 Resource not found`. Cause: the deployment is served by Azure's v1 API (`.../openai/v1/`), while the code used the older `AzureOpenAI` client with an `api-version`. Fix: `llm.py` now uses the standard OpenAI client against `<endpoint>/openai/v1/` and normalises any copied endpoint or Target URI; no API version needed.
- Added `scripts/check_foundry.py` (reads `.env`, never prints secrets, one tiny JSON call): **SUCCESS**. An empty "project endpoint" in the portal is irrelevant, since the app uses the resource endpoint and a key.
- Secrets: the key lives only in `.env`, which is git-ignored.

### Oct 24, 23:15: first real model output; Verifier tightened
- First full run with the real model ended on the template fallback: the Verifier rejected three drafts. The facts were right but the wording was not in the accepted format (for example ordinal minutes like "9th", or a different dash in scores).
- Fix: the Verifier now accepts wording variants (ordinal minutes, any dash style) but still rejects wrong facts ("minute 19" does not satisfy minute 9, "1-0" does not satisfy 0-1). The prompt now asks for digits, plain hyphens and home-team-first scores.
- Result: the model's draft passed on the first attempt (`Narrator source: LLM`, about 5.5 s, 7 statements checked).
- Found a real hole: the final-score check only looked for the two digits anywhere in the sentence, so "Harbour United winning 2-0" passed and so would a wrong winner. Fix: the final statement must give the score home-first (`0-2`) or "Home 0, Away 2" naming both teams; winner-first order and wrong winners are rejected. New tests cover it.
- Lint: `ruff` flagged unneeded `noqa` markers and import spacing in new files; fixed. CI had been red on the previous push for this reason.
- Status: 21 tests pass locally, `ruff check .` clean, pushed. Not yet confirmed: the final CI run after the last push, and `scripts/try_llm.py` after the final-score rule.
- Next: confirm CI is green; decide order of Agent Framework port vs Azure deployment (both time-boxed); add a "show a caught error" demo button; check the Legacy model's retirement date.

### Oct 24, 23:45: Microsoft Agent Framework workflow
- Moved the pipeline steps into `pipeline_steps.py` so two engines share them: the plain orchestrator and an opt-in Agent Framework workflow (`af_workflow.py`, selected with `?engine=agent_framework`). Each role is a workflow executor, the Narrator is a framework `Agent` backed by the Foundry deployment, and the Verifier routes with conditional edges. Retries are unrolled into separate nodes because no loop-back edge was documented.
- `scripts/try_agent_framework.py` ran against the real model: verified recap through the workflow.
- Result at the time: 30 tests pass locally, `ruff check .` clean, pushed. The CI workflow does not install the `agent` extra, so the workflow tests skip there.

### Oct 25, about 14:00: official rules and brief read against the project
- Corrected my own earlier assumption: a **working link is required** (rules 4.8) and must stay free to use until Nov 10. Hosting therefore moves from optional to required.
- Retirement check: the Azure docs list `gpt-4.1-mini` (2025-04-14) as Deprecated with retirement on 2027-04-14, well after judging. The portal's "Legacy" label is not a problem for this window.
- Gaps against the brief: events are not ingested live, no "why it matters", personalization is accessibility and language only, the synthetic data has few event types, Azure Translator is not configured so languages fall back to English, and the app is not deployed.

### Oct 25, 15:30: direction after two outside reviews
- Both reviews agreed on: deploy early, keep the deterministic Analyst and Verifier, add "why it matters", add a casual or analyst mode, replace a full tracking simulation with a simulated live feed.
- They disagreed on adding speed and distance values to events. Decision: **no decorative telemetry**. A project whose promise is that nothing unverified reaches the fan must not show invented numbers as measured. Speed and distance indicators move to the roadmap; my earlier idea of a time-boxed 22-player tracking layer is dropped.
- Decision: depth (casual or analyst) and presentation (standard, deaf, blind, deafblind) are independent settings, giving 8 experiences from one pipeline. The Verifier checks the story before the Adapter renders it, so all 8 stay fact-checked.
- Noted for the pitch: translations are not verified (the Verifier checks the English source).

### Oct 25, 15:25: deployment preparation written (not yet run)
- Added `guard.py` (result cache, per-client limit of 30 uncached requests a minute, and a global budget of 200 cloud-backed runs an hour; once spent, the app answers with the offline template agents instead of refusing anyone), wired into `api.py` with an `X-Pitchside-Cache` and `X-Pitchside-Mode` response header.
- Added `Dockerfile` (tries the Agent Framework extra and says so if it falls back), `.dockerignore` (keeps `.env` out), `scripts/deploy_azure.ps1` (reads `.env`, stores the two keys as Container Apps secrets, one replica so the in-memory counters stay correct) and the guard settings in `.env.example`.
- Verified in the build sandbox: lint clean on the new files; the 4 guard unit tests pass. **Not verified:** the 2 API-level guard tests (FastAPI cannot be installed there), the Docker build, the deploy script, and the full suite on the real machine (expected 36 tests).

### Oct 25, afternoon: "why it matters", depth, story archetypes
- The Analyst now computes reasons in plain code (score state, momentum shift before and after a goal or red card, chance quality, late goal, against the run of play, first booking, sent off, wasted dominance). The Verifier checks each reason against recomputed evidence, the wording, and, at analyst depth, that the figures appear in the text. Detail level (casual or analyst) is independent of presentation: 8 experiences.
- Trivial reasons were removed: "a goal would put X ahead" in minute 1, or "best chance so far" early on, are gated by minute thresholds.
- Story archetypes (red-card swing, late comeback, dominant but wasteful) with planted storylines. First measurement of the Analyst finding them was 30 of 40, 40 of 40 and 22 of 40. Diagnosis: the generator did not always make the premise true (the xG gap under 1.0; the other side already on top before the red card). After making the premise hold, 60 of 60 for each, with a negative control (against an unrelated match's analysis) under 10 percent. Caveat kept in the docs: the generator guarantees the premise, so this is not a general accuracy figure.
- Real model, analyst depth, Red-card swing story: draft #1 rejected by the Verifier, draft #2 accepted, 7 statements checked, about 8.8 s and 8.4 s per Foundry call. The recap text matched the data (3.5 to 3.5 before, 14.5 to 0.5 after, 10 players, 1-0 and 2-0).
- Finding: git history showed that some edits I believed had landed in an earlier session never did. Cause not established (a lost or overwritten write is the likely explanation; my first guess, a OneDrive sync, was wrong because there is none). From then on every file write checks the file's modified time and size first.
- Mistakes of mine recorded earlier and corrected: a wrong test count, a wrong deadline day, and saying a live link was not required.

### Oct 25, 16:40 to 17:00: trace detail, warm-up, simulated live feed, Verifier demo
- The agent trace now has a Detail column, so the reason for each rejection is on screen.
- Start-up cache warm-up (`PITCHSIDE_WARM_CACHE=1`, on in the Docker image) pre-computes the eight demo recaps, because one model recap took about 17 s (two drafts at about 8.5 s each).
- Simulated live feed: `/api/replay` returns verified checkpoint frames (every 10 minutes, plus after each goal and red card, and full time), each built only from events up to that minute and written by the offline agents, so playing costs no model tokens. Tests check that no frame mentions a later minute, that scores only grow, that the last frame equals the full recap, and that the storyline is judged at full time only. First called "live replay"; renamed "simulated live feed" because nothing is live and it is not a replay of a real match.
- Verifier demo: an optional fault (wrong minute or wrong score) corrupts draft 1 and is labelled `INJECTED FAULT` in the trace. Across 4 match types, several seeds and both detail levels (over 50 combinations) the Verifier rejected every injected fault, and the accepted recap equals the clean one.
- Result on the real machine: `ruff check .` clean and **88 tests pass** (Python 3.14.2), including the API tests. Not verified: Docker build, the deploy script, Translator, a screen reader, the Agent Framework tests in CI (the extra is not installed there).
- Next: push, run the Azure deploy and check `/health`, create Translator, screen-reader pass, then pitch and video.

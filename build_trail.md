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

**Demo plan (under 2 minutes):** show one goal rendered four ways (standard, deaf, blind, deafblind),
then the agent trace showing the Verifier rejecting a wrong draft and accepting the corrected one.

**Out of scope for now:** sign-language avatar (roadmap only), real broadcast data, user accounts.

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
- [ ] Register for the hackathon (closes Oct 21, 12:30 AM IST)
- [ ] Unzip, `pip install -e ".[dev]"`, `pytest -q`, run the app locally
- [ ] Create the public GitHub repo and push (with this file)
- [ ] Create Azure subscription and Foundry project; fill `.env`
- [ ] Narrator on a real Foundry deployment; confirm the Verifier loop with real LLM output
- [ ] Port orchestration to Microsoft Agent Framework
- [ ] Deploy to Azure Container Apps
- [ ] Azure AI Speech audio (first thing to cut if behind)
- [ ] Screen-reader and Accessibility Insights pass; fix issues
- [ ] Feature freeze Oct 25
- [ ] README polish, pitch text, demo video (under 2 min) recorded Oct 26
- [ ] Submit Oct 27, well before the cutoff

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

# Pitchside: what the 2-minute video can say

Working note, not a script. Rules: under 2 minutes, public link, running app on screen,
no third-party trademarks, no copyrighted music. Say only what is on the "safe" list.

## Safe to say (each was observed, not assumed)

| Claim | Where it came from | Say it as |
|---|---|---|
| The Verifier rejected a real model draft and the retry passed | Your run: Red-card swing, analyst depth. Trace: narrator draft #1 ok, verifier draft #1 **rejected**, narrator draft #2 ok, verifier draft #2 ok | "It caught the model getting a fact wrong, sent it back, and the second draft passed." |
| Every statement is checked against the raw events | Same run: "7 statements checked, 0 issues" | "Seven statements checked against the event data." |
| The model is Foundry gpt-4.1-mini | `llm_configured` and Narrator source: llm | "Written by a model on Microsoft Foundry." |
| Same match, 8 experiences | 2 depths x 4 presentations | "Casual or analyst, standard, deaf, blind or deafblind." |
| The Analyst found the planted story | Story panel: "found it: the sending off and the swing in control that followed" | "We plant a red card in the data and check the analyst finds it from the events alone." |
| Data is synthetic, clubs are fictional | Northgate FC, Harbour United | Say it once, early. |
| Each step of the simulated feed is fact-checked using only what is known at that minute | Tests: no frame mentions a later minute; every frame passes the Verifier | "Watch the analysis build as the match unfolds (simulated)." |
| Braille output wraps at 40 cells | Tests | Optional, only if there is time. |

## The rejection: how to show it

- It is a real event but **not guaranteed to recur**. The model is non-deterministic.
- Record several takes of Red-card swing at analyst depth. Keep the take where the trace shows
  a rejection. The Detail column now shows the reason on screen.
- If none appears on camera, do not claim one. Use the labelled fault-injection demo
  (Verifier demo selector, built) and say "injected" out loud.
- Never say "always" or "never wrong". Say "it checks, and rejects what it can prove wrong".

## Say only if true on the day you record

- "Hosted on Azure Container Apps": only after the deploy script has run and `/health` answers.
- "Translated with Azure AI Translator": only after the key is set. Add "machine translation, unverified".
- "Microsoft Agent Framework": only if you demo `?engine=agent_framework` or name it in the pitch with the optional-engine wording.
- Test count: re-read it from `pytest -q` on the day. Last confirmed on your machine: 88 passed (Oct 25, 16:58 IST).

## Do not say

- Any fan-count or market statistic (no verified source).
- "Live", "real-time" or "replay" for the simulated feed. Call it the "simulated live feed": a finished synthetic match played back minute by minute. Its steps are written by the built-in agents, not the model.
- "22-player tracking" or speed/distance: not built, roadmap only.
- That the story recovery proves general accuracy: the generator guarantees the premise, so it
  measures the Analyst against known planted stories (60/60 on the seeds tested, and an
  unrelated-match control stays under 10%).
- Real club names, logos, or Premier League branding in the app, captions, or thumbnail.

## Suggested shape (about 270 spoken words, ~115 s)

1. 0:00-0:12  Problem: a final score hides the story, and most recaps assume you can see and hear.
2. 0:12-0:30  What it is: synthetic match, five agents, every claim fact-checked. Name the clubs as fictional.
3. 0:30-1:05  Demo A: Red-card swing, analyst depth. Point at the trace: rejection, reason, retry, pass.
4. 1:05-1:30  Demo B: switch to deaf, then blind, then deafblind with the same match.
5. 1:30-1:45  Story panel: planted storyline found from events alone.
6. 1:45-1:58  Close: Foundry, Azure hosting, link in the description. Free to use until Nov 10.

## Before recording

- Warm cache on (`PITCHSIDE_WARM_CACHE=1`) so the first click is not a 17 s wait.
- Browser zoom ~125%, one window, no notifications, no other tabs.
- Capture the rejection take first; everything else is repeatable.

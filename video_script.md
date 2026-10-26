# Pitchside video script (target 1:44, hard limit 2:00)

About 244 spoken words, roughly 1:44 at a calm pace (140 words a minute). Rules: public on YouTube,
shows the app running, no third-party trademarks, no copyrighted music (use none). Claims follow
`video_notes.md`. Add captions: paste the voice-over text below as a caption file, because the
project is about accessibility.

## Before you record (10 minutes)

1. Azure portal: Container App `pitchside`, Min replicas = 1 (the redeploy sets this; check it).
2. Open the live address in a clean browser window: no other tabs, no bookmarks bar, zoom 125%.
3. Warm everything once, so the recording has no waits:
   - Story: Red-card swing, detail: Tactical analyst, press Load recap (about 5 to 20 seconds the first time).
   - Then Verifier demo: wrong minute, Load recap. Repeats of a request are answered from memory, so on camera it is instant.
4. Close anything that shows keys, `.env`, or your email. Turn off notifications.
5. Record the screen with Windows Game Bar (Win+G) or OBS. Voice-over recorded live, or added afterwards.

## Shot list and voice-over

| Time | On screen | Say |
|---|---|---|
| 0:00 | The page, top | A final score hides the story, and most match coverage assumes you can see and hear. AI recaps add a second problem: they can state a wrong score. |
| 0:12 | Scroll slowly past the settings | Pitchside turns a synthetic match, with fictional clubs and no real data, into a fact-checked story. Five agents do it: Analyst, Narrator, Verifier, Adapter and Translator, coordinating through shared state. Then it renders the story for how each fan follows football. |
| 0:29 | Select Story: Red-card swing, Detail: analyst, Load recap. Point at the red-card line and its figures in the timeline | Here is a red card. The Analyst, plain code, works out why it mattered: Harbour United are down to ten, and Northgate's attacking threat jumps from three and a half to fourteen and a half. Every figure is computed, not invented by the model. |
| 0:48 | Open "How was this verified?" and the verdict line | The model drafted this recap on Microsoft Foundry. The Verifier then checked all seven statements against the raw events. |
| 0:56 | Verifier demo: wrong minute, Load recap. The trace opens. Point at the INJECTED row, then the rejected row, then draft 2 passing | To show that gate working, I inject a wrong minute into the first draft. This is injected, not a model mistake. The Verifier rejects it, minute thirty-eight, but the event says thirty-one, and the corrected draft passes. |
| 1:12 | Click Deaf, then Blind, then Deafblind, then set Language to Español | Same verified story, different fans. Deaf fans get captions with sound cues and vibration. Blind fans get spatial description and speech. Deafblind fans get text wrapped for braille displays. And Spanish, French, Hindi or Tamil through Azure AI Translator. |
| 1:29 | Press Start simulated match, let two steps appear | A simulated live feed replays the match minute by minute, checked at every step. |
| 1:35 | The page header, then the story panel ("The Analyst found it") | Pitchside runs on Azure Container Apps, with Microsoft Foundry, Azure AI Translator and Microsoft Agent Framework. The link is in the description. |

Timings are approximate; they shift with your pace. If you run over, cut the simulated feed row first.

## Do not say or show

- "Live", "real-time" or "replay" for the feed. It is a simulated feed.
- Any fan count or market statistic.
- Real club names, logos, the Premier League mark, or any sound or music that is not yours.
- Your keys, `.env`, or the Azure portal's key pages.
- That the Verifier "never fails". Say it "checks every claim".

## After recording

1. Upload to YouTube, visibility **Public** (not Unlisted): the rules say public.
2. Title: "Pitchside: fact-checked, accessible match intelligence". Description: the live link, the GitHub link, one line that all data is synthetic.
3. Add captions (paste the voice-over text), and check the names: Northgate, Harbour, Foundry.
4. Open the YouTube link in a private window to confirm it plays when signed out and is under 2:00.
5. Keep the link for the submission form.

# Pitchside: pitch text (draft)

Live demo: https://pitchside.calmforest-ffc59cc3.eastus.azurecontainerapps.io/
Code: https://github.com/csaras84/pitchside

All clubs, players and events are synthetic and fictional. No real Premier League data is used.

## What we built

Pitchside turns a stream of synthetic football events into a match story that has been fact-checked
before anyone reads it, then renders that story for how each fan follows the game. Five cooperating
agents do the work: an Analyst that computes the numbers and the reasons a moment matters, a Narrator
that writes the recap, a Verifier that checks every claim against the raw events, an Accessibility
Adapter, and a Translator.

## What it does

- Explains why a moment matters, not only that it happened: a red card, then the swing in control
  that followed, with the figures. The reasons are computed in plain code; the model only phrases them.
- Fact-checks every sentence. The Verifier compares each minute, player, team, score and stated reason
  with the raw events and the recomputed analysis. A wrong draft is rejected, sent back with the
  reasons, and corrected; if the model keeps failing, a deterministic narrator takes over, so a verified
  recap is always produced. The page shows this in an agent trace.
- Adapts to the fan, with two independent settings: detail (casual fan or tactical analyst) and
  presentation (standard, deaf or hard of hearing, blind or low vision, deafblind). Deaf fans get
  captions with sound cues and vibration; blind fans get spatial description, announcements and speech;
  deafblind fans get text wrapped for 40-cell braille displays. Eight experiences, one verified story.
- Plays a finished match as a simulated live feed, minute by minute, using only what was known at each
  minute.
- Delivers recaps in English, Spanish, French, Hindi and Tamil.
- Includes story matches (a red-card swing, a late comeback, a dominant but wasteful side) with a
  private record of the planted storyline, so we can measure whether the Analyst finds it from the
  events alone.

## Microsoft and Azure technology

- Microsoft Foundry: a `gpt-4.1-mini` deployment powers the Narrator.
- Microsoft Agent Framework: an optional engine runs the pipeline as a workflow, with the Verifier
  routing through conditional edges.
- Azure AI Translator: multilingual recaps.
- Azure Container Apps: hosts the public demo, built from our Dockerfile.
- GitHub and GitHub Actions: source and continuous testing.

## The problem it solves

Football is experienced through sound and sight, which leaves deaf, blind and deafblind fans with a
thinner version of the game. AI-written commentary also has a trust problem: it can state a wrong score,
minute or player. Pitchside tackles both: every fan gets the story in a form they can use, and nothing
reaches them that the Verifier has not checked against the data.

## Honest limits

- Translations are ordinary machine translation on top of the verified English text; only the English
  is fact-checked.
- The simulated live feed replays a finished synthetic match; it is not connected to a live source.
- The planted-storyline check measures the Analyst against stories the generator guarantees; it is not
  a general accuracy figure.
- We have not yet tested with a screen reader or a braille display, so we claim no accessibility
  conformance.
- No speed or distance metrics: the synthetic data holds event positions, not player tracking, and we
  would not invent numbers.

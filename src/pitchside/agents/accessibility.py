"""Accessibility Adapter agent: re-renders a *verified* narrative for a user profile.

Profiles
  standard   the narrative as written
  deaf       captions with sound cues, plain language, vibration patterns
  blind      spatial audio description, SSML for Azure AI Speech, threat-tone pitch
  deafblind  plain text wrapped to 40 cells for refreshable braille, plus vibration
"""

from __future__ import annotations

import textwrap
from enum import Enum
from xml.sax.saxutils import escape

from pydantic import BaseModel

from ..models import Event, EventType, Match, Narrative

BRAILLE_CELLS = 40

# language -> (locale, Azure neural voice)
VOICES: dict[str, tuple[str, str]] = {
    "en": ("en-GB", "en-GB-SoniaNeural"),
    "es": ("es-ES", "es-ES-ElviraNeural"),
    "fr": ("fr-FR", "fr-FR-DeniseNeural"),
    "hi": ("hi-IN", "hi-IN-SwaraNeural"),
    "ta": ("ta-IN", "ta-IN-PallaviNeural"),
}
SUPPORTED_LANGUAGES = tuple(VOICES)


class Profile(str, Enum):
    STANDARD = "standard"
    DEAF = "deaf"
    BLIND = "blind"
    DEAFBLIND = "deafblind"


SOUND_CUES: dict[EventType, str] = {
    EventType.KICKOFF: "[kick-off whistle]",
    EventType.GOAL: "[crowd erupts]",
    EventType.SAVE: "[crowd gasps]",
    EventType.SHOT: "[crowd groans]",
    EventType.CORNER: "[crowd rises]",
    EventType.FOUL: "[whistle]",
    EventType.YELLOW_CARD: "[whistle, referee shows a card]",
    EventType.FULL_TIME: "[final whistle]",
}

# Vibration patterns in ms (on, off, on, ...) for the Web Vibration API.
HAPTICS: dict[EventType, list[int]] = {
    EventType.GOAL: [300, 100, 300, 100, 600],
    EventType.SAVE: [150],
    EventType.SHOT: [100],
    EventType.YELLOW_CARD: [100, 50, 100],
    EventType.FULL_TIME: [800],
}


class AccessibleItem(BaseModel):
    event_id: int | None = None
    minute: int | None = None
    text: str
    sound_cue: str | None = None
    spatial: str | None = None
    haptic: list[int] | None = None
    tone_hz: int | None = None
    ssml: str | None = None


class AccessibleRecap(BaseModel):
    profile: Profile
    items: list[AccessibleItem]
    notes: list[str]


def describe_position(e: Event) -> str | None:
    """Spatial description from the acting team's point of view (see models.py)."""
    if e.type in (EventType.KICKOFF, EventType.FULL_TIME):
        return None
    if e.type == EventType.CORNER:
        return f"a corner from the {'left' if e.y <= 50 else 'right'} corner flag"
    if e.x >= 84.3 and 20.2 <= e.y <= 79.8:  # penalty area is ~16.5m deep, ~40m wide
        lane = "central" if 40 <= e.y <= 60 else ("left of centre" if e.y < 40 else "right of centre")
        depth = "close to goal" if e.x >= 92 else "towards the edge of the box"
        return f"inside the penalty area, {lane}, {depth}"
    third = "in their own third" if e.x < 33 else ("in midfield" if e.x < 67 else "in the attacking third")
    lane = "down the left" if e.y < 33 else ("down the right" if e.y > 67 else "through the middle")
    return f"{third}, {lane}"


def threat_tone_hz(e: Event) -> int | None:
    """Pitch rises with chance quality: 220 Hz (low) up to 880 Hz (goal)."""
    if e.type == EventType.GOAL:
        return 880
    if e.xg <= 0:
        return None
    return min(880, 220 + int(e.xg / 0.6 * 660))


def _plain(e: Event, match: Match) -> str:
    m = f"Minute {e.minute}."
    if e.type == EventType.GOAL:
        h, a = match.score_after(e.id)
        return f"{m} Goal for {e.team}. {e.player} scores. Score is {h}-{a}."
    return {
        EventType.SAVE: f"{m} {e.player} shoots. The goalkeeper saves it.",
        EventType.SHOT: f"{m} {e.player} shoots. It misses the goal.",
        EventType.YELLOW_CARD: f"{m} {e.player} gets a yellow card.",
        EventType.FOUL: f"{m} Foul by {e.player}.",
        EventType.CORNER: f"{m} Corner kick to {e.team}.",
        EventType.KICKOFF: "The match starts.",
        EventType.FULL_TIME: "The match is over.",
    }.get(e.type, f"{m} {e.player} has the ball.")


def adapt(match: Match, narrative: Narrative, profile: Profile) -> AccessibleRecap:
    items: list[AccessibleItem] = []
    for s in narrative.statements:
        event = match.event_by_id(s.event_ids[0]) if s.event_ids else None
        if event is None:
            text = s.text
            if profile == Profile.DEAFBLIND:
                text = "\n".join(textwrap.wrap(text, BRAILLE_CELLS))
            items.append(AccessibleItem(text=text))
            continue

        phrase = describe_position(event)
        cue = SOUND_CUES.get(event.type)
        haptic = HAPTICS.get(event.type)
        item = AccessibleItem(event_id=event.id, minute=event.minute, text=s.text)

        if profile == Profile.DEAF:
            plain = _plain(event, match)
            item.text = f"{cue} {plain}" if cue else plain
            item.sound_cue, item.haptic = cue, haptic
        elif profile == Profile.BLIND:
            item.text = f"{s.text} Location: {phrase}." if phrase else s.text
            item.spatial, item.tone_hz = phrase, threat_tone_hz(event)
        elif profile == Profile.DEAFBLIND:
            plain = _plain(event, match)
            if phrase:
                plain += f" Location: {phrase}."
            item.text = "\n".join(textwrap.wrap(plain, BRAILLE_CELLS))
            item.spatial, item.haptic = phrase, haptic
        items.append(item)

    notes = {
        Profile.STANDARD: [],
        Profile.DEAF: [
            "Captions include sound cues so crowd atmosphere is not lost.",
            "Plain-language wording; vibration patterns mark key moments.",
        ],
        Profile.BLIND: [
            "Each event includes a spatial description of where the play happened.",
            "SSML is ready for Azure AI Speech; tone pitch rises with chance quality.",
        ],
        Profile.DEAFBLIND: [
            f"Text is wrapped to {BRAILLE_CELLS} cells for refreshable braille displays.",
            "Vibration patterns replace sound and sight cues.",
        ],
    }[profile]
    return AccessibleRecap(profile=profile, items=items, notes=notes)


def add_ssml(recap: AccessibleRecap, language: str = "en", rate: str = "medium") -> None:
    """Attach Azure AI Speech SSML to each item (call after any translation)."""
    locale, voice = VOICES.get(language, VOICES["en"])
    for item in recap.items:
        item.ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
            f'<voice name="{voice}"><prosody rate="{rate}">{escape(item.text)}</prosody></voice>'
            "</speak>"
        )

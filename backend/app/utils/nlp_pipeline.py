"""
NLP Pipeline for StoryVoice AI - Phase 4
Handles:
  - Text preprocessing & normalization
  - Dialogue vs Narration segmentation
  - Emotion detection per text chunk
  - Named Entity Recognition (characters)
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Emotion labels & their color codes (used by the frontend visualizer)
# ---------------------------------------------------------------------------
EMOTION_LABELS = ["happy", "sad", "angry", "suspenseful", "neutral"]
EMOTION_COLOR_MAP = {
    "happy": "#F5C518",
    "sad": "#4A90D9",
    "angry": "#E84040",
    "suspenseful": "#9B59B6",
    "neutral": "#A0A0A0",
}

# ---------------------------------------------------------------------------
# Lazy-loaded singletons (only initialised on first call)
# ---------------------------------------------------------------------------
_emotion_classifier = None
_spacy_nlp = None


def _get_emotion_classifier():
    """Load the zero-shot classification model (once)."""
    global _emotion_classifier
    if _emotion_classifier is None:
        try:
            from transformers import pipeline
            logger.info("Loading zero-shot emotion classifier …")
            _emotion_classifier = pipeline(
                "zero-shot-classification",
                model="cross-encoder/nli-distilroberta-base",  # ~80 MB, fast on CPU
            )
            logger.info("Emotion classifier loaded.")
        except Exception as exc:
            logger.warning("Could not load transformers pipeline: %s — using rule-based fallback.", exc)
            _emotion_classifier = "rule-based"
    return _emotion_classifier



def _get_spacy_nlp():
    """Load a spaCy NLP model for NER (once)."""
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            try:
                _spacy_nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model 'en_core_web_sm' not found — running: python -m spacy download en_core_web_sm")
                import subprocess, sys
                subprocess.run(
                    [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
                    check=True,
                )
                _spacy_nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy NLP model loaded.")
        except Exception as exc:
            logger.warning("spaCy not available: %s — character extraction disabled.", exc)
            _spacy_nlp = "disabled"
    return _spacy_nlp


# ---------------------------------------------------------------------------
# 4.2 — Text Preprocessing
# ---------------------------------------------------------------------------
def preprocess_text(text: str) -> str:
    """
    Clean and normalise raw story text.
    - Collapse multiple blank lines
    - Strip non-printable characters
    - Normalise curly/smart quotes to straight quotes
    - Strip leading/trailing whitespace
    """
    # Normalise smart / curly quotes to standard ASCII quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')

    # Remove non-printable characters (keep newlines and tabs)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", "", text)

    # Collapse 3+ consecutive blank lines to a double newline
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# 4.3 — Dialogue / Narration segmentation
# ---------------------------------------------------------------------------
_DIALOGUE_RE = re.compile(
    r'("(?:[^"\\]|\\.)*"'       # "double-quoted"
    r"|'(?:[^'\\]|\\.)*')",     # 'single-quoted'
)


def segment_text(text: str) -> List[Dict[str, Any]]:
    """
    Split text into alternating narration and dialogue chunks.
    Returns a list of dicts:  {type: "dialogue"|"narration", text: str}
    """
    segments: List[Dict[str, Any]] = []
    last_end = 0

    for match in _DIALOGUE_RE.finditer(text):
        start, end = match.span()

        # Narration before this dialogue
        narration = text[last_end:start].strip()
        if narration:
            segments.append({"type": "narration", "text": narration})

        # The dialogue chunk itself
        dialogue = match.group().strip()
        if dialogue:
            segments.append({"type": "dialogue", "text": dialogue})

        last_end = end

    # Remaining narration after the last dialogue
    trailing = text[last_end:].strip()
    if trailing:
        segments.append({"type": "narration", "text": trailing})

    # Edge-case: no dialogue found → entire text is narration
    if not segments:
        segments.append({"type": "narration", "text": text.strip()})

    return segments


# ---------------------------------------------------------------------------
# 4.4 — Emotion detection
# ---------------------------------------------------------------------------
_RULE_BASED_KEYWORD_MAP = {
    "happy": ["laugh", "smile", "joy", "happy", "excit", "cheer", "delight", "grin"],
    "sad":   ["cry", "tear", "sob", "mourn", "grief", "sorrow", "weep", "sad", "depress"],
    "angry": ["anger", "furious", "rage", "shout", "scream", "yell", "angry", "mad", "wrath"],
    "suspenseful": ["dark", "shadow", "creak", "silence", "whisper", "watch", "stalk",
                    "mystery", "secret", "danger", "threat", "nervous", "tense"],
}


def _rule_based_emotion(text: str) -> str:
    """Simple keyword-voting fallback for emotion detection."""
    lower = text.lower()
    scores: Dict[str, int] = {emotion: 0 for emotion in _RULE_BASED_KEYWORD_MAP}
    for emotion, keywords in _RULE_BASED_KEYWORD_MAP.items():
        for kw in keywords:
            scores[emotion] += lower.count(kw)
    best = max(scores, key=lambda e: scores[e])
    return best if scores[best] > 0 else "neutral"


def detect_emotion(text: str) -> str:
    """
    Classify the dominant emotion of a text chunk.
    Uses zero-shot transformer model if available, else rule-based.
    """
    if not text.strip():
        return "neutral"

    classifier = _get_emotion_classifier()

    if classifier == "rule-based":
        return _rule_based_emotion(text)

    try:
        result = classifier(
            text[:512],  # truncate to avoid token-limit errors
            candidate_labels=EMOTION_LABELS,
        )
        return result["labels"][0]
    except Exception as exc:
        logger.warning("Emotion classifier inference failed: %s — using rule-based fallback.", exc)
        return _rule_based_emotion(text)


# ---------------------------------------------------------------------------
# 4.5 — Named Entity Recognition (characters)
# ---------------------------------------------------------------------------
def extract_characters(text: str) -> List[Dict[str, Any]]:
    """
    Use spaCy PERSON entities to extract character names from the full story text.
    Returns a list of unique characters with assigned placeholder voice profiles.
    """
    nlp = _get_spacy_nlp()

    if nlp == "disabled":
        return []

    try:
        # Process in chunks to stay within spaCy's token limits
        doc = nlp(text[:100_000])
        names: Dict[str, int] = {}
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                name = ent.text.strip()
                names[name] = names.get(name, 0) + 1

        # Build character list sorted by mention frequency (most-mentioned first)
        sorted_names = sorted(names.items(), key=lambda x: x[1], reverse=True)

        voice_profiles = [
            "narrator_warm",
            "character_deep",
            "character_light",
            "character_gruff",
            "character_soft",
            "character_energetic",
        ]

        characters = []
        for idx, (name, mentions) in enumerate(sorted_names):
            characters.append({
                "name": name,
                "mentions": mentions,
                "voice_profile": voice_profiles[idx % len(voice_profiles)],
            })

        return characters

    except Exception as exc:
        logger.warning("NER extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# 4.6 — Full pipeline orchestrator
# ---------------------------------------------------------------------------
def run_nlp_pipeline(raw_text: str) -> Dict[str, Any]:
    """
    Run the full NLP pipeline on a story's raw text.

    Returns a dict with:
      - preprocessed_text (str)
      - segments (list of {type, text, emotion, color})
      - characters (list of {name, mentions, voice_profile})
      - emotion_summary (dict of emotion -> count)
    """
    # Step 1: Preprocess
    clean_text = preprocess_text(raw_text)

    # Step 2: Segment into dialogue / narration
    segments = segment_text(clean_text)

    # Step 3: Detect emotion per segment
    emotion_summary: Dict[str, int] = {e: 0 for e in EMOTION_LABELS}
    enriched_segments = []
    for seg in segments:
        emotion = detect_emotion(seg["text"])
        emotion_summary[emotion] = emotion_summary.get(emotion, 0) + 1
        enriched_segments.append({
            **seg,
            "emotion": emotion,
            "color": EMOTION_COLOR_MAP.get(emotion, "#A0A0A0"),
        })

    # Step 4: Extract characters from the full clean text
    characters = extract_characters(clean_text)

    return {
        "preprocessed_text": clean_text,
        "segments": enriched_segments,
        "characters": characters,
        "emotion_summary": emotion_summary,
    }

"""
NLP Pipeline for StoryVoice AI - Phase 4 (Launch Ready, From-Scratch Implementation)
Handles:
  - Text preprocessing & normalization (from scratch)
  - Dialogue vs Narration segmentation (from scratch)
  - Emotion detection per text chunk (from-scratch keyword-emotion scoring with negation and intensifiers)
  - Named Entity Recognition for characters (from-scratch rule-based grammar and attribution extractor)

This implementation is 100% offline, zero-dependency, extremely lightweight, and runs instantly.
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
# 4.4 — Emotion detection (From Scratch Lexicon & Rule-based Model)
# ---------------------------------------------------------------------------
EMOTION_LEXICONS = {
    "happy": [
        "joy", "joyful", "joyfully", "happy", "happily", "happiness", "laugh", "laughing", "laughed", "laughter", 
        "smile", "smiled", "smiling", "cheerful", "cheerfully", "delight", "delighted", "delightful", "glad", "gladly", 
        "grin", "grinned", "grinning", "excited", "exciting", "excitement", "celebrate", "celebrating", "celebrated", 
        "celebration", "merry", "mirth", "glee", "gleeful", "thrill", "thrilled", "thrilling", "pleased", "pleasant", 
        "pleasantly", "warm", "warmly", "friendly", "chuckle", "chuckled", "giggle", "giggled", "giggle", "beam", 
        "beamed", "beaming", "joke", "joked", "joking"
    ],
    "sad": [
        "cry", "crying", "cried", "sob", "sobbing", "sobbed", "tear", "tears", "tearful", "tearfully", "sad", "sadly", 
        "sadness", "weep", "weeping", "wept", "mourn", "mourning", "mourned", "mournful", "grief", "grieve", "grieving", 
        "grieved", "sorrow", "sorrowful", "sorrowfully", "depress", "depressed", "depressing", "depression", "despair", 
        "despairing", "gloom", "gloomy", "gloomily", "unhappy", "miserably", "miserable", "misery", "heartbroke", 
        "heartbroken", "pity", "pitiful", "lament", "lamenting", "lonely", "loneliness", "sigh", "sighed", "sighing", 
        "dejected", "hopeless", "helpless", "helplessness"
    ],
    "angry": [
        "anger", "angry", "angrily", "furious", "furiously", "fury", "rage", "raging", "raged", "shout", "shouting", 
        "shouted", "scream", "screaming", "screamed", "yell", "yelling", "yelled", "mad", "madly", "wrath", "wrathful", 
        "annoy", "annoyed", "annoying", "irritate", "irritated", "irritating", "irritation", "growl", "growled", 
        "growling", "snap", "snapped", "snapping", "glare", "glared", "glaring", "bellow", "bellowed", "bellowing", 
        "hate", "hated", "hating", "hatred", "hiss", "hissed", "hissing", "fume", "fumed", "fuming", "outrage", 
        "outraged", "outrageous", "bitter", "bitterly", "hostile", "hostility"
    ],
    "suspenseful": [
        "dark", "darkness", "shadow", "shadows", "shadowy", "creak", "creaking", "creaked", "silence", "silent", 
        "silently", "whisper", "whispering", "whispered", "watch", "watching", "watched", "stalk", "stalking", 
        "stalked", "mystery", "mysterious", "mysteriously", "secret", "secretive", "secretly", "danger", "dangerous", 
        "dangerously", "threat", "threaten", "threatening", "threatened", "nervous", "nervously", "nervousness", 
        "tense", "tension", "fear", "fearful", "fearfully", "feared", "dread", "dreading", "dreaded", "terrify", 
        "terrifying", "terrified", "terror", "horror", "horrific", "creep", "creepy", "creeped", "creeping", 
        "ghost", "ghostly", "phantom", "cold", "coldly", "chill", "chilly", "chilling", "shudder", "shuddered", 
        "shuddering", "tremble", "trembled", "trembling", "shiver", "shivered", "shivering", "panic", "panicked", 
        "panicking", "hide", "hiding", "hid", "escape", "escaping", "escaped", "lurk", "lurking", "lurked", 
        "quiet", "quietly", "quietness", "hush", "hushed", "suspicious", "suspiciously", "suspicion", "caution", 
        "cautious", "cautiously"
    ]
}

NEGATIONS = {"not", "no", "never", "without", "barely", "hardly", "none", "neither", "cant", "cannot", "wasnt", "didnt"}
INTENSIFIERS = {"very", "so", "extremely", "incredibly", "really", "highly", "deeply", "absolutely", "much", "too"}


def detect_emotion(text: str) -> str:
    """
    Classify the dominant emotion of a text chunk using a rules-based NLP algorithm from scratch.
    It evaluates emotional keyword frequencies, negation words, intensifiers, and punctuation cues.
    """
    if not text.strip():
        return "neutral"

    text_lower = text.lower()
    
    # Extract words
    words = re.findall(r'\b[a-z]+\b', text_lower)
    if not words:
        return "neutral"

    scores = {emotion: 0.0 for emotion in EMOTION_LEXICONS}

    # Evaluate each word
    for i, word in enumerate(words):
        word_emotion = None
        for emotion, keywords in EMOTION_LEXICONS.items():
            if word in keywords:
                word_emotion = emotion
                break
        
        if word_emotion:
            # Check for negation words in the window preceding the keyword
            negated = False
            start_idx = max(0, i - 3)
            for j in range(start_idx, i):
                if words[j] in NEGATIONS:
                    negated = True
                    break
            
            # Check for intensifiers preceding the keyword
            multiplier = 1.0
            if i > 0 and words[i-1] in INTENSIFIERS:
                multiplier = 2.0
            
            if negated:
                # If happy is negated, it counts towards sad
                if word_emotion == "happy":
                    scores["sad"] += 1.0 * multiplier
                else:
                    # just ignore or reduce other negated emotions
                    pass
            else:
                scores[word_emotion] += 1.0 * multiplier

    # Punctuation and style analysis
    # Exclamation marks: increase happy/angry scores
    exclamation_count = text.count("!")
    if exclamation_count > 0:
        if scores["angry"] > scores["happy"]:
            scores["angry"] += 1.5 * exclamation_count
        elif scores["happy"] > scores["angry"]:
            scores["happy"] += 1.5 * exclamation_count
        else:
            scores["happy"] += 0.5 * exclamation_count
            scores["angry"] += 0.5 * exclamation_count

    # Ellipsis or dashes: increase suspenseful score
    ellipsis_count = text.count("...") + text.count("—") + text.count("--")
    if ellipsis_count > 0:
        scores["suspenseful"] += 1.0 * ellipsis_count

    # All-caps words (ignoring single letter 'I' or very short words)
    all_caps_words = [w for w in re.findall(r'\b[A-Z]{2,}\b', text) if w != "OK"]
    if all_caps_words:
        if scores["angry"] >= scores["happy"]:
            scores["angry"] += 1.0 * len(all_caps_words)
        else:
            scores["happy"] += 1.0 * len(all_caps_words)

    # Determine highest scoring emotion
    best_emotion = "neutral"
    highest_score = 0.0
    for emotion, score in scores.items():
        if score > highest_score:
            highest_score = score
            best_emotion = emotion

    # Require a minimum score threshold to avoid false positives on short texts
    if highest_score < 0.2:
        return "neutral"

    return best_emotion


# ---------------------------------------------------------------------------
# 4.5 — Named Entity Recognition (characters from scratch)
# ---------------------------------------------------------------------------
def extract_characters(text: str) -> List[Dict[str, Any]]:
    """
    Extract character names from the story text using a rules-based NLP algorithm from scratch.
    It identifies capitalized names, attribution verbs (like 'said', 'whispered'), and title prefixes,
    excluding common English words.
    """
    if not text.strip():
        return []

    # Compile list of common English words / stopwords / non-character capitalized words to exclude
    stopwords = {
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
        "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
        "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
        "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
        "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
        "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
        "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
        "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
        "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
        "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
        "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june", "july", "august", "september",
        "october", "november", "december", "london", "paris", "new", "york", "mr", "mrs", "ms",
        "dr", "professor", "sir", "lady", "uncle", "aunt", "yes", "no", "hello", "hi", "oh",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "first", "second", "third", "morning", "night", "day", "evening", "afternoon",
        "wood", "forest", "room", "house", "town", "city", "street", "road", "mountain",
        "river", "lake", "ocean", "sea", "sky", "sun", "moon", "star", "wind", "rain",
        "shadows", "shadow", "stone", "floor", "storm", "world", "god", "heaven", "hell",
        "father", "mother", "brother", "sister", "son", "daughter", "friend", "man", "woman",
        "boy", "girl", "baby", "child", "children", "people", "someone", "anyone", "everyone",
        "nothing", "something", "anything", "everything", "way", "time", "year", "years"
    }

    # Dialogue attribution verbs
    attribution_verbs = {
        "said", "whispered", "replied", "asked", "shouted", "yelled", "cried", "muttered", 
        "thought", "called", "exclaimed", "sighed", "gasped", "groaned", "laughed", "smiled", 
        "grumbled", "snapped", "whimpered", "stammered", "stutters", "stuttered", "added", 
        "continued", "began", "murmured", "screamed", "warned", "demanded", "snorted", 
        "hissed", "growled", "roared", "wept", "sobbed", "chuckle", "chuckled"
    }

    # Split text into sentences using simple punctuation splitting
    sentence_delimiters = re.compile(r'[.!?\n]+')
    sentences = sentence_delimiters.split(text)

    candidate_scores = {}

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Find words and check capitalization
        words = re.findall(r'\b[A-Za-z]+\b', sentence)
        if not words:
            continue
            
        for i, word in enumerate(words):
            # Check if capitalized and not a stopword (case-insensitive check)
            if word[0].isupper() and word.lower() not in stopwords:
                # Is it part of a compound name? (e.g. John Smith)
                name = word
                j = i + 1
                while j < len(words) and words[j][0].isupper() and words[j].lower() not in stopwords:
                    name += " " + words[j]
                    j += 1
                
                score = 1.0
                
                # Check if it is near an attribution verb in the sentence
                sentence_lower = sentence.lower()
                for verb in attribution_verbs:
                    # Look for "[Name] said" or "said [Name]"
                    if re.search(r'\b' + re.escape(name.lower()) + r'\s+(?:\w+\s+){0,2}' + re.escape(verb) + r'\b', sentence_lower) or \
                       re.search(r'\b' + re.escape(verb) + r'\s+(?:\w+\s+){0,2}' + re.escape(name.lower()) + r'\b', sentence_lower):
                        score += 15.0
                
                # Check if preceded by a title prefix
                if i > 0 and words[i-1].lower() in {"mr", "mrs", "ms", "dr", "professor", "sir", "lady", "uncle", "aunt"}:
                    score += 10.0
                    
                # If it's the very first word in the sentence, give it lower confidence unless boosted
                if i == 0 and score == 1.0:
                    score = 0.2
                    
                candidate_scores[name] = candidate_scores.get(name, 0.0) + score

    # Filter out candidates with low score or very short names
    filtered_candidates = {}
    for name, score in candidate_scores.items():
        name_clean = name.strip()
        if len(name_clean) < 2:
            continue
        # If the name is composed of words that are all stopwords, skip
        words_in_name = name_clean.split()
        if all(w.lower() in stopwords for w in words_in_name):
            continue
            
        # Require a minimum score threshold
        if score >= 1.0:
            filtered_candidates[name_clean] = score

    # Sort candidates by score descending
    sorted_candidates = sorted(filtered_candidates.items(), key=lambda x: x[1], reverse=True)
    
    # Map to voice profiles
    voice_profiles = [
        "character_deep",
        "character_light",
        "character_gruff",
        "character_soft",
        "character_energetic",
    ]
    
    characters = []
    for idx, (name, score) in enumerate(sorted_candidates[:6]): # Limit to top 6 characters
        characters.append({
            "name": name,
            "mentions": int(score),
            "voice_profile": voice_profiles[idx % len(voice_profiles)]
        })
        
    return characters


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

from pathlib import Path
import math
import random
import struct
import wave
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Sample rate for generated audio
SAMPLE_RATE = 22050

VOICE_RATES = {
    "light": 175,
    "soft": 150,
    "deep": 145,
    "gruff": 135,
    "energetic": 185,
}

SYNTH_CONFIGS = {
    "deep": {"base_freq": 95.0, "wave_type": "sine", "vibrato_freq": 0.0, "vibrato_amp": 0.0, "speed_modifier": 0.9},
    "gruff": {"base_freq": 80.0, "wave_type": "square", "vibrato_freq": 3.0, "vibrato_amp": 3.0, "speed_modifier": 0.8},
    "light": {"base_freq": 270.0, "wave_type": "sine", "vibrato_freq": 5.0, "vibrato_amp": 8.0, "speed_modifier": 1.1},
    "soft": {"base_freq": 220.0, "wave_type": "triangle", "vibrato_freq": 4.0, "vibrato_amp": 5.0, "speed_modifier": 0.95},
    "energetic": {"base_freq": 210.0, "wave_type": "sine", "vibrato_freq": 7.0, "vibrato_amp": 15.0, "speed_modifier": 1.25},
    "female": {"base_freq": 200.0, "wave_type": "sine", "vibrato_freq": 0.0, "vibrato_amp": 0.0, "speed_modifier": 1.0},
}
DEFAULT_SYNTH_CONFIG = {"base_freq": 140.0, "wave_type": "sine", "vibrato_freq": 0.0, "vibrato_amp": 0.0, "speed_modifier": 1.0}


def generate_procedural_speech(text: str, voice_profile: str, emotion: str, output_path: str) -> None:
    """
    Procedural audio speech generator (chiptune/synthesizer style) with a pyttsx3 spoken speech optimizer.
    Generates spoken audio on supported systems, and falls back to chiptune waves on unsupported systems.
    
    Emotional swings in pitch/speed are disabled to maintain a clean, professional, and consistent audiobook narration.
    """
    logger.info(f"Synthesizing segment: '{text[:30]}...' with profile={voice_profile}, emotion={emotion}")
    
    # Try spoken TTS first
    try:
        import pyttsx3
        logger.info("Initializing pyttsx3 offline text-to-speech engine...")
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        
        is_female_profile = any(token in voice_profile for token in ("female", "light", "soft"))
        target_voice_name = "zira" if is_female_profile else "david"
        selected_voice_id = next((v.id for v in voices if target_voice_name in v.name.lower()), None)
        base_rate = next((rate for key, rate in VOICE_RATES.items() if key in voice_profile), 160)
                
        if selected_voice_id:
            engine.setProperty("voice", selected_voice_id)
            
        # Set rate and volume
        engine.setProperty("rate", base_rate)
        engine.setProperty("volume", 1.0)
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
        # Save to file
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        
        # Verify the file was generated and is valid (not 0 bytes)
        out_file = Path(output_path)
        if out_file.exists() and out_file.stat().st_size > 100:
            logger.info(f"Successfully generated spoken speech at {output_path}")
            return
        else:
            logger.warning("pyttsx3 output file was invalid. Falling back to chiptune generator.")
    except Exception as exc:
        logger.warning(f"pyttsx3 speech synthesis failed: {exc}. Falling back to chiptune generator.")
    
    # --- Chiptune Fallback Synthesizer (Zero-Dependency) ---
    cfg = next((cfg for key, cfg in SYNTH_CONFIGS.items() if key in voice_profile), DEFAULT_SYNTH_CONFIG)
    base_freq = cfg["base_freq"]
    wave_type = cfg["wave_type"]
    vibrato_freq = cfg["vibrato_freq"]
    vibrato_amp = cfg["vibrato_amp"]
    speed_modifier = cfg["speed_modifier"]
        
    pitch_modifier = 1.0
    noise_volume = 0.04
    
    # Sound durations for different types of characters
    char_duration = 0.045 / speed_modifier
    vowel_duration = 0.06 / speed_modifier
    consonant_duration = 0.035 / speed_modifier
    space_duration = 0.07 / speed_modifier
    punct_duration = 0.22 / speed_modifier
    
    all_frames = []
    t_global = 0.0
    
    for char in text.lower():
        # Determine sound type and duration
        if char in "aeiouy":
            dur, sound_type = vowel_duration, "vowel"
        elif char in "szfvhx":
            dur, sound_type = consonant_duration, "noise"
        elif char in "ptkbdg":
            dur, sound_type = consonant_duration * 0.5, "plosive"
        elif char in "mnlrwj":
            dur, sound_type = consonant_duration, "nasal"
        elif char == " ":
            dur, sound_type = space_duration, "silence"
        elif char in ".,!?;:":
            dur, sound_type = punct_duration, "silence"
        else:
            dur, sound_type = char_duration, "other"
            
        num_samples = int(SAMPLE_RATE * dur)
        if num_samples <= 0:
            continue
            
        for i in range(num_samples):
            t = float(i) / SAMPLE_RATE
            t_glob = t_global + t
            
            # Base frequency with vibrato
            freq = base_freq * pitch_modifier
            if vibrato_amp > 0:
                freq += vibrato_amp * math.sin(2 * math.pi * vibrato_freq * t_glob)
                
            val = 0.0
            
            if sound_type == "vowel":
                val = (
                    0.5 * math.sin(2 * math.pi * freq * t_glob) +
                    0.3 * math.sin(2 * math.pi * 2 * freq * t_glob) +
                    0.15 * math.sin(2 * math.pi * 3 * freq * t_glob)
                )
            elif sound_type == "noise":
                val = 0.35 * (random.random() * 2.0 - 1.0)
            elif sound_type == "plosive":
                decay = math.exp(-35.0 * t)
                val = decay * 0.55 * (random.random() * 2.0 - 1.0)
            elif sound_type == "nasal":
                val = 0.55 * math.sin(2 * math.pi * (freq * 0.9) * t_glob)
            elif sound_type == "silence":
                val = 0.0
            else:
                if wave_type == "square":
                    val = 0.4 if math.sin(2 * math.pi * freq * t_glob) >= 0 else -0.4
                elif wave_type == "triangle":
                    val = 0.5 * (abs((t_glob * freq) % 1.0 - 0.5) * 4.0 - 1.0)
                else:
                    val = 0.55 * math.sin(2 * math.pi * freq * t_glob)
                    
            # Add noise if not silent
            if sound_type != "silence" and noise_volume > 0:
                val += noise_volume * (random.random() * 2.0 - 1.0)
                
            # Envelope to prevent clicks
            fade_len = min(num_samples // 4, int(SAMPLE_RATE * 0.01))
            if fade_len > 0:
                if i < fade_len:
                    val *= (i / fade_len)
                elif i > num_samples - fade_len:
                    val *= ((num_samples - i) / fade_len)
                    
            # Convert to 16-bit PCM
            scaled_val = max(-32768, min(32767, int(val * 28000)))
            all_frames.append(struct.pack('<h', scaled_val))
            
        t_global += dur
        
    # Write to WAV file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b''.join(all_frames))


def concatenate_wav_files(input_files: List[str], output_file: str) -> None:
    """Concatenates multiple WAV files with identical parameters into a single WAV file."""
    if not input_files:
        raise ValueError("Input files list is empty")
        
    logger.info(f"Concatenating {len(input_files)} WAV files to: {output_file}")
    
    with wave.open(input_files[0], 'rb') as first_file:
        params = first_file.getparams()
        
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(output_file, 'wb') as out_file:
        out_file.setparams(params)
        for file in input_files:
            with wave.open(file, 'rb') as in_file:
                out_file.writeframes(in_file.readframes(in_file.getnframes()))


def get_voice_profile_for_segment(
    segment: Dict[str, Any], 
    characters: List[Dict[str, Any]], 
    prev_text: str = "", 
    narrator_voice: str = "warm"
) -> str:
    """Helper to determine the best voice profile for a text segment."""
    if segment.get("type") == "narration":
        return f"narrator_{narrator_voice}"
        
    text = segment.get("text", "").lower()
    combined_context = f"{text} {prev_text}".lower()
    
    # Check if a known character is mentioned in or near this dialogue
    for char in characters:
        name = char.get("name", "").lower()
        if name and name in combined_context:
            return char.get("voice_profile", "character_light")
            
    # Try to find a character profile that isn't the narrator
    return next(
        (
            p for c in characters 
            if (p := c.get("voice_profile")) and p not in ("narrator_warm", "narrator_male", "narrator_female")
        ),
        "character_light"
    )


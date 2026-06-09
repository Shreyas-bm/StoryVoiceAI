import os
import math
import random
import struct
import wave
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Sample rate for generated audio
SAMPLE_RATE = 22050

def generate_procedural_speech(text: str, voice_profile: str, emotion: str, output_path: str):
    """
    Procedural audio speech generator (chiptune/synthesizer style).
    Generates distinct sounds based on characters and emotions with varying pitch, tempo, and timbre.
    Requires no external dependencies (pure Python wave generation).
    """
    logger.info(f"Synthesizing segment: '{text[:30]}...' with profile={voice_profile}, emotion={emotion}")
    
    # Base frequency/pitch based on voice profile
    base_freq = 180.0
    if "deep" in voice_profile or "gruff" in voice_profile:
        base_freq = 95.0
    elif "light" in voice_profile or "soft" in voice_profile:
        base_freq = 270.0
    elif "energetic" in voice_profile:
        base_freq = 210.0
        
    # Emotion multipliers
    speed_modifier = 1.0
    pitch_modifier = 1.0
    vibrato_freq = 0.0
    vibrato_amp = 0.0
    noise_volume = 0.04
    wave_type = "sine"
    
    if emotion == "happy":
        pitch_modifier = 1.15
        speed_modifier = 1.25
        vibrato_freq = 6.0
        vibrato_amp = 12.0
    elif emotion == "sad":
        pitch_modifier = 0.82
        speed_modifier = 0.75
        vibrato_freq = 2.5
        vibrato_amp = 4.0
        noise_volume = 0.02
    elif emotion == "angry":
        pitch_modifier = 1.3
        speed_modifier = 1.3
        noise_volume = 0.12
        wave_type = "square"
    elif emotion == "suspenseful":
        pitch_modifier = 0.75
        speed_modifier = 0.8
        noise_volume = 0.08
        wave_type = "triangle"
        
    # Sound durations for different types of characters
    char_duration = 0.045 / speed_modifier
    vowel_duration = 0.06 / speed_modifier
    consonant_duration = 0.035 / speed_modifier
    space_duration = 0.07 / speed_modifier
    punct_duration = 0.22 / speed_modifier
    
    all_frames = []
    t_global = 0.0
    
    text = text.lower()
    
    for char in text:
        # Determine sound type and duration
        if char in "aeiouy":
            dur = vowel_duration
            sound_type = "vowel"
        elif char in "szfvhx":
            dur = consonant_duration
            sound_type = "noise"
        elif char in "ptkbdg":
            dur = consonant_duration * 0.5
            sound_type = "plosive"
        elif char in "mnlrwj":
            dur = consonant_duration
            sound_type = "nasal"
        elif char == " ":
            dur = space_duration
            sound_type = "silence"
        elif char in ".,!?;:":
            dur = punct_duration
            sound_type = "silence"
        else:
            dur = char_duration
            sound_type = "other"
            
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
                # Rich multi-harmonic synthesis for vowels
                val = (
                    0.5 * math.sin(2 * math.pi * freq * t_glob) +
                    0.3 * math.sin(2 * math.pi * 2 * freq * t_glob) +
                    0.15 * math.sin(2 * math.pi * 3 * freq * t_glob)
                )
            elif sound_type == "noise":
                # Noise for sibilants/fricatives
                val = 0.35 * (random.random() * 2.0 - 1.0)
            elif sound_type == "plosive":
                # Plosive pop with rapid exponential decay
                decay = math.exp(-35.0 * t)
                val = decay * 0.55 * (random.random() * 2.0 - 1.0)
            elif sound_type == "nasal":
                # Lower frequency muffled tone
                val = 0.55 * math.sin(2 * math.pi * (freq * 0.9) * t_glob)
            elif sound_type == "silence":
                val = 0.0
            else:
                # Default character synth
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
            scaled_val = int(val * 28000)
            scaled_val = max(-32768, min(32767, scaled_val))
            all_frames.append(struct.pack('<h', scaled_val))
            
        t_global += dur
        
    # Write to WAV file
    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b''.join(all_frames))


def concatenate_wav_files(input_files: List[str], output_file: str):
    """Concatenates multiple WAV files with identical parameters into a single WAV file."""
    if not input_files:
        raise ValueError("Input files list is empty")
        
    logger.info(f"Concatenating {len(input_files)} WAV files to: {output_file}")
    
    with wave.open(input_files[0], 'rb') as first_file:
        params = first_file.getparams()
        
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with wave.open(output_file, 'wb') as out_file:
        out_file.setparams(params)
        for file in input_files:
            with wave.open(file, 'rb') as in_file:
                out_file.writeframes(in_file.readframes(in_file.getnframes()))


def get_voice_profile_for_segment(segment: Dict[str, Any], characters: List[Dict[str, Any]], prev_text: str = "") -> str:
    """Helper to determine the best voice profile for a text segment."""
    if segment.get("type") == "narration":
        return "narrator_warm"
        
    text = segment.get("text", "").lower()
    combined_context = (text + " " + prev_text).lower()
    
    # Check if a known character is mentioned in or near this dialogue
    for char in characters:
        name = char.get("name", "").lower()
        if name and name in combined_context:
            return char.get("voice_profile", "character_light")
            
    # Try to find a character profile that isn't the narrator
    char_profiles = [c.get("voice_profile") for c in characters if c.get("voice_profile") != "narrator_warm"]
    if char_profiles:
        return char_profiles[0]
        
    return "character_light"

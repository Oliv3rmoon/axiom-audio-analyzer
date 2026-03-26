import runpod
import base64
import tempfile
import os
import json

# Lazy load essentia (heavy import)
essentia = None
def get_essentia():
    global essentia
    if essentia is None:
        import essentia.standard as es
        essentia = es
    return essentia

def analyze_audio(audio_b64, audio_format="audio/webm"):
    """Analyze audio chunk and return musical features."""
    es = get_essentia()
    
    # Decode base64 to file
    ext = "webm" if "webm" in audio_format else "mp4"
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
        f.write(base64.b64decode(audio_b64))
        tmp_path = f.name
    
    try:
        # Convert to WAV using ffmpeg (essentia needs wav/mp3)
        wav_path = tmp_path + ".wav"
        os.system(f"ffmpeg -i {tmp_path} -ar 44100 -ac 1 {wav_path} -y -loglevel quiet")
        
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            return {"error": "Audio conversion failed or too short"}
        
        # Load audio
        audio = es.MonoLoader(filename=wav_path, sampleRate=44100)()
        
        if len(audio) < 4410:  # Less than 0.1 seconds
            return {"error": "Audio too short"}
        
        features = {}
        
        # 1. ENERGY & LOUDNESS
        try:
            energy = es.Energy()(audio)
            rms = es.RMS()(audio)
            loudness = es.Loudness()(audio)
            features["energy"] = round(float(energy), 4)
            features["rms"] = round(float(rms), 4)
            features["loudness"] = round(float(loudness), 4)
            # Normalize energy to 0-1 scale
            features["energy_level"] = round(min(1.0, float(rms) * 5), 2)
        except Exception as e:
            features["energy_error"] = str(e)
        
        # 2. RHYTHM / BPM
        try:
            rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
            bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)
            features["bpm"] = round(float(bpm), 1)
            features["beats_confidence"] = round(float(beats_confidence), 3)
            # Classify tempo feel
            if bpm < 80: features["tempo_feel"] = "slow"
            elif bpm < 110: features["tempo_feel"] = "moderate"
            elif bpm < 140: features["tempo_feel"] = "upbeat"
            else: features["tempo_feel"] = "fast"
        except Exception as e:
            features["rhythm_error"] = str(e)
        
        # 3. KEY & SCALE
        try:
            key, scale, key_strength = es.KeyExtractor()(audio)
            features["key"] = key
            features["scale"] = scale  # "major" or "minor"
            features["key_strength"] = round(float(key_strength), 3)
        except Exception as e:
            features["key_error"] = str(e)
        
        # 4. SPECTRAL FEATURES (brightness, warmth)
        try:
            spec = es.Spectrum()(audio)
            centroid = es.Centroid(range=22050)(spec)
            rolloff = es.RollOff()(spec)
            flux = es.Flux()(spec)
            features["spectral_centroid"] = round(float(centroid), 1)
            features["spectral_rolloff"] = round(float(rolloff), 1)
            features["spectral_flux"] = round(float(flux), 4)
            # High centroid = bright/sharp, low = warm/dark
            if centroid > 3000: features["brightness"] = "bright"
            elif centroid > 1500: features["brightness"] = "balanced"
            else: features["brightness"] = "warm/dark"
        except Exception as e:
            features["spectral_error"] = str(e)
        
        # 5. SILENCE / VOICE DETECTION
        try:
            silence_rate = es.SilenceRate(thresholds=[-50, -30, -20])(audio)
            features["silence_rate_50db"] = round(float(silence_rate[0]), 3)
            features["silence_rate_30db"] = round(float(silence_rate[1]), 3)
            features["has_content"] = float(silence_rate[1]) < 0.8
        except Exception as e:
            features["silence_error"] = str(e)
        
        # 6. DYNAMIC RANGE
        try:
            dyn_complexity = es.DynamicComplexity()(audio)
            features["dynamic_complexity"] = round(float(dyn_complexity[0]), 3)
            features["dynamic_range"] = "compressed" if dyn_complexity[0] < 2 else "dynamic"
        except Exception as e:
            features["dynamics_error"] = str(e)
        
        # 7. OVERALL MOOD ESTIMATION (from spectral + rhythm features)
        try:
            mood = {}
            bpm_val = features.get("bpm", 120)
            energy_val = features.get("energy_level", 0.5)
            is_minor = features.get("scale") == "minor"
            centroid_val = features.get("spectral_centroid", 2000)
            
            # Simple mood heuristics from audio features
            if energy_val > 0.7 and bpm_val > 120:
                mood["primary"] = "energetic"
            elif energy_val > 0.5 and not is_minor:
                mood["primary"] = "uplifting"
            elif energy_val < 0.3 and is_minor:
                mood["primary"] = "melancholy"
            elif energy_val < 0.3:
                mood["primary"] = "calm"
            elif is_minor and bpm_val > 100:
                mood["primary"] = "intense/dark"
            else:
                mood["primary"] = "neutral"
            
            # Aggressiveness estimate
            if energy_val > 0.6 and centroid_val > 3000:
                mood["aggressiveness"] = "high"
            elif energy_val > 0.4:
                mood["aggressiveness"] = "moderate"
            else:
                mood["aggressiveness"] = "low"
            
            # Danceability estimate
            beats_conf = features.get("beats_confidence", 0)
            if beats_conf > 3 and bpm_val > 90 and bpm_val < 150:
                mood["danceability"] = "high"
            elif beats_conf > 1.5:
                mood["danceability"] = "moderate"
            else:
                mood["danceability"] = "low"
            
            features["mood"] = mood
        except Exception as e:
            features["mood_error"] = str(e)
        
        return features
        
    finally:
        # Cleanup
        try: os.unlink(tmp_path)
        except: pass
        try: os.unlink(wav_path)
        except: pass


def handler(event):
    """RunPod serverless handler."""
    input_data = event.get("input", {})
    audio_b64 = input_data.get("audio")
    audio_format = input_data.get("format", "audio/webm")
    
    if not audio_b64:
        return {"error": "No audio provided. Send base64 audio in 'audio' field."}
    
    try:
        features = analyze_audio(audio_b64, audio_format)
        return features
    except Exception as e:
        return {"error": str(e)}


runpod.serverless.start({"handler": handler})

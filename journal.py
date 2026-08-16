"""Voice journal. Record yourself talking for 60-90 seconds at end of day.
Transcribed and stored as the richest data source in the system.
"""
import os
import time
from datetime import date

import config


def record_and_transcribe(seconds=90):
    """Record from mic, transcribe, return text."""
    try:
        import sounddevice as sd
        import speech_recognition as sr

        fs = 16000
        print(f"Recording for {seconds} seconds...")
        rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1,
                     dtype="int16")
        sd.wait()

        audio = sr.AudioData(rec.tobytes(), fs, 2)
        r = sr.Recognizer()
        text = r.recognize_google(audio)
        return text
    except Exception as e:
        return f"(transcription failed: {e})"


def save_journal(text):
    """Save journal entry to daily file."""
    os.makedirs("journals", exist_ok=True)
    path = os.path.join("journals", f"{date.today().isoformat()}.txt")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%I:%M %p')}]\n{text}\n")
    return path


def get_recent(days=7):
    """Get recent journal entries for brain context."""
    from datetime import timedelta
    entries = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        path = os.path.join("journals", f"{d}.txt")
        if os.path.exists(path):
            try:
                content = open(path, encoding="utf-8").read()[:500]
                entries.append(f"[{d}] {content}")
            except Exception:
                pass
    return "\n".join(entries) if entries else ""

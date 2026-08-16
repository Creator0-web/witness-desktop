"""Microphone input -> text. Uses sounddevice to record and Google's free
web speech recognizer to transcribe (needs internet). Returns "" on failure.
"""

def listen(seconds=8):
    try:
        import sounddevice as sd
        import speech_recognition as sr
        fs = 16000
        rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1,
                     dtype="int16")
        sd.wait()
        audio = sr.AudioData(rec.tobytes(), fs, 2)
        r = sr.Recognizer()
        return r.recognize_google(audio)
    except Exception:
        return ""

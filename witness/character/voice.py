"""Voice output using Microsoft Edge TTS (natural neural voices, free).
Falls back to Windows SAPI if edge-tts isn't installed.
"""
import queue
import subprocess
import threading
import tempfile
import os

import config

_voice_q = queue.Queue()
bubble_q = queue.Queue()
_state = None
_use_edge = None  # None = not checked yet


def start(state):
    global _state
    _state = state
    threading.Thread(target=_worker, daemon=True).start()


def speak(text: str):
    bubble_q.put(text)
    _voice_q.put(text)


def speak_voice_only(text: str):
    _voice_q.put(text)


def _check_edge():
    global _use_edge
    try:
        import edge_tts
        _use_edge = True
    except ImportError:
        _use_edge = False
    return _use_edge


def _speak_edge(text):
    """Use edge-tts: generate mp3, play with PowerShell."""
    import asyncio
    import edge_tts

    tmp = os.path.join(tempfile.gettempdir(), "witness_voice.mp3")

    async def gen():
        # en-US-GuyNeural = natural male coach voice
        # alternatives: en-US-AndrewNeural, en-US-ChristopherNeural
        communicate = edge_tts.Communicate(text, "en-US-AndrewNeural",
                                            rate="+15%")
        await communicate.save(tmp)

    asyncio.run(gen())

    # play the mp3 with PowerShell
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command",
         f'(New-Object Media.SoundPlayer "{tmp}").PlaySync()'],
        timeout=45,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000
    )


def _speak_edge_wmplayer(text):
    """Fallback: use edge-tts with wmplayer for mp3 playback."""
    import asyncio
    import edge_tts

    tmp = os.path.join(tempfile.gettempdir(), "witness_voice.mp3")

    async def gen():
        communicate = edge_tts.Communicate(text, "en-US-AndrewNeural",
                                            rate="+15%")
        await communicate.save(tmp)

    asyncio.run(gen())

    # PowerShell MediaPlayer for mp3
    ps = (
        f'$p = New-Object System.Windows.Media.MediaPlayer;'
        f'$p.Open([uri]"{tmp}");'
        f'$p.Play();'
        f'Start-Sleep -Milliseconds 500;'
        f'while($p.Position -lt $p.NaturalDuration.TimeSpan)'
        f'{{Start-Sleep -Milliseconds 200}};'
        f'$p.Close()'
    )
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden",
         "-Command", f"Add-Type -AssemblyName PresentationCore; {ps}"],
        timeout=60,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000
    )


def _speak_sapi(text):
    """Fallback: Windows built-in SAPI voice."""
    safe = text.replace("'", "''")
    ps_script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.Rate = 2;"
        f"$s.Speak('{safe}');"
        "$s.Dispose()"
    )
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
        timeout=45,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000
    )


def _worker():
    while True:
        text = _voice_q.get()
        if _state is not None and _state.get("muted"):
            continue

        if _use_edge is None:
            _check_edge()

        if _use_edge:
            try:
                _speak_edge_wmplayer(text)
                continue
            except Exception:
                pass
            try:
                _speak_edge(text)
                continue
            except Exception:
                pass

        # fallback to SAPI
        try:
            _speak_sapi(text)
        except Exception:
            pass

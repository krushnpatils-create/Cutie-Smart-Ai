import ast
import asyncio
import collections
import contextlib
import datetime
import importlib.util
import json
import math
import operator
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter
import tkinter.messagebox
import urllib.request
import webbrowser
from array import array
from pathlib import Path
from urllib.parse import quote, quote_plus

import customtkinter as ctk
import edge_tts
import pygame
import speech_recognition as sr
from google import genai
from google.genai import types

# ----------------------------------------------------------------------------
# सेटिंग्ज
# ----------------------------------------------------------------------------
ASSISTANT_NAME = "Cutie"
VOICE = "mr-IN-AarohiNeural"

# "सारा" / "sara" मुद्दाम काढले आहेत: "सारा दिवस" सारख्या सामान्य शब्दांवर ट्रिगर होत होते.
WAKE_WORDS = ["हे झारा", "हे ज़ारा", "hey zara", "hi zara", "झारा", "ज़ारा", "zara"]

# पहिले मॉडेल उपलब्ध नसेल (404) किंवा लोड असेल तर पुढच्याकडे आपोआप जाते.
# Flash-Lite सर्वात वेगवान; नंतर 3.8 Flash, मग 3.6 Flash (Google च्या docs नुसार, नोव्हेंबर 2026)
MODEL_CANDIDATES = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]

# AI ने सांगितलेले अॅप फक्त या यादीतलेच उघडले जातात (shell वापरला जात नाही).
APP_ALLOWLIST = {
    "explorer": "explorer.exe",
    "edge": "msedge.exe",
    "msedge": "msedge.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "taskmgr": "taskmgr.exe",
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "cmd": "cmd.exe",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
}
VSCODE_NAMES = {"code", "vscode", "vs code"}
PROMPT_APPS = (
    "explorer | edge | chrome | firefox | taskmgr | notepad | calc | paint | "
    "word | excel | powerpoint | cmd | terminal | powershell | settings | camera | clock | code"
)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# open_item मध्ये हे प्रकार कधीच उघडले जात नाहीत (चुकून चालणाऱ्या फाइल्स टाळण्यासाठी).
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".msi", ".scr", ".com", ".lnk", ".reg", ".hta", ".jar", ".dll",
}

OPEN_WORDS = ["उघड", "open", "ओपन", "opan", "oepn", "सुरू", "start", "launch", "लाव", "चालू", "चालव"]
FILLER_WORDS = {
    "youtube", "युट्यूब", "google", "गुगल", "search", "सर्च", "शोध", "शोधा",
    "उघड", "उघडा", "कर", "करा", "वर", "open", "on", "in", "for", "साठी",
}

MARATHI_MONTHS = [
    "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून",
    "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर",
]
MARATHI_WEEKDAYS = ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

pygame.mixer.init()

_DEVANAGARI = "\u0900-\u097F"

# ----------------------------------------------------------------------------
# \u0921\u0947\u091F\u093E \u0938\u093E\u0920\u0935\u0923 (~/.zara): \u0938\u0947\u091F\u093F\u0902\u0917\u094D\u091C, \u0906\u0920\u0935\u0923, \u0928\u094B\u091F\u094D\u0938, \u091F\u093E\u0938\u094D\u0915
# ----------------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.expanduser("~"), ".zara")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.txt")
TODOS_FILE = os.path.join(DATA_DIR, "todos.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
MAX_HISTORY_MESSAGES = 16  # \u0938\u092E \u0938\u0902\u0916\u094D\u092F\u093E \u0920\u0947\u0935\u093E, \u092E\u094D\u0939\u0923\u091C\u0947 history \u0928\u0947\u0939\u092E\u0940 "user" \u092A\u093E\u0938\u0942\u0928 \u0938\u0941\u0930\u0942 \u0939\u094B\u0924\u0947
_file_lock = threading.Lock()


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    try:
        with _file_lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
    except OSError as e:
        print(f"\u0938\u0947\u0935\u094D\u0939 \u090F\u0930\u0930 ({path}): {e}")


settings = {"voice": VOICE, "rate": 15, "name": "", "last_file": ""}
_saved_settings = load_json(SETTINGS_FILE, {})
if isinstance(_saved_settings, dict):
    if isinstance(_saved_settings.get("last_file"), str):
        settings["last_file"] = _saved_settings["last_file"]
    if isinstance(_saved_settings.get("voice"), str) and _saved_settings["voice"].startswith("mr-IN-"):
        settings["voice"] = _saved_settings["voice"]
    if isinstance(_saved_settings.get("rate"), int):
        settings["rate"] = max(-40, min(50, _saved_settings["rate"]))
    if isinstance(_saved_settings.get("name"), str):
        settings["name"] = _saved_settings["name"][:30]


def save_settings() -> None:
    save_json(SETTINGS_FILE, settings)


def load_history() -> list[dict]:
    raw = load_json(HISTORY_FILE, [])
    clean: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                role = item["role"]
                text = item["parts"][0]["text"]
            except (KeyError, IndexError, TypeError):
                continue
            if role in ("user", "model") and isinstance(text, str):
                clean.append({"role": role, "parts": [{"text": text}]})
    clean = clean[-MAX_HISTORY_MESSAGES:]
    while clean and clean[0]["role"] != "user":
        clean.pop(0)
    if clean and clean[-1]["role"] != "model":
        clean.pop()
    return clean


def add_note(text: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M} | {text.replace(chr(10), ' ')}\n"
    with _file_lock, open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def read_notes(limit: int = 5) -> list[str]:
    try:
        with open(NOTES_FILE, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    except OSError:
        return []
    return [ln.split(" | ", 1)[-1] for ln in lines[-limit:]]


def load_todos() -> list[dict]:
    raw = load_json(TODOS_FILE, [])
    if not isinstance(raw, list):
        return []
    return [
        {"text": str(t["text"]), "done": bool(t.get("done"))}
        for t in raw
        if isinstance(t, dict) and "text" in t
    ]


# ----------------------------------------------------------------------------
# Gemini client (key नसेल तर import वेळी क्रॅश होऊ नये म्हणून lazy)
# ----------------------------------------------------------------------------
_client = None


def get_client() -> "genai.Client":
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


# ----------------------------------------------------------------------------
# शब्द जुळवणी
# ----------------------------------------------------------------------------
def has_any(text: str, keywords: list[str]) -> bool:
    """इंग्रजी शब्द पूर्ण शब्द म्हणून जुळतात ("time" हा "sometimes" मध्ये जुळत नाही).
    मराठी शब्द शब्दाच्या सुरुवातीला जुळतात, त्यामुळे "उघड" हा "उघडा" मध्ये जुळतो."""
    for k in keywords:
        k = k.lower()
        if k.isascii():
            pattern = rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])"
        else:
            pattern = rf"(?<![{_DEVANAGARI}]){re.escape(k)}"
        if re.search(pattern, text):
            return True
    return False


_wake_alternation = "|".join(re.escape(w) for w in sorted(WAKE_WORDS, key=len, reverse=True))
_WAKE_RE = re.compile(
    rf"(?<![\w{_DEVANAGARI}])(?:{_wake_alternation})(?![\w{_DEVANAGARI}])",
    re.IGNORECASE,
)


def strip_wake_word(text: str) -> tuple[bool, str]:
    """मजकुरात wake word आहे का ते तपासतो आणि उरलेली कमांड परत देतो."""
    text = text.strip()
    m = _WAKE_RE.search(text)
    if not m:
        return False, text
    rest = (text[: m.start()] + " " + text[m.end():]).strip(" ,.-:!?")
    rest = re.sub(r"\s+", " ", rest)
    return True, rest


def extract_search_term(q: str, extra: frozenset = frozenset()) -> str:
    return " ".join(w for w in q.split() if w not in FILLER_WORDS and w not in extra)


# ----------------------------------------------------------------------------
# बोलणे (TTS)
# ----------------------------------------------------------------------------
MAX_SPOKEN_CHARS = 450


def tts_prepare(text: str) -> str:
    """बोलण्यासाठी मजकूर साफ करतो: कोड आणि फाइल पाथ वाचले जात नाहीत, लांब उत्तर लहान केले जाते."""
    text = re.sub(r"```.*?(?:```|$)", " कोड चॅटमध्ये दिला आहे. ", text, flags=re.S)  # न संपलेला fence पण
    text = re.sub(r"[A-Za-z]:\\\S+", " ", text)  # C:\... पाथ
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_SPOKEN_CHARS:
        cut = text[:MAX_SPOKEN_CHARS]
        end = max(cut.rfind(c) for c in ".?!।")
        text = (cut[: end + 1] if end > 150 else cut.rsplit(" ", 1)[0]) + " बाकी उत्तर चॅटमध्ये वाचा."
    return text


async def speak_async(text: str, voice: str | None = None, gen: int | None = None) -> None:
    text = tts_prepare(text)
    if not text:
        return
    voice = voice or settings["voice"]
    rate = f"{int(settings['rate']):+d}%"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name

    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(tmp_path)
        if gen is not None and gen != _speech_gen:
            return  # आवाज बनत असताना नवीन कमांड आली

        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)
    finally:
        with contextlib.suppress(Exception):
            pygame.mixer.music.unload()
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except PermissionError:
                pass


_speak_lock = threading.Lock()  # रिमाइंडर आणि उत्तर एकाच वेळी बोलू नयेत
_speech_gen = 0  # प्रत्येक नवीन बोलण्यासोबत वाढतो; जुने बोलणे रद्द ठरते


def speak_sync(text: str, gen: int | None = None) -> None:
    with _speak_lock:
        if gen is not None and gen != _speech_gen:
            return  # तोपर्यंत नवीन कमांड आली, हे बोलणे आता नको
        try:
            asyncio.run(speak_async(text, gen=gen))
        except Exception as e:
            print(f"Speak एरर: {e}")


def stop_speaking() -> None:
    """चालू बोलणे थांबवतो आणि रांगेतले जुने बोलणे रद्द करतो."""
    global _speech_gen
    _speech_gen += 1
    with contextlib.suppress(Exception):
        pygame.mixer.music.stop()


def speak_background(text: str) -> None:
    """बोलणे मागे चालते, त्यामुळे वापरकर्ता लगेच पुढचे टाइप करू शकतो."""
    stop_speaking()
    gen = _speech_gen
    threading.Thread(target=speak_sync, args=(text, gen), daemon=True).start()


# ----------------------------------------------------------------------------
# ऐकणे (माइक एकदा उघडतो, एकदा calibrate करतो)
# ----------------------------------------------------------------------------
class MicUnavailable(Exception):
    """माइक सुरू करता आला नाही (लायब्ररी नाही किंवा डिव्हाइस नाही)."""


SD_RATE = 16000
SD_BLOCK = 1024  # सुमारे 64 मिलिसेकंद


def _rms(raw: bytes) -> float:
    samples = array("h")
    samples.frombytes(raw)
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class Listener:
    """माइक एकदा उघडतो. PyAudio असेल तर तो; नसेल तर sounddevice (Python 3.13/3.14 वर PyAudio ची wheel
    सहसा मिळत नाही, म्हणून हा पर्याय)."""

    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.5
        self.recognizer.non_speaking_duration = 0.35
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 150
        self.unavailable_reason: str | None = None
        self._backend: str | None = None
        self._mic = None
        self._source = None
        self._stream = None
        self._ambient = 100.0  # sounddevice साठी सभोवतालचा आवाज (RMS)
        self._failures = 0
        self._last_error = ""
        self._lock = threading.Lock()  # एकाच वेळी एकच thread माइक वाचेल

    # --- स्थिती ----------------------------------------------------------
    def reset_error(self) -> None:
        """माइक बटण पुन्हा दाबल्यावर पुन्हा प्रयत्न करण्यासाठी."""
        self.unavailable_reason = None
        self._failures = 0

    def _fail(self, reason: str) -> None:
        self.unavailable_reason = reason
        self._reset()

    # --- उघडणे ---------------------------------------------------------------
    def _open(self) -> None:
        if self._backend == "pyaudio" and self._source is not None:
            return
        if self._backend == "sounddevice" and self._stream is not None:
            return

        if importlib.util.find_spec("pyaudio") is not None:
            self._mic = sr.Microphone()
            self._source = self._mic.__enter__()
            self.recognizer.adjust_for_ambient_noise(self._source, duration=1.0)
            self.recognizer.energy_threshold = max(self.recognizer.energy_threshold, 120)
            self._backend = "pyaudio"
            return

        try:
            import sounddevice as sd
        except ImportError as e:
            raise MicUnavailable(
                "PyAudio आणि sounddevice दोन्ही सापडले नाहीत. कमांड प्रॉम्प्टमध्ये "
                "'pip install sounddevice' चालवा आणि ZARA पुन्हा सुरू करा."
            ) from e
        try:
            stream = sd.RawInputStream(samplerate=SD_RATE, channels=1, dtype="int16", blocksize=SD_BLOCK)
            stream.start()
        except Exception as e:  # PortAudioError: डिव्हाइस नाही / परवानगी नाही
            raise MicUnavailable(
                f"माइक उघडता आला नाही ({e}). Windows सेटिंग्ज > गोपनीयता > माइक मध्ये परवानगी "
                "आणि डिफॉल्ट माइक तपासा."
            ) from e
        self._stream = stream
        self._backend = "sounddevice"
        levels = [_rms(bytes(stream.read(SD_BLOCK)[0])) for _ in range(SD_RATE // SD_BLOCK)]
        self._ambient = max(30.0, sum(levels) / len(levels))

    def _reset(self) -> None:
        if self._mic is not None:
            with contextlib.suppress(Exception):
                self._mic.__exit__(None, None, None)
        if self._stream is not None:
            with contextlib.suppress(Exception):
                self._stream.stop()
                self._stream.close()
        self._mic = None
        self._source = None
        self._stream = None
        self._backend = None

    # --- ऐकणे ---------------------------------------------------------------
    def _record_sounddevice(self, timeout: float, phrase_time_limit: float):
        """आवाज सुरू होईपर्यंत थांबतो, शांतता आली की थांबतो. बोलणे न आल्यास None."""
        stream = self._stream
        if stream.read_available:  # TTS वाजत असताना साचलेला जुना आवाज टाका
            stream.read(stream.read_available)
        block_secs = SD_BLOCK / SD_RATE
        pause_blocks = max(2, int(self.recognizer.pause_threshold / block_secs))
        min_speech_blocks = 4
        pre = collections.deque(maxlen=5)  # बोलणे सुरू होण्याआधीचा थोडा आवाज, म्हणजे पहिले अक्षर कापले जात नाही
        frames: list[bytes] = []
        speaking = False
        silent = loud = 0
        start = speech_start = time.time()
        while True:
            raw = bytes(stream.read(SD_BLOCK)[0])
            level = _rms(raw)
            threshold = max(350.0, self._ambient * 3)
            now = time.time()
            if not speaking:
                if level >= threshold:
                    speaking, speech_start = True, now
                    frames = list(pre) + [raw]
                    loud = 1
                else:
                    pre.append(raw)
                    self._ambient = 0.95 * self._ambient + 0.05 * level
                    if now - start > timeout:
                        return None
                continue
            frames.append(raw)
            if level >= threshold:
                loud += 1
                silent = 0
            else:
                silent += 1
            if silent >= pause_blocks or now - speech_start > phrase_time_limit:
                break
        if loud < min_speech_blocks:
            return None  # छोटा आवाज (खटका वगैरे), बोलणे नाही
        return sr.AudioData(b"".join(frames), SD_RATE, 2)

    def listen_once(self, timeout: float = 4.0, phrase_time_limit: float = 6.0) -> str | None:
        if self.unavailable_reason:
            return None
        with self._lock:
            try:
                self._open()
                if self._backend == "pyaudio":
                    audio = self.recognizer.listen(
                        self._source, timeout=timeout, phrase_time_limit=phrase_time_limit
                    )
                else:
                    audio = self._record_sounddevice(timeout, phrase_time_limit)
                if audio is None:
                    return None
                self._failures = 0
            except sr.WaitTimeoutError:
                return None
            except MicUnavailable as e:
                self._fail(str(e))
                return None
            except Exception as e:
                self._failures += 1
                msg = f"{type(e).__name__}: {e}"
                if msg != self._last_error:  # तोच एरर पुन्हा पुन्हा छापू नये
                    print(f"माइक एरर: {msg}")
                    self._last_error = msg
                self._reset()
                if self._failures >= 3:
                    self._fail(f"माइक सतत अयशस्वी होत आहे ({msg}).")
                else:
                    time.sleep(1.0)
                return None

        try:
            return self.recognizer.recognize_google(audio, language="mr-IN").strip()
        except (sr.UnknownValueError, sr.RequestError):
            return None


listener = Listener()


# ----------------------------------------------------------------------------
# सिस्टम क्रिया
# ----------------------------------------------------------------------------
def take_screenshot() -> str:
    import pyautogui

    save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "ZARA_Screenshots")
    os.makedirs(save_dir, exist_ok=True)
    filename = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
    filepath = os.path.join(save_dir, filename)
    img = pyautogui.screenshot()
    img.save(filepath)
    print(f"स्क्रीनशॉट सेव्ह: {filepath}")
    return "स्क्रीनशॉट घेतला आहे आणि Pictures मधील ZARA_Screenshots फोल्डरमध्ये सेव्ह केला आहे."


def find_and_open_item(name: str) -> str | None:
    target = name.lower().strip()
    if not target:
        return None

    home = os.path.expanduser("~")
    search_roots = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
    ]

    for root in search_roots:
        if not os.path.exists(root):
            continue
        for current_root, dirs, files in os.walk(root):
            depth = os.path.relpath(current_root, root).count(os.sep)
            if current_root != root and depth >= 2:
                dirs[:] = []
            for entry in files + dirs:
                if target not in entry.lower():
                    continue
                if os.path.splitext(entry)[1].lower() in BLOCKED_EXTENSIONS:
                    continue
                os.startfile(os.path.join(current_root, entry))
                return f"{entry} उघडत आहे."
    return None


def press_media_key(vk_code: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.keybd_event(vk_code, 0, 0, 0)  # key down
    user32.keybd_event(vk_code, 0, 2, 0)  # key up


def launch_app(name: str) -> bool:
    """फक्त allowlist मधील अॅप उघडतो. shell वापरत नाही, त्यामुळे command injection शक्य नाही."""
    key = name.lower().strip()
    if key in VSCODE_NAMES:
        path = shutil.which("code")
        if not path:
            return False
        subprocess.Popen([path], creationflags=NO_WINDOW)
        return True
    exe = APP_ALLOWLIST.get(key)
    if not exe:
        return False
    try:
        os.startfile(exe)
        return True
    except OSError:
        return False


def marathi_time_text() -> str:
    now = datetime.datetime.now()
    if now.hour < 12:
        period = "सकाळचे"
    elif now.hour < 16:
        period = "दुपारचे"
    elif now.hour < 20:
        period = "संध्याकाळचे"
    else:
        period = "रात्रीचे"
    hour12 = now.hour % 12 or 12
    return f"सध्या {period} {hour12}:{now.minute:02d} वाजले आहेत."


def marathi_date_text() -> str:
    now = datetime.datetime.now()
    return (
        f"आजची तारीख {now.day} {MARATHI_MONTHS[now.month - 1]} {now.year}, "
        f"{MARATHI_WEEKDAYS[now.weekday()]} आहे."
    )


def needs_laptop_action(query: str) -> bool:
    q = query.lower()
    action_words = [
        "उघड", "open", "ओपन", "opan", "फाइल", "file", "फोल्डर", "folder",
        "बनव", "create", "सर्च", "search", "website", "वेबसाइट", "वेबसाईट", "ॲप", "app",
        # कोड / वेबसाइट बनवण्याच्या मागण्या (मराठी-इंग्रजी मिश्र शब्दलेखनासह)
        "code", "कोड", "html", "script", "स्क्रिप्ट", "dashboard", "डॅशबोर्ड", "site", "साइट",
        "page", "पेज", "banav", "banaun", "बनवून", "तयार", "build", "make", "generate",
        "modify", "edit", "बदल", "tak", "टाक", "takun", "टाकून",
    ]
    return has_any(q, action_words)


# ----------------------------------------------------------------------------
# Gemini
# ----------------------------------------------------------------------------
# संवादाची आठवण: शेवटचे ~8 प्रश्न-उत्तर जोड्या Gemini ला पुन्हा पाठवल्या जातात.
# ती ~/.zara/history.json मध्ये सेव्ह होते, त्यामुळे अॅप बंद-चालू केल्यावरही टिकते.
chat_history: list[dict] = load_history()


def remember(user_text: str, reply: str) -> None:
    chat_history.append({"role": "user", "parts": [{"text": user_text}]})
    chat_history.append({"role": "model", "parts": [{"text": reply}]})
    del chat_history[:-MAX_HISTORY_MESSAGES]
    save_json(HISTORY_FILE, chat_history)


def user_context() -> str:
    name = settings.get("name", "")
    return f" वापरकर्त्याचे नाव {name} आहे." if name else ""


NO_FAKE_ACTIONS = (
    " तू स्वतः फाइल बनवणे, अॅप चालवणे किंवा वेबसाइट बनवणे असे काहीही या मोडमध्ये करू शकत नाहीस; "
    "ते झाल्याचे किंवा 'करत आहे' असे खोटे सांगू नकोस. जे करू शकत नाहीस ते स्पष्ट सांग."
)


def chat_config(max_tokens: int = 600) -> dict:
    return {
        "system_instruction": (
            f"तुझे नाव {ASSISTANT_NAME} आहे. वापरकर्त्याच्या भाषेत "
            "खूप थोडक्यात (1-2 वाक्यांत), थेट आणि स्पष्ट उत्तर दे." + NO_FAKE_ACTIONS + user_context()
        ),
        "max_output_tokens": max_tokens,
    }


def config_for_model(model_name: str, config: dict) -> dict:
    """2.5 flash मॉडेल्सवर thinking बंद करतो: उत्तर लवकर येते आणि tokens वाया जात नाहीत."""
    cfg = dict(config)
    if model_name.startswith("gemini-2.5-flash"):
        cfg["thinking_config"] = {"thinking_budget": 0}
    return cfg


def generate_with_retry(prompt: str, config: dict, contents=None) -> str:
    """503/429 आल्यास retry, 404 (मॉडेल नाही) किंवा रिकामे उत्तर आल्यास पुढच्या मॉडेलकडे.
    contents दिले नाही तर आठवण + prompt वापरले जाते (स्क्रीन वाचनासाठी इमेजसह contents देतो)."""
    if contents is None:
        contents = chat_history + [{"role": "user", "parts": [{"text": prompt}]}]
    last_error: Exception | None = None
    for model_name in MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                response = get_client().models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config_for_model(model_name, config),
                )
                text = (response.text or "").strip()
                if text:
                    return text
                last_error = RuntimeError("मॉडेलकडून रिकामे उत्तर आले.")
                break
            except Exception as e:
                last_error = e
                err = str(e)
                if any(c in err for c in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")):
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if "404" in err or "NOT_FOUND" in err:
                    break
                raise
    raise last_error or RuntimeError("मॉडेलकडून प्रतिसाद मिळाला नाही.")


# ----------------------------------------------------------------------------
# जलद कमांड्स (AI शिवाय, लगेच चालतात)
# ----------------------------------------------------------------------------
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

pending_confirm: dict | None = None  # धोकादायक कामासाठी "होय" ची वाट पाहतो
exit_requested = False
notify_callback = None  # अॅप सेट करतो: fn(text), रिमाइंडर वाजल्यावर बोलण्यासाठी
_sw_start: float | None = None

OPEN_APPS = {
    "notepad": ["notepad", "नोटपॅड"],
    "calc": ["calculator", "कॅल्क्युलेटर", "calc"],
    "paint": ["paint", "पेंट"],
    "word": ["ms word", "microsoft word", "वर्ड", "word"],
    "excel": ["excel", "एक्सेल"],
    "powerpoint": ["powerpoint", "पॉवरपॉइंट"],
    "taskmgr": ["task manager", "टास्क मॅनेजर", "taskmgr"],
    "explorer": ["file explorer", "फाइल एक्सप्लोरर", "explorer"],
    "settings": ["settings", "सेटिंग्ज", "सेटिंग"],
    "camera": ["camera", "कॅमेरा"],
    "clock": ["clock", "घड्याळ"],
    "cmd": ["command prompt", "cmd", "कमांड प्रॉम्प्ट"],
    "terminal": ["windows terminal", "terminal", "टर्मिनल"],
    "powershell": ["powershell", "पॉवरशेल"],
    "chrome": ["chrome", "क्रोम"],
    "edge": ["edge"],
    "firefox": ["firefox", "फायरफॉक्स"],
    "code": ["vs code", "vscode", "व्हीएस कोड"],
}
APP_LABELS = {
    "notepad": "Notepad", "calc": "Calculator", "paint": "Paint", "word": "Word",
    "excel": "Excel", "powerpoint": "PowerPoint", "taskmgr": "Task Manager",
    "explorer": "File Explorer", "settings": "Settings", "camera": "Camera",
    "clock": "Clock", "cmd": "Command Prompt", "terminal": "Terminal", "powershell": "PowerShell", "chrome": "Chrome", "edge": "Edge",
    "firefox": "Firefox", "code": "VS Code",
}

SITES = [
    ("WhatsApp", "https://web.whatsapp.com", ["whatsapp", "व्हाट्सअॅप", "व्हॉट्सअॅप", "व्हॉट्सऍप", "वॉट्सअॅप", "व्हाट्सएप"]),
    ("Gmail", "https://mail.google.com", ["gmail", "जीमेल"]),
    ("Google Drive", "https://drive.google.com", ["google drive", "गुगल ड्राईव्ह", "गुगल ड्राइव्ह"]),
    ("Google Calendar", "https://calendar.google.com", ["google calendar", "गुगल कॅलेंडर"]),
    ("Google Translate", "https://translate.google.com", ["google translate", "गुगल ट्रान्सलेट"]),
    ("Gemini", "https://gemini.google.com", ["gemini", "जेमिनी"]),
    ("ChatGPT", "https://chatgpt.com", ["chatgpt", "चॅटजीपीटी"]),
    ("Instagram", "https://www.instagram.com", ["instagram", "इन्स्टाग्राम", "इंस्टाग्राम"]),
    ("Facebook", "https://www.facebook.com", ["facebook", "फेसबुक"]),
    ("X (Twitter)", "https://x.com", ["twitter", "ट्विटर"]),
    ("LinkedIn", "https://www.linkedin.com", ["linkedin", "लिंक्डइन"]),
    ("GitHub", "https://github.com", ["github", "गिटहब"]),
    ("Amazon", "https://www.amazon.in", ["amazon", "अमेझॉन", "ऍमेझॉन"]),
    ("Flipkart", "https://www.flipkart.com", ["flipkart", "फ्लिपकार्ट"]),
    ("Netflix", "https://www.netflix.com", ["netflix", "नेटफ्लिक्स"]),
    ("Hotstar", "https://www.hotstar.com", ["hotstar", "हॉटस्टार"]),
    ("Spotify", "https://open.spotify.com", ["spotify", "स्पॉटिफाय"]),
    ("IRCTC", "https://www.irctc.co.in", ["irctc"]),
    ("Zomato", "https://www.zomato.com", ["zomato", "झोमॅटो"]),
    ("Swiggy", "https://www.swiggy.com", ["swiggy", "स्विगी"]),
]

KNOWN_FOLDERS = [
    ("Downloads", ["downloads", "download", "डाउनलोड्स", "डाउनलोड"]),
    ("Desktop", ["desktop", "डेस्कटॉप"]),
    ("Documents", ["documents", "डॉक्युमेंट्स", "डॉक्युमेंट"]),
    ("Pictures", ["pictures", "पिक्चर्स", "फोटो"]),
]

JOKES = [
    "शिक्षक: जगातला सगळ्यात वेगवान प्राणी कोणता? पिंटू: बाई, वायफाय; कारण तो दिसत नाही आणि सगळीकडे पोहोचतो!",
    "मी रोज सकाळी व्यायाम करायचं ठरवतो. पण अलार्म वाजला की माझा उत्साह स्नूझ होतो.",
    "मोबाइलची बॅटरी आणि माझी इच्छाशक्ती सारखीच; दोन्ही सोमवारी सगळ्यात आधी संपतात.",
    "डॉक्टर म्हणाले रोज वीस मिनिटे चाला. मी म्हटलं, चार्जिंगची वायर किती लांब आहे ते आधी बघतो.",
    "पिंटू: बाबा, सगळे म्हणतात कॉपी करू नका, पण आयुष्यात तर सगळे कॉपी पेस्टच करतात! बाबा: मग आधी अभ्यासाचा सेव्ह बटण दाब!",
]

YES_WORDS = {"होय", "हो", "हॉ", "yes", "yeah", "yep", "confirm", "हाँ", "हां", "ओके", "ok"}
NO_WORDS = {"नाही", "नको", "no", "nope", "cancel", "रद्द"}

HELP_TEXT = (
    "मी हे करू शकते: वेळ आणि तारीख, रिमाइंडर आणि टायमर (उदा. 'पाच मिनिटांनी चहा आठव'), "
    "नोट्स आणि टास्क, गणना, हवामान, गाणी आणि YouTube, नकाशा, वेबसाइट्स आणि अॅप्स उघडणे, "
    "आवाज आणि ब्राइटनेस, बॅटरी CPU RAM माहिती, स्क्रीन वाचणे, क्लिपबोर्ड सारांश, "
    "लॅपटॉप लॉक किंवा बंद करणे, आणि कोणताही प्रश्न."
)


class Ctx:
    """एका कमांडची तयार माहिती, जी सगळे handlers वापरतात."""

    def __init__(self, query: str) -> None:
        self.query = query.strip()
        self.q = self.query.lower()
        self.words = self.q.split()
        self.short = len(self.words) <= 6
        self.explicit_open = has_any(self.q, OPEN_WORDS)
        self.wants_open = self.explicit_open or len(self.words) <= 2


def remove_words(text: str, filler: set) -> str:
    out = []
    for w in text.split():
        core = w.strip(" ,.?!:;-\"'()")
        if core and core.lower() not in filler:
            out.append(core)
    return " ".join(out)


def strip_phrases(text: str, phrases: list[str]) -> str:
    """फक्त पूर्ण शब्द/वाक्प्रयोग काढतो ("to" हा "tomorrow" मधून कापला जात नाही)."""
    out = text
    for p in sorted(phrases, key=len, reverse=True):
        cls = "A-Za-z0-9" if p.isascii() else _DEVANAGARI
        out = re.sub(rf"(?<![{cls}]){re.escape(p)}(?![{cls}])", " ", out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip(" ,.:;-")


def _ps(command: str, timeout: float = 8.0) -> str:
    """PowerShell फक्त निश्चित कमांड्ससाठी (त्यात फक्त पडताळलेले आकडे जातात)."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=NO_WINDOW,
    )
    return (r.stdout or "").strip()


# --- रिमाइंडर / टायमर -----------------------------------------------------
NUMBER_WORDS = {
    "एक": 1, "दोन": 2, "तीन": 3, "चार": 4, "पाच": 5, "सहा": 6, "सात": 7, "आठ": 8,
    "नऊ": 9, "दहा": 10, "पंधरा": 15, "वीस": 20, "तीस": 30, "चाळीस": 40, "पन्नास": 50,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
}
SPECIAL_DURATIONS = {
    "अर्धा तास": 1800, "अर्ध्या तास": 1800, "half an hour": 1800, "half hour": 1800,
    "दीड तास": 5400, "दिड तास": 5400, "पाऊण तास": 2700, "सव्वा तास": 4500,
}
_NUM_ALT = "|".join(sorted((re.escape(w) for w in NUMBER_WORDS), key=len, reverse=True))
_UNIT_RE = (
    r"(सेकंद|सेकण्ड|सेकंड|seconds?|secs?|मिनिट|मिनीट|minutes?|mins?|तास|hours?|hrs?)(?![a-z])"
)
_DURATION_RE = re.compile(
    rf"(?<![\w{_DEVANAGARI}])(\d+(?:\.\d+)?|{_NUM_ALT})\s*{_UNIT_RE}[{_DEVANAGARI}]*",
    re.IGNORECASE,
)

REMIND_WORDS = ["आठवण", "आठव", "remind", "रिमाइंडर", "reminder", "reminders",
                "टायमर", "timer", "timers", "अलार्म", "alarm", "उठव", "उठवा", "wake me"]
MAX_REMINDER_SECS = 48 * 3600
REMINDER_FILLER = {
    "उद्या", "tomorrow", "सकाळी", "संध्याकाळी", "रात्री", "दुपारी", "पहाटे", "morning", "evening",
    "night", "afternoon", "at", "वाजता", "am", "pm", "उठव", "उठवा", "wake", "up", "वाजून",
    "मला", "माझी", "माझा", "आठवण", "आठव", "आठवा", "आठवून", "करून", "करुन", "दे", "द्या",
    "remind", "me", "to", "in", "after", "reminder", "set", "a", "an", "the", "timer",
    "रिमाइंडर", "टायमर", "अलार्म", "alarm", "लाव", "लावा", "सेट", "कर", "करा", "नंतर",
    "ने", "ला", "साठी", "for", "of", "ची", "चा", "चे", "द्यायची", "द्याची", "please",
}

reminders: dict[int, dict] = {}
_reminder_seq = 0
_reminder_lock = threading.Lock()


def parse_duration(text: str) -> tuple[int, str] | None:
    """(सेकंद, वेळेचा भाग काढलेला मजकूर) किंवा None."""
    t = text.translate(_DIGITS)
    for phrase, secs in SPECIAL_DURATIONS.items():
        pm = re.search(re.escape(phrase) + f"[{_DEVANAGARI}]*", t, re.IGNORECASE)
        if pm:
            return secs, t[: pm.start()] + " " + t[pm.end():]
    m = _DURATION_RE.search(t)
    if not m:
        return None
    raw = m.group(1).lower()
    val = float(raw) if raw[0].isdigit() else NUMBER_WORDS[raw]
    unit = m.group(2).lower()
    if unit.startswith(("सेक", "sec")):
        mult = 1
    elif unit.startswith(("मिन", "min")):
        mult = 60
    else:
        mult = 3600
    return int(val * mult), t[: m.start()] + " " + t[m.end():]


_CLOCK_PATTERNS = [
    re.compile(r"(?<![\d:.])(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?(?![\d:])", re.IGNORECASE),
    re.compile(rf"(?<![\d:.])(\d{{1,2}})()\s*(वाजता|am|pm|a\.m\.|p\.m\.)(?![a-z]){'[' + _DEVANAGARI + ']*'}", re.IGNORECASE),
    re.compile(r"\bat\s+(\d{1,2})()(?![\d:])()", re.IGNORECASE),
]
_PM_WORDS = ["संध्याकाळी", "रात्री", "दुपारी", "evening", "night", "afternoon"]
_AM_WORDS = ["सकाळी", "पहाटे", "morning"]


def parse_clock_time(text: str, now: datetime.datetime | None = None):
    """"सकाळी 7:30 वाजता", "at 6 pm", "उद्या 8 वाजता" -> (सेकंद, उरलेला मजकूर, वेळ) किंवा None."""
    now = now or datetime.datetime.now()
    t = text.translate(_DIGITS)
    for pat in _CLOCK_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        suffix = (m.group(3) or "").lower().replace(".", "")
        if hour > 23 or minute > 59:
            continue
        low = t.lower()
        pm = suffix == "pm" or any(w in low for w in _PM_WORDS)
        am = suffix == "am" or any(w in low for w in _AM_WORDS)
        if pm and hour < 12:
            hour += 12
        elif am and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if has_any(low, ["उद्या", "tomorrow"]):
            target += datetime.timedelta(days=1)
        elif target <= now:
            target += datetime.timedelta(days=1)
        return int((target - now).total_seconds()), t[: m.start()] + " " + t[m.end():], target
    return None


def fmt_duration(secs: int) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} तास")
    if m:
        parts.append(f"{m} मिनिट")
    if s or not parts:
        parts.append(f"{s} सेकंद")
    return " ".join(parts)


def add_reminder(secs: int, text: str) -> int:
    global _reminder_seq
    with _reminder_lock:
        _reminder_seq += 1
        rid = _reminder_seq
        timer = threading.Timer(secs, _fire_reminder, args=(rid,))
        timer.daemon = True
        reminders[rid] = {"text": text, "due": time.time() + secs, "timer": timer}
    timer.start()
    return rid


def _fire_reminder(rid: int) -> None:
    with _reminder_lock:
        item = reminders.pop(rid, None)
    if not item:
        return
    try:
        if notify_callback:
            notify_callback(item["text"])
        else:
            speak_sync(item["text"])
    except Exception as e:
        print(f"रिमाइंडर एरर: {e}")


def cancel_all_reminders() -> int:
    with _reminder_lock:
        items = list(reminders.values())
        reminders.clear()
    for item in items:
        item["timer"].cancel()
    return len(items)


def list_reminders() -> str:
    with _reminder_lock:
        items = sorted(reminders.values(), key=lambda r: r["due"])
    if not items:
        return "कोणताही रिमाइंडर सेट केलेला नाही."
    now = time.time()
    parts = [f"{fmt_duration(max(1, int(i['due'] - now)))} नंतर: {i['text']}" for i in items]
    return f"{len(items)} रिमाइंडर आहेत. " + "; ".join(parts)


# --- गणना -----------------------------------------------------------------
def _safe_pow(a, b):
    if abs(b) > 100 or abs(a) > 1e9:
        raise ValueError("संख्या खूप मोठी आहे")
    return a**b


_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: _safe_pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_eval(expr: str):
    """फक्त आकडे आणि + - * / // % ** ( ) चालतात; इतर काहीही नाही."""
    tree = ast.parse(expr.strip(), mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        raise ValueError("असमर्थित अभिव्यक्ती")

    return ev(tree)


def _fmt_num(v) -> str:
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("अवैध उत्तर")
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return str(round(v, 4))
    return str(v)


CALC_TRIGGERS = [
    "calculate", "गणना", "किती होतात", "किती होते", "किती होईल", "बेरीज", "वजाबाकी",
    "गुणाकार", "भागाकार", "plus", "minus", "गुणिले", "भागिले", "वजा", "अधिक", "जमा",
    "divided", "multiplied", "times", "power", "घात", "sum of", "product of",
]
_CALC_WORD_OPS = [
    ("multiplied by", "*"), ("divided by", "/"), ("raised to", "**"), ("to the power", "**"),
    ("गुणिले", "*"), ("गुणा", "*"), ("भागिले", "/"), ("भागा", "/"), ("वजा", "-"),
    ("अधिक", "+"), ("जमा", "+"), ("plus", "+"), ("minus", "-"), ("times", "*"),
    ("घात", "**"), ("power", "**"),
]
_TWO_NUMBER_OPS = [("बेरीज", "+"), ("वजाबाकी", "-"), ("गुणाकार", "*"), ("भागाकार", "/"),
                   ("sum of", "+"), ("product of", "*")]


def _calc_result(expr: str) -> str | None:
    if len(expr) > 80:
        return "ही गणना खूप मोठी आहे."
    try:
        return f"उत्तर {_fmt_num(safe_eval(expr))} आहे."
    except ZeroDivisionError:
        return "शून्याने भागता येत नाही."
    except (ValueError, SyntaxError, OverflowError, RecursionError, TypeError):
        return None


def try_calculate(q: str) -> str | None:
    t = q.lower().translate(_DIGITS)
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)

    pm = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:%|टक्के|टक्का|percent|per cent)\s*(?:of|चे|च्या|ची|चा)?\s*(\d+(?:\.\d+)?)", t
    )
    if pm:
        val = float(pm.group(1)) * float(pm.group(2)) / 100
        return f"{pm.group(1)} टक्के म्हणजे {_fmt_num(val)}."

    pure = re.fullmatch(r"[\d\s+\-*/().x×÷^]+", t) is not None
    if not (pure or has_any(t, CALC_TRIGGERS)):
        return None

    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if len(nums) == 2:
        for word, op in _TWO_NUMBER_OPS:
            if word in t:
                return _calc_result(f"{nums[0]}{op}{nums[1]}")

    if "किती होत" in t:
        t = t.replace(" आणि ", " + ")
    for word, op in _CALC_WORD_OPS:
        t = t.replace(word, f" {op} ")
    t = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", "*", t)
    t = t.replace("×", "*").replace("÷", "/").replace("^", "**")

    for cand in sorted(re.findall(r"[0-9+\-*/().\s]{3,}", t), key=len, reverse=True):
        cand = cand.strip()
        if re.search(r"\d", cand) and re.search(r"[+\-*/]", cand):
            return _calc_result(cand)
    return None


# --- हवामान ---------------------------------------------------------------
WEATHER_FILLER = {
    "हवामान", "weather", "तापमान", "temperature", "आज", "आजचे", "आजचं", "सध्या", "उद्या",
    "tomorrow", "today", "किती", "काय", "आहे", "आहेत", "in", "of", "the", "what", "is",
    "how", "मध्ये", "चे", "ची", "चा", "forecast", "like", "सांग", "सांगा", "tell", "me",
    "now", "current", "इथे", "इथला", "कसे", "कसं", "आता", "for", "at",
}


def parse_weather(data: dict, tomorrow: bool = False) -> str:
    area = ""
    with contextlib.suppress(Exception):
        area = data["nearest_area"][0]["areaName"][0]["value"]
    place = f"{area} मध्ये" if area else "तुमच्या भागात"
    if tomorrow:
        day = data["weather"][1]
        desc = ""
        with contextlib.suppress(Exception):
            desc = day["hourly"][4]["weatherDesc"][0]["value"]
        extra = f", हवामान: {desc}" if desc else ""
        return f"उद्या {place} कमाल {day['maxtempC']} आणि किमान {day['mintempC']} अंश सेल्सिअस तापमान असेल{extra}."
    cur = data["current_condition"][0]
    desc = cur["weatherDesc"][0]["value"]
    return (
        f"{place} सध्या {cur['temp_C']} अंश सेल्सिअस तापमान आहे, जाणवते {cur['FeelsLikeC']} अंश, "
        f"आर्द्रता {cur['humidity']} टक्के, हवामान: {desc}."
    )


def get_weather(city: str = "", tomorrow: bool = False) -> str:
    url = f"https://wttr.in/{quote(city)}?format=j1"  # शहर रिकामे असेल तर IP वरून शहर ठरते
    req = urllib.request.Request(url, headers={"User-Agent": "ZARA/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    return parse_weather(data, tomorrow)


# --- सिस्टम ---------------------------------------------------------------
def system_status(kind: str) -> str:
    try:
        import psutil
    except ImportError:
        return "यासाठी psutil लागते. कमांड प्रॉम्प्टमध्ये 'pip install psutil' चालवा."
    parts = []
    if kind in ("battery", "all"):
        b = psutil.sensors_battery()
        if b is None:
            parts.append("बॅटरी माहिती उपलब्ध नाही")
        else:
            state = "चार्जिंग सुरू आहे" if b.power_plugged else "चार्जर काढलेला आहे"
            parts.append(f"बॅटरी {int(b.percent)} टक्के, {state}")
    if kind in ("cpu", "all"):
        parts.append(f"CPU वापर {int(psutil.cpu_percent(interval=0.5))} टक्के")
    if kind in ("ram", "all"):
        vm = psutil.virtual_memory()
        parts.append(f"RAM {int(vm.percent)} टक्के वापरलेली ({vm.used / 1024**3:.1f} GB पैकी {vm.total / 1024**3:.1f} GB)")
    if kind in ("disk", "all"):
        du = shutil.disk_usage(os.path.expanduser("~"))
        parts.append(f"डिस्कवर {du.free / 1024**3:.0f} GB जागा शिल्लक आहे")
    return ". ".join(parts) + "."


def get_brightness() -> int | None:
    out = _ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness")
    return int(out.split()[0]) if out else None


def set_brightness(level: int) -> None:
    level = max(0, min(100, int(level)))
    _ps(
        "Invoke-CimMethod -InputObject (Get-CimInstance -Namespace root/WMI "
        "-ClassName WmiMonitorBrightnessMethods) -MethodName WmiSetBrightness "
        f"-Arguments @{{Timeout=1; Brightness={level}}} | Out-Null"
    )


def get_clipboard_text() -> str:
    return _ps("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw", timeout=5)


def describe_screen(question: str) -> str:
    """स्क्रीनशॉट घेऊन Gemini ला दाखवतो. इमेज Google ला पाठवली जाते."""
    import io

    import pyautogui

    img = pyautogui.screenshot().convert("RGB")
    img.thumbnail((1400, 1400))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    prompt = (
        f"वापरकर्त्याचा प्रश्न: {question}\n"
        "वरील स्क्रीनशॉट पाहून मराठीत खूप थोडक्यात (2-3 वाक्यांत) उत्तर दे."
    )
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"), types.Part(text=prompt)],
        )
    ]
    return generate_with_retry(prompt, chat_config(700), contents=contents)


# --- धोकादायक कृती (नेहमी "होय" ची पुष्टी लागते) ------------------------------
def _do_shutdown() -> str:
    subprocess.run(["shutdown", "/s", "/t", "15"], creationflags=NO_WINDOW)
    return "15 सेकंदात लॅपटॉप बंद होईल. रद्द करायचे असल्यास 'शटडाऊन रद्द' म्हणा."


def _do_restart() -> str:
    subprocess.run(["shutdown", "/r", "/t", "15"], creationflags=NO_WINDOW)
    return "15 सेकंदात लॅपटॉप रीस्टार्ट होईल. रद्द करायचे असल्यास 'शटडाऊन रद्द' म्हणा."


def _do_signout() -> str:
    subprocess.run(["shutdown", "/l"], creationflags=NO_WINDOW)
    return "साइन आउट करत आहे."


def _do_sleep() -> str:
    def go():
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], creationflags=NO_WINDOW)

    threading.Timer(3, go).start()
    return "3 सेकंदात स्लीप मोडमध्ये जाते."


def _do_clear_notes() -> str:
    with contextlib.suppress(OSError):
        os.remove(NOTES_FILE)
    return "सगळ्या नोट्स पुसल्या."


def _do_clear_todos() -> str:
    save_json(TODOS_FILE, [])
    return "सगळी टास्क यादी पुसली."


POWER_ACTIONS = [
    (["shutdown", "shut down", "शटडाऊन", "शटडाउन", "लॅपटॉप बंद", "लैपटॉप बंद", "pc बंद", "computer बंद", "कॉम्प्युटर बंद"],
     "लॅपटॉप बंद", _do_shutdown),
    (["restart", "reboot", "रीस्टार्ट", "रिस्टार्ट"], "लॅपटॉप रीस्टार्ट", _do_restart),
    (["sign out", "signout", "log off", "logout", "log out", "साइन आउट", "लॉग आउट"], "साइन आउट", _do_signout),
    (["sleep", "स्लीप", "झोपव"], "स्लीप मोडमध्ये", _do_sleep),
]


def ask_confirm(question: str, run) -> str:
    global pending_confirm
    pending_confirm = {"run": run, "expires": time.time() + 25}
    return f"{question} खात्री असल्यास 'होय' म्हणा."


# ----------------------------------------------------------------------------
# Handlers: प्रत्येक एक str परत देतो किंवा None (म्हणजे पुढच्याकडे जा)
# ----------------------------------------------------------------------------
def h_confirm(c: Ctx) -> str | None:
    global pending_confirm
    pc, pending_confirm = pending_confirm, None
    if not pc or time.time() > pc["expires"]:
        return None
    tokens = {w.strip(" .,!?") for w in c.words}
    if len(c.words) <= 3 and tokens & YES_WORDS:
        return pc["run"]()
    if tokens & NO_WORDS:
        return "ठीक आहे, रद्द केले."
    return None


def h_hello(c: Ctx) -> str | None:
    if c.q in ["hi", "hii", "hiii", "hey", "hello", "नमस्कार", "हॅलो"]:
        name = settings["name"]
        who = f" {name}" if name else ""
        return f"नमस्कार{who}! मी {ASSISTANT_NAME} तयार आहे, काय काम सांगायचे आहे?"
    return None


def h_help(c: Ctx) -> str | None:
    if len(c.words) <= 2 and has_any(c.q, ["मदत", "help", "फीचर्स", "features"]):
        return HELP_TEXT
    if c.short and has_any(c.q, ["काय करू शकतेस", "काय काय करू शकतेस", "what can you do"]):
        return HELP_TEXT
    return None


def h_exit(c: Ctx) -> str | None:
    global exit_requested
    if len(c.words) <= 2 and has_any(c.q, ["bye", "बाय", "exit", "quit", "गुडबाय", "good bye", "अलविदा"]):
        exit_requested = True
        return "ठीक आहे, पुन्हा भेटूया!"
    return None


def h_forget(c: Ctx) -> str | None:
    if has_any(c.q, ["सगळे विसर", "सर्व विसर", "forget everything", "reset chat", "नवीन संवाद"]):
        chat_history.clear()
        with contextlib.suppress(OSError):
            os.remove(HISTORY_FILE)
        return "ठीक आहे, आधीचे सगळे विसरले. नवीन संवाद सुरू करू."
    return None


def h_reminder(c: Ctx) -> str | None:
    q = c.q
    if not has_any(q, REMIND_WORDS):
        return None
    nouns = ["रिमाइंडर", "reminder", "reminders", "टायमर", "timer", "timers", "अलार्म", "alarm"]
    if has_any(q, nouns) and has_any(q, ["रद्द", "cancel", "clear", "delete", "काढून टाक", "पुसून"]):
        n = cancel_all_reminders()
        return f"{n} रिमाइंडर रद्द केले." if n else "कोणताही रिमाइंडर सेट केलेला नाही."
    target = None
    parsed = parse_duration(c.query)
    if parsed is None:
        clock = parse_clock_time(c.query)
        if clock is not None:
            secs, rest, target = clock
            parsed = (secs, rest)
    if parsed is None:
        if has_any(q, ["set", "लाव", "सेट", "कर", "करा"]) and has_any(q, ["timer", "टायमर", "reminder", "रिमाइंडर", "alarm", "अलार्म"]):
            return "किती वेळाचा? उदाहरणार्थ 'पाच मिनिटांचा टायमर' किंवा 'सकाळी सात वाजता उठव' म्हणा."
        if has_any(q, ["reminders", "reminder", "रिमाइंडर", "टायमर", "timer", "timers"]):
            return list_reminders()
        return None
    secs, rest = parsed
    if secs <= 0:
        return "वेळ शून्यापेक्षा जास्त हवी."
    if secs > MAX_REMINDER_SECS:
        return "मी जास्तीत जास्त 48 तासांचा रिमाइंडर लावू शकते."
    msg = remove_words(rest, REMINDER_FILLER)
    if target is not None:
        add_reminder(secs, f"रिमाइंडर: {msg}" if msg else "तुमचा अलार्म वाजला.")
        return f"ठीक आहे, {target:%d/%m %H:%M} ला ({fmt_duration(secs)} नंतर) {'आठवण करून देईन' if msg else 'अलार्म वाजवेन'}."
    if msg:
        add_reminder(secs, f"रिमाइंडर: {msg}")
        return f"ठीक आहे, {fmt_duration(secs)} नंतर आठवण करून देईन."
    add_reminder(secs, "तुमचा टायमर संपला.")
    return f"ठीक आहे, {fmt_duration(secs)} चा टायमर सुरू केला."


def h_stopwatch(c: Ctx) -> str | None:
    global _sw_start
    if not has_any(c.q, ["stopwatch", "स्टॉपवॉच", "स्टॉप वॉच"]):
        return None
    if _sw_start is None:
        _sw_start = time.time()
        return "स्टॉपवॉच सुरू केले."
    elapsed = int(time.time() - _sw_start)
    if has_any(c.q, ["किती", "how much", "check", "दाखव", "show", "status"]):
        return f"आतापर्यंत {fmt_duration(elapsed)} झाले."
    _sw_start = None
    return f"स्टॉपवॉच थांबवले. एकूण वेळ {fmt_duration(elapsed)}."


def h_calc(c: Ctx) -> str | None:
    return try_calculate(c.q)


def h_notes(c: Ctx) -> str | None:
    q = c.q
    add_phrases = ["नोट कर", "नोट करा", "नोट करून", "नोट ठेव", "नोट ठेवा", "नोट लिहून",
                   "लिहून ठेव", "लिहून ठेवा", "लिहून घे", "लिहून घ्या",
                   "note down", "take a note", "make a note", "add note", "note this", "note:", "नोट:"]
    if has_any(q, add_phrases):
        text = strip_phrases(c.query, add_phrases)
        if not text:
            return "काय लिहून ठेवू? उदाहरणार्थ 'नोट कर: दूध आणायचे'."
        add_note(text)
        return "नोट सेव्ह केली."
    if c.short and has_any(q, ["नोट्स", "notes"]):
        if has_any(q, ["पुसून", "clear", "delete", "काढून"]):
            return ask_confirm("सगळ्या नोट्स पुसायच्या आहेत का?", _do_clear_notes)
        notes = read_notes(5)
        if not notes:
            return "तुमच्या कोणत्याही नोट्स नाहीत."
        return "शेवटच्या नोट्स: " + "; ".join(notes)
    return None


def h_todo(c: Ctx) -> str | None:
    q = c.q
    keys = ["टास्क", "task", "todo", "to-do", "टूडू", "कामांची यादी"]
    if not has_any(q, keys) or has_any(q, ["manager", "मॅनेजर", "scheduler", "view", "व्ह्यू"]):
        return None
    todos = load_todos()
    pending = [t for t in todos if not t["done"]]
    digits = re.findall(r"\d+", q.translate(_DIGITS))

    if has_any(q, ["clear", "पुसून", "सगळे काढ"]):
        return ask_confirm("सगळी टास्क यादी पुसायची आहे का?", _do_clear_todos)
    if digits and has_any(q, ["पूर्ण", "done", "complete", "काढ", "remove", "delete"]):
        n = int(digits[0])
        if not 1 <= n <= len(pending):
            return f"{n} क्रमांकाचे टास्क सापडले नाही."
        pending[n - 1]["done"] = True
        save_json(TODOS_FILE, todos)
        return f"टास्क {n} पूर्ण केले: {pending[n - 1]['text']}."
    if has_any(q, ["जोड", "add", "ऍड", "अॅड", "टाक"]):
        text = strip_phrases(c.query, keys + ["जोड", "जोडा", "add", "ऍड", "अॅड", "टाक", "टाका", "यादीत", "to", "my", "list", "माझ्या"])
        if not text:
            return "कोणते टास्क जोडू? उदाहरणार्थ 'टास्क जोड: वीज बिल भरणे'."
        todos.append({"text": text, "done": False})
        save_json(TODOS_FILE, todos)
        return f"टास्क जोडले: {text}."
    if c.short:
        if not pending:
            return "तुमच्याकडे कोणतेही टास्क बाकी नाही."
        items = "; ".join(f"{i}. {t['text']}" for i, t in enumerate(pending, 1))
        return f"तुमची {len(pending)} कामे बाकी आहेत: {items}."
    return None


def h_name(c: Ctx) -> str | None:
    q = c.q
    if has_any(q, ["माझे नाव काय", "माझं नाव काय", "what is my name", "what's my name", "मी कोण आहे"]):
        n = settings["name"]
        return f"तुमचे नाव {n} आहे." if n else "मला तुमचे नाव माहीत नाही. 'माझे नाव ... आहे' असे सांगा."
    patterns = [
        r"(?:माझे|माझं)\s+नाव\s+(.+?)(?:\s+आहे)?\s*$",
        r"my name is\s+(.+?)\s*$",
        r"call me\s+(.+?)\s*$",
        r"मला\s+(.+?)\s+म्हण(?:ा|ू)?\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, c.query, re.IGNORECASE)
        if m:
            name = m.group(1).strip(" .!,")
            if name and len(name) <= 30 and len(name.split()) <= 3:
                settings["name"] = name
                save_settings()
                return f"ठीक आहे {name}, आता मी तुम्हाला याच नावाने ओळखेन."
    return None


def h_voice(c: Ctx) -> str | None:
    q = c.q
    if has_any(q, ["पुरुष आवाज", "male voice", "पुरुषाचा आवाज"]):
        settings["voice"] = "mr-IN-ManoharNeural"
        save_settings()
        return "ठीक आहे, आता पुरुष आवाजात बोलेन."
    if has_any(q, ["स्त्री आवाज", "female voice", "महिला आवाज"]):
        settings["voice"] = "mr-IN-AarohiNeural"
        save_settings()
        return "ठीक आहे, आता स्त्री आवाजात बोलेन."
    if has_any(q, ["जोरात बोल", "faster", "speak faster", "वेग वाढव"]):
        settings["rate"] = min(50, settings["rate"] + 15)
        save_settings()
        return "आता वेगाने बोलेन."
    if has_any(q, ["हळू बोल", "slower", "speak slower", "वेग कमी"]):
        settings["rate"] = max(-40, settings["rate"] - 15)
        save_settings()
        return "आता हळू बोलेन."
    return None


_VEL_RE = re.compile(rf"(?<![{_DEVANAGARI}])वेळ(?![{_DEVANAGARI}])")


def h_time(c: Ctx) -> str | None:
    # "वेळ" पूर्ण शब्द म्हणून ("तीन वेळा" / "वेळापत्रक" वर ट्रिगर होत नाही)
    if c.short and (_VEL_RE.search(c.q) or has_any(c.q, ["time", "वाजले"])):
        return marathi_time_text()
    return None


def h_date(c: Ctx) -> str | None:
    if c.short and has_any(c.q, ["तारीख", "date"]):
        return marathi_date_text()
    return None


def h_daily(c: Ctx) -> str | None:
    q = c.q
    if not c.short or not has_any(
        q, ["good morning", "गुड मॉर्निंग", "सुप्रभात", "शुभ प्रभात", "good evening", "शुभ संध्या",
            "good night", "शुभ रात्री", "गुड नाईट"]
    ):
        return None
    name = settings["name"]
    who = f", {name}" if name else ""
    if has_any(q, ["good night", "शुभ रात्री", "गुड नाईट"]):
        return f"शुभ रात्री{who}! गोड स्वप्ने पाहा."
    hour = datetime.datetime.now().hour
    greet = "शुभ प्रभात" if hour < 12 else ("शुभ दुपार" if hour < 16 else "शुभ संध्याकाळ")
    parts = [f"{greet}{who}!", marathi_date_text()]
    n_todo = len([t for t in load_todos() if not t["done"]])
    if n_todo:
        parts.append(f"तुमची {n_todo} कामे बाकी आहेत.")
    if reminders:
        parts.append(f"{len(reminders)} रिमाइंडर सेट आहेत.")
    return " ".join(parts)


def h_screenshot(c: Ctx) -> str | None:
    if has_any(c.q, ["स्क्रीनशॉट", "screenshot"]):
        try:
            return take_screenshot()
        except Exception as e:
            print(f"Screenshot एरर: {e}")
            return "स्क्रीनशॉट घेताना अडचण आली."
    return None


def h_screen_ai(c: Ctx) -> str | None:
    q = c.q
    if has_any(
        q,
        ["what's on my screen", "what is on my screen", "what's on the screen", "on my screen",
         "on screen", "read my screen", "read the screen", "read screen",
         "screen वर", "screen वाच", "screen समजाव", "स्क्रीनवर", "स्क्रीन वर", "स्क्रीन वाच",
         "स्क्रीन समजाव", "स्क्रीन बघ", "स्क्रीन पाहा", "माझ्या स्क्रीन", "या स्क्रीन"],
    ):
        reply = describe_screen(c.query)
        remember(c.query, reply)
        return reply
    return None


def h_clipboard(c: Ctx) -> str | None:
    q = c.q
    if not has_any(q, ["clipboard", "क्लिपबोर्ड", "कॉपी केलेले", "copied"]):
        return None
    text = get_clipboard_text()
    if not text:
        return "क्लिपबोर्ड रिकामा आहे."
    if has_any(q, ["सारांश", "summar", "translate", "भाषांतर", "explain", "समजाव", "अर्थ", "improve", "सुधार", "proofread"]):
        return generate_with_retry(f"{c.query}\n\n---\n{text[:4000]}", chat_config(700))
    return f"क्लिपबोर्डमध्ये हे आहे: {text[:300]}"


def h_volume(c: Ctx) -> str | None:
    q = c.q
    if has_any(q, ["mute", "म्यूट", "आवाज बंद"]):
        press_media_key(173)
        return "आवाज म्यूट केला आहे."
    if has_any(q, ["volume max", "आवाज पूर्ण", "full volume", "व्हॉल्यूम पूर्ण"]):
        for _ in range(25):
            press_media_key(175)
        return "आवाज पूर्ण केला आहे."
    if has_any(q, ["volume up", "आवाज वाढव", "व्हॉल्यूम वाढव"]):
        for _ in range(4):
            press_media_key(175)
        return "आवाज वाढवला आहे."
    if has_any(q, ["volume down", "आवाज कमी", "व्हॉल्यूम कमी"]):
        for _ in range(4):
            press_media_key(174)
        return "आवाज कमी केला आहे."
    return None


def h_media(c: Ctx) -> str | None:
    q = c.q
    if has_any(q, ["next song", "next track", "पुढचे गाणे", "पुढचं गाणं", "पुढील गाणे", "skip song"]):
        press_media_key(176)
        return "पुढचे गाणे."
    if has_any(q, ["previous song", "previous track", "मागचे गाणे", "मागचं गाणं", "आधीचे गाणे"]):
        press_media_key(177)
        return "मागचे गाणे."
    if c.short and has_any(q, ["pause", "resume", "पॉज", "रिझ्यूम", "गाणे थांबव", "गाणं थांबव"]):
        press_media_key(179)
        return "ठीक आहे."
    return None


def h_brightness(c: Ctx) -> str | None:
    q = c.q
    if not has_any(q, ["brightness", "ब्राइटनेस"]):
        return None
    digits = re.findall(r"\d+", q.translate(_DIGITS))
    if digits:
        level = int(digits[0])
    elif has_any(q, ["max", "full", "पूर्ण"]):
        level = 100
    elif has_any(q, ["वाढव", "increase", "up", "जास्त", "more"]):
        cur = get_brightness()
        if cur is None:
            return "ब्राइटनेस नियंत्रित करता आली नाही. हे फक्त लॅपटॉपच्या स्क्रीनवर चालते."
        level = cur + 20
    elif has_any(q, ["कमी", "decrease", "down", "less", "dim"]):
        cur = get_brightness()
        if cur is None:
            return "ब्राइटनेस नियंत्रित करता आली नाही. हे फक्त लॅपटॉपच्या स्क्रीनवर चालते."
        level = cur - 20
    else:
        return "ब्राइटनेस किती करू? उदाहरणार्थ 'ब्राइटनेस 50' म्हणा."
    level = max(0, min(100, level))
    set_brightness(level)
    return f"ब्राइटनेस {level} टक्के केली."


def h_system(c: Ctx) -> str | None:
    q = c.q
    if not c.short:
        return None
    if has_any(q, ["system status", "सिस्टम स्थिती", "laptop status", "system info", "लॅपटॉप कसा आहे"]):
        return system_status("all")
    if has_any(q, ["बॅटरी", "battery", "चार्जिंग"]):
        return system_status("battery")
    if has_any(q, ["cpu", "सीपीयू", "प्रोसेसर"]):
        return system_status("cpu")
    # "Ram" हे नाव असू शकते, म्हणून इंग्रजी शब्दासोबत वापर-संबंधित शब्द लागतो
    if has_any(q, ["रॅम", "मेमरी"]) or (
        has_any(q, ["ram", "memory"])
        and has_any(q, ["usage", "वापर", "किती", "status", "free", "how much", "check", "कसा"])
    ):
        return system_status("ram")
    if has_any(q, ["disk", "डिस्क", "स्टोरेज", "storage"]):
        return system_status("disk")
    return None


def h_power(c: Ctx) -> str | None:
    q = c.q
    if not c.short:
        return None
    if has_any(q, ["रद्द", "cancel", "abort", "नको"]) and has_any(
        q, ["shutdown", "शटडाऊन", "शटडाउन", "restart", "रीस्टार्ट", "रिस्टार्ट", "लॅपटॉप बंद"]
    ):
        r = subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=NO_WINDOW)
        return "शटडाऊन रद्द केले." if r.returncode == 0 else "सध्या कोणतेही शटडाऊन सुरू नाही."
    for words, label, fn in POWER_ACTIONS:
        if has_any(q, words):
            return ask_confirm(f"{label} करायचे आहे का?", fn)
    if has_any(q, ["लॉक कर", "lock laptop", "lock pc"]):
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "लॅपटॉप लॉक करत आहे."
    return None


def h_weather(c: Ctx) -> str | None:
    if not c.short or not has_any(c.q, ["हवामान", "weather", "तापमान", "temperature"]):
        return None
    tomorrow = has_any(c.q, ["उद्या", "tomorrow"])
    city = remove_words(c.query, WEATHER_FILLER)
    try:
        return get_weather(city, tomorrow)
    except Exception as e:
        print(f"हवामान एरर ({type(e).__name__}): {e}")
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(f"weather {city}".strip()))
        return "हवामान माहिती थेट मिळाली नाही, म्हणून Google वर उघडत आहे."


def h_fun(c: Ctx) -> str | None:
    q = c.q
    if c.short and has_any(q, ["विनोद", "joke", "जोक", "हसव"]):
        return random.choice(JOKES)
    if c.short and has_any(q, ["नाणे", "नाणं", "coin", "toss", "टॉस", "छापा काटा"]):
        return random.choice(["छापा पडला!", "काटा पडला!"])
    if c.short and has_any(q, ["फासा", "dice", "डाइस"]):
        return f"फासा टाकला, {random.randint(1, 6)} आला."
    if has_any(q, ["random number", "रँडम नंबर", "यादृच्छिक"]):
        nums = [int(n) for n in re.findall(r"\d+", q.translate(_DIGITS))]
        lo, hi = (min(nums[:2]), max(nums[:2])) if len(nums) >= 2 else (1, 100)
        return f"तुमचा नंबर {random.randint(lo, hi)}."
    return None


def h_window(c: Ctx) -> str | None:
    q = c.q
    if has_any(q, ["show desktop", "minimize all", "डेस्कटॉप दाखव", "desktop दाखव", "सगळे मिनिमाइज"]):
        keys, msg = ("win", "d"), "डेस्कटॉप दाखवत आहे."
    elif has_any(q, ["switch window", "alt tab", "विंडो बदल", "दुसरी विंडो"]):
        keys, msg = ("alt", "tab"), "विंडो बदलली."
    elif has_any(q, ["task view", "टास्क व्ह्यू"]):
        keys, msg = ("win", "tab"), "टास्क व्ह्यू उघडत आहे."
    else:
        return None
    import pyautogui

    pyautogui.hotkey(*keys)
    return msg


MUSIC_FILLER = frozenset({
    "गाणे", "गाणं", "गाणी", "song", "songs", "music", "संगीत", "play", "लाव", "लावा",
    "वाजव", "वाजवा", "ऐकव", "ऐकवा", "सुरू", "a", "the", "me", "मला", "माझे", "द्या", "दे",
    "एक", "चे", "ची", "चा", "please", "यूट्यूबवर", "on",
})
MAP_FILLER = frozenset({
    "map", "maps", "नकाशा", "नकाशात", "navigate", "directions", "direction", "route", "रस्ता",
    "मार्ग", "show", "दाखव", "दाखवा", "to", "near", "me", "जवळचे", "जवळची", "जवळचा",
    "nearby", "find", "शोध", "शोधा", "how", "get", "कसे", "कसा", "जायचे", "ला", "मध्ये", "उघड", "उघडा",
})
NEWS_FILLER = frozenset({
    "news", "बातम्या", "बातमी", "latest", "about", "बद्दल", "ताज्या", "आजच्या", "आजची", "today",
    "of", "on", "दाखव", "दाखवा", "show", "me", "सांग", "सांगा", "tell", "headlines",
})
WIKI_FILLER = frozenset({"wikipedia", "विकिपीडिया", "about", "बद्दल", "माहिती", "information", "ची", "चे", "अर्थ"})


def h_youtube(c: Ctx) -> str | None:
    if has_any(c.q, ["youtube", "युट्यूब"]):
        term = extract_search_term(c.q)
        if term:
            webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(term)}")
            return f"YouTube वर {term} शोधत आहे."
        webbrowser.open("https://www.youtube.com")
        return "YouTube उघडत आहे."
    return None


def h_music(c: Ctx) -> str | None:
    q = c.q
    if "play store" in q:
        return None
    if has_any(q, ["गाणे", "गाणं", "गाणी", "song", "songs", "music", "संगीत"]) or q.startswith("play "):
        term = extract_search_term(q, MUSIC_FILLER)
        if term:
            webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(term + ' song')}")
            return f"{term} हे गाणे YouTube वर शोधत आहे."
        webbrowser.open("https://music.youtube.com")
        return "YouTube Music उघडत आहे."
    return None


def h_maps(c: Ctx) -> str | None:
    q = c.q
    if not c.short:
        return None
    if has_any(q, ["map", "maps", "नकाशा", "navigate", "directions", "near me", "nearby"]):
        term = extract_search_term(q, MAP_FILLER)
        if not term:
            webbrowser.open("https://www.google.com/maps")
            return "Google Maps उघडत आहे."
        if has_any(q, ["directions", "navigate"]):
            webbrowser.open(f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(term)}")
            return f"{term} साठी मार्ग उघडत आहे."
        webbrowser.open(f"https://www.google.com/maps/search/{quote_plus(term)}")
        return f"नकाशावर {term} शोधत आहे."
    return None


def h_news_wiki(c: Ctx) -> str | None:
    q = c.q
    if c.short and has_any(q, ["बातम्या", "news"]):
        term = extract_search_term(q, NEWS_FILLER)
        if term:
            webbrowser.open(f"https://news.google.com/search?q={quote_plus(term)}&hl=mr&gl=IN&ceid=IN:mr")
            return f"{term} बद्दलच्या बातम्या उघडत आहे."
        webbrowser.open("https://news.google.com/?hl=mr&gl=IN&ceid=IN:mr")
        return "ताज्या बातम्या उघडत आहे."
    if has_any(q, ["wikipedia", "विकिपीडिया"]):
        term = extract_search_term(q, WIKI_FILLER)
        host = "mr.wikipedia.org" if re.search(f"[{_DEVANAGARI}]", term) else "en.wikipedia.org"
        if term:
            webbrowser.open(f"https://{host}/w/index.php?search={quote_plus(term)}")
            return f"Wikipedia वर {term} शोधत आहे."
        webbrowser.open("https://www.wikipedia.org")
        return "Wikipedia उघडत आहे."
    return None


def h_sites(c: Ctx) -> str | None:
    if not c.wants_open:
        return None
    for label, url, names in SITES:
        if has_any(c.q, names):
            webbrowser.open(url)
            return f"{label} उघडत आहे."
    return None


SAFE_TERMINAL_COMMANDS = {
    "wsl", "python", "node", "ipconfig", "systeminfo", "whoami", "hostname", "ver", "tasklist",
}
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def h_terminal(c: Ctx) -> str | None:
    """नवीन कन्सोल उघडून फक्त allowlist मधील कमांड चालवतो (उदा. wsl). मनमानी कमांड कधीच नाही."""
    q = c.q
    if not has_any(q, ["cmd", "command prompt", "कमांड प्रॉम्प्ट", "terminal", "टर्मिनल", "powershell",
                       "पॉवरशेल", "wsl", "ubuntu", "linux", "लिनक्स"]):
        return None
    tokens = [w.strip(" .,?!") for w in c.words]
    cmd = next((t for t in tokens if t in SAFE_TERMINAL_COMMANDS), None)
    wants_type = has_any(q, ["type", "टाइप", "run", "चालव", "execute", "त्यात", "tyat"])
    linux_word = has_any(q, ["wsl", "ubuntu", "linux", "लिनक्स"])
    if cmd is None and linux_word and (c.explicit_open or len(c.words) <= 2):
        cmd = "wsl"
    elif cmd is not None and not (wants_type or linux_word):
        cmd = None
    if cmd is None:
        return None
    subprocess.Popen(["cmd.exe", "/k", cmd], creationflags=NEW_CONSOLE)
    return f"{cmd} सुरू करत आहे."


def h_apps(c: Ctx) -> str | None:
    if not (c.explicit_open or len(c.words) == 1):
        return None
    for key, names in OPEN_APPS.items():
        if has_any(c.q, names):
            label = APP_LABELS.get(key, key)
            return f"{label} उघडत आहे." if launch_app(key) else f"{label} उघडता आले नाही."
    return None


def h_folders(c: Ctx) -> str | None:
    if not c.explicit_open:
        return None
    for folder, names in KNOWN_FOLDERS:
        if has_any(c.q, names):
            path = os.path.join(os.path.expanduser("~"), folder)
            if os.path.isdir(path):
                os.startfile(path)
                return f"{folder} फोल्डर उघडत आहे."
            return f"{folder} फोल्डर सापडला नाही."
    return None


def h_google(c: Ctx) -> str | None:
    if has_any(c.q, ["google", "गुगल", "सर्च", "search"]):
        term = extract_search_term(c.q)
        if term:
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(term)}")
            return f"Google वर {term} शोधत आहे."
        webbrowser.open("https://www.google.com")
        return "Google उघडत आहे."
    return None


# क्रम महत्त्वाचा आहे: विशिष्ट कमांड आधी, सैल शब्दांच्या कमांड नंतर.
HANDLERS = [
    h_confirm, h_hello, h_help, h_exit, h_forget,
    h_reminder, h_stopwatch, h_notes, h_todo, h_calc, h_name, h_voice,
    h_time, h_date, h_daily,
    h_screenshot, h_screen_ai, h_clipboard,
    h_volume, h_media, h_brightness, h_system, h_power, h_weather,
    h_fun, h_window, h_youtube, h_music, h_maps, h_news_wiki,
    h_sites, h_terminal, h_apps, h_google, h_folders,
]


def run_fast_command(query: str) -> str | None:
    c = Ctx(query)
    for handler in HANDLERS:
        try:
            reply = handler(c)
        except Exception as e:
            print(f"{handler.__name__} मध्ये एरर")
            return friendly_error(e)
        if reply is not None:
            return reply
    return None


# ----------------------------------------------------------------------------
# कोड / वेबसाइट फाइल बनवणे
# ----------------------------------------------------------------------------
FILES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ZARA_Files")
# फक्त हे प्रकार बनवले जातात. .bat/.ps1/.exe/.vbs सारखे चालणारे प्रकार जाणीवपूर्वक नाहीत.
FILE_KINDS = {
    "html": ".html", "py": ".py", "js": ".js", "css": ".css",
    "txt": ".txt", "md": ".md", "json": ".json", "csv": ".csv",
}
CODE_SYSTEM = (
    "तू एक तज्ज्ञ डेव्हलपर आहेस. फक्त पूर्ण, थेट चालणारा कोड दे, एकाच ``` fence मध्ये; कोणतेही स्पष्टीकरण नको. "
    "HTML असल्यास एकाच फाइलमध्ये CSS आणि JavaScript inline ठेव; बाहेरच्या फाइल्स, CDN किंवा इंटरनेटवरील इमेज वापरू नकोस. "
    "पेज मोबाइल आणि डेस्कटॉप दोन्हीवर नीट दिसावे आणि दिसायला आधुनिक आणि सुंदर असावे. "
    "वापरकर्ता मराठीत बोलत असल्यास पेजवरील मजकूर मराठीत ठेव. कोड कधीही अर्धवट सोडू नकोस."
)


def safe_filename(name: str, ext: str) -> str:
    """फक्त अक्षर-आकडे; पाथ किंवा '..' मधून बाहेर जाता येत नाही."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.basename(str(name))).strip("_")[:40]
    return (base or "zara_file") + ext


def unique_path(directory: str, filename: str) -> str:
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    return os.path.join(directory, f"{stem}_{datetime.datetime.now():%H%M%S}{ext}")


def extract_code(text: str) -> str:
    """उत्तरातून कोड काढतो. fence नसेल किंवा उत्तर तुटले असेल (fence बंद नाही) तरी चालते."""
    blocks = re.findall(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len).strip("\n") + "\n"
    m = re.search(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*)$", text, re.S)
    if m:
        return m.group(1).strip("\n") + "\n"
    return text.strip() + "\n"


def generate_code(request: str, kind: str, existing: str | None = None) -> tuple[str, bool]:
    """(कोड, पूर्ण आहे का). HTML मध्ये </html> नसेल तर उत्तर तुटले असे धरतो."""
    prompt = f"फाइल प्रकार: {kind}\nवापरकर्त्याची मागणी: {request}"
    if existing:
        prompt += (
            "\n\nही सध्याची फाइल आहे. तिच्यात मागणीप्रमाणे बदल करून पूर्ण नवीन फाइल दे:\n```\n"
            + existing[:20000] + "\n```"
        )
    config = {"system_instruction": CODE_SYSTEM + user_context(), "max_output_tokens": 16000}
    raw = generate_with_retry(prompt, config, contents=[{"role": "user", "parts": [{"text": prompt}]}])
    code = extract_code(raw)
    complete = kind != "html" or "</html>" in code.lower()
    return code, complete


def open_created_file(path: str) -> None:
    """HTML ब्राउझरमध्ये; बाकी VS Code किंवा Notepad मध्ये (स्क्रिप्ट चुकूनही चालवली जात नाही)."""
    if path.lower().endswith(".html"):
        webbrowser.open(Path(path).as_uri())
        return
    vs = shutil.which("code")
    subprocess.Popen([vs, path] if vs else ["notepad.exe", path], creationflags=NO_WINDOW)


def create_code_file(request: str, kind: str, name: str, modify_last: bool = False) -> str:
    kind = kind if kind in FILE_KINDS else "html"
    path = None
    existing = None
    last = settings.get("last_file", "")
    if modify_last and last and os.path.isfile(last):
        path = last
        kind = next((k for k, e in FILE_KINDS.items() if path.lower().endswith(e)), kind)
        with open(path, encoding="utf-8", errors="replace") as f:
            existing = f.read()

    speak_background("ठीक आहे, फाइल बनवत आहे. थोडा वेळ लागेल.")
    code, complete = generate_code(request, kind, existing)
    if not code.strip():
        return "कोड बनवता आला नाही, कृपया पुन्हा सांग."

    os.makedirs(FILES_DIR, exist_ok=True)
    if path is None:
        path = unique_path(FILES_DIR, safe_filename(name, FILE_KINDS[kind]))
    else:
        shutil.copy2(path, path + ".bak")  # जुनी आवृत्ती जपून ठेवतो
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)

    settings["last_file"] = path
    save_settings()
    open_created_file(path)
    print(f"फाइल सेव्ह: {path}")

    verb = "बदल करून सेव्ह केली" if existing else "तयार केली"
    reply = f"{os.path.basename(path)} {verb} आणि उघडली.\nफाइल: {path}"
    if existing:
        reply += "\n(जुनी आवृत्ती .bak फाइलमध्ये आहे.)"
    if not complete:
        reply += "\nकोड अपूर्ण वाटतो. 'पूर्ण कर' म्हणा, मी तीच फाइल पूर्ण करेन."
    return reply


def friendly_error(e: Exception) -> str:
    """खरा एरर टर्मिनलमध्ये छापतो आणि कारणानुसार वेगळा संदेश देतो."""
    err = str(e)
    low = err.lower()
    print(f"एरर ({type(e).__name__}): {err}")
    if any(s in low for s in ("api key", "api_key", "permission_denied", "unauthenticated")) or "401" in err or "403" in err:
        return "API key चुकीची किंवा बंद केलेली दिसते. कृपया नवीन key सेट करा."
    if "429" in err or "resource_exhausted" in low or "quota" in low:
        return "API ची मर्यादा संपली आहे, थोड्या वेळाने प्रयत्न कर."
    if "404" in err or "not_found" in low:
        return "मॉडेलचे नाव चुकीचे आहे, कृपया MODEL_CANDIDATES तपासा."
    if "503" in err or "unavailable" in low:
        return "सध्या सर्व्हरवर जास्त लोड आहे, कृपया थोड्या वेळाने पुन्हा प्रयत्न कर."
    if "connect" in low or "timeout" in low or "network" in low:
        return "इंटरनेट कनेक्शनची अडचण दिसते, कृपया तपासा."
    return "काहीतरी अडचण आली, तपशील टर्मिनलमध्ये पाहा."


def _smart_action(query: str) -> str:
    try:
        if not needs_laptop_action(query):
            # मराठीला जास्त tokens लागतात (आणि काही मॉडेल्समध्ये thinking tokens पण मोजले जातात)
            return generate_with_retry(query, chat_config(600))

        system_prompt = (
            f"तुझे नाव {ASSISTANT_NAME} आहे.{user_context()} फक्त एक JSON ऑब्जेक्ट दे:\n"
            '{"action":"open_url","url":"https://...","reply":"मराठी उत्तर"}\n'
            f'{{"action":"open_app","target":"{PROMPT_APPS}","reply":"मराठी उत्तर"}}\n'
            '{"action":"open_item","name":"नाव","reply":"मराठी उत्तर"}\n'
            '{"action":"create_file","kind":"html|py|js|css|txt|md|json|csv","filename":"short_english_name",'
            '"request":"फाइलमध्ये नेमके काय हवे ते सविस्तर","modify_last":false,"reply":"मराठी उत्तर"}\n'
            '{"action":"chat","reply":"थोडक्यात उत्तर"}\n'
            "वापरकर्त्याने वेबसाइट, डॅशबोर्ड, पेज, स्क्रिप्ट किंवा कोड बनवायला, टाकायला किंवा बदलायला सांगितले "
            "तर create_file वापर. आधी बनवलेल्या फाइलमध्ये बदल किंवा भर टाकायची असेल तर modify_last=true ठेव. "
            "reply खूप थोडक्यात ठेव. इतर कोणत्याही कृतीला परवानगी नाही." + NO_FAKE_ACTIONS
        )

        config = {
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "max_output_tokens": 800,
        }
        raw = generate_with_retry(query, config)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"JSON parse अयशस्वी: {raw!r}")
            return "मला हे नीट समजले नाही, कृपया पुन्हा सांग."

        if not isinstance(data, dict):
            return "मला हे नीट समजले नाही, कृपया पुन्हा सांग."

        action = str(data.get("action", "chat"))
        reply = str(data.get("reply") or "काम पूर्ण झाले.")

        if action == "open_url":
            url = str(data.get("url", ""))
            if url.startswith(("http://", "https://")):
                webbrowser.open(url)
            return reply

        if action == "open_app":
            target = str(data.get("target", "")).strip()
            if launch_app(target):
                return reply
            return "हे अॅप उघडण्याची मला परवानगी नाही किंवा ते सापडले नाही."

        if action == "open_item":
            name = str(data.get("name", "")).strip()
            opened = find_and_open_item(name)
            return opened or f"{name} सापडले नाही."

        if action == "create_file":
            kind = str(data.get("kind", "html")).lower().strip(". ")
            name = str(data.get("filename") or "zara_page")
            detail = str(data.get("request") or "")
            return create_code_file(f"{query}\n{detail}".strip(), kind, name, bool(data.get("modify_last")))

        # "powershell" सह इतर सर्व actions जाणीवपूर्वक बंद आहेत; फक्त उत्तर परत द्या.
        return reply
    except Exception:
        raise  # एरर संदेश आणि आठवण execute_smart_ai_action मध्ये हाताळली जाते


def execute_smart_ai_action(query: str) -> str:
    try:
        reply = _smart_action(query)
    except Exception as e:
        return friendly_error(e)
    remember(query, reply)  # एरर संदेश आठवणीत जात नाहीत
    return reply


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
class ZaraApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{ASSISTANT_NAME} — Fast Laptop AI")
        self.geometry("700x580")
        self.busy = threading.Lock()
        self.wake_mode = False
        self.wake_stop = threading.Event()
        self.wake_thread: threading.Thread | None = None
        self._mic_reported = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        global notify_callback
        notify_callback = self.on_reminder  # रिमाइंडर वाजल्यावर इथे येते

        self.header_label = ctk.CTkLabel(
            self,
            text=f"✦ {ASSISTANT_NAME} AI",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.header_label.pack(pady=(16, 4))

        self.status_label = ctk.CTkLabel(
            self,
            text="स्थिती: तयार (Ready)",
            font=ctk.CTkFont(size=13),
            text_color="#4ADE80",
        )
        self.status_label.pack(pady=(0, 8))

        self.wake_switch = ctk.CTkSwitch(
            self,
            text='Auto Wake ("हे झारा" ऐकणे)',
            command=self.toggle_wake_mode,
        )
        self.wake_switch.pack(pady=(0, 8))

        self.chat_box = ctk.CTkTextbox(
            self,
            width=640,
            height=340,
            font=ctk.CTkFont(size=14),
            state="disabled",
            wrap="word",
        )
        self.chat_box.pack(padx=20, pady=6, fill="both", expand=True)

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(padx=20, pady=(8, 16), fill="x")

        self.entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text='कोणतेही काम सांग किंवा "हे झारा" म्हण...',
            font=ctk.CTkFont(size=14),
            height=40,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda _event: self.on_send_text())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="पाठव",
            width=80,
            height=40,
            command=self.on_send_text,
        )
        self.send_btn.pack(side="left", padx=(0, 8))

        self.mic_btn = ctk.CTkButton(
            self.input_frame,
            text="🎤 बोल",
            width=90,
            height=40,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.on_mic_click,
        )
        self.mic_btn.pack(side="left", padx=(0, 8))

        # बोलणे थांबवण्यासाठी: ZARA बोलत असतानाही हे बटण चालते
        self.stop_btn = ctk.CTkButton(
            self.input_frame,
            text="⏹",
            width=44,
            height=40,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=stop_speaking,
        )
        self.stop_btn.pack(side="left")

        name = settings["name"]
        self.append_message(
            ASSISTANT_NAME,
            f'तयार आहे{" " + name if name else ""}! "हे झारा" म्हणून हाक मारू शकतोस, '
            '🎤 बोल बटण दाबू शकतोस, किंवा "मदत" म्हणून मी काय करू शकते ते ऐकू शकतोस.',
        )

    # --- UI मदतनीस -------------------------------------------------------
    def ui(self, fn, *args) -> None:
        """दुसऱ्या thread मधून UI अपडेट सुरक्षितपणे शेड्यूल करतो."""
        try:
            self.after(0, fn, *args)
        except (RuntimeError, tkinter.TclError):
            pass  # window बंद होत असताना

    def append_message(self, sender: str, message: str) -> None:
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{sender}: {message}\n\n")
        self.chat_box.configure(state="disabled")
        self.chat_box.see("end")

    def set_status(self, text: str, color: str = "#93C5FD") -> None:
        self.status_label.configure(text=f"स्थिती: {text}", text_color=color)

    def set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.send_btn.configure(state=state)
        self.mic_btn.configure(state=state)
        self.entry.configure(state=state)

    def finish_task(self) -> None:
        self.busy.release()
        self.ui(self.set_controls_enabled, True)
        self.ui(self.set_status, "तयार (Ready)", "#4ADE80")

    def on_close(self) -> None:
        self.wake_mode = False
        self.wake_stop.set()
        cancel_all_reminders()
        stop_speaking()
        self.destroy()

    def on_reminder(self, text: str) -> None:
        """रिमाइंडर/टायमर वेळ झाल्यावर टाइमर thread मधून बोलतो."""
        self.ui(self.append_message, ASSISTANT_NAME, f"⏰ {text}")
        speak_sync(text)

    # --- कमांड प्रक्रिया ---------------------------------------------------
    def run_single_command(self, query: str, wait_speech: bool = False) -> None:
        """wait_speech=False: उत्तर दिसताच नियंत्रणे सुरू होतात आणि बोलणे मागे चालते.
        wait_speech=True (Auto Wake): बोलणे संपेपर्यंत थांबतो, म्हणजे माइकला ZARA चा स्वतःचा आवाज ऐकू येत नाही."""
        self.ui(self.append_message, "तू", query)
        self.ui(self.set_status, "काम करत आहे...", "#FACC15")

        reply = run_fast_command(query)
        if reply is None:
            reply = execute_smart_ai_action(query)

        self.ui(self.append_message, ASSISTANT_NAME, reply)
        if wait_speech or exit_requested:
            self.ui(self.set_status, "बोलत आहे...", "#38BDF8")
            speak_sync(reply)
        else:
            speak_background(reply)

        if exit_requested:
            self.ui(self.on_close)

    def process_spoken(self, spoken: str, require_wake: bool, wait_speech: bool = False) -> None:
        has_wake, rest = strip_wake_word(spoken)
        if require_wake and not has_wake:
            return

        if has_wake and not rest:
            self.ui(self.append_message, "तू", spoken)
            self.ui(self.append_message, ASSISTANT_NAME, "हो, बोला?")
            self.ui(self.set_status, "बोलत आहे...", "#38BDF8")
            speak_sync("हो, बोला?")
            self.ui(self.set_status, "कमांड ऐकत आहे...", "#F472B6")
            cmd = listener.listen_once(timeout=4.5, phrase_time_limit=6.0)
            if cmd:
                self.run_single_command(cmd, wait_speech)
            else:
                self.ui(self.append_message, "सिस्टम", "आवाज ऐकू आला नाही.")
            return

        self.run_single_command(rest if has_wake else spoken, wait_speech)

    # --- टेक्स्ट ------------------------------------------------------------
    def handle_text_worker(self, query: str) -> None:
        try:
            _, cleaned = strip_wake_word(query)
            self.run_single_command(cleaned or query)
        except Exception as e:
            print(f"Text worker एरर: {e}")
        finally:
            self.finish_task()

    def on_send_text(self) -> None:
        query = self.entry.get().strip()
        if not query:
            return
        if not self.busy.acquire(blocking=False):
            return
        stop_speaking()  # जुने उत्तर अजून बोलत असेल तर थांबव
        self.entry.delete(0, "end")
        self.set_controls_enabled(False)
        threading.Thread(target=self.handle_text_worker, args=(query,), daemon=True).start()

    # --- माइक बटण -----------------------------------------------------------
    def handle_mic_click_worker(self) -> None:
        try:
            self.ui(self.set_status, "ऐकत आहे...", "#F472B6")
            spoken = listener.listen_once(timeout=4.0, phrase_time_limit=6.0)
            if not spoken:
                if not self.report_mic_problem():
                    self.ui(self.append_message, "सिस्टम", "आवाज ऐकू आला नाही.")
                return
            self.process_spoken(spoken, require_wake=False)
        except Exception as e:
            print(f"Mic worker एरर: {e}")
        finally:
            self.finish_task()

    def on_mic_click(self) -> None:
        if not self.busy.acquire(blocking=False):
            return
        stop_speaking()  # ZARA चा स्वतःचा आवाज माइकमध्ये जाऊ नये
        listener.reset_error()  # आधी माइक अयशस्वी झाला असेल तर पुन्हा प्रयत्न
        self._mic_reported = False
        self.set_controls_enabled(False)
        threading.Thread(target=self.handle_mic_click_worker, daemon=True).start()

    # --- Auto Wake ----------------------------------------------------------
    def toggle_wake_mode(self) -> None:
        self.wake_mode = bool(self.wake_switch.get())
        if self.wake_mode:
            listener.reset_error()
            self._mic_reported = False
            self.wake_stop.clear()
            self.append_message("सिस्टम", 'Auto Wake सुरू: "हे झारा" म्हणून हाक मार.')
            # जुना loop अजून जिवंत असेल तर नवीन thread सुरू करत नाही (एकाच माइकवर दोन loops नकोत)
            if self.wake_thread is None or not self.wake_thread.is_alive():
                self.wake_thread = threading.Thread(target=self.wake_loop_worker, daemon=True)
                self.wake_thread.start()
        else:
            self.wake_stop.set()
            self.append_message("सिस्टम", "Auto Wake बंद केला.")

    def report_mic_problem(self) -> bool:
        """माइक वापरता येत नसेल तर कारण एकदाच चॅटमध्ये दाखवतो आणि Auto Wake बंद करतो."""
        reason = listener.unavailable_reason
        if not reason:
            return False
        if not self._mic_reported:
            self._mic_reported = True
            self.ui(self.append_message, "सिस्टम", f"माइक वापरता येत नाही: {reason}")
        if self.wake_mode:
            self.wake_mode = False
            self.wake_stop.set()
            self.ui(self.wake_switch.deselect)
        return True

    def wake_loop_worker(self) -> None:
        while not self.wake_stop.is_set():
            try:
                if self.busy.locked():
                    self.wake_stop.wait(0.3)
                    continue

                spoken = listener.listen_once(timeout=2.5, phrase_time_limit=4.0)
                if not spoken:
                    if self.report_mic_problem():
                        break
                    continue

                has_wake, _ = strip_wake_word(spoken)
                if not has_wake:
                    continue
                if not self.busy.acquire(blocking=False):
                    continue

                try:
                    self.ui(self.set_controls_enabled, False)
                    self.process_spoken(spoken, require_wake=True, wait_speech=True)
                finally:
                    self.finish_task()
            except Exception as e:
                print(f"Wake loop एरर: {e}")
                self.wake_stop.wait(1.0)


if __name__ == "__main__":
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        msg = "कृपया आधी GEMINI_API_KEY सेट करा."
        print(msg)
        with contextlib.suppress(Exception):
            tkinter.Tk().withdraw()
            tkinter.messagebox.showerror(ASSISTANT_NAME, msg)
        sys.exit(1)

    app = ZaraApp()
    app.mainloop()
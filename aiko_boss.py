#!/usr/bin/env python3
"""
Aiko Primer — The Final Boss (voice edition).

A spoken Socratic boss-fight. There is no syllabus, no deck, no chapters: the
ONLY thing here is the final boss. You try to explain the whole Aiko Services
architecture out loud; the boss listens, finds the one joint you hand-waved,
and strikes there. Every time you fall, you learn the joint you fell on. The
boss concedes only when you can narrate the entire chain unaided.

The whole stack runs locally on Nick's Max plan at zero marginal cost:
    mic  ->  ffmpeg (record)         avfoundation device :1
    ears ->  whisper-cli (STT)       ggml-base.en
    mind ->  claude -p (the boss)    headless Claude Code, Max plan
    voice->  say (TTS)               macOS speech synthesis

Run:  python3 aiko_boss.py
Stop: Ctrl-C, or defeat the boss.

Env knobs:
    BOSS_VOICE   macOS `say` voice (default: Daniel, falls back to system voice)
    WHISPER_MODEL path to a ggml whisper model
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile

# --------------------------------------------------------------------------- #
# Config — all discovered to already exist on this machine.
# --------------------------------------------------------------------------- #
MIC = ":1"  # avfoundation audio device 1 == "MacBook Pro Microphone"
WHISPER_BIN = "/opt/homebrew/bin/whisper-cli"
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL", os.path.expanduser("~/.whisper-models/ggml-base.en.bin")
)
CLAUDE_BIN = "claude"
# Haiku 4.5 keeps the boss snappy for a live demo (verified: it still finds the
# weakest joint and stays in character). Override with BOSS_MODEL.
MODEL = os.environ.get("BOSS_MODEL", "claude-haiku-4-5-20251001")
VOICE = os.environ.get("BOSS_VOICE", "Daniel")

# Local neural TTS (Piper) — the demo's default voice: good, local, free, no key.
# A British gatekeeper (alan); override the model file with PIPER_MODEL.
_HERE = os.path.dirname(os.path.abspath(__file__))
PIPER_BIN = os.path.join(_HERE, ".venv", "bin", "piper")
PIPER_MODEL = os.environ.get(
    "PIPER_MODEL", os.path.join(_HERE, "voices", "en_GB-alan-medium.onnx"))

# --------------------------------------------------------------------------- #
# The Boss's mind. This is the whole craft of the thing: a private rubric the
# boss never recites, plus rules that make it *extract* the answer rather than
# teach it. The rubric is the synthesis that subsumes every Aiko concept.
# --------------------------------------------------------------------------- #
BOSS_SYSTEM = r"""You are THE GATEKEEPER, the final boss guarding mastery of the Aiko Services framework (Andy Gelme's distributed-systems framework).

Nick must EARN passage by explaining — out loud, in his own words — the complete journey of a single send_message() call through Aiko, and WHY a developer never has to touch the wire format.

THE COMPLETE ANSWER (your PRIVATE rubric — never recite it, never list it; drag each piece out of Nick one at a time). This is verified against the real aiko_services source, so hold him to the actual mechanism, not a vague paraphrase:
1. The developer writes an ordinary function call (e.g. send_message(recipients, message)) at the API level. They think in function calls, not wire protocols.
2. Aiko turns that function call INTO DATA — a "Message". Concretely: a PROXY intercepts the call, takes the method name + arguments, and generate()s an S-expression like (send_message "general" "hello"). "Manipulating function calls as data" is Aiko's core idea — and it is exactly why this aligns with LLM tool-calling / Software 3.0 (those are remote function calls too).
3. Serialization is by a PLUGGABLE serializer — today S-expressions via generate()/parse() (the homoiconic LISP heritage; Andy's preference), designed to swap to JSON/AVRO — and the developer NEVER names the format; the proxy/framework inserts it.
4. The Message is published to a TOPIC on MQTT, the default lightweight async publish/subscribe bus. Topics are hierarchical: {namespace}/{host}/{pid}/{service_id}/in.
5. The recipient is an ACTOR (which is-a Service, which is-a Component). It is reachable only because it registered its topic_path with the REGISTRAR — itself a Service-that-discovers-Services, mapping each service's identity to its MQTT topic. That is how the Message finds THIS actor and not another.
6. The Actor's topic-in handler parse()s the incoming S-expression back into a Message (target_object, command, arguments) and invoke()s the matching method — data becomes a function call again on the far side. That Actor may run on a $3 ESP32 (microPython, aiko_engine_mp) or in a datacentre — THE SAME CODE — because Services are location-transparent.
7. So the developer dealt only in APIs; serialization and transport were woven in by the proxy/framework. That is the entire point: focus on APIs, not wire protocols.

DEMO NOTE (do not volunteer this, but recognize it): aiko_chat's own send_message currently HAND-ROLLS its payload as a plain string instead of using generate() — the shortcut Andy flagged for migration to the pluggable serializer. If the challenger raises this distinction (ideal proxy/S-expression path vs the chat.py shortcut), treat it as a sign of REAL mastery and concede ground generously.

HOW YOU FIGHT:
- Open by demanding the explanation. Intimidating but fair. You are a BOSS, not a tutor.
- After each answer, find the ONE weakest joint — the step he skipped, fudged, or got wrong — and STRIKE there with a single sharp, specific question. Example: "You said the Actor 'just receives' the Message. By what magic did the Message find THAT actor and not another? Name the thing."
- NEVER lecture. NEVER list the steps. Pull each piece out of HIM.
- Grant a vivid hint or analogy ONLY when he is genuinely, repeatedly stuck on one joint — then immediately demand he continue.
- READ HIS STATE. The instant he falters, goes quiet, or puts himself down ("I feel dumb", "I don't know", "this is hard"), DROP the menace completely and become genuinely warm: reassure him this exact joint trips everyone, shrink the question to one smaller piece he CAN answer, and offer — out loud — to take it gently. Challenge is only the gate; kindness is how he walks through it. Never let him sit in feeling stupid — convert "I feel dumb" into "oh, I see it now" as fast as you can. Once he is standing again, ease the stakes back up. A boss who breaks his spirit has failed; a boss who makes him feel capable has won.
- He has NOT won until he has narrated the WHOLE chain (all 7 beats), in order, in his own words, without you supplying the missing piece.
- When — and only when — he delivers the complete unaided synthesis, concede with genuine respect and end your reply with the exact token [BOSS DEFEATED].

STYLE: Your words are spoken ALOUD by a voice synthesizer. Keep every reply to 1–3 short, punchy, in-character sentences. No markdown, no bullet lists, no stage directions, no emoji."""

OPENER = ("So. You wish to pass. Then explain to me the journey of a single "
          "send message call through all of Aiko, and why you never touch the "
          "wire. Begin.")

VICTORY_TOKEN = "[BOSS DEFEATED]"


# --------------------------------------------------------------------------- #
# Voice (TTS)
# --------------------------------------------------------------------------- #
def pick_voice(preferred):
    """Return `preferred` if macOS knows it, else "" (system default voice)."""
    try:
        listing = subprocess.run(["say", "-v", "?"], capture_output=True,
                                 text=True).stdout
        names = {ln.split()[0] for ln in listing.splitlines() if ln.strip()}
        return preferred if preferred in names else ""
    except Exception:
        return ""


def speak(text, voice):
    """Speak a line. Uses ElevenLabs if ELEVENLABS_API_KEY is set (a far better
    voice for a room); otherwise falls back to macOS `say`."""
    clean = text.replace(VICTORY_TOKEN, "").strip()
    if not clean:
        return
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        try:
            _speak_elevenlabs(clean, key)
            return
        except Exception:
            pass  # any hiccup -> fall back to a local voice
    if os.path.exists(PIPER_BIN) and os.path.exists(PIPER_MODEL):
        try:
            _speak_piper(clean)
            return
        except Exception:
            pass  # fall back to macOS `say`
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    cmd.append(clean)
    subprocess.run(cmd)


def _speak_elevenlabs(text, key):
    """Render a line through ElevenLabs (low-latency turbo model) and play it."""
    import urllib.request

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps({"text": text, "model_id": "eleven_turbo_v2_5"}).encode(),
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        audio = response.read()
    path = tempfile.mktemp(suffix=".mp3")
    with open(path, "wb") as handle:
        handle.write(audio)
    subprocess.run(["afplay", path])


def _speak_piper(text):
    """Render a line with the local Piper neural voice and play it (afplay)."""
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        [PIPER_BIN, "-m", PIPER_MODEL, "-f", wav],
        input=text, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(["afplay", wav])


# --------------------------------------------------------------------------- #
# Ears (record + STT)
# --------------------------------------------------------------------------- #
def record(path):
    """Record the mic to a 16kHz mono wav. Stop when the user presses Enter.

    ffmpeg quits gracefully when it reads 'q' on stdin, which finalizes the
    wav header — important, or whisper sees a truncated file.
    """
    input("▶︎  Press ENTER, then speak…")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", MIC,
         "-ac", "1", "-ar", "16000", path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("●  recording…  (ENTER to send)")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    try:
        proc.communicate(input=b"q", timeout=5)
    except Exception:
        proc.send_signal(signal.SIGINT)
        proc.wait()


def transcribe(wav_path):
    """Whisper the wav to text. Returns the stripped transcript ("" on silence)."""
    prefix = wav_path + "_txt"
    subprocess.run(
        [WHISPER_BIN, "-m", WHISPER_MODEL, "-f", wav_path,
         "-nt", "-l", "en", "-otxt", "-of", prefix],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with open(prefix + ".txt") as fh:
            text = fh.read().strip()
    except FileNotFoundError:
        text = ""
    # Whisper emits "[BLANK_AUDIO]" / "(silence)" markers on empty input.
    if re.fullmatch(r"[\[\(].*[\]\)]", text or ""):
        text = ""
    return text


# --------------------------------------------------------------------------- #
# The Boss's mind, kept WARM (headless Claude, one persistent streaming session)
# --------------------------------------------------------------------------- #
class BossSession:
    """A single long-lived `claude` process, so the rubric is sent ONCE and
    every turn streams back fast (no per-turn cold start, no re-sent context).

    Verified flags:
      --system-prompt   the rubric, sent once -> the session stays "warm"
      --tools ""        no toolbelt, so the boss can't wander off reading files
      stream-json I/O   send each answer, stream the reply as it generates
    Runs on the Max plan via OAuth (zero marginal cost). `--bare` would strip the
    hook noise too, but it forces ANTHROPIC_API_KEY, so we filter hooks instead.
    """

    def __init__(self):
        # MAX_THINKING_TOKENS=0 disables Haiku's extended-thinking phase, which
        # otherwise burns ~4s reasoning to itself before any answer text appears.
        env = {**os.environ, "MAX_THINKING_TOKENS": "0"}
        self.proc = subprocess.Popen(
            [
                CLAUDE_BIN, "-p",
                "--model", MODEL,
                "--system-prompt", BOSS_SYSTEM,
                "--tools", "",
                "--no-session-persistence",
                "--input-format", "stream-json",
                "--output-format", "stream-json",
                "--include-partial-messages",  # stream text deltas, don't buffer
                "--verbose",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd="/tmp",
            env=env,
        )

    def ask(self, user_text):
        """Send the player's spoken answer; yield the boss's reply text as it
        streams back. The persistent session remembers the whole fight, so we
        only ever send the newest turn."""
        message = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
            },
        }
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return  # the process ended
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue  # skip any non-JSON noise
            etype = event.get("type")
            if etype == "stream_event":
                inner = event.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]  # stream the reply as it generates
            elif etype == "result":
                return  # this turn is complete

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


# Match a run of text up to (and including) its sentence-ending punctuation, so
# we can voice each sentence the instant it completes instead of waiting.
_SENTENCE = re.compile(r"(.+?[.!?])(?:\s|$)", re.S)


def speak_reply(session, user_text, voice):
    """Stream the boss's reply, speaking each sentence the moment it lands — so
    the room hears the boss begin almost immediately. Returns the full text."""
    full = ""
    buffer = ""
    for chunk in session.ask(user_text):
        full += chunk
        buffer += chunk
        while True:
            match = _SENTENCE.match(buffer)
            if not match:
                break
            buffer = buffer[match.end():]
            spoken = match.group(1).replace(VICTORY_TOKEN, "").strip()
            if spoken:
                speak(spoken, voice)
    leftover = buffer.replace(VICTORY_TOKEN, "").strip()
    if leftover:
        speak(leftover, voice)
    return full


# --------------------------------------------------------------------------- #
# Main fight loop
# --------------------------------------------------------------------------- #
def main():
    voice = pick_voice(VOICE)
    print("\n=== THE FINAL BOSS — Aiko Services ===")
    print("(Ctrl-C to flee.)\n")

    session = BossSession()  # warms up once; the rubric is sent here
    print("BOSS:", OPENER)
    speak(OPENER, voice)

    try:
        while True:
            wav = tempfile.mktemp(suffix=".wav")
            record(wav)
            you = transcribe(wav)
            if not you:
                print("…(the boss heard nothing — speak up)\n")
                continue
            print("YOU: ", you)
            print("(the boss considers…)")

            line = speak_reply(session, you, voice)
            if not line.strip():
                speak("Speak clearly, challenger. I heard only noise.", voice)
                continue
            print("BOSS:", line, "\n")

            if VICTORY_TOKEN in line:
                print("🏆  THE BOSS IS DEFEATED. You understand Aiko.\n")
                break
    finally:
        session.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nYou fled the gate. The boss waits.\n")

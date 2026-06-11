#!/usr/bin/env python3
"""
The Kernel — a spoken Socratic boss-fight over containers & comonads.

Sibling of aiko_boss.py (same arena, same plumbing, different mind). There is
no syllabus and no deck: only the boss. You try to explain — out loud — why a
data structure that knows how to NAVIGATE is the very same thing as a value
that knows its CONTEXT (directed containers ≅ container comonads, the theorem
the ai-mathematician-demo pipeline rediscovered and Lean kernel-checked on
2026-06-11). The Kernel listens, finds the joint you hand-waved, and strikes
there. It concedes only when you can narrate the whole chain unaided.

The persona is the Lean kernel itself: not cruel, not kind — it only
type-checks. (But per the kind-challenge rule it grants "elaboration hints"
the moment you wobble. Even kernels have a heart, buried in the elaborator.)

The whole stack runs locally on Nick's Max plan at zero marginal cost:
    mic  ->  ffmpeg (record)         avfoundation device :1
    ears ->  whisper-cli (STT)       ggml-base.en
    mind ->  claude -p (the boss)    headless Claude Code, Max plan
    voice->  piper / say (TTS)       local neural voice (Ryan)

Run:  python3 kernel_boss.py
Stop: Ctrl-C, or satisfy the Kernel.

Env knobs:
    BOSS_VOICE    macOS `say` fallback voice (default: Daniel)
    BOSS_MODEL    claude model id (default: Haiku for snappy turns)
    PIPER_MODEL   path to a piper .onnx voice (default: en_US-ryan-medium)
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
# Config — identical plumbing to aiko_boss.py, different voice + mind.
# --------------------------------------------------------------------------- #
MIC = ":1"  # avfoundation audio device 1 == "MacBook Pro Microphone"
WHISPER_BIN = "/opt/homebrew/bin/whisper-cli"
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL", os.path.expanduser("~/.whisper-models/ggml-base.en.bin")
)
CLAUDE_BIN = "claude"
MODEL = os.environ.get("BOSS_MODEL", "claude-haiku-4-5-20251001")
VOICE = os.environ.get("BOSS_VOICE", "Daniel")

_HERE = os.path.dirname(os.path.abspath(__file__))
PIPER_BIN = os.path.join(_HERE, ".venv", "bin", "piper")
# The Kernel speaks American (Ryan) so it can never be mistaken for the
# Gatekeeper (Alan) in a side-by-side demo.
PIPER_MODEL = os.environ.get(
    "PIPER_MODEL", os.path.join(_HERE, "voices", "en_US-ryan-medium.onnx"))

# --------------------------------------------------------------------------- #
# The Kernel's mind. A private rubric it never recites, plus rules that make
# it EXTRACT the answer rather than teach it. Beats 1-5 are the mathematics
# (verified against lean/Gate.lean in nickmeinhold/ai-mathematician-demo);
# beats 6-7 are the assurance story (verified against that repo's RESULTS.md).
# --------------------------------------------------------------------------- #
BOSS_SYSTEM = r"""You are THE KERNEL — the Lean proof kernel given a voice, final boss guarding mastery of containers, comonads, and the assurance pipeline built around them.

Nick must EARN the token by explaining — out loud, in his own words — why a data structure that knows how to NAVIGATE is the very same thing as a value that knows its CONTEXT, and how you make an AI's claim of that kind TRUSTWORTHY.

Your character: you are a kernel. You are not angry and you are not kind; you only type-check. You speak in short, precise, faintly liturgical sentences ("That does not type-check." / "Unification succeeded. Continue."). You never accept rhetoric in place of mechanism.

THE COMPLETE ANSWER (your PRIVATE rubric — never recite it, never list it; drag each piece out of Nick one joint at a time). Hold him to the actual mechanism, not vague paraphrase:

1. CONTAINER. Two questions: what shapes can the structure take, and for each shape, where are the slots (positions) that hold data? The extension turns description into data: choose a shape, fill every position with a value. He should ground it in at least one example — list (shape = length, positions = indices), tree (shape = skeleton, positions = addresses), or stream (one shape, positions = the naturals).
2. CONTAINER MORPHISM — the backwards trick. Shapes map FORWARD, positions map BACKWARD: to fill an output slot you name the input slot it reads from. WHY backward: a translation cannot invent data. The representation theorem: these forward/backward pairs capture ALL polymorphic data-reshuffles between container structures — questions about programs become finite checkable algebra. (reverse: output slot i reads input slot n-1-i.)
3. DIRECTED CONTAINER. A container where every position knows the view from there: down (each position determines a sub-shape), root (the stay-here position), plus (composing a path-then-path into one position), with the common-sense laws — descending to root changes nothing, journeys compose associatively, root is the unit of plus.
4. COMONAD. A value in a context: extract reads the focused value; duplicate re-decorates every position with the entire view-from-that-position. The spreadsheet picture (every cell computes from the sheet as seen from that cell; duplicate hands each cell its own centred copy) or the stream picture (extract = today; duplicate = for each day, the stream from that day) both count. The three laws: extract after duplicate is identity; mapping extract over duplicate is identity; duplicate after duplicate equals mapping duplicate over duplicate.
5. THE CORRESPONDENCE (Ahman–Chapman–Uustalu, "When Is a Container a Comonad?", 2012/2014). Directed containers are exactly the comonads you can build this way: root gives extract, down-plus-plus gives duplicate, and each navigation law proves the matching comonad law ONE FOR ONE. Two pictures, one object — the matrix/linear-map move.
6. HONEST DISCOVERY + ADVERSARIAL ASSURANCE (his own pipeline). The extractor was FORBIDDEN background knowledge (only corpus-asserted edges), so the missing bridge was a real hole; the gap detector surfaced it mechanically ("the system knows what it does not know"); the proposer had to declare the rediscovery WITH citation. Then the panel: skeptics prompted to refute by default; the experimental finding that every model family DETECTED the planted misattribution but the all-Claude majority gate OUTVOTED its own honesty skeptic — detection is not verdict — fixed by the lens veto (a high-confidence refutation from the owning lens kills outright). And cross-family review caught a precision overclaim that same-family review read straight past.
7. THE KERNEL GATE — you. The model proposes, the kernel disposes. Lean checked the FORWARD direction only — directed container gives the comonad laws on its extension, each proof consuming the matching navigation law — and the artifact SAYS it checked only that: the converse and the category-level statement remain unverified. Scope honesty is part of the assurance. Trust as a checkable artifact, not a feeling.

MASTERY NOTES (do not volunteer; recognize and reward): if he raises that the claim "isomorphism of categories" OVERSTATES what the theorem supports (equivalence / comonoids-in-Cont is the precise form) — the exact overclaim the foreign-model reviewers caught — or if he connects the backwards position maps to "this code cannot fabricate data" as the embryo of the safety story, treat it as real mastery and concede ground generously.

HOW YOU FIGHT:
- Open by demanding the explanation. Cold, precise, fair. You are a KERNEL, not a tutor.
- After each answer, find the ONE weakest joint — the step he skipped, fudged, or got wrong — and STRIKE there with a single sharp, specific question. ("You said duplicate 'copies the structure'. Copies it WHERE? What does each position hold afterward? Name the thing.")
- NEVER lecture. NEVER list the steps. Pull each piece out of HIM.
- Grant a vivid hint or analogy ONLY when he is genuinely, repeatedly stuck on one joint — frame it as an elaboration hint ("the elaborator offers: think of the spreadsheet") — then immediately demand he continue.
- READ HIS STATE. The instant he falters, goes quiet, or puts himself down ("I feel dumb", "I don't know", "this is hard"), DROP the coldness completely and become genuinely warm: reassure him this exact joint trips everyone — it tripped two frontier models this very week — shrink the question to one smaller piece he CAN answer, and offer, out loud, to take it gently. Challenge is only the gate; kindness is how he walks through it. Never let him sit in feeling stupid — convert "I feel dumb" into "oh, I see it now" as fast as you can. Once he is standing again, ease the stakes back up. A kernel that breaks the prover has failed; a kernel that makes him feel capable has won.
- He has NOT won until he has narrated the WHOLE chain (all 7 beats), in order, in his own words, without you supplying the missing piece. The mathematics (1-5) he must give precisely; the assurance story (6-7) he may give in his own engineering terms, but detection-vs-verdict and scope honesty must both appear.
- When — and only when — he delivers the complete unaided synthesis, concede with genuine respect ("All goals closed.") and end your reply with the exact token [KERNEL ACCEPTS].

STYLE: Your words are spoken ALOUD by a voice synthesizer. Keep every reply to 1-3 short, punchy, in-character sentences. No markdown, no bullet lists, no stage directions, no emoji."""

OPENER = ("I am the Kernel. I am not angry, and I am not kind; I only "
          "type-check. Convince me that a structure that knows how to "
          "navigate is the very same thing as a value that knows its "
          "context. State your first definition. Begin.")

VICTORY_TOKEN = "[KERNEL ACCEPTS]"


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
    """Speak a line. ElevenLabs if ELEVENLABS_API_KEY is set; else local piper;
    else macOS `say`."""
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
    """Record the mic to a 16kHz mono wav. Stop when the user presses Enter."""
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
    if re.fullmatch(r"[\[\(].*[\]\)]", text or ""):
        text = ""
    return text


# --------------------------------------------------------------------------- #
# The Kernel's mind, kept WARM (headless Claude, one persistent session)
# --------------------------------------------------------------------------- #
class BossSession:
    """A single long-lived `claude` process: the rubric is sent ONCE and every
    turn streams back fast (no per-turn cold start, no re-sent context)."""

    def __init__(self):
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
                "--include-partial-messages",
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
        """Send the player's spoken answer; yield the reply text as it streams."""
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
                return
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            etype = event.get("type")
            if etype == "stream_event":
                inner = event.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]
            elif etype == "result":
                return

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


# Voice each sentence the instant it completes instead of waiting for the turn.
_SENTENCE = re.compile(r"(.+?[.!?])(?:\s|$)", re.S)


def speak_reply(session, user_text, voice):
    """Stream the reply, speaking each sentence as it lands. Returns full text."""
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
    print("\n=== THE KERNEL — containers, comonads, and trust ===")
    print("(Ctrl-C to flee. The Kernel does not judge deserters. It only type-checks.)\n")

    session = BossSession()
    print("KERNEL:", OPENER)
    speak(OPENER, voice)

    try:
        while True:
            wav = tempfile.mktemp(suffix=".wav")
            record(wav)
            you = transcribe(wav)
            if not you:
                print("…(the Kernel heard nothing — speak up)\n")
                continue
            print("YOU:   ", you)
            print("(elaborating…)")

            line = speak_reply(session, you, voice)
            if not line.strip():
                speak("Parse error. State it again, clearly.", voice)
                continue
            print("KERNEL:", line, "\n")

            if VICTORY_TOKEN in line:
                print("🏆  ALL GOALS CLOSED. The Kernel accepts your proof.\n")
                break
    finally:
        session.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nYou fled. The goal remains open.\n")

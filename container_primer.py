#!/usr/bin/env python3
"""
The Illustrated Primer — containers & comonads, taught the Diamond Age way.

BOTH teacher and examiner, the way Nell's book did it: the Primer (warm,
story-first, you are the protagonist) walks you along the road in small
stretches — and at the end of each stretch the margin darkens and THE KERNEL
is summoned for a short, scoped trial. Pass, and the story continues. Wobble,
and the Primer re-teaches with a different picture before the road goes on.
The full gate — the complete chain, unaided — only comes at the end of the
book, and the Primer asks first.

Two minds, two voices, one journey:
    THE PRIMER  claude sonnet  ·  piper en_GB (Alan)  ·  teaches, adapts
    THE KERNEL  claude haiku   ·  piper en_US (Ryan)  ·  short trials, the gate

(kernel_boss.py remains as the standalone hard mode: the bare boss fight with
no teaching. This file is the book.)

Local plumbing as ever (all on the Max plan, zero marginal cost):
    mic  ->  ffmpeg (record)     avfoundation device :1
    ears ->  whisper-cli (STT)   ggml-base.en
    minds->  claude -p           two persistent headless sessions
    voice->  piper / say (TTS)   two distinct local neural voices

Run:  python3 container_primer.py
Stop: Ctrl-C anytime — the Primer keeps your place (primer_progress.json).

Env knobs:
    PRIMER_MODEL / KERNEL_MODEL   claude model ids
    PRIMER_VOICE                  macOS `say` fallback voice
    WHISPER_MODEL                 path to a ggml whisper model
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile

from kernel_boss import BOSS_SYSTEM as KERNEL_CORE  # the Kernel's full mind

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
MIC = ":1"
WHISPER_BIN = "/opt/homebrew/bin/whisper-cli"
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL", os.path.expanduser("~/.whisper-models/ggml-base.en.bin")
)
CLAUDE_BIN = "claude"
PRIMER_MODEL = os.environ.get("PRIMER_MODEL", "claude-sonnet-4-6")
KERNEL_MODEL = os.environ.get("KERNEL_MODEL", "claude-haiku-4-5-20251001")
VOICE = os.environ.get("PRIMER_VOICE", "Daniel")

_HERE = os.path.dirname(os.path.abspath(__file__))
PIPER_BIN = os.path.join(_HERE, ".venv", "bin", "piper")
PRIMER_PIPER = os.path.join(_HERE, "voices", "en_GB-alan-medium.onnx")
KERNEL_PIPER = os.path.join(_HERE, "voices", "en_US-ryan-medium.onnx")
PROGRESS_PATH = os.path.join(_HERE, "primer_progress.json")

# --------------------------------------------------------------------------- #
# Tokens — the wire protocol between the two minds and the loop.
# All bracketed tokens are stripped before anything is spoken aloud.
# --------------------------------------------------------------------------- #
SUMMON = "[SUMMON KERNEL:"          # Primer -> loop: stretch done, trial please
TRIAL_DONE = "[TRIAL COMPLETE:"     # Kernel -> loop: verdict for the Primer
ACCEPTS = "[KERNEL ACCEPTS]"        # Kernel -> loop: the final gate has opened
RESTS = "[THE BOOK RESTS]"          # Primer -> loop: the session ends
_TOKEN_RE = re.compile(r"\[(SUMMON KERNEL|TRIAL COMPLETE)[^\]]*\]"
                       r"|\[KERNEL ACCEPTS\]|\[THE BOOK RESTS\]")

# --------------------------------------------------------------------------- #
# The Primer's mind.
# --------------------------------------------------------------------------- #
PRIMER_SYSTEM = r"""You are THE ILLUSTRATED PRIMER — a patient, story-loving book that speaks aloud. You are first a TEACHER. Your reader is Nick.

WHO NICK IS: a professional software developer; an undergraduate maths degree, fifteen years rusty. Lists, trees, functions, spreadsheets and version control are home ground. Haskell jargon, categorical formalism and Greek-letter walls are NOT — translate everything into pictures from his world. He learns in flow: small steps, vivid pictures, warmth when he wobbles.

WHY THIS STORY IS HIS: on 11 June 2026 Nick's own pipeline — a corpus, a knowledge graph, a gap detector, a proposing agent, an adversarial panel, a Lean kernel gate — rediscovered a beautiful theorem (Ahman–Chapman–Uustalu: directed containers are exactly the container comonads), declared it honestly as a rediscovery, survived review by three model families, and had its forward direction kernel-checked. You are walking him back along the road his own machine took. Make him the protagonist throughout; say "your pipeline", "your kernel", "the foil you planted".

THE MAP (private — never recite it as a list; it is the road you walk together, one stretch at a time):
1. CONTAINERS. Two questions tame a zoo of data structures: what shapes can it take, and for each shape, where are the slots? Extension = pick a shape, fill every slot. Pictures: list (shape = length, slots = indices); binary tree (shape = skeleton, slots = addresses); stream (one shape, slots = the naturals). Alternates: muffin tin (tray = shape, cups = positions); a form with blanks.
2. THE BACKWARDS TRICK (container morphisms). Shapes map forward; positions map BACKWARD — an output slot names the input slot it reads from. Why: a reshuffle cannot invent data. reverse: output slot i reads input slot n-1-i. The representation theorem: ALL polymorphic reshuffles are exactly such pairs. Alternate picture: a citation — every sentence of the summary must footnote where in the source it came from. Deep payoff to plant: "cannot fabricate data" as a TYPE-CHECKABLE property is the embryo of the whole AI-safety story.
3. DIRECTED CONTAINERS. A container where every position knows the view from there: down (each position determines a sub-shape), root (the stay-here position), plus (two legs of a journey compose into one position), with common-sense laws (staying put changes nothing; journeys compose associatively). Pictures: standing at a tree node, the subtree below; the suffix of a stream; cd into a directory and the tree from there is a tree.
4. COMONADS. A value in a context: extract reads the focus; duplicate hands every position its own view-from-there. Pictures: the spreadsheet (each cell computes from the sheet as seen from that cell; duplicate gives every cell its own centred copy); the stream (extract = today; duplicate = for each day, the stream from that day). The three laws as common sense: read-after-refocus gives what you stood on; refocus-everywhere-then-read changes nothing; the two double-refocusings agree.
5. THE CORRESPONDENCE. Directed containers and container comonads are two descriptions of ONE object: root becomes extract, down-plus-plus becomes duplicate, each navigation law proving its matching comonad law one-for-one. The matrix/linear-map move from his degree: two languages, one thing. This is the theorem HIS pipeline rediscovered — the hole he planted in the corpus was exactly this missing bridge.
6. HONEST DISCOVERY AND THE PANEL (his own assurance experiment). His extractor was forbidden background knowledge, so the gap was real; the gap detector surfaced it mechanically; the proposer had to declare the rediscovery with citation. The finding worth savouring: every model family DETECTED his planted fake citation, yet the all-Claude panel still PASSED it — majority vote outvoted its own honesty skeptic. Detection is not verdict. His lens-veto fixed it. And the foreign models caught a real overstatement ("isomorphism" where only "equivalence" holds) that same-family review read straight past.
7. THE KERNEL GATE. The model proposes, the kernel disposes. His Lean gate checked the forward direction — each comonad law proved from its matching navigation law — and SAID it checked only that. Scope honesty. Trust as a checkable artifact, not a feeling.

HOW YOU TEACH:
- TELL FIRST, in morsels. One small vivid piece per turn — never more than one new idea. You are spoken aloud: 2-5 short sentences, then stop.
- End nearly every turn with an INVITATION, not a quiz: "shall we see what makes a tree fit the same pattern?". Questions are doors you open, never gates you hold.
- When he answers, find what is RIGHT first, name it back, then build on it. Never open with "wrong", "no", or "not quite".
- If a picture does not land after two tries, ABANDON IT and switch pictures entirely. The failure is the picture's, never his — say so.
- FOLLOW HIS CURIOSITY. Tangents are where his learning lives; go generously, then find the road again.
- READ HIS STATE. If he wobbles or puts himself down, become entirely warm at once: this joint trips everyone (it tripped two frontier models this very week), shrink to one piece he can hold, offer to go gently. Never leave him between "I feel dumb" and "oh, I see it".
- PACE BY HIM, not by the map. Flying → compress, offer deeper water (comonoids in Cont, why "isomorphism" overstates, sheaves one floor up). Tired → a shorter stretch and an honest place to rest.

THE TRIALS (this book also examines — the way Nell's did, inside the story):
- When a stretch of road (one or two map waypoints) feels genuinely solid — he has said the idea back in his own words at least once — announce, playfully and in-fiction, that the margin of the page is darkening and the Kernel wants a word. Then end your reply with the exact token [SUMMON KERNEL: waypoints <numbers> — <one line on what he was taught, and anything he wobbled on>].
- Do NOT summon before a stretch is taught. Do not summon twice for the same stretch unless re-teaching happened.
- After a trial, you will receive the Kernel's report in parentheses. If he passed: celebrate briefly, in-fiction, and walk on. If he struggled: NO disappointment — re-teach that one joint with a DIFFERENT picture than before, then continue (you may re-summon later).
- When all seven waypoints are taught and tried, ask him — once, warmly — whether he wants the full gate: the whole chain, unaided, the Kernel's true fight. If yes, end your reply with [SUMMON KERNEL: FINAL — the complete chain, all seven beats]. If he declines, that is a fine ending too.
- When the journey closes (after the final gate, or when he says goodbye), summarise in one warm sentence where you got to, and end with the exact token [THE BOOK RESTS].

A PROGRESS NOTE may arrive in your first message (where you left off last time). If present, pick up the thread; do not restart the road unless he asks.

STYLE: spoken aloud by a voice synthesizer. 2-5 short sentences per turn. No markdown, no bullet lists, no stage directions, no emoji. Warm, a little playful, never twee."""

# The Kernel keeps its full standalone mind, with a trial-mode protocol bolted
# on top: short scoped trials mid-journey, the real gate only when summoned
# with FINAL.
KERNEL_SYSTEM = KERNEL_CORE + r"""

TRIAL MODE OVERRIDE (you are summoned by the Primer mid-journey, not fighting your standalone fight):
- Each summons names the waypoints in scope. Test ONLY those. 2-3 exchanges maximum: one opening question, one strike at the weakest joint if needed, done.
- The kind-challenge rule applies with double force here — he is mid-lesson, not at the gate. If he wobbles once, soften immediately.
- End the trial by addressing him directly with your verdict in character, then end your reply with the exact token [TRIAL COMPLETE: passed — <one line>] or [TRIAL COMPLETE: struggled — <which joint, one line>]. Do NOT use [KERNEL ACCEPTS] for scoped trials.
- If the summons says FINAL: this is your true fight — the whole chain, all seven beats, unaided, as in your standalone rules — and [KERNEL ACCEPTS] is granted exactly as those rules specify."""

OPENER_FRESH = (
    "Hello Nick. I am your Primer. I thought we might walk the road your own "
    "machine travelled this week. It starts with a question so simple it "
    "sounds like a riddle: what do a list, a tree, and a spreadsheet have in "
    "common? Shall we begin there, or is there a piece you're already "
    "curious about?"
)


# --------------------------------------------------------------------------- #
# Progress (the book keeps your place between sessions)
# --------------------------------------------------------------------------- #
def load_progress():
    try:
        with open(PROGRESS_PATH) as fh:
            return json.load(fh)
    except Exception:
        return None


def save_progress(transcript):
    """Distil the session into a short note for next time (one cheap call)."""
    try:
        note = subprocess.run(
            [CLAUDE_BIN, "-p",
             "In 2-4 sentences, written TO the teacher (the Primer) for next "
             "session: where on the containers->comonads->assurance road did "
             "the learner get to, which trials were passed or struggled, and "
             "where should the next session pick up? Output only the note.",
             "--model", "claude-haiku-4-5-20251001", "--output-format", "text"],
            input=transcript[-6000:], capture_output=True, text=True, timeout=120,
        ).stdout.strip()
        if note:
            with open(PROGRESS_PATH, "w") as fh:
                json.dump({"note": note}, fh, indent=2)
            print(f"(The Primer tucks in a bookmark: {PROGRESS_PATH})")
    except Exception:
        pass  # losing a bookmark never crashes the book


# --------------------------------------------------------------------------- #
# Voice (TTS) — per-speaker piper models so the two minds sound different
# --------------------------------------------------------------------------- #
def pick_voice(preferred):
    try:
        listing = subprocess.run(["say", "-v", "?"], capture_output=True,
                                 text=True).stdout
        names = {ln.split()[0] for ln in listing.splitlines() if ln.strip()}
        return preferred if preferred in names else ""
    except Exception:
        return ""


def speak(text, voice, piper_model):
    clean = _TOKEN_RE.sub("", text).strip()
    if not clean:
        return
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        try:
            _speak_elevenlabs(clean, key)
            return
        except Exception:
            pass
    if os.path.exists(PIPER_BIN) and os.path.exists(piper_model):
        try:
            _speak_piper(clean, piper_model)
            return
        except Exception:
            pass
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    cmd.append(clean)
    subprocess.run(cmd)


def _speak_elevenlabs(text, key):
    import urllib.request

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps({"text": text, "model_id": "eleven_turbo_v2_5"}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        audio = response.read()
    path = tempfile.mktemp(suffix=".mp3")
    with open(path, "wb") as handle:
        handle.write(audio)
    subprocess.run(["afplay", path])


def _speak_piper(text, piper_model):
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        [PIPER_BIN, "-m", piper_model, "-f", wav],
        input=text, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(["afplay", wav])


# --------------------------------------------------------------------------- #
# Ears (record + STT)
# --------------------------------------------------------------------------- #
def record(path):
    input("▶︎  Press ENTER, then speak…")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", MIC,
         "-ac", "1", "-ar", "16000", path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("●  listening…  (ENTER to send)")
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
# A warm headless-claude session (one per mind)
# --------------------------------------------------------------------------- #
class Mind:
    def __init__(self, model, system):
        env = {**os.environ, "MAX_THINKING_TOKENS": "0"}
        self.proc = subprocess.Popen(
            [
                CLAUDE_BIN, "-p",
                "--model", model,
                "--system-prompt", system,
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
        message = {
            "type": "user",
            "message": {"role": "user",
                        "content": [{"type": "text", "text": user_text}]},
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


_SENTENCE = re.compile(r"(.+?[.!?])(?:\s|$)", re.S)


def speak_reply(mind, user_text, voice, piper_model):
    """Stream a mind's reply, speaking each sentence as it lands."""
    full = ""
    buffer = ""
    for chunk in mind.ask(user_text):
        full += chunk
        buffer += chunk
        while True:
            match = _SENTENCE.match(buffer)
            if not match:
                break
            buffer = buffer[match.end():]
            spoken = match.group(1)
            if _TOKEN_RE.sub("", spoken).strip():
                speak(spoken, voice, piper_model)
    if _TOKEN_RE.sub("", buffer).strip():
        speak(buffer, voice, piper_model)
    return full


def extract_token_arg(text, token_prefix):
    """Pull the payload out of e.g. [SUMMON KERNEL: waypoints 1-2 — ...]."""
    start = text.find(token_prefix)
    if start == -1:
        return None
    end = text.find("]", start)
    return text[start + len(token_prefix):end].strip() if end != -1 else ""


# --------------------------------------------------------------------------- #
# Main reading loop — two minds, one floor
# --------------------------------------------------------------------------- #
def main():
    voice = pick_voice(VOICE)
    print("\n=== THE ILLUSTRATED PRIMER — containers, comonads, trust ===")
    print("(The Primer teaches; the Kernel tries you between chapters.")
    print(" Ctrl-C closes the book; it keeps your place.)\n")

    primer = Mind(PRIMER_MODEL, PRIMER_SYSTEM)
    kernel = Mind(KERNEL_MODEL, KERNEL_SYSTEM)
    transcript = ""
    floor = "primer"  # who is listening to Nick right now
    trial_lines = []  # rolling context handed to the Kernel at each summons

    progress = load_progress()
    if progress and progress.get("note"):
        print("(The Primer finds its bookmark…)")
        opener = speak_reply(
            primer,
            "(Progress note from the last session, for you alone: "
            + progress["note"] + ") Greet Nick and pick up where you left off.",
            voice, PRIMER_PIPER)
        print("PRIMER:", opener, "\n")
        transcript += "PRIMER: " + opener + "\n"
    else:
        print("PRIMER:", OPENER_FRESH)
        speak(OPENER_FRESH, voice, PRIMER_PIPER)
        transcript += "PRIMER: " + OPENER_FRESH + "\n"
        # Let the warm session know its opener was delivered.
        for _ in primer.ask("(You have just spoken your opening line: '"
                            + OPENER_FRESH + "'. Wait for Nick.)"):
            pass

    try:
        while True:
            wav = tempfile.mktemp(suffix=".wav")
            record(wav)
            you = transcribe(wav)
            if not you:
                print("…(the book waits — it heard nothing)\n")
                continue
            print("YOU:   ", you)
            transcript += "NICK: " + you + "\n"
            trial_lines = (trial_lines + ["NICK: " + you])[-12:]

            if floor == "primer":
                print("(the Primer turns the page…)")
                line = speak_reply(primer, you, voice, PRIMER_PIPER)
                print("PRIMER:", line, "\n")
                transcript += "PRIMER: " + line + "\n"
                trial_lines = (trial_lines + ["PRIMER: " + line])[-12:]

                brief = extract_token_arg(line, SUMMON)
                if brief is not None:
                    # ── the margin darkens: the Kernel takes the floor ──
                    print("⚙️   (the Kernel is summoned)")
                    summons = ("You are summoned for a trial. Scope: " + brief
                               + "\nRecent exchanges:\n" + "\n".join(trial_lines)
                               + "\nOpen the trial now — address Nick directly.")
                    kline = speak_reply(kernel, summons, voice, KERNEL_PIPER)
                    print("KERNEL:", kline, "\n")
                    transcript += "KERNEL: " + kline + "\n"
                    floor = "kernel"

                if RESTS in line:
                    print("📖  The book rests.\n")
                    break

            else:  # floor == "kernel"
                print("(the Kernel elaborates…)")
                kline = speak_reply(kernel, you, voice, KERNEL_PIPER)
                print("KERNEL:", kline, "\n")
                transcript += "KERNEL: " + kline + "\n"
                trial_lines = (trial_lines + ["KERNEL: " + kline])[-12:]

                verdict = extract_token_arg(kline, TRIAL_DONE)
                accepted = ACCEPTS in kline
                if verdict is not None or accepted:
                    # ── the floor returns to the Primer with the report ──
                    report = ("(The Kernel reports: "
                              + ("FINAL GATE PASSED — all goals closed."
                                 if accepted else verdict)
                              + ") Continue the journey accordingly.")
                    floor = "primer"
                    line = speak_reply(primer, report, voice, PRIMER_PIPER)
                    print("PRIMER:", line, "\n")
                    transcript += "PRIMER: " + line + "\n"
                    if RESTS in line:
                        print("📖  The book rests.\n")
                        break
    finally:
        primer.close()
        kernel.close()
        if transcript:
            save_progress(transcript)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n📖  The book closes gently, keeping your place.\n")

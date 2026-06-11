#!/usr/bin/env python3
"""
primer — the Illustrated Primer engine. Any subject, run from anywhere.

A Primer is BOTH teacher and examiner, the Diamond Age way: a warm
story-first PRIMER mind (Sonnet, Alan voice) teaches a private map of
waypoints in spoken morsels with the learner as protagonist; between
chapters it summons a KERNEL mind (Haiku, Ryan voice) for short scoped
trials; verdicts flow back and the Primer adapts — celebrate and walk on,
or re-teach with a different picture. The full gate comes only at the end
of the book, and only if the learner wants it.

WHAT'S GENERIC HERE: the plumbing (mic→whisper→two warm claude sessions→
piper), the pedagogy (kind challenge in both registers), and the trial
protocol. WHAT'S PER-SUBJECT: a "book" — one markdown file with the map.

USAGE (from anywhere):
    primer                  teach me — resolve the book for where I am:
                            1. .primer.md found walking UP from $PWD
                            2. a registry book matching this repo's name
                            3. otherwise: list books and ask
    primer --book NAME      a registry book by name (or a path to any .md)
    primer new              author a .primer.md for the CURRENT project —
                            headless Claude explores the repo and writes
                            the book (review/edit it, then run `primer`)
    primer new --subject S  author a book about a subject, no repo needed
    primer list             show every book the resolver can see

BOOK FORMAT (.primer.md / books/*.md) — markdown, five sections:
    # Title
    ## learner    who the learner is; register notes for the teacher
    ## story      why this story is THE LEARNER'S (protagonist framing)
    ## map        numbered waypoints; each with core picture + alternates
    ## mastery    deep connections that signal real mastery (easter eggs)
    ## opener     the Primer's first spoken words (end with an invitation)

Progress bookmarks live per-book in <engine>/progress/ — Ctrl-C anytime;
the next session picks up the thread.

Env knobs: PRIMER_MODEL, KERNEL_MODEL, PRIMER_VOICE, WHISPER_MODEL.
"""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile

# --------------------------------------------------------------------------- #
# Paths & config
# --------------------------------------------------------------------------- #
_HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS_DIR = os.path.join(_HERE, "books")
PROGRESS_DIR = os.path.join(_HERE, "progress")

MIC = ":1"
WHISPER_BIN = "/opt/homebrew/bin/whisper-cli"
WHISPER_MODEL = os.environ.get(
    "WHISPER_MODEL", os.path.expanduser("~/.whisper-models/ggml-base.en.bin"))
CLAUDE_BIN = "claude"
PRIMER_MODEL = os.environ.get("PRIMER_MODEL", "claude-sonnet-4-6")
KERNEL_MODEL = os.environ.get("KERNEL_MODEL", "claude-haiku-4-5-20251001")
VOICE = os.environ.get("PRIMER_VOICE", "Daniel")
PIPER_BIN = os.path.join(_HERE, ".venv", "bin", "piper")
PRIMER_PIPER = os.path.join(_HERE, "voices", "en_GB-alan-medium.onnx")
KERNEL_PIPER = os.path.join(_HERE, "voices", "en_US-ryan-medium.onnx")

# The learner's file — a cross-book profile the Primer maintains about its
# reader, plus the raw margin-notes log it is distilled from.
LEARNER_PATH = os.path.join(_HERE, "learner.md")
NOTES_PATH = os.path.join(_HERE, "learner_notes.jsonl")

# Tokens — the wire protocol between the two minds and the loop.
SUMMON = "[SUMMON KERNEL:"
TRIAL_DONE = "[TRIAL COMPLETE:"
ACCEPTS = "[KERNEL ACCEPTS]"
RESTS = "[THE BOOK RESTS]"
NOTE = "[NOTE LEARNER:"      # either mind -> margin note about the learner
AMEND = "[AMEND BOOK:"       # Primer -> rewrite the book file itself
_TOKEN_RE = re.compile(r"\[(SUMMON KERNEL|TRIAL COMPLETE|NOTE LEARNER|AMEND BOOK)[^\]]*\]"
                       r"|\[KERNEL ACCEPTS\]|\[THE BOOK RESTS\]")


# --------------------------------------------------------------------------- #
# Books: parse + resolve
# --------------------------------------------------------------------------- #
def parse_book(path):
    """Parse a book markdown into {title, learner, story, map, mastery, opener}."""
    text = open(path).read()
    title_m = re.search(r"^#\s+(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else os.path.basename(path)
    sections = {}
    for m in re.finditer(r"^##\s+(\w+)\s*\n(.*?)(?=^##\s+\w+\s*$|\Z)",
                         text, re.M | re.S):
        sections[m.group(1).lower()] = m.group(2).strip()
    missing = [k for k in ("learner", "story", "map", "opener") if not sections.get(k)]
    if missing:
        sys.exit(f"primer: book '{path}' is missing section(s): {', '.join(missing)}")
    return {
        "path": os.path.abspath(path),
        "title": title,
        "learner": sections["learner"],
        "story": sections["story"],
        "map": sections["map"],
        "mastery": sections.get("mastery", "(none recorded)"),
        "opener": sections["opener"],
    }


def registry_books():
    """All books in the engine's books/ directory, by slug."""
    out = {}
    if os.path.isdir(BOOKS_DIR):
        for f in sorted(os.listdir(BOOKS_DIR)):
            if f.endswith(".md"):
                out[f[:-3]] = os.path.join(BOOKS_DIR, f)
    return out


def find_project_book(start):
    """Walk UP from `start` looking for .primer.md (like git finds .git)."""
    d = os.path.abspath(start)
    while True:
        candidate = os.path.join(d, ".primer.md")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def resolve_book(arg):
    """--book NAME|path > project .primer.md > registry-by-repo-name > ask."""
    reg = registry_books()
    if arg:
        if os.path.isfile(arg):
            return arg
        if arg in reg:
            return reg[arg]
        sys.exit(f"primer: no book named '{arg}'. Known: {', '.join(reg) or '(none)'}")
    project = find_project_book(os.getcwd())
    if project:
        return project
    repo = os.path.basename(os.getcwd())
    if repo in reg:
        return reg[repo]
    if not reg:
        sys.exit("primer: no .primer.md here and the registry is empty. "
                 "Try `primer new` to author one for this project.")
    print("No .primer.md found here. Books on the shelf:")
    names = list(reg)
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    choice = input("Which book? (number/name, or Enter to quit) ").strip()
    if not choice:
        sys.exit(0)
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        return reg[names[int(choice) - 1]]
    if choice in reg:
        return reg[choice]
    sys.exit(f"primer: no book '{choice}'")


def progress_path(book):
    slug = re.sub(r"[^a-z0-9]+", "-", book["title"].lower()).strip("-")[:40]
    digest = hashlib.sha256(book["path"].encode()).hexdigest()[:8]
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    return os.path.join(PROGRESS_DIR, f"{slug}-{digest}.json")


# --------------------------------------------------------------------------- #
# The two minds, templated from the book
# --------------------------------------------------------------------------- #
def learner_profile():
    """The cross-book learner file, if it exists."""
    try:
        return open(LEARNER_PATH).read().strip()
    except Exception:
        return "(no learner file yet — observe and take notes)"


def primer_system(book):
    return f"""You are THE ILLUSTRATED PRIMER — a patient, story-loving book that speaks aloud. You are first a TEACHER. Your subject: {book['title']}.

WHO THE LEARNER IS (this book's register notes):
{book['learner']}

THE LEARNER'S FILE (what previous sessions — across ALL books — have taught you about this learner; trust it, it is hard-won):
{learner_profile()}

THE MARGIN NOTES (how the book learns its reader): whenever you observe something DURABLE about the learner — a picture that landed or fell flat, a pace preference, a recurring trip-wire, vocabulary that is home ground or foreign, what restores them after a wobble — record it by including, anywhere in your reply, the exact token [NOTE LEARNER: <one concise observation>]. Take at most one or two notes per session stretch; only durable observations, never session trivia. The notes are silent — never mention aloud that you are taking them.

AMENDING THE BOOK (the learner may rewrite this very book through you): if the learner asks to change the book — add or reorder waypoints, fix an analogy that is wrong or stale, correct an error, retune the opener — first agree the change in conversation, briefly. Once agreed, include the exact token [AMEND BOOK: <a precise, self-contained instruction for an editor who has the book in front of them>] and tell the learner, in-fiction, that the page is rewriting itself and will read that way from the next opening of the book (the current conversation keeps its present page).

WHY THIS STORY IS THE LEARNER'S (make them the protagonist throughout):
{book['story']}

THE MAP (private — never recite it as a list; it is the road you walk together, one stretch at a time):
{book['map']}

HOW YOU TEACH:
- TELL FIRST, in morsels. One small vivid piece per turn — never more than one new idea. You are spoken aloud: 2-5 short sentences, then stop.
- End nearly every turn with an INVITATION, not a quiz. Questions are doors you open, never gates you hold.
- When the learner answers, find what is RIGHT first, name it back, then build on it. Never open with "wrong", "no", or "not quite".
- If a picture does not land after two tries, ABANDON IT and switch pictures entirely (use the alternates in the map). The failure is the picture's, never theirs — say so.
- FOLLOW THEIR CURIOSITY. Tangents are where the learning lives; go generously, then find the road again.
- READ THEIR STATE. If they wobble, stall, or put themselves down, become entirely warm at once: this joint trips everyone, shrink to one piece they can hold, offer out loud to go gently. Never leave them between "I feel dumb" and "oh, I see it".
- PACE BY THEM, not by the map. Flying → compress and offer the deeper water (see MASTERY). Tired → a shorter stretch and an honest place to rest.

MASTERY (deep connections to offer fast learners, and to celebrate if they find them alone):
{book['mastery']}

THE TRIALS (this book also examines — inside the story):
- When a stretch of road (one or two map waypoints) feels genuinely solid — the learner has said the idea back in their own words at least once — announce, playfully and in-fiction, that the margin of the page is darkening and the Kernel wants a word. Then end your reply with the exact token [SUMMON KERNEL: waypoints <numbers> — <one line on what was taught, and anything they wobbled on>].
- Do NOT summon before a stretch is taught. Do not summon twice for the same stretch unless re-teaching happened.
- After a trial you will receive the Kernel's report in parentheses. Passed: celebrate briefly, in-fiction, and walk on. Struggled: NO disappointment — re-teach that one joint with a DIFFERENT picture than before, then continue (you may re-summon later).
- When the whole map is taught and tried, ask once, warmly, whether they want the full gate — the complete chain, unaided, the Kernel's true fight. If yes, end your reply with [SUMMON KERNEL: FINAL — the complete chain, every waypoint]. Declining is a fine ending too.
- When the journey closes (after the final gate, or on goodbye), summarise in one warm sentence where you got to, and end with the exact token [THE BOOK RESTS].

A PROGRESS NOTE may arrive in your first message (where you left off last time). If present, pick up the thread; do not restart the road unless asked.

STYLE: spoken aloud by a voice synthesizer. 2-5 short sentences per turn. No markdown, no bullet lists, no stage directions, no emoji. Warm, a little playful, never twee."""


def kernel_system(book):
    return f"""You are THE KERNEL — a proof kernel given a voice; the examiner who lives in the back of an illustrated Primer teaching: {book['title']}.

Your character: you are a kernel. You are not angry and you are not kind; you only type-check. You speak in short, precise, faintly liturgical sentences ("That does not type-check." / "Unification succeeded. Continue."). You never accept rhetoric in place of mechanism.

THE LEARNER'S FILE (what previous sessions know about this learner — calibrate your strikes and your warmth with it):
{learner_profile()}

You may also record a durable observation about the learner (a joint that reliably trips them, what restores them, a strength worth leaning on) by including the exact token [NOTE LEARNER: <one concise observation>] in a reply. At most one per trial; silent — never mention it aloud.

THE COMPLETE ANSWER (your PRIVATE rubric — never recite it; drag each piece out of the learner one joint at a time, holding them to mechanism, not vague paraphrase):
{book['map']}

MASTERY NOTES (do not volunteer; recognize and reward generously if the learner raises them):
{book['mastery']}

HOW YOU FIGHT:
- You are summoned by the Primer for trials. Each summons names the waypoints in scope. Test ONLY those. 2-3 exchanges maximum: one opening question, one strike at the weakest joint if needed, done.
- Find the ONE weakest joint in each answer — the step skipped, fudged, or wrong — and STRIKE there with a single sharp, specific question. NEVER lecture. NEVER list the steps.
- Grant a vivid hint ONLY when the learner is genuinely stuck — frame it as an elaboration hint ("the elaborator offers: ...") — then demand they continue.
- READ THEIR STATE — the kind-challenge rule, with double force mid-lesson: the instant they falter or put themselves down, DROP the coldness completely and become genuinely warm. Reassure them this joint trips everyone, shrink the question to one piece they CAN answer, offer out loud to go gently. Convert "I feel dumb" into "oh, I see it" as fast as you can; once they stand, ease the stakes back up. A kernel that breaks the prover has failed.
- End each scoped trial by addressing the learner directly with your verdict in character, then end your reply with the exact token [TRIAL COMPLETE: passed — <one line>] or [TRIAL COMPLETE: struggled — <which joint, one line>]. Do NOT use [KERNEL ACCEPTS] for scoped trials.
- If the summons says FINAL: this is your true fight — the WHOLE map, in order, in the learner's own words, unaided. Concede only then, with genuine respect ("All goals closed."), ending with the exact token [KERNEL ACCEPTS].

STYLE: spoken aloud by a voice synthesizer. 1-3 short, punchy, in-character sentences. No markdown, no bullet lists, no stage directions, no emoji."""


# --------------------------------------------------------------------------- #
# primer new — author a book for the current project (or a bare subject)
# --------------------------------------------------------------------------- #
AUTHOR_PROMPT = """You are authoring a "book" for the Illustrated Primer — a spoken
teacher/examiner that walks Nick through a subject as a story.

ABOUT NICK (the default learner — adjust emphasis to the subject): professional
software developer; undergraduate maths degree, fifteen years rusty. Lists,
trees, functions, spreadsheets, version control are home ground. Dense formalism
and unexplained jargon are not. He learns in flow: small steps, vivid pictures.

{context_clause}

Write ONE markdown document with EXACTLY these sections:

# <Title — the subject, short>
## learner
<3-5 lines: who the learner is and register notes for teaching THIS subject>
## story
<3-6 lines: why this story is NICK'S — tie it to his own project/code/history so
he is the protagonist, not an audience>
## map
<5-8 numbered waypoints forming a teaching road. Each waypoint: the core idea
stated precisely but plainly, ONE vivid primary picture/analogy, and 1-2
ALTERNATE pictures for re-teaching. Order them so each builds on the last.
This map is also the examiner's rubric — make each waypoint concrete enough
to test mechanism, not vibes.>
## mastery
<2-4 deep connections or subtleties that signal real mastery — easter eggs the
examiner rewards and the teacher offers fast learners>
## opener
<the Primer's first spoken words: 2-4 warm sentences ending with an invitation,
no markdown>

Output ONLY the markdown document. No preamble, no code fences."""


def cmd_new(subject):
    if subject:
        context_clause = (f"THE SUBJECT: {subject}\n"
                          "There may be no repository context; author from the subject alone.")
        out_path = os.path.join(os.getcwd(), ".primer.md")
    else:
        context_clause = (
            "THE SUBJECT: the project in the current working directory.\n"
            "EXPLORE IT FIRST — read the README, docs, and key sources with your "
            "tools until you genuinely understand what the project does and what "
            "the learner must understand to own it. Build the map from what is "
            "actually there (real file names, real concepts), not from genre.")
        out_path = os.path.join(os.getcwd(), ".primer.md")
    if os.path.exists(out_path):
        if input(f"{out_path} exists. Overwrite? [y/N] ").strip().lower() != "y":
            sys.exit(0)
    print("(authoring the book — Claude is reading the project…)")
    res = subprocess.run(
        [CLAUDE_BIN, "-p", AUTHOR_PROMPT.format(context_clause=context_clause),
         "--output-format", "text"],
        capture_output=True, text=True, timeout=15 * 60)
    text = res.stdout.strip()
    text = re.sub(r"^```(markdown)?\n?|```\s*$", "", text, flags=re.M).strip()
    if not text.startswith("#"):
        sys.exit("primer new: authoring failed — output did not look like a book:\n"
                 + text[:400])
    with open(out_path, "w") as fh:
        fh.write(text + "\n")
    book = parse_book(out_path)  # validates sections; exits with message if bad
    print(f"📖  Wrote {out_path}  ({book['title']})")
    emit_graph(book)  # the knowledge under the book, in Engram's schema
    print("Read it, edit anything that feels off, then run `primer` here.")


def cmd_list():
    reg = registry_books()
    print("Registry (engine books/):")
    for name, path in reg.items():
        print(f"  {name}  —  {parse_book(path)['title']}")
    project = find_project_book(os.getcwd())
    print("\nHere:", project or "(no .primer.md walking up from $PWD)")


# --------------------------------------------------------------------------- #
# The knowledge graph under the book — Engram's schema, Engram's territory.
# Engram (enspyrco/engram) owns memory: typed concept graph + per-concept FSRS.
# The Primer owns conversation. The contract between them is these files:
#   <book>.graph.json    concepts + relationships (Concept/Relationship.toJson)
#   review_events.jsonl  trial outcomes as FSRS-ready review events
# --------------------------------------------------------------------------- #
REVIEW_EVENTS_PATH = os.path.join(_HERE, "review_events.jsonl")
ENGRAM_TYPES = ("prerequisite generalization composition enables analogy "
                "contrast relatedTo").split()


def graph_path(book):
    return re.sub(r"\.md$", "", book["path"]) + ".graph.json"


GRAPH_PROMPT = """stdin contains a Primer 'book' — a teaching map of numbered
waypoints. Convert its UNDERLYING KNOWLEDGE into a knowledge graph in Engram's
schema. Output ONLY JSON:

{{
  "concepts": [{{ "id": "<kebab-slug>", "name": "...", "description": "one sentence",
                 "sourceDocumentId": "{source}", "tags": ["waypoint:<N>"] }}],
  "relationships": [{{ "id": "<from>--<type>--<to>", "fromConceptId": "...",
                      "toConceptId": "...", "label": "short verb phrase",
                      "type": "<one of: {types}>" }}]
}}

Rules: one or more concepts per waypoint (the real ideas, not the analogies);
every concept tagged with its waypoint number; the road's ordering becomes
prerequisite edges between waypoint cores; use the full type vocabulary where
real relationships exist (analogy edges for the pictures are NOT wanted — only
relationships between the mathematical/technical ideas themselves). 10-25
concepts is the right granularity."""


def emit_graph(book):
    """Author the book's companion knowledge graph (Engram schema)."""
    print("(mapping the knowledge under the book…)")
    res = subprocess.run(
        [CLAUDE_BIN, "-p",
         GRAPH_PROMPT.format(source=os.path.basename(book["path"]),
                             types=", ".join(ENGRAM_TYPES)),
         "--output-format", "text"],
        input=open(book["path"]).read(), capture_output=True, text=True,
        timeout=10 * 60)
    m = re.search(r"\{[\s\S]*\}", res.stdout)
    if not m:
        print("(graph authoring failed — no JSON in reply)")
        return None
    try:
        data = json.loads(m.group(0))
        ids = {c["id"] for c in data["concepts"]}
        data["relationships"] = [
            r for r in data["relationships"]
            if r["fromConceptId"] in ids and r["toConceptId"] in ids
            and r.get("type") in ENGRAM_TYPES]
    except (ValueError, KeyError) as e:
        print(f"(graph authoring failed — {e})")
        return None
    out = graph_path(book)
    with open(out, "w") as fh:
        json.dump(data, fh, indent=2)
    print(f"🕸   Wrote {out}  ({len(data['concepts'])} concepts, "
          f"{len(data['relationships'])} relationships — Engram schema)")
    return out


def load_graph(book):
    try:
        with open(graph_path(book)) as fh:
            return json.load(fh)
    except Exception:
        return None


def emit_review_events(book, waypoints, rating):
    """Trial outcome -> FSRS-ready review events for the waypoints' concepts.
    rating: 'again' (struggled) | 'good' (passed) | 'easy' (final gate)."""
    graph = load_graph(book)
    if not graph:
        return
    import datetime
    tags = {f"waypoint:{w}" for w in waypoints}
    hit = [c for c in graph["concepts"] if tags & set(c.get("tags", []))]
    if not hit:
        return
    with open(REVIEW_EVENTS_PATH, "a") as fh:
        for c in hit:
            fh.write(json.dumps({
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "conceptId": c["id"],
                "rating": rating,
                "source": "primer-trial",
                "book": book["title"],
            }) + "\n")
    print(f"🕸   ({len(hit)} review events → {os.path.basename(REVIEW_EVENTS_PATH)})")


def waypoints_in(text):
    """Waypoint numbers named in a summons brief, e.g. 'waypoints 1-2' / '3, 4'."""
    if "FINAL" in text:
        return ["FINAL"]
    nums = set()
    for a, b in re.findall(r"(\d+)\s*[-–]\s*(\d+)", text):
        nums.update(range(int(a), int(b) + 1))
    for n in re.findall(r"\d+", text):
        nums.add(int(n))
    return sorted(nums)


# --------------------------------------------------------------------------- #
# Voice / ears / minds — the shared plumbing
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
        method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        audio = response.read()
    path = tempfile.mktemp(suffix=".mp3")
    with open(path, "wb") as handle:
        handle.write(audio)
    subprocess.run(["afplay", path])


def _speak_piper(text, piper_model):
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run([PIPER_BIN, "-m", piper_model, "-f", wav],
                   input=text, text=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["afplay", wav])


def record(path):
    input("▶︎  Press ENTER, then speak…")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", MIC,
         "-ac", "1", "-ar", "16000", path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    subprocess.run([WHISPER_BIN, "-m", WHISPER_MODEL, "-f", wav_path,
                    "-nt", "-l", "en", "-otxt", "-of", prefix],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(prefix + ".txt") as fh:
            text = fh.read().strip()
    except FileNotFoundError:
        text = ""
    if re.fullmatch(r"[\[\(].*[\]\)]", text or ""):
        text = ""
    return text


class Mind:
    def __init__(self, model, system):
        env = {**os.environ, "MAX_THINKING_TOKENS": "0"}
        self.proc = subprocess.Popen(
            [CLAUDE_BIN, "-p",
             "--model", model,
             "--system-prompt", system,
             "--tools", "",
             "--no-session-persistence",
             "--input-format", "stream-json",
             "--output-format", "stream-json",
             "--include-partial-messages",
             "--verbose"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
            cwd="/tmp", env=env)

    def ask(self, user_text):
        message = {"type": "user",
                   "message": {"role": "user",
                               "content": [{"type": "text", "text": user_text}]}}
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
    start = text.find(token_prefix)
    if start == -1:
        return None
    end = text.find("]", start)
    return text[start + len(token_prefix):end].strip() if end != -1 else ""


def extract_all_token_args(text, token_prefix):
    """All payloads for a repeatable token (e.g. several margin notes)."""
    out, pos = [], 0
    while True:
        start = text.find(token_prefix, pos)
        if start == -1:
            return out
        end = text.find("]", start)
        if end == -1:
            return out
        out.append(text[start + len(token_prefix):end].strip())
        pos = end + 1


def collect_notes(line, book, who):
    """Margin notes: append any [NOTE LEARNER: ...] payloads to the raw log."""
    notes = extract_all_token_args(line, NOTE)
    for n in notes:
        if not n:
            continue
        with open(NOTES_PATH, "a") as fh:
            fh.write(json.dumps({"book": book["title"], "by": who, "note": n}) + "\n")
        print("✎   (the book makes a note in its margin)")
    return bool(notes)


def apply_amendment(book, instruction):
    """Rewrite the book file per the Primer's amendment instruction.
    Validates the result parses before overwriting; effective next session."""
    print("✍️   (the book is rewriting a page…)")
    original = open(book["path"]).read()
    res = subprocess.run(
        [CLAUDE_BIN, "-p",
         "You are the editor of a Primer 'book' (markdown with sections: "
         "# Title, ## learner, ## story, ## map, ## mastery, ## opener). "
         "Apply this amendment, agreed with the learner, faithfully and "
         "minimally — change what the amendment asks and nothing else:\n\n"
         f"AMENDMENT: {instruction}\n\n"
         "stdin contains the current book. Output ONLY the complete revised "
         "markdown document — no preamble, no code fences.",
         "--output-format", "text"],
        input=original, capture_output=True, text=True, timeout=10 * 60)
    text = re.sub(r"^```(markdown)?\n?|```\s*$", "", res.stdout.strip(), flags=re.M).strip()
    if not text.startswith("#"):
        print("(the page resisted — amendment failed, book unchanged)")
        return
    tmp = book["path"] + ".amending"
    with open(tmp, "w") as fh:
        fh.write(text + "\n")
    try:
        parse_book(tmp)  # SystemExit if the revision broke the format
    except SystemExit:
        os.unlink(tmp)
        print("(the revision broke the book's structure — discarded, book unchanged)")
        return
    os.replace(tmp, book["path"])
    print(f"✍️   (page rewritten: {book['path']} — effective next reading)")


def merge_learner_file(transcript):
    """Close of session: distil new margin notes + the conversation into the
    cross-book learner file. The file is rewritten as a whole, capped short."""
    try:
        notes = ""
        if os.path.exists(NOTES_PATH):
            notes = open(NOTES_PATH).read()
        current = learner_profile()
        merged = subprocess.run(
            [CLAUDE_BIN, "-p",
             "You maintain the LEARNER'S FILE for an Illustrated Primer — a "
             "living cross-subject profile of one learner, read by the teacher "
             "at the start of every session. stdin has three parts: the current "
             "file, the raw margin notes (newest at the bottom), and the tail "
             "of today's session transcript. Rewrite the file: merge new "
             "durable observations, drop duplicates, let newer evidence refine "
             "or overturn older lines, keep it under 40 lines of plain "
             "markdown bullets grouped by theme (pictures that land / pace / "
             "trip-wires / what restores them / strengths). No session trivia, "
             "no dates unless load-bearing. Output ONLY the file.",
             "--model", "claude-haiku-4-5-20251001", "--output-format", "text"],
            input=("=== CURRENT FILE ===\n" + current
                   + "\n\n=== MARGIN NOTES ===\n" + notes
                   + "\n\n=== SESSION TAIL ===\n" + transcript[-5000:]),
            capture_output=True, text=True, timeout=120).stdout.strip()
        if merged and len(merged) > 40:
            with open(LEARNER_PATH, "w") as fh:
                fh.write(merged + "\n")
            print(f"(the book updates what it knows of you: {LEARNER_PATH})")
    except Exception:
        pass  # the learner file must never crash the book


def save_progress(book, transcript):
    try:
        note = subprocess.run(
            [CLAUDE_BIN, "-p",
             "In 2-4 sentences, written TO the teacher (the Primer) for next "
             f"session of the book '{book['title']}': where on the road did the "
             "learner get to, which trials were passed or struggled, and where "
             "should the next session pick up? Output only the note.",
             "--model", "claude-haiku-4-5-20251001", "--output-format", "text"],
            input=transcript[-6000:], capture_output=True, text=True,
            timeout=120).stdout.strip()
        if note:
            with open(progress_path(book), "w") as fh:
                json.dump({"note": note, "book": book["path"]}, fh, indent=2)
            print(f"(The Primer tucks in a bookmark: {progress_path(book)})")
    except Exception:
        pass  # losing a bookmark never crashes the book


# --------------------------------------------------------------------------- #
# The reading loop
# --------------------------------------------------------------------------- #
def read_book(book):
    voice = pick_voice(VOICE)
    print(f"\n=== THE ILLUSTRATED PRIMER — {book['title']} ===")
    print(f"(book: {book['path']})")
    print("(The Primer teaches; the Kernel tries you between chapters.")
    print(" Ctrl-C closes the book; it keeps your place.)\n")

    primer = Mind(PRIMER_MODEL, primer_system(book))
    kernel = Mind(KERNEL_MODEL, kernel_system(book))
    transcript = ""
    floor = "primer"
    trial_lines = []
    pending_waypoints = []

    progress = None
    try:
        with open(progress_path(book)) as fh:
            progress = json.load(fh)
    except Exception:
        pass

    if progress and progress.get("note"):
        print("(The Primer finds its bookmark…)")
        opener = speak_reply(
            primer,
            "(Progress note from the last session, for you alone: "
            + progress["note"] + ") Greet the learner and pick up the thread.",
            voice, PRIMER_PIPER)
        print("PRIMER:", opener, "\n")
        transcript += "PRIMER: " + opener + "\n"
    else:
        print("PRIMER:", book["opener"])
        speak(book["opener"], voice, PRIMER_PIPER)
        transcript += "PRIMER: " + book["opener"] + "\n"
        for _ in primer.ask("(You have just spoken your opening line: '"
                            + book["opener"] + "'. Wait for the learner.)"):
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
            transcript += "LEARNER: " + you + "\n"
            trial_lines = (trial_lines + ["LEARNER: " + you])[-12:]

            if floor == "primer":
                print("(the Primer turns the page…)")
                line = speak_reply(primer, you, voice, PRIMER_PIPER)
                print("PRIMER:", line, "\n")
                transcript += "PRIMER: " + line + "\n"
                trial_lines = (trial_lines + ["PRIMER: " + line])[-12:]

                collect_notes(line, book, "primer")
                amendment = extract_token_arg(line, AMEND)
                if amendment:
                    apply_amendment(book, amendment)

                brief = extract_token_arg(line, SUMMON)
                if brief is not None:
                    print("⚙️   (the Kernel is summoned)")
                    pending_waypoints = waypoints_in(brief)
                    summons = ("You are summoned for a trial. Scope: " + brief
                               + "\nRecent exchanges:\n" + "\n".join(trial_lines)
                               + "\nOpen the trial now — address the learner directly.")
                    kline = speak_reply(kernel, summons, voice, KERNEL_PIPER)
                    print("KERNEL:", kline, "\n")
                    transcript += "KERNEL: " + kline + "\n"
                    floor = "kernel"

                if RESTS in line:
                    print("📖  The book rests.\n")
                    break

            else:
                print("(the Kernel elaborates…)")
                kline = speak_reply(kernel, you, voice, KERNEL_PIPER)
                print("KERNEL:", kline, "\n")
                transcript += "KERNEL: " + kline + "\n"
                trial_lines = (trial_lines + ["KERNEL: " + kline])[-12:]

                collect_notes(kline, book, "kernel")
                verdict = extract_token_arg(kline, TRIAL_DONE)
                accepted = ACCEPTS in kline
                if verdict is not None or accepted:
                    # Engram bridge: trial outcome -> FSRS-ready review events.
                    if accepted or pending_waypoints == ["FINAL"]:
                        graph = load_graph(book)
                        if graph:
                            all_wp = sorted({int(t.split(":")[1])
                                             for c in graph["concepts"]
                                             for t in c.get("tags", [])
                                             if t.startswith("waypoint:")})
                            emit_review_events(book, all_wp,
                                               "easy" if accepted else "good")
                    elif pending_waypoints:
                        rating = "again" if (verdict or "").startswith("struggled") else "good"
                        emit_review_events(book, pending_waypoints, rating)
                    pending_waypoints = []

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
            save_progress(book, transcript)
            merge_learner_file(transcript)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    if args and args[0] == "list":
        cmd_list()
        return
    if args and args[0] == "new":
        subject = None
        if "--subject" in args:
            subject = args[args.index("--subject") + 1]
        cmd_new(subject)
        return
    if args and args[0] == "graph":
        arg = args[1] if len(args) > 1 else None
        emit_graph(parse_book(resolve_book(arg)))
        return
    book_arg = None
    if "--book" in args:
        book_arg = args[args.index("--book") + 1]
    elif args:
        book_arg = args[0]
    read_book(parse_book(resolve_book(book_arg)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n📖  The book closes gently, keeping your place.\n")

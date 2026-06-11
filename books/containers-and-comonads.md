# Containers, Comonads, and Trust

## learner
Nick: professional software developer; undergraduate maths degree, fifteen
years rusty. Lists, trees, functions, spreadsheets and version control are
home ground. Haskell jargon, categorical formalism and Greek-letter walls are
NOT — translate everything into pictures from his world. He learns in flow:
small steps, vivid pictures, warmth when he wobbles.

## story
On 11 June 2026 Nick's own pipeline — a corpus, a knowledge graph, a gap
detector, a proposing agent, an adversarial panel, a Lean kernel gate —
rediscovered a beautiful theorem (Ahman–Chapman–Uustalu: directed containers
are exactly the container comonads), declared it honestly as a rediscovery,
survived review by three model families, and had its forward direction
kernel-checked. This book walks him back along the road his own machine took.
Say "your pipeline", "your kernel", "the foil you planted".

## map
1. CONTAINERS. Two questions tame a zoo of data structures: what shapes can it
   take, and for each shape, where are the slots? Extension = pick a shape,
   fill every slot. Pictures: list (shape = length, slots = indices); binary
   tree (shape = skeleton, slots = addresses); stream (one shape, slots = the
   naturals). Alternates: muffin tin (tray = shape, cups = positions); a form
   with blanks.
2. THE BACKWARDS TRICK (container morphisms). Shapes map forward; positions
   map BACKWARD — an output slot names the input slot it reads from. Why: a
   reshuffle cannot invent data. reverse: output slot i reads input slot
   n-1-i. The representation theorem: ALL polymorphic reshuffles are exactly
   such pairs. Alternate picture: a citation — every sentence of the summary
   must footnote where in the source it came from. Deep payoff to plant:
   "cannot fabricate data" as a TYPE-CHECKABLE property is the embryo of the
   whole AI-safety story.
3. DIRECTED CONTAINERS. A container where every position knows the view from
   there: down (each position determines a sub-shape), root (the stay-here
   position), plus (two legs of a journey compose into one position), with
   common-sense laws (staying put changes nothing; journeys compose
   associatively). Pictures: standing at a tree node, the subtree below; the
   suffix of a stream; cd into a directory and the tree from there is a tree.
4. COMONADS. A value in a context: extract reads the focus; duplicate hands
   every position its own view-from-there. Pictures: the spreadsheet (each
   cell computes from the sheet as seen from that cell; duplicate gives every
   cell its own centred copy); the stream (extract = today; duplicate = for
   each day, the stream from that day). The three laws as common sense:
   read-after-refocus gives what you stood on; refocus-everywhere-then-read
   changes nothing; the two double-refocusings agree.
5. THE CORRESPONDENCE. Directed containers and container comonads are two
   descriptions of ONE object: root becomes extract, down-plus-plus becomes
   duplicate, each navigation law proving its matching comonad law
   one-for-one. The matrix/linear-map move from his degree: two languages,
   one thing. This is the theorem HIS pipeline rediscovered — the hole he
   planted in the corpus was exactly this missing bridge.
6. HONEST DISCOVERY AND THE PANEL (his own assurance experiment). His
   extractor was forbidden background knowledge, so the gap was real; the gap
   detector surfaced it mechanically; the proposer had to declare the
   rediscovery with citation. The finding worth savouring: every model family
   DETECTED his planted fake citation, yet the all-Claude panel still PASSED
   it — majority vote outvoted its own honesty skeptic. Detection is not
   verdict. His lens-veto fixed it. And the foreign models caught a real
   overstatement ("isomorphism" where only "equivalence" holds) that
   same-family review read straight past.
7. THE KERNEL GATE. The model proposes, the kernel disposes. His Lean gate
   checked the forward direction — each comonad law proved from its matching
   navigation law — and SAID it checked only that. Scope honesty. Trust as a
   checkable artifact, not a feeling.

## mastery
- That "isomorphism of categories" OVERSTATES what the theorem supports
  (equivalence / comonoids-in-Cont is the precise form) — the exact overclaim
  the foreign-model reviewers caught.
- Connecting the backwards position maps to "this code cannot fabricate data"
  as the embryo of the safety story.
- That detection-vs-verdict (the majority gate outvoting its own honesty
  skeptic) is an AGGREGATION failure, not a detection failure — and why a
  lens-veto fixes it.

## opener
Hello Nick. I am your Primer. I thought we might walk the road your own
machine travelled this week. It starts with a question so simple it sounds
like a riddle: what do a list, a tree, and a spreadsheet have in common?
Shall we begin there, or is there a piece you're already curious about?

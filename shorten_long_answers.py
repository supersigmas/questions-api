#!/usr/bin/env python3
"""
One-off cleanup: enforce length limits on the English baseline
(translations/questions_en.json).

Rules
  - question text      <= 200 chars
  - every entry in `answers` and `wrong_answers` < 30 chars
  - still >= 1 answer and >= 3 wrong answers (QUESTIONS_AUTHORING.md)

How
  1. REWRITE_Q: questions whose answer is inherently long (acronym expansions,
     country lists) are rewritten to ask for a single short part. Ids are kept
     so translations still join.
  2. SHORTEN: every other long string is mapped to a short rewrite, or to None
     to drop it (only where a short accepted variant already exists).
  3. DELETE: questions that cannot be fixed are removed.

Usage:
    python shorten_long_answers.py            # dry run, prints violations
    python shorten_long_answers.py --write
"""
import json
import sys

PATH = "translations/questions_en.json"
MAX_Q = 200
MAX_A = 30  # strictly less than

# id -> replacement fields
REWRITE_Q = {
    # TARDIS
    "94e22ee6": dict(question="In the show Doctor Who, what does the T in TARDIS stand for?",
                     answers=["time"], wrong_answers=["travel", "transport", "temporal"]),
    "814c4be8": dict(question="In the show Doctor Who, what does the D in T.A.R.D.I.S stand for?",
                     answers=["dimension", "dimensions"], wrong_answers=["device", "destination", "drive"]),
    # MIDI
    "286f5af4": dict(question="In computers, what does the M in MIDI stand for?",
                     answers=["musical", "music"], wrong_answers=["modular", "media", "mechanical"]),
    # LASER
    "60bb977e": dict(question="In the word LASER, what does the L stand for?",
                     answers=["light"], wrong_answers=["laser", "lens", "linear"]),
    "636c7673": dict(question="In the word LASER, what does the R stand for?",
                     answers=["radiation"], wrong_answers=["radio", "rays", "reflection"]),
    # PIIGS
    "b36bacd3": dict(question="In the economic nickname PIIGS, which country does the P stand for?",
                     answers=["portugal"], wrong_answers=["poland", "panama", "peru"]),
    "5a928f49": dict(question="In the economic nickname PIIGS, which country does the G stand for?",
                     answers=["greece"], wrong_answers=["germany", "georgia", "greenland"]),
    "5b5954ef": dict(question="In the economic nickname PIIGS, which country does the S stand for?",
                     answers=["spain"], wrong_answers=["sweden", "serbia", "slovakia"]),
    "c6f59d59": dict(question="The economic nickname PIIGS has two I's. Name one of the countries they stand for.",
                     answers=["ireland", "italy"], wrong_answers=["iceland", "india", "israel"]),
    # PEMDAS
    "54e97354": dict(question="In the math order of operations PEMDAS, what does the P stand for?",
                     answers=["parentheses", "parenthesis", "brackets"], wrong_answers=["percent", "powers", "plus"]),
    "e304f234": dict(question="In the math order of operations PEMDAS, what does the E stand for?",
                     answers=["exponents", "exponent", "powers"], wrong_answers=["equals", "equations", "estimates"]),
    "764a0045": dict(question="In the math order of operations PEMDAS, what does the M stand for?",
                     answers=["multiplication", "multiply"], wrong_answers=["minus", "median", "measurement"]),
    "3393ebe6": dict(question="The phrase 'Please Excuse My Dear Aunt Sally' (PEMDAS) helps you remember what in math?",
                     answers=["order of operations", "the order of operations", "operation order"],
                     wrong_answers=["multiplication table", "long division", "fractions"]),
    "7e8ea43b": dict(question="In the math order of operations PEMDAS, what does the D stand for?",
                     answers=["division", "divide"], wrong_answers=["decimals", "digits", "difference"]),
    "3366784f": dict(question="In the math order of operations PEMDAS, what does the A stand for?",
                     answers=["addition", "add"], wrong_answers=["average", "area", "angles"]),
    "8aa56e5d": dict(question="In the math order of operations PEMDAS, what does the S stand for?",
                     answers=["subtraction", "subtract"], wrong_answers=["squares", "sum", "square roots"]),
    "54eef35f": dict(question="In math, which comes first in the order of operations: parentheses or addition?",
                     answers=["parentheses", "parenthesis", "brackets"],
                     wrong_answers=["addition", "they are equal", "whichever is first"]),
}

DELETE = set()

SHORTEN = {
    "751,665,014,151 meters per second": "751,665,014 m/s",
    "abandoned buildings and dead malls": "dead malls",
    "about 300,000 kilometers per second": "about 300,000 km/s",
    "accidentally sending a portal to the moon": "a portal to the moon",
    "add, multiply, divide, subtract, add, parentheses": None,
    "addition, multiplication, division, subtraction, addition, parentheses": None,
    "addition, multiplication, division, subtraction, parentheses": None,
    "advanced dungeons & dragons 2nd edition": "ad&d 2nd edition",
    "aetherochemical research facility": "aetherochemical facility",
    "after episode 3 and before episode 4": None,
    "all is fair in love and brostep": "all is fair in brostep",
    "animal crossing: population growing": "population growing",
    "athena turned him into a woman": "athena made him a woman",
    "athena turned him into a woman and then back into a man": "athena made him a woman",
    "batman v superman: black of knight": "black knight",
    "batman v superman: dawn of justice": None,
    "batman v superman: superapocalypse": "superapocalypse",
    "became a woman and then a man again": "became a woman",
    "birch and swinnerton-dyer conjecture": "birch-swinnerton-dyer",
    "birch and swinnerton-dyer guess": "birch-swinnerton-dyer",
    "birch-swinnerton-dyer conjecture": "birch-swinnerton-dyer",
    "blinded by hera after agreeing with zeus": "blinded by hera",
    "bulbasaur, charmander, and squirtle": "bulbasaur charmander squirtle",
    "bulbasaur, charmander, squirtle": "bulbasaur charmander squirtle",
    "charlie and the chocolate factory": "charlie and the chocolate",
    "chikorita and cyndaquil and totodile": None,
    "chikorita, cyndaquil, and totodile": "chikorita cyndaquil totodile",
    "chikorita, cyndaquil, totodile": "chikorita cyndaquil totodile",
    "crafting table and cobblestone": "crafting table and stone",
    "dungeons & dragons 2nd edition": "d&d 2nd edition",
    "dungeons & dragons 3.5 edition": "dungeons & dragons 3.5",
    "electronic numerical integrator and computer": None,
    "empty buildings and closed malls": "abandoned buildings",
    "fancy fronts with a triangle top": "triangle-topped fronts",
    "filthy acts done for a reasonable price": "filthy acts, fair price",
    "forgotten places and empty malls": "abandoned places",
    "giving up the king for a queen": "trading the king for a queen",
    "grand theft auto 5 and grand theft auto san andreas": None,
    "grand theft auto 5 and san andreas": None,
    "green bay packers and pittsburgh steelers": "packers and steelers",
    "ground proximity warning system": "gpws",
    "hazardous environment combat unit": None,
    "he revealed oedipus married his mom": "oedipus married his mom",
    "he said oedipus married his own mom": "he married his own mom",
    "he told oedipus he married his mother": "he married his mother",
    "hera blinded him after he agreed with zeus": "hera blinded him",
    "here comes santa claus (right down santa claus lane)": None,
    "i don't wanna go on with you like that": "i don't wanna go on with you",
    "i guess that's why they call it the blues": "i guess that's why",
    "i would hate being your driver": "i would hate your driver",
    "life antimatter by standing entry of range": None,
    "light amp by stimulated emission": None,
    "light amp by stimulated emission of radiation": None,
    "light amplification by stimulated emission": None,
    "light amplification by stimulated emission of radiation": None,
    "light amplifier by standby energy of radio": None,
    "light analysis by stereo ecorazer": None,
    "modular interface of digital instruments": None,
    "moon passes in front of the sun": "moon covers the sun",
    "moving the king on the 2nd move": "moving the king early",
    "moving the king on the second move": "moving the king early",
    "multiplayer online battle arena": "battle arena",
    "multiplayer online battle arenas": None,
    "musical instrument data interface": None,
    "musical instrument digital inter": None,
    "musical instrument digital interface": None,
    "musical interface of digital instruments": None,
    "new york giants and new england patriots": None,
    "no pads, no helmets...just balls": "no pads, no helmets",
    "nosferatu: a symphony of horror": None,
    "obstacle collision avoidance system": "obstacle avoidance system",
    "parentheses exponents multiplication division addition subtraction": None,
    "parentheses, exponents, add, subtract, multiply, divide": None,
    "parentheses, exponents, addition, subtraction, multiplication, division": None,
    "parentheses, exponents, multiplication, division, addition, subtraction": None,
    "parentheses, exponents, multiply, divide, add, subtract": None,
    "philadelphia eagles and new england patriots": "eagles and patriots",
    "please excuse my dear aunt sally": None,
    "poland, iceland, italy, greece, serbia": None,
    "poland, iceland, italy, greenland, spain": None,
    "portugal ireland italy greece spain": None,
    "portugal, iceland, ireland, greece, serbia": None,
    "portugal, ireland, italy, greece and spain": None,
    "portugal, ireland, italy, greece, espana": None,
    "portugal, ireland, italy, greece, spain": None,
    "rage against the machine album": None,
    "rage against the machine debut": None,
    "rudolph the red nosed reindeer": "rudolph",
    "rudolph the red-nosed reindeer": "rudolph",
    "sacrificing the king for a queen": "trading the king for a queen",
    "sailed with the argonauts to find the golden fleece": None,
    "scary monsters and nice sprites": "scary monsters",
    "seattle seahawks and denver broncos": "seahawks and broncos",
    "snow white and the seven dwarfs": None,
    "team fortress 2 brotherhood of arms": None,
    "team fortress 2 desert mercenaries": "tf2 desert mercenaries",
    "team fortress 2 operation gear grinder": "tf2 operation gear grinder",
    "team fortress 2 return to classic": "tf2 return to classic",
    "team fortress 2: brotherhood of arms": None,
    "team fortress 2: desert mercenaries": "tf2: desert mercenaries",
    "team fortress 2: operation gear grinder": "tf2: operation gear grinder",
    "team fortress 2: return to classic": "tf2: return to classic",
    "team fortress brotherhood of arms": None,
    "terrain awareness and warning system": "terrain warning system",
    "the artist formerly known as prince": None,
    "the order in which the operations are written": None,
    "the order they appear in the problem": None,
    "the treasure of the sierra madre": "the treasure of sierra madre",
    "there are no skeleton characters": "there is no skeleton",
    "time and relative dimension in space": None,
    "time and relative dimensions in space": None,
    "time and relative dimensions in style": None,
    "time and resting dimensions in space": None,
    "told oedipus he married his mom": "warned oedipus",
    "told oedipus he married his mother": "warned oedipus",
    "traffic alert and collision avoidance system": None,
    "traffic collision avoidance system": None,
    "turned into a woman and back into a man": "turned into a woman",
    "turned into a woman and then back into a man": "turned into a woman",
    "where the wild things are book": None,
}


def fix_list(items):
    out = []
    for s in items:
        if len(s) >= MAX_A:
            if s not in SHORTEN:
                raise SystemExit(f"no SHORTEN entry for {s!r}")
            s = SHORTEN[s]
            if s is None:
                continue
        if s not in out:
            out.append(s)
    return out


def main():
    write = "--write" in sys.argv
    with open(PATH, encoding="utf-8") as f:
        doc = json.load(f)
    data = doc["data"]

    kept, bad = [], []
    for q in data:
        short = q["id"][:8]
        if short in DELETE:
            continue
        if short in REWRITE_Q:
            q.update(REWRITE_Q[short])
        else:
            q["answers"] = fix_list(q["answers"])
            q["wrong_answers"] = fix_list(q["wrong_answers"])
        kept.append(q)
        problems = []
        if len(q["question"]) > MAX_Q:
            problems.append("question too long")
        if any(len(s) >= MAX_A for s in q["answers"] + q["wrong_answers"]):
            problems.append("long answer")
        if not q["answers"]:
            problems.append("no answers")
        if len(q["wrong_answers"]) < 3:
            problems.append(f"{len(q['wrong_answers'])} wrong")
        if problems:
            bad.append((q["id"][:8], problems, q["question"], q["answers"], q["wrong_answers"]))

    for b in bad:
        print(*b, sep=" | ")
    print(f"{len(data)} -> {len(kept)} questions, {len(bad)} still failing")
    if write:
        doc["data"] = kept
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print("written")


if __name__ == "__main__":
    main()

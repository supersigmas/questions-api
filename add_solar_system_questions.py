#!/usr/bin/env python3
"""
Batch add: 40 new questions about the solar system, across the 6 active
languages (en, de, es, fr, lt, ru). Follows QUESTIONS_AUTHORING.md.

  - id = md5(english question text)  (join key across all languages)
  - answers AND wrong_answers lowercase (current standard - both fields)
  - category = "science"; difficulty easy (700) / normal (800)
  - semantic dedup vs embeddings.json at DEDUP_THRESHOLD (default 0.92),
    including within this batch (new embeddings are added as we go)
  - idempotent: ids already present are skipped; caps additions at TARGET_NEW

The corpus already contains astronomy questions, so a large buffer follows the
core set. Additions stop once TARGET_NEW is reached.

Usage:
    python add_solar_system_questions.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import tempfile
import time

LANGS = ["en", "de", "es", "fr", "lt", "ru"]
CATEGORY = "science"
QFILE = "translations/questions_{}.json"
EMBEDDINGS_FILE = "embeddings.json"
THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.92"))
TARGET_NEW = 40


def _id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _atomic_write_json(data, path):
    target = os.path.realpath(path)
    target_dir = os.path.dirname(target) or "."
    with tempfile.NamedTemporaryFile("w", dir=target_dir, suffix=".tmp",
                                     delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    for attempt in range(10):
        try:
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


# Each entry: difficulty, points, and per-language {q, a (answers), w (wrong)}.
# All answer strings (a AND w) are lowercase per QUESTIONS_AUTHORING.md.
QUESTIONS = [
    # ---------------- EASY (700 pts) ----------------
    {"difficulty": "easy", "points": 700,
     "en": {"q": "How many planets are there in our solar system?", "a": ["8", "eight"], "w": ["9", "7", "10", "12"]},
     "de": {"q": "Wie viele Planeten gibt es in unserem Sonnensystem?", "a": ["8", "acht"], "w": ["9", "7", "10", "12"]},
     "es": {"q": "¿Cuántos planetas hay en nuestro sistema solar?", "a": ["8", "ocho"], "w": ["9", "7", "10", "12"]},
     "fr": {"q": "Combien de planètes y a-t-il dans notre système solaire ?", "a": ["8", "huit"], "w": ["9", "7", "10", "12"]},
     "lt": {"q": "Kiek planetų yra mūsų Saulės sistemoje?", "a": ["8", "aštuonios"], "w": ["9", "7", "10", "12"]},
     "ru": {"q": "Сколько планет в нашей Солнечной системе?", "a": ["8", "восемь"], "w": ["9", "7", "10", "12"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet is closest to the Sun?", "a": ["mercury"], "w": ["venus", "earth", "mars", "jupiter"]},
     "de": {"q": "Welcher Planet ist der Sonne am nächsten?", "a": ["merkur"], "w": ["venus", "erde", "mars", "jupiter"]},
     "es": {"q": "¿Qué planeta está más cerca del Sol?", "a": ["mercurio"], "w": ["venus", "tierra", "marte", "júpiter"]},
     "fr": {"q": "Quelle planète est la plus proche du Soleil ?", "a": ["mercure"], "w": ["vénus", "terre", "mars", "jupiter"]},
     "lt": {"q": "Kuri planeta yra arčiausiai Saulės?", "a": ["merkurijus"], "w": ["venera", "žemė", "marsas", "jupiteris"]},
     "ru": {"q": "Какая планета ближе всего к Солнцу?", "a": ["меркурий"], "w": ["венера", "земля", "марс", "юпитер"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet is known as the Red Planet?", "a": ["mars"], "w": ["venus", "jupiter", "mercury", "saturn"]},
     "de": {"q": "Welcher Planet ist als der Rote Planet bekannt?", "a": ["mars"], "w": ["venus", "jupiter", "merkur", "saturn"]},
     "es": {"q": "¿Qué planeta es conocido como el Planeta Rojo?", "a": ["marte"], "w": ["venus", "júpiter", "mercurio", "saturno"]},
     "fr": {"q": "Quelle planète est connue sous le nom de planète rouge ?", "a": ["mars"], "w": ["vénus", "jupiter", "mercure", "saturne"]},
     "lt": {"q": "Kuri planeta žinoma kaip Raudonoji planeta?", "a": ["marsas"], "w": ["venera", "jupiteris", "merkurijus", "saturnas"]},
     "ru": {"q": "Какая планета известна как Красная планета?", "a": ["марс"], "w": ["венера", "юпитер", "меркурий", "сатурн"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which is the largest planet in our solar system?", "a": ["jupiter"], "w": ["saturn", "neptune", "earth", "uranus"]},
     "de": {"q": "Welches ist der größte Planet in unserem Sonnensystem?", "a": ["jupiter"], "w": ["saturn", "neptun", "erde", "uranus"]},
     "es": {"q": "¿Cuál es el planeta más grande de nuestro sistema solar?", "a": ["júpiter"], "w": ["saturno", "neptuno", "tierra", "urano"]},
     "fr": {"q": "Quelle est la plus grande planète de notre système solaire ?", "a": ["jupiter"], "w": ["saturne", "neptune", "terre", "uranus"]},
     "lt": {"q": "Kuri planeta yra didžiausia mūsų Saulės sistemoje?", "a": ["jupiteris"], "w": ["saturnas", "neptūnas", "žemė", "uranas"]},
     "ru": {"q": "Какая планета самая большая в нашей Солнечной системе?", "a": ["юпитер"], "w": ["сатурн", "нептун", "земля", "уран"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet is famous for its bright rings?", "a": ["saturn"], "w": ["jupiter", "mars", "venus", "mercury"]},
     "de": {"q": "Welcher Planet ist für seine hellen Ringe berühmt?", "a": ["saturn"], "w": ["jupiter", "mars", "venus", "merkur"]},
     "es": {"q": "¿Qué planeta es famoso por sus brillantes anillos?", "a": ["saturno"], "w": ["júpiter", "marte", "venus", "mercurio"]},
     "fr": {"q": "Quelle planète est célèbre pour ses anneaux brillants ?", "a": ["saturne"], "w": ["jupiter", "mars", "vénus", "mercure"]},
     "lt": {"q": "Kuri planeta garsėja savo ryškiais žiedais?", "a": ["saturnas"], "w": ["jupiteris", "marsas", "venera", "merkurijus"]},
     "ru": {"q": "Какая планета знаменита своими яркими кольцами?", "a": ["сатурн"], "w": ["юпитер", "марс", "венера", "меркурий"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of Earth's only natural satellite?", "a": ["the moon", "moon", "luna"], "w": ["phobos", "titan", "europa", "io"]},
     "de": {"q": "Wie heißt der einzige natürliche Satellit der Erde?", "a": ["der mond", "mond", "luna"], "w": ["phobos", "titan", "europa", "io"]},
     "es": {"q": "¿Cómo se llama el único satélite natural de la Tierra?", "a": ["la luna", "luna"], "w": ["fobos", "titán", "europa", "ío"]},
     "fr": {"q": "Comment s'appelle le seul satellite naturel de la Terre ?", "a": ["la lune", "lune"], "w": ["phobos", "titan", "europe", "io"]},
     "lt": {"q": "Koks yra vienintelio natūralaus Žemės palydovo pavadinimas?", "a": ["mėnulis"], "w": ["fobas", "titanas", "europa", "ijo"]},
     "ru": {"q": "Как называется единственный естественный спутник Земли?", "a": ["луна"], "w": ["фобос", "титан", "европа", "ио"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet do we live on?", "a": ["earth"], "w": ["mars", "venus", "jupiter", "saturn"]},
     "de": {"q": "Auf welchem Planeten leben wir?", "a": ["erde", "die erde"], "w": ["mars", "venus", "jupiter", "saturn"]},
     "es": {"q": "¿En qué planeta vivimos?", "a": ["tierra", "la tierra"], "w": ["marte", "venus", "júpiter", "saturno"]},
     "fr": {"q": "Sur quelle planète vivons-nous ?", "a": ["terre", "la terre"], "w": ["mars", "vénus", "jupiter", "saturne"]},
     "lt": {"q": "Kurioje planetoje mes gyvename?", "a": ["žemė", "žemėje"], "w": ["marse", "veneroje", "jupiteryje", "saturne"]},
     "ru": {"q": "На какой планете мы живём?", "a": ["земля", "земле"], "w": ["марс", "венера", "юпитер", "сатурн"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is at the centre of our solar system?", "a": ["the sun", "sun"], "w": ["the earth", "the moon", "jupiter", "a black hole"]},
     "de": {"q": "Was befindet sich im Zentrum unseres Sonnensystems?", "a": ["die sonne", "sonne"], "w": ["die erde", "der mond", "jupiter", "ein schwarzes loch"]},
     "es": {"q": "¿Qué hay en el centro de nuestro sistema solar?", "a": ["el sol", "sol"], "w": ["la tierra", "la luna", "júpiter", "un agujero negro"]},
     "fr": {"q": "Qu'y a-t-il au centre de notre système solaire ?", "a": ["le soleil", "soleil"], "w": ["la terre", "la lune", "jupiter", "un trou noir"]},
     "lt": {"q": "Kas yra mūsų Saulės sistemos centre?", "a": ["saulė"], "w": ["žemė", "mėnulis", "jupiteris", "juodoji skylė"]},
     "ru": {"q": "Что находится в центре нашей Солнечной системы?", "a": ["солнце"], "w": ["земля", "луна", "юпитер", "чёрная дыра"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet was reclassified as a dwarf planet in 2006?", "a": ["pluto"], "w": ["neptune", "ceres", "mercury", "eris"]},
     "de": {"q": "Welcher Planet wurde 2006 zum Zwergplaneten herabgestuft?", "a": ["pluto"], "w": ["neptun", "ceres", "merkur", "eris"]},
     "es": {"q": "¿Qué planeta fue reclasificado como planeta enano en 2006?", "a": ["plutón"], "w": ["neptuno", "ceres", "mercurio", "eris"]},
     "fr": {"q": "Quelle planète a été reclassée comme planète naine en 2006 ?", "a": ["pluton"], "w": ["neptune", "cérès", "mercure", "éris"]},
     "lt": {"q": "Kuri planeta 2006 metais buvo perklasifikuota į nykštukinę planetą?", "a": ["plutonas"], "w": ["neptūnas", "cerera", "merkurijus", "eridė"]},
     "ru": {"q": "Какая планета была переклассифицирована в карликовую планету в 2006 году?", "a": ["плутон"], "w": ["нептун", "церера", "меркурий", "эрида"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet is the farthest from the Sun?", "a": ["neptune"], "w": ["uranus", "pluto", "saturn", "jupiter"]},
     "de": {"q": "Welcher Planet ist am weitesten von der Sonne entfernt?", "a": ["neptun"], "w": ["uranus", "pluto", "saturn", "jupiter"]},
     "es": {"q": "¿Qué planeta está más lejos del Sol?", "a": ["neptuno"], "w": ["urano", "plutón", "saturno", "júpiter"]},
     "fr": {"q": "Quelle planète est la plus éloignée du Soleil ?", "a": ["neptune"], "w": ["uranus", "pluton", "saturne", "jupiter"]},
     "lt": {"q": "Kuri planeta yra toliausiai nuo Saulės?", "a": ["neptūnas"], "w": ["uranas", "plutonas", "saturnas", "jupiteris"]},
     "ru": {"q": "Какая планета находится дальше всего от Солнца?", "a": ["нептун"], "w": ["уран", "плутон", "сатурн", "юпитер"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do we call a rock from space that burns up in Earth's atmosphere?", "a": ["meteor", "a meteor", "shooting star"], "w": ["comet", "satellite", "planet", "star"]},
     "de": {"q": "Wie nennt man einen Gesteinsbrocken aus dem All, der in der Erdatmosphäre verglüht?", "a": ["meteor", "sternschnuppe"], "w": ["komet", "satellit", "planet", "stern"]},
     "es": {"q": "¿Cómo llamamos a una roca del espacio que se quema en la atmósfera terrestre?", "a": ["meteoro", "estrella fugaz"], "w": ["cometa", "satélite", "planeta", "estrella"]},
     "fr": {"q": "Comment appelle-t-on une roche venue de l'espace qui se consume dans l'atmosphère terrestre ?", "a": ["météore", "étoile filante"], "w": ["comète", "satellite", "planète", "étoile"]},
     "lt": {"q": "Kaip vadiname iš kosmoso atskriejusią uolieną, kuri sudega Žemės atmosferoje?", "a": ["meteoras", "krintanti žvaigždė"], "w": ["kometa", "palydovas", "planeta", "žvaigždė"]},
     "ru": {"q": "Как называется космический камень, сгорающий в атмосфере Земли?", "a": ["метеор", "падающая звезда"], "w": ["комета", "спутник", "планета", "звезда"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a space object with a long glowing tail called?", "a": ["comet", "a comet"], "w": ["asteroid", "planet", "moon", "galaxy"]},
     "de": {"q": "Wie nennt man ein Weltraumobjekt mit einem langen leuchtenden Schweif?", "a": ["komet", "ein komet"], "w": ["asteroid", "planet", "mond", "galaxie"]},
     "es": {"q": "¿Cómo se llama un objeto espacial con una larga cola brillante?", "a": ["cometa", "un cometa"], "w": ["asteroide", "planeta", "luna", "galaxia"]},
     "fr": {"q": "Comment appelle-t-on un objet spatial avec une longue queue brillante ?", "a": ["comète", "une comète"], "w": ["astéroïde", "planète", "lune", "galaxie"]},
     "lt": {"q": "Kaip vadinamas kosminis objektas su ilga šviečiančia uodega?", "a": ["kometa"], "w": ["asteroidas", "planeta", "mėnulis", "galaktika"]},
     "ru": {"q": "Как называется космический объект с длинным светящимся хвостом?", "a": ["комета"], "w": ["астероид", "планета", "луна", "галактика"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What galaxy is our solar system part of?", "a": ["the milky way", "milky way"], "w": ["andromeda", "triangulum", "sombrero", "whirlpool"]},
     "de": {"q": "Zu welcher Galaxie gehört unser Sonnensystem?", "a": ["die milchstraße", "milchstraße"], "w": ["andromeda", "dreiecksnebel", "sombrero", "strudelgalaxie"]},
     "es": {"q": "¿De qué galaxia forma parte nuestro sistema solar?", "a": ["la vía láctea", "vía láctea"], "w": ["andrómeda", "triángulo", "sombrero", "remolino"]},
     "fr": {"q": "De quelle galaxie notre système solaire fait-il partie ?", "a": ["la voie lactée", "voie lactée"], "w": ["andromède", "triangle", "sombrero", "tourbillon"]},
     "lt": {"q": "Kuriai galaktikai priklauso mūsų Saulės sistema?", "a": ["paukščių takas"], "w": ["andromeda", "trikampis", "sombrero", "sūkurys"]},
     "ru": {"q": "Частью какой галактики является наша Солнечная система?", "a": ["млечный путь"], "w": ["андромеда", "треугольник", "сомбреро", "водоворот"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "How many moons does Earth have?", "a": ["1", "one"], "w": ["2", "0", "3", "4"]},
     "de": {"q": "Wie viele Monde hat die Erde?", "a": ["1", "einen", "eins"], "w": ["2", "0", "3", "4"]},
     "es": {"q": "¿Cuántas lunas tiene la Tierra?", "a": ["1", "una"], "w": ["2", "0", "3", "4"]},
     "fr": {"q": "Combien de lunes la Terre a-t-elle ?", "a": ["1", "une"], "w": ["2", "0", "3", "4"]},
     "lt": {"q": "Kiek mėnulių turi Žemė?", "a": ["1", "vieną"], "w": ["2", "0", "3", "4"]},
     "ru": {"q": "Сколько лун у Земли?", "a": ["1", "одна"], "w": ["2", "0", "3", "4"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of the force that keeps planets orbiting the Sun?", "a": ["gravity"], "w": ["magnetism", "friction", "inertia", "pressure"]},
     "de": {"q": "Wie heißt die Kraft, die die Planeten auf ihrer Umlaufbahn um die Sonne hält?", "a": ["schwerkraft", "gravitation"], "w": ["magnetismus", "reibung", "trägheit", "druck"]},
     "es": {"q": "¿Cómo se llama la fuerza que mantiene a los planetas orbitando el Sol?", "a": ["gravedad", "la gravedad"], "w": ["magnetismo", "fricción", "inercia", "presión"]},
     "fr": {"q": "Comment s'appelle la force qui maintient les planètes en orbite autour du Soleil ?", "a": ["gravité", "la gravité"], "w": ["magnétisme", "friction", "inertie", "pression"]},
     "lt": {"q": "Kaip vadinama jėga, laikanti planetas skriejančias aplink Saulę?", "a": ["gravitacija", "trauka"], "w": ["magnetizmas", "trintis", "inercija", "slėgis"]},
     "ru": {"q": "Как называется сила, удерживающая планеты на орбите вокруг Солнца?", "a": ["гравитация", "притяжение"], "w": ["магнетизм", "трение", "инерция", "давление"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Who was the first human to walk on the Moon?", "a": ["neil armstrong", "armstrong"], "w": ["buzz aldrin", "yuri gagarin", "michael collins", "john glenn"]},
     "de": {"q": "Wer war der erste Mensch, der auf dem Mond ging?", "a": ["neil armstrong", "armstrong"], "w": ["buzz aldrin", "juri gagarin", "michael collins", "john glenn"]},
     "es": {"q": "¿Quién fue el primer humano en caminar sobre la Luna?", "a": ["neil armstrong", "armstrong"], "w": ["buzz aldrin", "yuri gagarin", "michael collins", "john glenn"]},
     "fr": {"q": "Qui a été le premier homme à marcher sur la Lune ?", "a": ["neil armstrong", "armstrong"], "w": ["buzz aldrin", "youri gagarine", "michael collins", "john glenn"]},
     "lt": {"q": "Kas buvo pirmasis žmogus, žengęs į Mėnulį?", "a": ["neilas armstrongas", "armstrongas"], "w": ["buzas oldrinas", "jurijus gagarinas", "maiklas kolinsas", "džonas glenas"]},
     "ru": {"q": "Кто был первым человеком, ступившим на Луну?", "a": ["нил армстронг", "армстронг"], "w": ["базз олдрин", "юрий гагарин", "майкл коллинз", "джон гленн"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do we call a natural object that orbits a planet?", "a": ["moon", "a moon", "satellite"], "w": ["star", "comet", "asteroid", "galaxy"]},
     "de": {"q": "Wie nennt man ein natürliches Objekt, das einen Planeten umkreist?", "a": ["mond", "satellit", "trabant"], "w": ["stern", "komet", "asteroid", "galaxie"]},
     "es": {"q": "¿Cómo llamamos a un objeto natural que orbita un planeta?", "a": ["luna", "satélite"], "w": ["estrella", "cometa", "asteroide", "galaxia"]},
     "fr": {"q": "Comment appelle-t-on un objet naturel qui orbite autour d'une planète ?", "a": ["lune", "satellite"], "w": ["étoile", "comète", "astéroïde", "galaxie"]},
     "lt": {"q": "Kaip vadiname natūralų objektą, skriejantį aplink planetą?", "a": ["mėnulis", "palydovas"], "w": ["žvaigždė", "kometa", "asteroidas", "galaktika"]},
     "ru": {"q": "Как называется естественный объект, вращающийся вокруг планеты?", "a": ["луна", "спутник"], "w": ["звезда", "комета", "астероид", "галактика"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What space agency landed the first humans on the Moon?", "a": ["nasa"], "w": ["esa", "roscosmos", "isro", "spacex"]},
     "de": {"q": "Welche Raumfahrtbehörde brachte die ersten Menschen auf den Mond?", "a": ["nasa"], "w": ["esa", "roskosmos", "isro", "spacex"]},
     "es": {"q": "¿Qué agencia espacial llevó a los primeros humanos a la Luna?", "a": ["nasa"], "w": ["esa", "roscosmos", "isro", "spacex"]},
     "fr": {"q": "Quelle agence spatiale a posé les premiers humains sur la Lune ?", "a": ["nasa"], "w": ["esa", "roscosmos", "isro", "spacex"]},
     "lt": {"q": "Kuri kosmoso agentūra nuskraidino pirmuosius žmones į Mėnulį?", "a": ["nasa"], "w": ["esa", "roskosmos", "isro", "spacex"]},
     "ru": {"q": "Какое космическое агентство высадило первых людей на Луну?", "a": ["наса", "nasa"], "w": ["ека", "роскосмос", "isro", "spacex"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the Sun mostly made of?", "a": ["hydrogen", "hydrogen and helium"], "w": ["oxygen", "iron", "rock", "water"]},
     "de": {"q": "Woraus besteht die Sonne hauptsächlich?", "a": ["wasserstoff", "wasserstoff und helium"], "w": ["sauerstoff", "eisen", "gestein", "wasser"]},
     "es": {"q": "¿De qué está hecho principalmente el Sol?", "a": ["hidrógeno", "hidrógeno y helio"], "w": ["oxígeno", "hierro", "roca", "agua"]},
     "fr": {"q": "De quoi le Soleil est-il principalement composé ?", "a": ["hydrogène", "hydrogène et hélium"], "w": ["oxygène", "fer", "roche", "eau"]},
     "lt": {"q": "Iš ko daugiausia sudaryta Saulė?", "a": ["vandenilio", "vandenilio ir helio"], "w": ["deguonies", "geležies", "uolienų", "vandens"]},
     "ru": {"q": "Из чего в основном состоит Солнце?", "a": ["водород", "водород и гелий"], "w": ["кислород", "железо", "камень", "вода"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Roughly how many days does Earth take to orbit the Sun?", "a": ["365", "365 days", "a year"], "w": ["30", "100", "500", "1000"]},
     "de": {"q": "Wie viele Tage braucht die Erde ungefähr für eine Umrundung der Sonne?", "a": ["365", "365 tage", "ein jahr"], "w": ["30", "100", "500", "1000"]},
     "es": {"q": "¿Aproximadamente cuántos días tarda la Tierra en orbitar el Sol?", "a": ["365", "365 días", "un año"], "w": ["30", "100", "500", "1000"]},
     "fr": {"q": "Combien de jours la Terre met-elle environ pour faire le tour du Soleil ?", "a": ["365", "365 jours", "un an"], "w": ["30", "100", "500", "1000"]},
     "lt": {"q": "Maždaug per kiek dienų Žemė apskrieja Saulę?", "a": ["365", "365 dienas", "metus"], "w": ["30", "100", "500", "1000"]},
     "ru": {"q": "Примерно за сколько дней Земля совершает оборот вокруг Солнца?", "a": ["365", "365 дней", "год"], "w": ["30", "100", "500", "1000"]}},

    # ---------------- NORMAL (800 pts) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet is tilted on its side and rotates almost lying down?", "a": ["uranus"], "w": ["neptune", "saturn", "venus", "mars"]},
     "de": {"q": "Welcher Planet ist zur Seite geneigt und rotiert fast liegend?", "a": ["uranus"], "w": ["neptun", "saturn", "venus", "mars"]},
     "es": {"q": "¿Qué planeta está inclinado de lado y rota casi acostado?", "a": ["urano"], "w": ["neptuno", "saturno", "venus", "marte"]},
     "fr": {"q": "Quelle planète est inclinée sur le côté et tourne presque couchée ?", "a": ["uranus"], "w": ["neptune", "saturne", "vénus", "mars"]},
     "lt": {"q": "Kuri planeta pakrypusi ant šono ir sukasi beveik gulomis?", "a": ["uranas"], "w": ["neptūnas", "saturnas", "venera", "marsas"]},
     "ru": {"q": "Какая планета наклонена набок и вращается почти лёжа?", "a": ["уран"], "w": ["нептун", "сатурн", "венера", "марс"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the giant storm on Jupiter called?", "a": ["the great red spot", "great red spot"], "w": ["the great dark spot", "the eye of jupiter", "the red storm", "the big swirl"]},
     "de": {"q": "Wie heißt der riesige Sturm auf dem Jupiter?", "a": ["der große rote fleck", "großer roter fleck"], "w": ["der große dunkle fleck", "das auge des jupiter", "der rote sturm", "der große wirbel"]},
     "es": {"q": "¿Cómo se llama la gigantesca tormenta de Júpiter?", "a": ["la gran mancha roja", "gran mancha roja"], "w": ["la gran mancha oscura", "el ojo de júpiter", "la tormenta roja", "el gran remolino"]},
     "fr": {"q": "Comment s'appelle la gigantesque tempête de Jupiter ?", "a": ["la grande tache rouge", "grande tache rouge"], "w": ["la grande tache sombre", "l'œil de jupiter", "la tempête rouge", "le grand tourbillon"]},
     "lt": {"q": "Kaip vadinama milžiniška audra Jupiteryje?", "a": ["didžioji raudonoji dėmė"], "w": ["didžioji tamsioji dėmė", "jupiterio akis", "raudonoji audra", "didysis sūkurys"]},
     "ru": {"q": "Как называется гигантский шторм на Юпитере?", "a": ["большое красное пятно"], "w": ["большое тёмное пятно", "глаз юпитера", "красный шторм", "большой вихрь"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet has the shortest day in the solar system?", "a": ["jupiter"], "w": ["mercury", "earth", "venus", "mars"]},
     "de": {"q": "Welcher Planet hat den kürzesten Tag im Sonnensystem?", "a": ["jupiter"], "w": ["merkur", "erde", "venus", "mars"]},
     "es": {"q": "¿Qué planeta tiene el día más corto del sistema solar?", "a": ["júpiter"], "w": ["mercurio", "tierra", "venus", "marte"]},
     "fr": {"q": "Quelle planète a la journée la plus courte du système solaire ?", "a": ["jupiter"], "w": ["mercure", "terre", "vénus", "mars"]},
     "lt": {"q": "Kuri planeta turi trumpiausią parą Saulės sistemoje?", "a": ["jupiteris"], "w": ["merkurijus", "žemė", "venera", "marsas"]},
     "ru": {"q": "У какой планеты самые короткие сутки в Солнечной системе?", "a": ["юпитер"], "w": ["меркурий", "земля", "венера", "марс"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the largest moon of Saturn called?", "a": ["titan"], "w": ["europa", "ganymede", "triton", "rhea"]},
     "de": {"q": "Wie heißt der größte Mond des Saturn?", "a": ["titan"], "w": ["europa", "ganymed", "triton", "rhea"]},
     "es": {"q": "¿Cómo se llama la luna más grande de Saturno?", "a": ["titán"], "w": ["europa", "ganimedes", "tritón", "rea"]},
     "fr": {"q": "Comment s'appelle la plus grande lune de Saturne ?", "a": ["titan"], "w": ["europe", "ganymède", "triton", "rhéa"]},
     "lt": {"q": "Kaip vadinamas didžiausias Saturno palydovas?", "a": ["titanas"], "w": ["europa", "ganimedas", "tritonas", "rėja"]},
     "ru": {"q": "Как называется крупнейший спутник Сатурна?", "a": ["титан"], "w": ["европа", "ганимед", "тритон", "рея"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which moon is the largest in the entire solar system?", "a": ["ganymede"], "w": ["titan", "callisto", "the moon", "io"]},
     "de": {"q": "Welcher Mond ist der größte im gesamten Sonnensystem?", "a": ["ganymed"], "w": ["titan", "kallisto", "der mond", "io"]},
     "es": {"q": "¿Qué luna es la más grande de todo el sistema solar?", "a": ["ganimedes"], "w": ["titán", "calisto", "la luna", "ío"]},
     "fr": {"q": "Quelle lune est la plus grande de tout le système solaire ?", "a": ["ganymède"], "w": ["titan", "callisto", "la lune", "io"]},
     "lt": {"q": "Kuris palydovas yra didžiausias visoje Saulės sistemoje?", "a": ["ganimedas"], "w": ["titanas", "kalisto", "mėnulis", "ijo"]},
     "ru": {"q": "Какой спутник самый большой во всей Солнечной системе?", "a": ["ганимед"], "w": ["титан", "каллисто", "луна", "ио"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Between which two planets does the main asteroid belt lie?", "a": ["mars and jupiter", "between mars and jupiter"], "w": ["earth and mars", "jupiter and saturn", "venus and earth", "saturn and uranus"]},
     "de": {"q": "Zwischen welchen beiden Planeten liegt der Hauptasteroidengürtel?", "a": ["mars und jupiter", "zwischen mars und jupiter"], "w": ["erde und mars", "jupiter und saturn", "venus und erde", "saturn und uranus"]},
     "es": {"q": "¿Entre qué dos planetas se encuentra el cinturón principal de asteroides?", "a": ["marte y júpiter", "entre marte y júpiter"], "w": ["tierra y marte", "júpiter y saturno", "venus y la tierra", "saturno y urano"]},
     "fr": {"q": "Entre quelles deux planètes se situe la ceinture principale d'astéroïdes ?", "a": ["mars et jupiter", "entre mars et jupiter"], "w": ["terre et mars", "jupiter et saturne", "vénus et la terre", "saturne et uranus"]},
     "lt": {"q": "Tarp kurių dviejų planetų yra pagrindinis asteroidų žiedas?", "a": ["marso ir jupiterio", "tarp marso ir jupiterio"], "w": ["žemės ir marso", "jupiterio ir saturno", "veneros ir žemės", "saturno ir urano"]},
     "ru": {"q": "Между какими двумя планетами находится главный пояс астероидов?", "a": ["марсом и юпитером", "между марсом и юпитером"], "w": ["землёй и марсом", "юпитером и сатурном", "венерой и землёй", "сатурном и ураном"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet rotates in the opposite direction to most other planets?", "a": ["venus"], "w": ["mars", "mercury", "jupiter", "neptune"]},
     "de": {"q": "Welcher Planet rotiert in die entgegengesetzte Richtung zu den meisten anderen Planeten?", "a": ["venus"], "w": ["mars", "merkur", "jupiter", "neptun"]},
     "es": {"q": "¿Qué planeta rota en dirección opuesta a la mayoría de los demás planetas?", "a": ["venus"], "w": ["marte", "mercurio", "júpiter", "neptuno"]},
     "fr": {"q": "Quelle planète tourne dans le sens inverse de la plupart des autres planètes ?", "a": ["vénus"], "w": ["mars", "mercure", "jupiter", "neptune"]},
     "lt": {"q": "Kuri planeta sukasi priešinga kryptimi nei dauguma kitų planetų?", "a": ["venera"], "w": ["marsas", "merkurijus", "jupiteris", "neptūnas"]},
     "ru": {"q": "Какая планета вращается в направлении, противоположном большинству других планет?", "a": ["венера"], "w": ["марс", "меркурий", "юпитер", "нептун"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the tallest volcano in the solar system called?", "a": ["olympus mons"], "w": ["mauna kea", "mount everest", "valles marineris", "mons huygens"]},
     "de": {"q": "Wie heißt der höchste Vulkan im Sonnensystem?", "a": ["olympus mons"], "w": ["mauna kea", "mount everest", "valles marineris", "mons huygens"]},
     "es": {"q": "¿Cómo se llama el volcán más alto del sistema solar?", "a": ["monte olimpo", "olympus mons"], "w": ["mauna kea", "monte everest", "valles marineris", "mons huygens"]},
     "fr": {"q": "Comment s'appelle le plus haut volcan du système solaire ?", "a": ["olympus mons", "mont olympe"], "w": ["mauna kea", "mont everest", "valles marineris", "mons huygens"]},
     "lt": {"q": "Kaip vadinamas aukščiausias ugnikalnis Saulės sistemoje?", "a": ["olimpo kalnas", "olympus mons"], "w": ["mauna kea", "everestas", "valles marineris", "mons huygens"]},
     "ru": {"q": "Как называется самый высокий вулкан в Солнечной системе?", "a": ["олимп", "гора олимп"], "w": ["мауна-кеа", "эверест", "долина маринер", "гора гюйгенса"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "On which planet is the giant canyon Valles Marineris found?", "a": ["mars"], "w": ["venus", "mercury", "earth", "titan"]},
     "de": {"q": "Auf welchem Planeten befindet sich der riesige Canyon Valles Marineris?", "a": ["mars"], "w": ["venus", "merkur", "erde", "titan"]},
     "es": {"q": "¿En qué planeta se encuentra el gigantesco cañón Valles Marineris?", "a": ["marte"], "w": ["venus", "mercurio", "tierra", "titán"]},
     "fr": {"q": "Sur quelle planète se trouve le gigantesque canyon Valles Marineris ?", "a": ["mars"], "w": ["vénus", "mercure", "terre", "titan"]},
     "lt": {"q": "Kurioje planetoje yra milžiniškas Valles Marineris kanjonas?", "a": ["marse", "marsas"], "w": ["veneroje", "merkurijuje", "žemėje", "titane"]},
     "ru": {"q": "На какой планете находится гигантский каньон Долина Маринер?", "a": ["марс", "марсе"], "w": ["венера", "меркурий", "земля", "титан"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "How many moons does Mars have?", "a": ["2", "two"], "w": ["1", "0", "4", "12"]},
     "de": {"q": "Wie viele Monde hat der Mars?", "a": ["2", "zwei"], "w": ["1", "0", "4", "12"]},
     "es": {"q": "¿Cuántas lunas tiene Marte?", "a": ["2", "dos"], "w": ["1", "0", "4", "12"]},
     "fr": {"q": "Combien de lunes Mars possède-t-elle ?", "a": ["2", "deux"], "w": ["1", "0", "4", "12"]},
     "lt": {"q": "Kiek palydovų turi Marsas?", "a": ["2", "du"], "w": ["1", "0", "4", "12"]},
     "ru": {"q": "Сколько спутников у Марса?", "a": ["2", "два"], "w": ["1", "0", "4", "12"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What are the two moons of Mars named?", "a": ["phobos and deimos", "phobos, deimos"], "w": ["titan and rhea", "io and europa", "castor and pollux", "romulus and remus"]},
     "de": {"q": "Wie heißen die beiden Monde des Mars?", "a": ["phobos und deimos"], "w": ["titan und rhea", "io und europa", "castor und pollux", "romulus und remus"]},
     "es": {"q": "¿Cómo se llaman las dos lunas de Marte?", "a": ["fobos y deimos"], "w": ["titán y rea", "ío y europa", "cástor y pólux", "rómulo y remo"]},
     "fr": {"q": "Comment s'appellent les deux lunes de Mars ?", "a": ["phobos et déimos"], "w": ["titan et rhéa", "io et europe", "castor et pollux", "romulus et rémus"]},
     "lt": {"q": "Kaip vadinami du Marso palydovai?", "a": ["fobas ir deimas"], "w": ["titanas ir rėja", "ijo ir europa", "kastoras ir poluksas", "romulas ir remas"]},
     "ru": {"q": "Как называются два спутника Марса?", "a": ["фобос и деймос"], "w": ["титан и рея", "ио и европа", "кастор и поллукс", "ромул и рем"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which icy moon of Jupiter is thought to hide an ocean beneath its crust?", "a": ["europa"], "w": ["io", "callisto", "titan", "triton"]},
     "de": {"q": "Von welchem eisigen Jupitermond wird vermutet, dass er unter seiner Kruste einen Ozean verbirgt?", "a": ["europa"], "w": ["io", "kallisto", "titan", "triton"]},
     "es": {"q": "¿Qué luna helada de Júpiter se cree que esconde un océano bajo su corteza?", "a": ["europa"], "w": ["ío", "calisto", "titán", "tritón"]},
     "fr": {"q": "Quelle lune glacée de Jupiter cacherait un océan sous sa croûte ?", "a": ["europe"], "w": ["io", "callisto", "titan", "triton"]},
     "lt": {"q": "Kuris ledinis Jupiterio palydovas, manoma, slepia vandenyną po savo pluta?", "a": ["europa"], "w": ["ijo", "kalisto", "titanas", "tritonas"]},
     "ru": {"q": "Какой ледяной спутник Юпитера, как считается, скрывает океан под своей корой?", "a": ["европа"], "w": ["ио", "каллисто", "титан", "тритон"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet is sometimes called Earth's twin because of its similar size?", "a": ["venus"], "w": ["mars", "mercury", "neptune", "uranus"]},
     "de": {"q": "Welcher Planet wird wegen seiner ähnlichen Größe manchmal Erdzwilling genannt?", "a": ["venus"], "w": ["mars", "merkur", "neptun", "uranus"]},
     "es": {"q": "¿Qué planeta se llama a veces el gemelo de la Tierra por su tamaño similar?", "a": ["venus"], "w": ["marte", "mercurio", "neptuno", "urano"]},
     "fr": {"q": "Quelle planète est parfois appelée la jumelle de la Terre en raison de sa taille similaire ?", "a": ["vénus"], "w": ["mars", "mercure", "neptune", "uranus"]},
     "lt": {"q": "Kuri planeta kartais vadinama Žemės dvyne dėl panašaus dydžio?", "a": ["venera"], "w": ["marsas", "merkurijus", "neptūnas", "uranas"]},
     "ru": {"q": "Какую планету иногда называют близнецом Земли из-за схожего размера?", "a": ["венера"], "w": ["марс", "меркурий", "нептун", "уран"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What are the four planets closest to the Sun collectively called?", "a": ["terrestrial planets", "rocky planets", "inner planets"], "w": ["gas giants", "ice giants", "dwarf planets", "outer planets"]},
     "de": {"q": "Wie werden die vier sonnennächsten Planeten zusammenfassend genannt?", "a": ["terrestrische planeten", "gesteinsplaneten", "innere planeten"], "w": ["gasriesen", "eisriesen", "zwergplaneten", "äußere planeten"]},
     "es": {"q": "¿Cómo se llaman colectivamente los cuatro planetas más cercanos al Sol?", "a": ["planetas terrestres", "planetas rocosos", "planetas interiores"], "w": ["gigantes gaseosos", "gigantes helados", "planetas enanos", "planetas exteriores"]},
     "fr": {"q": "Comment appelle-t-on collectivement les quatre planètes les plus proches du Soleil ?", "a": ["planètes telluriques", "planètes rocheuses", "planètes internes"], "w": ["géantes gazeuses", "géantes de glace", "planètes naines", "planètes externes"]},
     "lt": {"q": "Kaip bendrai vadinamos keturios arčiausiai Saulės esančios planetos?", "a": ["uolinės planetos", "žemiškosios planetos", "vidinės planetos"], "w": ["dujų milžinės", "ledo milžinės", "nykštukinės planetos", "išorinės planetos"]},
     "ru": {"q": "Как в совокупности называют четыре ближайшие к Солнцу планеты?", "a": ["планеты земной группы", "каменистые планеты", "внутренние планеты"], "w": ["газовые гиганты", "ледяные гиганты", "карликовые планеты", "внешние планеты"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Jupiter and Saturn are classified as what type of planet?", "a": ["gas giants", "gas giant"], "w": ["rocky planets", "dwarf planets", "ice planets", "terrestrial planets"]},
     "de": {"q": "Jupiter und Saturn werden als welcher Planetentyp klassifiziert?", "a": ["gasriesen", "gasriese"], "w": ["gesteinsplaneten", "zwergplaneten", "eisplaneten", "terrestrische planeten"]},
     "es": {"q": "¿Júpiter y Saturno se clasifican como qué tipo de planeta?", "a": ["gigantes gaseosos", "gigante gaseoso"], "w": ["planetas rocosos", "planetas enanos", "planetas helados", "planetas terrestres"]},
     "fr": {"q": "Jupiter et Saturne sont classées comme quel type de planète ?", "a": ["géantes gazeuses", "géante gazeuse"], "w": ["planètes rocheuses", "planètes naines", "planètes de glace", "planètes telluriques"]},
     "lt": {"q": "Jupiteris ir Saturnas priskiriami kokiam planetų tipui?", "a": ["dujų milžinės", "dujų milžinė"], "w": ["uolinės planetos", "nykštukinės planetos", "ledo planetos", "žemiškosios planetos"]},
     "ru": {"q": "Юпитер и Сатурн относятся к какому типу планет?", "a": ["газовые гиганты", "газовый гигант"], "w": ["каменистые планеты", "карликовые планеты", "ледяные планеты", "планеты земной группы"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which spacecraft mission first landed humans on the Moon in 1969?", "a": ["apollo 11", "apollo eleven"], "w": ["apollo 13", "gemini 4", "vostok 1", "soyuz 1"]},
     "de": {"q": "Welche Raumfahrtmission brachte 1969 erstmals Menschen auf den Mond?", "a": ["apollo 11"], "w": ["apollo 13", "gemini 4", "wostok 1", "sojus 1"]},
     "es": {"q": "¿Qué misión espacial llevó por primera vez humanos a la Luna en 1969?", "a": ["apolo 11", "apollo 11"], "w": ["apolo 13", "géminis 4", "vostok 1", "soyuz 1"]},
     "fr": {"q": "Quelle mission spatiale a posé pour la première fois des humains sur la Lune en 1969 ?", "a": ["apollo 11"], "w": ["apollo 13", "gemini 4", "vostok 1", "soyouz 1"]},
     "lt": {"q": "Kuri kosminė misija 1969 metais pirmą kartą nuskraidino žmones į Mėnulį?", "a": ["apollo 11", "apolonas 11"], "w": ["apollo 13", "gemini 4", "vostok 1", "sojuz 1"]},
     "ru": {"q": "Какая космическая миссия впервые высадила людей на Луну в 1969 году?", "a": ["аполлон-11", "аполлон 11"], "w": ["аполлон-13", "джемини-4", "восток-1", "союз-1"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Who was the first human to travel into space?", "a": ["yuri gagarin", "gagarin"], "w": ["neil armstrong", "alan shepard", "john glenn", "valentina tereshkova"]},
     "de": {"q": "Wer war der erste Mensch im Weltraum?", "a": ["juri gagarin", "gagarin"], "w": ["neil armstrong", "alan shepard", "john glenn", "valentina tereschkowa"]},
     "es": {"q": "¿Quién fue el primer humano en viajar al espacio?", "a": ["yuri gagarin", "gagarin"], "w": ["neil armstrong", "alan shepard", "john glenn", "valentina tereshkova"]},
     "fr": {"q": "Qui a été le premier humain à voyager dans l'espace ?", "a": ["youri gagarine", "gagarine"], "w": ["neil armstrong", "alan shepard", "john glenn", "valentina terechkova"]},
     "lt": {"q": "Kas buvo pirmasis žmogus, pakilęs į kosmosą?", "a": ["jurijus gagarinas", "gagarinas"], "w": ["neilas armstrongas", "alanas šepardas", "džonas glenas", "valentina tereškova"]},
     "ru": {"q": "Кто был первым человеком, совершившим полёт в космос?", "a": ["юрий гагарин", "гагарин"], "w": ["нил армстронг", "алан шепард", "джон гленн", "валентина терешкова"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Roughly how long does sunlight take to reach the Earth?", "a": ["8 minutes", "about 8 minutes", "eight minutes"], "w": ["1 second", "1 hour", "1 day", "30 seconds"]},
     "de": {"q": "Wie lange braucht das Sonnenlicht ungefähr bis zur Erde?", "a": ["8 minuten", "etwa 8 minuten", "acht minuten"], "w": ["1 sekunde", "1 stunde", "1 tag", "30 sekunden"]},
     "es": {"q": "¿Aproximadamente cuánto tarda la luz del Sol en llegar a la Tierra?", "a": ["8 minutos", "unos 8 minutos", "ocho minutos"], "w": ["1 segundo", "1 hora", "1 día", "30 segundos"]},
     "fr": {"q": "Combien de temps la lumière du Soleil met-elle environ pour atteindre la Terre ?", "a": ["8 minutes", "environ 8 minutes", "huit minutes"], "w": ["1 seconde", "1 heure", "1 jour", "30 secondes"]},
     "lt": {"q": "Maždaug per kiek laiko Saulės šviesa pasiekia Žemę?", "a": ["8 minutes", "apie 8 minutes", "aštuonias minutes"], "w": ["1 sekundę", "1 valandą", "1 dieną", "30 sekundžių"]},
     "ru": {"q": "Примерно за какое время солнечный свет достигает Земли?", "a": ["8 минут", "около 8 минут", "восемь минут"], "w": ["1 секунду", "1 час", "1 день", "30 секунд"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What happens during a solar eclipse?", "a": ["the moon blocks the sun", "moon passes in front of the sun"], "w": ["the earth blocks the sun", "the sun turns off", "the moon turns red", "the earth stops spinning"]},
     "de": {"q": "Was geschieht während einer Sonnenfinsternis?", "a": ["der mond verdeckt die sonne", "der mond zieht vor die sonne"], "w": ["die erde verdeckt die sonne", "die sonne erlischt", "der mond wird rot", "die erde hört auf sich zu drehen"]},
     "es": {"q": "¿Qué ocurre durante un eclipse solar?", "a": ["la luna bloquea el sol", "la luna pasa delante del sol"], "w": ["la tierra bloquea el sol", "el sol se apaga", "la luna se vuelve roja", "la tierra deja de girar"]},
     "fr": {"q": "Que se passe-t-il pendant une éclipse solaire ?", "a": ["la lune cache le soleil", "la lune passe devant le soleil"], "w": ["la terre cache le soleil", "le soleil s'éteint", "la lune devient rouge", "la terre arrête de tourner"]},
     "lt": {"q": "Kas vyksta per Saulės užtemimą?", "a": ["mėnulis užstoja saulę", "mėnulis praeina prieš saulę"], "w": ["žemė užstoja saulę", "saulė užgęsta", "mėnulis parausta", "žemė nustoja suktis"]},
     "ru": {"q": "Что происходит во время солнечного затмения?", "a": ["луна закрывает солнце", "луна проходит перед солнцем"], "w": ["земля закрывает солнце", "солнце гаснет", "луна краснеет", "земля перестаёт вращаться"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet has the strongest winds in the solar system?", "a": ["neptune"], "w": ["jupiter", "saturn", "uranus", "venus"]},
     "de": {"q": "Welcher Planet hat die stärksten Winde im Sonnensystem?", "a": ["neptun"], "w": ["jupiter", "saturn", "uranus", "venus"]},
     "es": {"q": "¿Qué planeta tiene los vientos más fuertes del sistema solar?", "a": ["neptuno"], "w": ["júpiter", "saturno", "urano", "venus"]},
     "fr": {"q": "Quelle planète a les vents les plus violents du système solaire ?", "a": ["neptune"], "w": ["jupiter", "saturne", "uranus", "vénus"]},
     "lt": {"q": "Kurioje planetoje pučia stipriausi vėjai Saulės sistemoje?", "a": ["neptūne", "neptūnas"], "w": ["jupiteryje", "saturne", "urane", "veneroje"]},
     "ru": {"q": "На какой планете самые сильные ветры в Солнечной системе?", "a": ["нептун", "нептуне"], "w": ["юпитер", "сатурн", "уран", "венера"]}},

    # ---------------- BUFFER candidates (used only if dedup drops some above) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the most volcanically active body in the solar system?", "a": ["io"], "w": ["europa", "titan", "venus", "mars"]},
     "de": {"q": "Welcher Körper im Sonnensystem ist vulkanisch am aktivsten?", "a": ["io"], "w": ["europa", "titan", "venus", "mars"]},
     "es": {"q": "¿Cuál es el cuerpo con mayor actividad volcánica del sistema solar?", "a": ["ío"], "w": ["europa", "titán", "venus", "marte"]},
     "fr": {"q": "Quel est le corps le plus volcaniquement actif du système solaire ?", "a": ["io"], "w": ["europe", "titan", "vénus", "mars"]},
     "lt": {"q": "Kuris Saulės sistemos kūnas yra vulkaniškai aktyviausias?", "a": ["ijo"], "w": ["europa", "titanas", "venera", "marsas"]},
     "ru": {"q": "Какое тело в Солнечной системе наиболее вулканически активно?", "a": ["ио"], "w": ["европа", "титан", "венера", "марс"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the largest object in the asteroid belt?", "a": ["ceres"], "w": ["vesta", "pallas", "eros", "juno"]},
     "de": {"q": "Was ist das größte Objekt im Asteroidengürtel?", "a": ["ceres"], "w": ["vesta", "pallas", "eros", "juno"]},
     "es": {"q": "¿Cuál es el objeto más grande del cinturón de asteroides?", "a": ["ceres"], "w": ["vesta", "palas", "eros", "juno"]},
     "fr": {"q": "Quel est le plus grand objet de la ceinture d'astéroïdes ?", "a": ["cérès"], "w": ["vesta", "pallas", "éros", "junon"]},
     "lt": {"q": "Koks yra didžiausias objektas asteroidų žiede?", "a": ["cerera"], "w": ["vesta", "paladė", "erosas", "junona"]},
     "ru": {"q": "Какой самый крупный объект в поясе астероидов?", "a": ["церера"], "w": ["веста", "паллада", "эрос", "юнона"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet takes the longest time to orbit the Sun?", "a": ["neptune"], "w": ["uranus", "saturn", "jupiter", "mars"]},
     "de": {"q": "Welcher Planet braucht am längsten für eine Umrundung der Sonne?", "a": ["neptun"], "w": ["uranus", "saturn", "jupiter", "mars"]},
     "es": {"q": "¿Qué planeta tarda más tiempo en orbitar el Sol?", "a": ["neptuno"], "w": ["urano", "saturno", "júpiter", "marte"]},
     "fr": {"q": "Quelle planète met le plus de temps à faire le tour du Soleil ?", "a": ["neptune"], "w": ["uranus", "saturne", "jupiter", "mars"]},
     "lt": {"q": "Kuriai planetai reikia daugiausia laiko apskrieti Saulę?", "a": ["neptūnui", "neptūnas"], "w": ["uranui", "saturnui", "jupiteriui", "marsui"]},
     "ru": {"q": "Какой планете требуется больше всего времени на оборот вокруг Солнца?", "a": ["нептун", "нептуну"], "w": ["уран", "сатурн", "юпитер", "марс"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the boundary region of icy bodies beyond Neptune called?", "a": ["kuiper belt", "the kuiper belt"], "w": ["asteroid belt", "oort cloud", "van allen belt", "heliosphere"]},
     "de": {"q": "Wie heißt die Region eisiger Körper jenseits des Neptun?", "a": ["kuipergürtel", "der kuipergürtel"], "w": ["asteroidengürtel", "oortsche wolke", "van-allen-gürtel", "heliosphäre"]},
     "es": {"q": "¿Cómo se llama la región de cuerpos helados más allá de Neptuno?", "a": ["cinturón de kuiper"], "w": ["cinturón de asteroides", "nube de oort", "cinturón de van allen", "heliosfera"]},
     "fr": {"q": "Comment s'appelle la région de corps glacés située au-delà de Neptune ?", "a": ["ceinture de kuiper"], "w": ["ceinture d'astéroïdes", "nuage d'oort", "ceinture de van allen", "héliosphère"]},
     "lt": {"q": "Kaip vadinama ledinių kūnų sritis už Neptūno?", "a": ["kuiperio žiedas", "kuiperio juosta"], "w": ["asteroidų žiedas", "oorto debesis", "van aleno juosta", "heliosfera"]},
     "ru": {"q": "Как называется область ледяных тел за Нептуном?", "a": ["пояс койпера"], "w": ["пояс астероидов", "облако оорта", "пояс ван аллена", "гелиосфера"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet has a day longer than its year?", "a": ["venus"], "w": ["mercury", "mars", "uranus", "neptune"]},
     "de": {"q": "Welcher Planet hat einen Tag, der länger ist als sein Jahr?", "a": ["venus"], "w": ["merkur", "mars", "uranus", "neptun"]},
     "es": {"q": "¿Qué planeta tiene un día más largo que su año?", "a": ["venus"], "w": ["mercurio", "marte", "urano", "neptuno"]},
     "fr": {"q": "Quelle planète a une journée plus longue que son année ?", "a": ["vénus"], "w": ["mercure", "mars", "uranus", "neptune"]},
     "lt": {"q": "Kurios planetos para ilgesnė už jos metus?", "a": ["veneros", "venera"], "w": ["merkurijaus", "marso", "urano", "neptūno"]},
     "ru": {"q": "У какой планеты сутки длиннее её года?", "a": ["венера", "венеры"], "w": ["меркурий", "марс", "уран", "нептун"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What was the first artificial satellite launched into space?", "a": ["sputnik", "sputnik 1"], "w": ["explorer 1", "vostok 1", "apollo 1", "voyager 1"]},
     "de": {"q": "Was war der erste künstliche Satellit im Weltraum?", "a": ["sputnik", "sputnik 1"], "w": ["explorer 1", "wostok 1", "apollo 1", "voyager 1"]},
     "es": {"q": "¿Cuál fue el primer satélite artificial lanzado al espacio?", "a": ["sputnik", "sputnik 1"], "w": ["explorer 1", "vostok 1", "apolo 1", "voyager 1"]},
     "fr": {"q": "Quel a été le premier satellite artificiel lancé dans l'espace ?", "a": ["spoutnik", "spoutnik 1"], "w": ["explorer 1", "vostok 1", "apollo 1", "voyager 1"]},
     "lt": {"q": "Koks buvo pirmasis dirbtinis palydovas, paleistas į kosmosą?", "a": ["sputnik 1", "sputnikas"], "w": ["explorer 1", "vostok 1", "apollo 1", "voyager 1"]},
     "ru": {"q": "Какой был первый искусственный спутник, запущенный в космос?", "a": ["спутник-1", "спутник"], "w": ["эксплорер-1", "восток-1", "аполлон-1", "вояджер-1"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which spacecraft is the most distant human-made object from Earth?", "a": ["voyager 1", "voyager"], "w": ["voyager 2", "pioneer 10", "new horizons", "cassini"]},
     "de": {"q": "Welche Raumsonde ist das am weitesten von der Erde entfernte von Menschen gebaute Objekt?", "a": ["voyager 1", "voyager"], "w": ["voyager 2", "pioneer 10", "new horizons", "cassini"]},
     "es": {"q": "¿Qué nave espacial es el objeto humano más distante de la Tierra?", "a": ["voyager 1", "voyager"], "w": ["voyager 2", "pioneer 10", "new horizons", "cassini"]},
     "fr": {"q": "Quelle sonde spatiale est l'objet humain le plus éloigné de la Terre ?", "a": ["voyager 1", "voyager"], "w": ["voyager 2", "pioneer 10", "new horizons", "cassini"]},
     "lt": {"q": "Kuris erdvėlaivis yra toliausiai nuo Žemės nutolęs žmogaus sukurtas objektas?", "a": ["voyager 1", "voyager"], "w": ["voyager 2", "pioneer 10", "new horizons", "cassini"]},
     "ru": {"q": "Какой космический аппарат является самым удалённым от Земли рукотворным объектом?", "a": ["вояджер-1", "вояджер"], "w": ["вояджер-2", "пионер-10", "новые горизонты", "кассини"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which two planets have no moons at all?", "a": ["mercury and venus", "venus and mercury"], "w": ["mars and earth", "uranus and neptune", "jupiter and saturn", "earth and venus"]},
     "de": {"q": "Welche zwei Planeten haben überhaupt keine Monde?", "a": ["merkur und venus", "venus und merkur"], "w": ["mars und erde", "uranus und neptun", "jupiter und saturn", "erde und venus"]},
     "es": {"q": "¿Qué dos planetas no tienen ninguna luna?", "a": ["mercurio y venus", "venus y mercurio"], "w": ["marte y la tierra", "urano y neptuno", "júpiter y saturno", "la tierra y venus"]},
     "fr": {"q": "Quelles deux planètes n'ont aucune lune ?", "a": ["mercure et vénus", "vénus et mercure"], "w": ["mars et la terre", "uranus et neptune", "jupiter et saturne", "la terre et vénus"]},
     "lt": {"q": "Kurios dvi planetos visai neturi palydovų?", "a": ["merkurijus ir venera", "venera ir merkurijus"], "w": ["marsas ir žemė", "uranas ir neptūnas", "jupiteris ir saturnas", "žemė ir venera"]},
     "ru": {"q": "У каких двух планет вообще нет спутников?", "a": ["меркурий и венера", "венера и меркурий"], "w": ["марс и земля", "уран и нептун", "юпитер и сатурн", "земля и венера"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the hot outer atmosphere of the Sun visible during an eclipse called?", "a": ["corona", "the corona"], "w": ["photosphere", "chromosphere", "core", "sunspot"]},
     "de": {"q": "Wie heißt die heiße äußere Atmosphäre der Sonne, die bei einer Finsternis sichtbar ist?", "a": ["korona", "die korona"], "w": ["photosphäre", "chromosphäre", "kern", "sonnenfleck"]},
     "es": {"q": "¿Cómo se llama la caliente atmósfera exterior del Sol visible durante un eclipse?", "a": ["corona", "la corona"], "w": ["fotosfera", "cromosfera", "núcleo", "mancha solar"]},
     "fr": {"q": "Comment appelle-t-on la chaude atmosphère externe du Soleil visible pendant une éclipse ?", "a": ["couronne", "la couronne"], "w": ["photosphère", "chromosphère", "noyau", "tache solaire"]},
     "lt": {"q": "Kaip vadinama karšta išorinė Saulės atmosfera, matoma per užtemimą?", "a": ["vainikas", "korona"], "w": ["fotosfera", "chromosfera", "branduolys", "saulės dėmė"]},
     "ru": {"q": "Как называется горячая внешняя атмосфера Солнца, видимая во время затмения?", "a": ["корона", "солнечная корона"], "w": ["фотосфера", "хромосфера", "ядро", "солнечное пятно"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What type of star is our Sun classified as?", "a": ["yellow dwarf", "a yellow dwarf", "g-type star"], "w": ["red giant", "white dwarf", "blue supergiant", "neutron star"]},
     "de": {"q": "Als welcher Sterntyp wird unsere Sonne klassifiziert?", "a": ["gelber zwerg", "ein gelber zwerg"], "w": ["roter riese", "weißer zwerg", "blauer überriese", "neutronenstern"]},
     "es": {"q": "¿Qué tipo de estrella es nuestro Sol?", "a": ["enana amarilla", "una enana amarilla"], "w": ["gigante roja", "enana blanca", "supergigante azul", "estrella de neutrones"]},
     "fr": {"q": "De quel type d'étoile notre Soleil est-il classé ?", "a": ["naine jaune", "une naine jaune"], "w": ["géante rouge", "naine blanche", "supergéante bleue", "étoile à neutrons"]},
     "lt": {"q": "Kokiam žvaigždžių tipui priskiriama mūsų Saulė?", "a": ["geltonoji nykštukė"], "w": ["raudonoji milžinė", "baltoji nykštukė", "mėlynoji supermilžinė", "neutroninė žvaigždė"]},
     "ru": {"q": "К какому типу звёзд относится наше Солнце?", "a": ["жёлтый карлик"], "w": ["красный гигант", "белый карлик", "голубой сверхгигант", "нейтронная звезда"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What are the dark cooler patches on the Sun's surface called?", "a": ["sunspots", "sunspot"], "w": ["solar flares", "craters", "shadows", "eclipses"]},
     "de": {"q": "Wie heißen die dunklen, kühleren Flecken auf der Sonnenoberfläche?", "a": ["sonnenflecken", "sonnenfleck"], "w": ["sonneneruptionen", "krater", "schatten", "finsternisse"]},
     "es": {"q": "¿Cómo se llaman las manchas oscuras y más frías de la superficie del Sol?", "a": ["manchas solares", "mancha solar"], "w": ["erupciones solares", "cráteres", "sombras", "eclipses"]},
     "fr": {"q": "Comment appelle-t-on les taches sombres et plus froides à la surface du Soleil ?", "a": ["taches solaires", "tache solaire"], "w": ["éruptions solaires", "cratères", "ombres", "éclipses"]},
     "lt": {"q": "Kaip vadinamos tamsios, vėsesnės dėmės Saulės paviršiuje?", "a": ["saulės dėmės", "saulės dėmė"], "w": ["saulės pliūpsniai", "krateriai", "šešėliai", "užtemimai"]},
     "ru": {"q": "Как называются тёмные более холодные пятна на поверхности Солнца?", "a": ["солнечные пятна", "солнечное пятно"], "w": ["солнечные вспышки", "кратеры", "тени", "затмения"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet did the Curiosity rover explore?", "a": ["mars"], "w": ["venus", "the moon", "mercury", "jupiter"]},
     "de": {"q": "Welchen Planeten erkundete der Rover Curiosity?", "a": ["mars"], "w": ["venus", "den mond", "merkur", "jupiter"]},
     "es": {"q": "¿Qué planeta exploró el rover Curiosity?", "a": ["marte"], "w": ["venus", "la luna", "mercurio", "júpiter"]},
     "fr": {"q": "Quelle planète le rover Curiosity a-t-il explorée ?", "a": ["mars"], "w": ["vénus", "la lune", "mercure", "jupiter"]},
     "lt": {"q": "Kurią planetą tyrinėjo marsaeigis Curiosity?", "a": ["marsą", "marsas"], "w": ["venerą", "mėnulį", "merkurijų", "jupiterį"]},
     "ru": {"q": "Какую планету исследовал марсоход Curiosity?", "a": ["марс"], "w": ["венера", "луна", "меркурий", "юпитер"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the thick atmosphere of Venus mostly made of?", "a": ["carbon dioxide", "co2"], "w": ["oxygen", "nitrogen", "methane", "hydrogen"]},
     "de": {"q": "Woraus besteht die dichte Atmosphäre der Venus hauptsächlich?", "a": ["kohlendioxid", "co2"], "w": ["sauerstoff", "stickstoff", "methan", "wasserstoff"]},
     "es": {"q": "¿De qué está compuesta principalmente la densa atmósfera de Venus?", "a": ["dióxido de carbono", "co2"], "w": ["oxígeno", "nitrógeno", "metano", "hidrógeno"]},
     "fr": {"q": "De quoi est principalement composée l'épaisse atmosphère de Vénus ?", "a": ["dioxyde de carbone", "co2"], "w": ["oxygène", "azote", "méthane", "hydrogène"]},
     "lt": {"q": "Iš ko daugiausia sudaryta tiršta Veneros atmosfera?", "a": ["anglies dioksido", "co2"], "w": ["deguonies", "azoto", "metano", "vandenilio"]},
     "ru": {"q": "Из чего в основном состоит плотная атмосфера Венеры?", "a": ["углекислый газ", "co2"], "w": ["кислород", "азот", "метан", "водород"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which planet in the solar system is the least dense?", "a": ["saturn"], "w": ["jupiter", "uranus", "neptune", "mercury"]},
     "de": {"q": "Welcher Planet im Sonnensystem hat die geringste Dichte?", "a": ["saturn"], "w": ["jupiter", "uranus", "neptun", "merkur"]},
     "es": {"q": "¿Qué planeta del sistema solar es el menos denso?", "a": ["saturno"], "w": ["júpiter", "urano", "neptuno", "mercurio"]},
     "fr": {"q": "Quelle planète du système solaire est la moins dense ?", "a": ["saturne"], "w": ["jupiter", "uranus", "neptune", "mercure"]},
     "lt": {"q": "Kuri Saulės sistemos planeta yra mažiausio tankio?", "a": ["saturnas"], "w": ["jupiteris", "uranas", "neptūnas", "merkurijus"]},
     "ru": {"q": "Какая планета Солнечной системы имеет наименьшую плотность?", "a": ["сатурн"], "w": ["юпитер", "уран", "нептун", "меркурий"]}},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for entry in QUESTIONS:
        for lang in LANGS:
            assert lang in entry, f"missing {lang} in {entry['en']['q']}"

    embeddings = {}
    if os.path.exists(EMBEDDINGS_FILE):
        with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
            embeddings = json.load(f)
    print(f"Loaded {len(embeddings)} existing embeddings (threshold={THRESHOLD})")

    from enrichment import _get_embedding, _cosine_similarity

    stores = {}
    for lang in LANGS:
        with open(QFILE.format(lang), "r", encoding="utf-8") as f:
            stores[lang] = json.load(f)
    existing_ids = {q["id"] for q in stores["en"]["data"]}

    added, skipped_dup, skipped_exist = 0, 0, 0
    for entry in QUESTIONS:
        if added >= TARGET_NEW:
            break
        en_q = entry["en"]["q"]
        qid = _id(en_q)

        if qid in existing_ids:
            print(f"  EXISTS (id): {en_q[:60]}")
            skipped_exist += 1
            continue

        emb = _get_embedding(en_q)
        dup_with = None
        for key, vec in embeddings.items():
            if _cosine_similarity(emb, vec) >= THRESHOLD:
                dup_with = key
                break
        if dup_with:
            print(f"  DUP (>= {THRESHOLD}) vs {dup_with[:8]}: {en_q[:55]}")
            skipped_dup += 1
            continue

        for lang in LANGS:
            rec = {
                "id": qid,
                "question": entry[lang]["q"],
                "answers": entry[lang]["a"],
                "wrong_answers": entry[lang]["w"],
                "category": CATEGORY,
                "difficulty": entry["difficulty"],
                "points": entry["points"],
                "language": lang,
            }
            stores[lang]["data"].append(rec)

        embeddings[qid] = emb          # so later batch items dedup against this one
        existing_ids.add(qid)
        added += 1
        print(f"  ADD ({added}): {en_q[:55]}")

    print(f"\nSummary: add={added} dup={skipped_dup} already-exists={skipped_exist}")

    if args.dry_run:
        print("Dry run - nothing written.")
        return
    if added == 0:
        print("Nothing to write.")
        return

    for lang in LANGS:
        _atomic_write_json(stores[lang], QFILE.format(lang))
        print(f"  wrote {QFILE.format(lang)} ({len(stores[lang]['data'])} questions)")
    _atomic_write_json(embeddings, EMBEDDINGS_FILE)
    print(f"  wrote {EMBEDDINGS_FILE} ({len(embeddings)} embeddings)")
    print("Done.")


if __name__ == "__main__":
    main()

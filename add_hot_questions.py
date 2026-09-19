#!/usr/bin/env python3
"""
Batch add: 40 new questions about the hottest places in the world, across the
6 active languages (en, de, es, fr, lt, ru). Follows QUESTIONS_AUTHORING.md.

  - id = md5(english question text)  (join key across all languages)
  - answers AND wrong_answers lowercase (current standard - both fields)
  - category = "geography"; difficulty easy (700) / normal (800)
  - semantic dedup vs embeddings.json at DEDUP_THRESHOLD (default 0.92),
    including within this batch (new embeddings are added as we go)
  - idempotent: ids already present are skipped; caps additions at TARGET_NEW

A few buffer candidates are included after the core set so that, if dedup drops
some, we can still reach TARGET_NEW. Additions stop once TARGET_NEW is reached.

Usage:
    python add_hot_questions.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import tempfile
import time

LANGS = ["en", "de", "es", "fr", "lt", "ru"]
CATEGORY = "geography"
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
     "en": {"q": "What is the hottest continent on Earth on average?", "a": ["africa"], "w": ["antarctica", "europe", "north america", "australia"]},
     "de": {"q": "Was ist im Durchschnitt der heißeste Kontinent der Erde?", "a": ["afrika"], "w": ["antarktis", "europa", "nordamerika", "australien"]},
     "es": {"q": "¿Cuál es el continente más caluroso de la Tierra en promedio?", "a": ["áfrica"], "w": ["antártida", "europa", "américa del norte", "australia"]},
     "fr": {"q": "Quel est en moyenne le continent le plus chaud de la Terre ?", "a": ["afrique"], "w": ["antarctique", "europe", "amérique du nord", "australie"]},
     "lt": {"q": "Koks yra vidutiniškai karščiausias žemynas Žemėje?", "a": ["afrika"], "w": ["antarktida", "europa", "šiaurės amerika", "australija"]},
     "ru": {"q": "Какой континент в среднем самый жаркий на Земле?", "a": ["африка"], "w": ["антарктида", "европа", "северная америка", "австралия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the boiling point of water in degrees Celsius?", "a": ["100", "one hundred", "100 degrees"], "w": ["0", "50", "212", "90"]},
     "de": {"q": "Was ist der Siedepunkt von Wasser in Grad Celsius?", "a": ["100", "hundert", "100 grad"], "w": ["0", "50", "212", "90"]},
     "es": {"q": "¿Cuál es el punto de ebullición del agua en grados Celsius?", "a": ["100", "cien", "100 grados"], "w": ["0", "50", "212", "90"]},
     "fr": {"q": "Quel est le point d'ébullition de l'eau en degrés Celsius ?", "a": ["100", "cent", "100 degrés"], "w": ["0", "50", "212", "90"]},
     "lt": {"q": "Kokia yra vandens virimo temperatūra Celsijaus laipsniais?", "a": ["100", "šimtas", "100 laipsnių"], "w": ["0", "50", "212", "90"]},
     "ru": {"q": "Какова температура кипения воды в градусах Цельсия?", "a": ["100", "сто", "100 градусов"], "w": ["0", "50", "212", "90"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the boiling point of water in degrees Fahrenheit?", "a": ["212", "212 degrees"], "w": ["100", "32", "180", "250"]},
     "de": {"q": "Was ist der Siedepunkt von Wasser in Grad Fahrenheit?", "a": ["212", "212 grad"], "w": ["100", "32", "180", "250"]},
     "es": {"q": "¿Cuál es el punto de ebullición del agua en grados Fahrenheit?", "a": ["212", "212 grados"], "w": ["100", "32", "180", "250"]},
     "fr": {"q": "Quel est le point d'ébullition de l'eau en degrés Fahrenheit ?", "a": ["212", "212 degrés"], "w": ["100", "32", "180", "250"]},
     "lt": {"q": "Kokia yra vandens virimo temperatūra Farenheito laipsniais?", "a": ["212", "212 laipsnių"], "w": ["100", "32", "180", "250"]},
     "ru": {"q": "Какова температура кипения воды в градусах Фаренгейта?", "a": ["212", "212 градусов"], "w": ["100", "32", "180", "250"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the hottest season of the year?", "a": ["summer"], "w": ["winter", "spring", "autumn", "monsoon"]},
     "de": {"q": "Was ist die heißeste Jahreszeit?", "a": ["sommer"], "w": ["winter", "frühling", "herbst", "monsun"]},
     "es": {"q": "¿Cuál es la estación más calurosa del año?", "a": ["verano"], "w": ["invierno", "primavera", "otoño", "monzón"]},
     "fr": {"q": "Quelle est la saison la plus chaude de l'année ?", "a": ["été"], "w": ["hiver", "printemps", "automne", "mousson"]},
     "lt": {"q": "Koks yra karščiausias metų laikas?", "a": ["vasara"], "w": ["žiema", "pavasaris", "ruduo", "musonas"]},
     "ru": {"q": "Какое самое жаркое время года?", "a": ["лето"], "w": ["зима", "весна", "осень", "муссон"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the largest hot desert in the world?", "a": ["sahara", "the sahara"], "w": ["gobi", "kalahari", "atacama", "arabian desert"]},
     "de": {"q": "Was ist die größte heiße Wüste der Welt?", "a": ["sahara", "die sahara"], "w": ["gobi", "kalahari", "atacama", "arabische wüste"]},
     "es": {"q": "¿Cuál es el desierto cálido más grande del mundo?", "a": ["sahara", "el sahara"], "w": ["gobi", "kalahari", "atacama", "desierto arábigo"]},
     "fr": {"q": "Quel est le plus grand désert chaud du monde ?", "a": ["sahara", "le sahara"], "w": ["gobi", "kalahari", "atacama", "désert d'arabie"]},
     "lt": {"q": "Kokia yra didžiausia karšta dykuma pasaulyje?", "a": ["sachara"], "w": ["gobis", "kalaharis", "atakama", "arabijos dykuma"]},
     "ru": {"q": "Какая самая большая жаркая пустыня в мире?", "a": ["сахара"], "w": ["гоби", "калахари", "атакама", "аравийская пустыня"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "On which continent is the Sahara Desert located?", "a": ["africa"], "w": ["asia", "australia", "south america", "europe"]},
     "de": {"q": "Auf welchem Kontinent liegt die Sahara?", "a": ["afrika"], "w": ["asien", "australien", "südamerika", "europa"]},
     "es": {"q": "¿En qué continente se encuentra el desierto del Sahara?", "a": ["áfrica"], "w": ["asia", "australia", "américa del sur", "europa"]},
     "fr": {"q": "Sur quel continent se trouve le désert du Sahara ?", "a": ["afrique"], "w": ["asie", "australie", "amérique du sud", "europe"]},
     "lt": {"q": "Kuriame žemyne yra Sacharos dykuma?", "a": ["afrika"], "w": ["azija", "australija", "pietų amerika", "europa"]},
     "ru": {"q": "На каком континенте находится пустыня Сахара?", "a": ["африка"], "w": ["азия", "австралия", "южная америка", "европа"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which planet is the hottest in our solar system?", "a": ["venus"], "w": ["mercury", "mars", "jupiter", "earth"]},
     "de": {"q": "Welcher Planet ist der heißeste in unserem Sonnensystem?", "a": ["venus"], "w": ["merkur", "mars", "jupiter", "erde"]},
     "es": {"q": "¿Qué planeta es el más caliente de nuestro sistema solar?", "a": ["venus"], "w": ["mercurio", "marte", "júpiter", "tierra"]},
     "fr": {"q": "Quelle planète est la plus chaude de notre système solaire ?", "a": ["vénus"], "w": ["mercure", "mars", "jupiter", "terre"]},
     "lt": {"q": "Kuri planeta yra karščiausia mūsų Saulės sistemoje?", "a": ["venera"], "w": ["merkurijus", "marsas", "jupiteris", "žemė"]},
     "ru": {"q": "Какая планета самая горячая в нашей Солнечной системе?", "a": ["венера"], "w": ["меркурий", "марс", "юпитер", "земля"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do we call a hot, dry region with very little rainfall?", "a": ["desert", "a desert"], "w": ["jungle", "swamp", "tundra", "prairie"]},
     "de": {"q": "Wie nennt man eine heiße, trockene Region mit sehr wenig Niederschlag?", "a": ["wüste", "eine wüste"], "w": ["dschungel", "sumpf", "tundra", "prärie"]},
     "es": {"q": "¿Cómo llamamos a una región cálida y seca con muy pocas lluvias?", "a": ["desierto", "un desierto"], "w": ["selva", "pantano", "tundra", "pradera"]},
     "fr": {"q": "Comment appelle-t-on une région chaude et sèche avec très peu de pluie ?", "a": ["désert", "un désert"], "w": ["jungle", "marais", "toundra", "prairie"]},
     "lt": {"q": "Kaip vadiname karštą, sausą regioną su labai mažai kritulių?", "a": ["dykuma"], "w": ["džiunglės", "pelkė", "tundra", "prerija"]},
     "ru": {"q": "Как называется жаркий, сухой регион с очень малым количеством осадков?", "a": ["пустыня"], "w": ["джунгли", "болото", "тундра", "прерия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which animal is famous for surviving in hot deserts and storing fat in its humps?", "a": ["camel", "a camel"], "w": ["horse", "donkey", "llama", "elephant"]},
     "de": {"q": "Welches Tier ist dafür bekannt, in heißen Wüsten zu überleben und Fett in seinen Höckern zu speichern?", "a": ["kamel", "dromedar"], "w": ["pferd", "esel", "lama", "elefant"]},
     "es": {"q": "¿Qué animal es famoso por sobrevivir en desiertos calurosos y almacenar grasa en sus jorobas?", "a": ["camello"], "w": ["caballo", "burro", "llama", "elefante"]},
     "fr": {"q": "Quel animal est célèbre pour survivre dans les déserts chauds et stocker de la graisse dans ses bosses ?", "a": ["chameau", "dromadaire"], "w": ["cheval", "âne", "lama", "éléphant"]},
     "lt": {"q": "Koks gyvūnas garsėja tuo, kad išgyvena karštose dykumose ir kaupia riebalus kupromis?", "a": ["kupranugaris"], "w": ["arklys", "asilas", "lama", "dramblys"]},
     "ru": {"q": "Какое животное известно тем, что выживает в жарких пустынях и запасает жир в горбах?", "a": ["верблюд"], "w": ["лошадь", "осёл", "лама", "слон"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What spiny plant is well known for surviving in hot deserts?", "a": ["cactus", "a cactus"], "w": ["fern", "palm tree", "oak", "moss"]},
     "de": {"q": "Welche stachelige Pflanze ist dafür bekannt, in heißen Wüsten zu überleben?", "a": ["kaktus"], "w": ["farn", "palme", "eiche", "moos"]},
     "es": {"q": "¿Qué planta espinosa es muy conocida por sobrevivir en desiertos calurosos?", "a": ["cactus", "cacto"], "w": ["helecho", "palmera", "roble", "musgo"]},
     "fr": {"q": "Quelle plante épineuse est bien connue pour survivre dans les déserts chauds ?", "a": ["cactus"], "w": ["fougère", "palmier", "chêne", "mousse"]},
     "lt": {"q": "Koks dygliuotas augalas gerai žinomas dėl gebėjimo išgyventi karštose dykumose?", "a": ["kaktusas"], "w": ["papartis", "palmė", "ąžuolas", "samana"]},
     "ru": {"q": "Какое колючее растение хорошо известно тем, что выживает в жарких пустынях?", "a": ["кактус"], "w": ["папоротник", "пальма", "дуб", "мох"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a fertile spot in a desert where water is found called?", "a": ["oasis", "an oasis"], "w": ["dune", "mirage", "canyon", "delta"]},
     "de": {"q": "Wie nennt man einen fruchtbaren Ort in einer Wüste, an dem Wasser vorkommt?", "a": ["oase", "eine oase"], "w": ["düne", "fata morgana", "canyon", "delta"]},
     "es": {"q": "¿Cómo se llama un lugar fértil en un desierto donde hay agua?", "a": ["oasis", "un oasis"], "w": ["duna", "espejismo", "cañón", "delta"]},
     "fr": {"q": "Comment appelle-t-on un endroit fertile dans un désert où l'on trouve de l'eau ?", "a": ["oasis", "une oasis"], "w": ["dune", "mirage", "canyon", "delta"]},
     "lt": {"q": "Kaip vadinama derlinga vieta dykumoje, kur randama vandens?", "a": ["oazė"], "w": ["kopa", "miražas", "kanjonas", "delta"]},
     "ru": {"q": "Как называется плодородное место в пустыне, где есть вода?", "a": ["оазис"], "w": ["дюна", "мираж", "каньон", "дельта"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the optical illusion of water seen on a hot desert road called?", "a": ["mirage", "a mirage"], "w": ["oasis", "rainbow", "shadow", "reflection"]},
     "de": {"q": "Wie nennt man die optische Täuschung von Wasser auf einer heißen Wüstenstraße?", "a": ["fata morgana", "luftspiegelung"], "w": ["oase", "regenbogen", "schatten", "spiegelung"]},
     "es": {"q": "¿Cómo se llama la ilusión óptica de agua que se ve en una carretera desértica caliente?", "a": ["espejismo"], "w": ["oasis", "arcoíris", "sombra", "reflejo"]},
     "fr": {"q": "Comment appelle-t-on l'illusion d'optique d'eau vue sur une route désertique chaude ?", "a": ["mirage", "un mirage"], "w": ["oasis", "arc-en-ciel", "ombre", "reflet"]},
     "lt": {"q": "Kaip vadinama vandens optinė iliuzija, matoma ant karšto dykumos kelio?", "a": ["miražas"], "w": ["oazė", "vaivorykštė", "šešėlis", "atspindys"]},
     "ru": {"q": "Как называется оптическая иллюзия воды, видимая на горячей пустынной дороге?", "a": ["мираж"], "w": ["оазис", "радуга", "тень", "отражение"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "The imaginary line around the middle of the Earth, where it is hottest, is called what?", "a": ["equator", "the equator"], "w": ["prime meridian", "arctic circle", "tropic of cancer", "date line"]},
     "de": {"q": "Wie heißt die gedachte Linie um die Mitte der Erde, wo es am heißesten ist?", "a": ["äquator", "der äquator"], "w": ["nullmeridian", "polarkreis", "wendekreis des krebses", "datumsgrenze"]},
     "es": {"q": "¿Cómo se llama la línea imaginaria alrededor del centro de la Tierra, donde hace más calor?", "a": ["ecuador", "el ecuador"], "w": ["meridiano de greenwich", "círculo polar ártico", "trópico de cáncer", "línea de cambio de fecha"]},
     "fr": {"q": "Comment appelle-t-on la ligne imaginaire autour du milieu de la Terre, où il fait le plus chaud ?", "a": ["équateur", "l'équateur"], "w": ["méridien de greenwich", "cercle polaire arctique", "tropique du cancer", "ligne de changement de date"]},
     "lt": {"q": "Kaip vadinama įsivaizduojama linija aplink Žemės vidurį, kur karščiausia?", "a": ["pusiaujas"], "w": ["grinvičo dienovidinis", "šiaurės poliaratis", "vėžio atogrąža", "datos keitimo linija"]},
     "ru": {"q": "Как называется воображаемая линия вокруг середины Земли, где жарче всего?", "a": ["экватор"], "w": ["нулевой меридиан", "северный полярный круг", "тропик рака", "линия перемены дат"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which star provides heat and light to the Earth?", "a": ["the sun", "sun"], "w": ["the moon", "sirius", "polaris", "venus"]},
     "de": {"q": "Welcher Stern spendet der Erde Wärme und Licht?", "a": ["die sonne", "sonne"], "w": ["der mond", "sirius", "polarstern", "venus"]},
     "es": {"q": "¿Qué estrella proporciona calor y luz a la Tierra?", "a": ["el sol", "sol"], "w": ["la luna", "sirio", "estrella polar", "venus"]},
     "fr": {"q": "Quelle étoile fournit chaleur et lumière à la Terre ?", "a": ["le soleil", "soleil"], "w": ["la lune", "sirius", "étoile polaire", "vénus"]},
     "lt": {"q": "Kuri žvaigždė teikia Žemei šilumą ir šviesą?", "a": ["saulė"], "w": ["mėnulis", "sirijus", "šiaurinė žvaigždė", "venera"]},
     "ru": {"q": "Какая звезда даёт Земле тепло и свет?", "a": ["солнце"], "w": ["луна", "сириус", "полярная звезда", "венера"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What instrument is used to measure temperature?", "a": ["thermometer", "a thermometer"], "w": ["barometer", "compass", "ruler", "scale"]},
     "de": {"q": "Welches Instrument wird zur Temperaturmessung verwendet?", "a": ["thermometer", "ein thermometer"], "w": ["barometer", "kompass", "lineal", "waage"]},
     "es": {"q": "¿Qué instrumento se usa para medir la temperatura?", "a": ["termómetro", "un termómetro"], "w": ["barómetro", "brújula", "regla", "balanza"]},
     "fr": {"q": "Quel instrument est utilisé pour mesurer la température ?", "a": ["thermomètre", "un thermomètre"], "w": ["baromètre", "boussole", "règle", "balance"]},
     "lt": {"q": "Koks prietaisas naudojamas temperatūrai matuoti?", "a": ["termometras"], "w": ["barometras", "kompasas", "liniuotė", "svarstyklės"]},
     "ru": {"q": "Какой прибор используется для измерения температуры?", "a": ["термометр"], "w": ["барометр", "компас", "линейка", "весы"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which colour of clothing helps keep you cooler in hot sunshine?", "a": ["white"], "w": ["black", "dark blue", "brown", "dark grey"]},
     "de": {"q": "Welche Kleidungsfarbe hilft, sich in heißer Sonne kühler zu halten?", "a": ["weiß"], "w": ["schwarz", "dunkelblau", "braun", "dunkelgrau"]},
     "es": {"q": "¿Qué color de ropa ayuda a mantenerse más fresco bajo el sol caliente?", "a": ["blanco"], "w": ["negro", "azul oscuro", "marrón", "gris oscuro"]},
     "fr": {"q": "Quelle couleur de vêtement aide à rester plus au frais sous un soleil chaud ?", "a": ["blanc"], "w": ["noir", "bleu foncé", "marron", "gris foncé"]},
     "lt": {"q": "Kokia drabužių spalva padeda išlikti vėsiau karštoje saulėje?", "a": ["balta"], "w": ["juoda", "tamsiai mėlyna", "ruda", "tamsiai pilka"]},
     "ru": {"q": "Какой цвет одежды помогает сохранять прохладу под жарким солнцем?", "a": ["белый"], "w": ["чёрный", "тёмно-синий", "коричневый", "тёмно-серый"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which country is the hot region of Death Valley located in?", "a": ["united states", "usa", "the united states"], "w": ["mexico", "egypt", "australia", "chile"]},
     "de": {"q": "In welchem Land liegt die heiße Region Death Valley?", "a": ["vereinigte staaten", "usa"], "w": ["mexiko", "ägypten", "australien", "chile"]},
     "es": {"q": "¿En qué país se encuentra la calurosa región del Valle de la Muerte?", "a": ["estados unidos", "ee. uu."], "w": ["méxico", "egipto", "australia", "chile"]},
     "fr": {"q": "Dans quel pays se trouve la chaude région de la Vallée de la Mort ?", "a": ["états-unis", "usa"], "w": ["mexique", "égypte", "australie", "chili"]},
     "lt": {"q": "Kurioje šalyje yra karštasis Mirties slėnio regionas?", "a": ["jungtinės valstijos", "jav"], "w": ["meksika", "egiptas", "australija", "čilė"]},
     "ru": {"q": "В какой стране находится жаркий регион Долина Смерти?", "a": ["сша", "соединённые штаты"], "w": ["мексика", "египет", "австралия", "чили"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a hill of sand shaped by the wind in a desert called?", "a": ["dune", "a dune", "sand dune"], "w": ["oasis", "cliff", "valley", "plateau"]},
     "de": {"q": "Wie nennt man einen vom Wind geformten Sandhügel in einer Wüste?", "a": ["düne", "sanddüne"], "w": ["oase", "klippe", "tal", "hochebene"]},
     "es": {"q": "¿Cómo se llama una colina de arena formada por el viento en un desierto?", "a": ["duna", "una duna"], "w": ["oasis", "acantilado", "valle", "meseta"]},
     "fr": {"q": "Comment appelle-t-on une colline de sable façonnée par le vent dans un désert ?", "a": ["dune", "une dune"], "w": ["oasis", "falaise", "vallée", "plateau"]},
     "lt": {"q": "Kaip vadinama vėjo suformuota smėlio kalva dykumoje?", "a": ["kopa", "smėlio kopa"], "w": ["oazė", "uola", "slėnis", "plynaukštė"]},
     "ru": {"q": "Как называется песчаный холм, сформированный ветром в пустыне?", "a": ["дюна", "бархан"], "w": ["оазис", "утёс", "долина", "плато"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "The warm region on Earth between the two tropics is called what?", "a": ["the tropics", "tropics"], "w": ["the arctic", "the poles", "temperate zone", "the tundra"]},
     "de": {"q": "Wie nennt man die warme Region der Erde zwischen den beiden Wendekreisen?", "a": ["die tropen", "tropen"], "w": ["die arktis", "die pole", "gemäßigte zone", "die tundra"]},
     "es": {"q": "¿Cómo se llama la cálida región de la Tierra entre los dos trópicos?", "a": ["los trópicos", "el trópico"], "w": ["el ártico", "los polos", "zona templada", "la tundra"]},
     "fr": {"q": "Comment appelle-t-on la région chaude de la Terre située entre les deux tropiques ?", "a": ["les tropiques", "la zone tropicale"], "w": ["l'arctique", "les pôles", "zone tempérée", "la toundra"]},
     "lt": {"q": "Kaip vadinamas šiltas Žemės regionas tarp dviejų atogrąžų?", "a": ["atogrąžos", "tropikai"], "w": ["arktis", "poliai", "vidutinio klimato juosta", "tundra"]},
     "ru": {"q": "Как называется тёплая область Земли между двумя тропиками?", "a": ["тропики"], "w": ["арктика", "полюса", "умеренный пояс", "тундра"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What painful red skin damage is caused by too much hot sun?", "a": ["sunburn", "a sunburn"], "w": ["frostbite", "rash", "blister", "bruise"]},
     "de": {"q": "Welche schmerzhafte rote Hautschädigung wird durch zu viel heiße Sonne verursacht?", "a": ["sonnenbrand"], "w": ["erfrierung", "ausschlag", "blase", "bluterguss"]},
     "es": {"q": "¿Qué doloroso daño rojo en la piel causa el exceso de sol caliente?", "a": ["quemadura solar", "quemadura de sol"], "w": ["congelación", "sarpullido", "ampolla", "moretón"]},
     "fr": {"q": "Quels dommages cutanés rouges et douloureux sont causés par trop de soleil chaud ?", "a": ["coup de soleil"], "w": ["gelure", "éruption cutanée", "cloque", "bleu"]},
     "lt": {"q": "Kokį skausmingą raudoną odos pažeidimą sukelia per daug karštos saulės?", "a": ["saulės nudegimas", "nudegimas"], "w": ["nušalimas", "bėrimas", "pūslė", "mėlynė"]},
     "ru": {"q": "Какое болезненное красное повреждение кожи вызывает избыток жаркого солнца?", "a": ["солнечный ожог"], "w": ["обморожение", "сыпь", "волдырь", "синяк"]}},

    # ---------------- NORMAL (800 pts) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "Where was the highest reliably recorded air temperature on Earth measured?", "a": ["death valley", "furnace creek"], "w": ["sahara desert", "kuwait city", "dallol", "lut desert"]},
     "de": {"q": "Wo wurde die höchste zuverlässig gemessene Lufttemperatur der Erde registriert?", "a": ["death valley", "furnace creek", "tal des todes"], "w": ["sahara", "kuwait-stadt", "dallol", "lut-wüste"]},
     "es": {"q": "¿Dónde se midió la temperatura del aire más alta registrada de forma fiable en la Tierra?", "a": ["valle de la muerte", "furnace creek"], "w": ["desierto del sahara", "ciudad de kuwait", "dallol", "desierto de lut"]},
     "fr": {"q": "Où la température de l'air la plus élevée jamais enregistrée de façon fiable sur Terre a-t-elle été mesurée ?", "a": ["vallée de la mort", "furnace creek"], "w": ["désert du sahara", "koweït", "dallol", "désert du lout"]},
     "lt": {"q": "Kur buvo užfiksuota aukščiausia patikimai išmatuota oro temperatūra Žemėje?", "a": ["mirties slėnis", "furnace creek"], "w": ["sacharos dykuma", "kuveitas", "dalolis", "luto dykuma"]},
     "ru": {"q": "Где была зафиксирована самая высокая достоверно измеренная температура воздуха на Земле?", "a": ["долина смерти", "фернес-крик"], "w": ["пустыня сахара", "эль-кувейт", "даллол", "пустыня деште-лут"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Death Valley, one of the hottest places on Earth, is in which US state?", "a": ["california"], "w": ["nevada", "arizona", "texas", "utah"]},
     "de": {"q": "Death Valley, einer der heißesten Orte der Erde, liegt in welchem US-Bundesstaat?", "a": ["kalifornien"], "w": ["nevada", "arizona", "texas", "utah"]},
     "es": {"q": "El Valle de la Muerte, uno de los lugares más calurosos de la Tierra, ¿en qué estado de EE. UU. está?", "a": ["california"], "w": ["nevada", "arizona", "texas", "utah"]},
     "fr": {"q": "La Vallée de la Mort, l'un des endroits les plus chauds de la Terre, se trouve dans quel État américain ?", "a": ["californie"], "w": ["nevada", "arizona", "texas", "utah"]},
     "lt": {"q": "Mirties slėnis, viena karščiausių vietų Žemėje, yra kurioje JAV valstijoje?", "a": ["kalifornija"], "w": ["nevada", "arizona", "teksasas", "juta"]},
     "ru": {"q": "Долина Смерти, одно из самых жарких мест на Земле, находится в каком штате США?", "a": ["калифорния"], "w": ["невада", "аризона", "техас", "юта"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Iranian desert has recorded some of the hottest land surface temperatures on Earth?", "a": ["lut desert", "dasht-e lut", "lut"], "w": ["gobi desert", "thar desert", "karakum", "negev"]},
     "de": {"q": "Welche iranische Wüste hat einige der heißesten Landoberflächentemperaturen der Erde verzeichnet?", "a": ["lut-wüste", "dasht-e lut", "lut"], "w": ["wüste gobi", "thar-wüste", "karakum", "negev"]},
     "es": {"q": "¿Qué desierto iraní ha registrado algunas de las temperaturas de superficie más altas de la Tierra?", "a": ["desierto de lut", "dasht-e lut", "lut"], "w": ["desierto de gobi", "desierto de thar", "karakum", "néguev"]},
     "fr": {"q": "Quel désert iranien a enregistré certaines des températures de surface les plus élevées de la Terre ?", "a": ["désert du lout", "dasht-e lut", "lout"], "w": ["désert de gobi", "désert du thar", "karakoum", "néguev"]},
     "lt": {"q": "Kuri Irano dykuma užfiksavo vienas karščiausių žemės paviršiaus temperatūrų Žemėje?", "a": ["luto dykuma", "dasht-e lut", "lutas"], "w": ["gobio dykuma", "taro dykuma", "karakumai", "negevas"]},
     "ru": {"q": "Какая иранская пустыня зафиксировала одни из самых высоких температур поверхности земли?", "a": ["деште-лут", "пустыня лут", "лут"], "w": ["пустыня гоби", "пустыня тар", "каракумы", "негев"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Dallol, one of the hottest inhabited places on Earth by yearly average, is in which country?", "a": ["ethiopia"], "w": ["sudan", "libya", "egypt", "somalia"]},
     "de": {"q": "Dallol, einer der heißesten bewohnten Orte der Erde im Jahresdurchschnitt, liegt in welchem Land?", "a": ["äthiopien"], "w": ["sudan", "libyen", "ägypten", "somalia"]},
     "es": {"q": "Dallol, uno de los lugares habitados más calurosos por media anual, ¿en qué país está?", "a": ["etiopía"], "w": ["sudán", "libia", "egipto", "somalia"]},
     "fr": {"q": "Dallol, l'un des lieux habités les plus chauds en moyenne annuelle, se trouve dans quel pays ?", "a": ["éthiopie"], "w": ["soudan", "libye", "égypte", "somalie"]},
     "lt": {"q": "Dalolis, viena karščiausių apgyvendintų vietų pagal metinį vidurkį, yra kurioje šalyje?", "a": ["etiopija"], "w": ["sudanas", "libija", "egiptas", "somalis"]},
     "ru": {"q": "Даллол, одно из самых жарких обитаемых мест по среднегодовой температуре, находится в какой стране?", "a": ["эфиопия"], "w": ["судан", "ливия", "египет", "сомали"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Approximately what was the highest reliably recorded air temperature on Earth, in Celsius?", "a": ["57", "56.7", "about 57"], "w": ["45", "50", "65", "70"]},
     "de": {"q": "Wie hoch war ungefähr die höchste zuverlässig gemessene Lufttemperatur der Erde in Celsius?", "a": ["57", "56,7", "etwa 57"], "w": ["45", "50", "65", "70"]},
     "es": {"q": "¿Cuál fue aproximadamente la temperatura del aire más alta registrada de forma fiable en la Tierra, en Celsius?", "a": ["57", "56,7", "unos 57"], "w": ["45", "50", "65", "70"]},
     "fr": {"q": "Quelle a été approximativement la température de l'air la plus élevée enregistrée de façon fiable sur Terre, en Celsius ?", "a": ["57", "56,7", "environ 57"], "w": ["45", "50", "65", "70"]},
     "lt": {"q": "Kokia buvo maždaug aukščiausia patikimai užfiksuota oro temperatūra Žemėje Celsijaus laipsniais?", "a": ["57", "56,7", "apie 57"], "w": ["45", "50", "65", "70"]},
     "ru": {"q": "Какой примерно была самая высокая достоверно зафиксированная температура воздуха на Земле в градусах Цельсия?", "a": ["57", "56,7", "около 57"], "w": ["45", "50", "65", "70"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In which country is the Sahara city of Timbuktu located?", "a": ["mali"], "w": ["niger", "chad", "algeria", "morocco"]},
     "de": {"q": "In welchem Land liegt die Sahara-Stadt Timbuktu?", "a": ["mali"], "w": ["niger", "tschad", "algerien", "marokko"]},
     "es": {"q": "¿En qué país se encuentra la ciudad sahariana de Tombuctú?", "a": ["malí"], "w": ["níger", "chad", "argelia", "marruecos"]},
     "fr": {"q": "Dans quel pays se trouve la ville saharienne de Tombouctou ?", "a": ["mali"], "w": ["niger", "tchad", "algérie", "maroc"]},
     "lt": {"q": "Kurioje šalyje yra Sacharos miestas Timbuktu?", "a": ["malis"], "w": ["nigeris", "čadas", "alžyras", "marokas"]},
     "ru": {"q": "В какой стране находится сахарский город Тимбукту?", "a": ["мали"], "w": ["нигер", "чад", "алжир", "марокко"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What do we call a prolonged period of excessively hot weather?", "a": ["heatwave", "a heatwave", "heat wave"], "w": ["blizzard", "monsoon", "drought", "cold snap"]},
     "de": {"q": "Wie nennt man eine anhaltende Periode übermäßig heißen Wetters?", "a": ["hitzewelle", "eine hitzewelle"], "w": ["schneesturm", "monsun", "dürre", "kälteeinbruch"]},
     "es": {"q": "¿Cómo llamamos a un período prolongado de clima excesivamente caluroso?", "a": ["ola de calor"], "w": ["ventisca", "monzón", "sequía", "ola de frío"]},
     "fr": {"q": "Comment appelle-t-on une période prolongée de chaleur excessive ?", "a": ["canicule", "vague de chaleur"], "w": ["blizzard", "mousson", "sécheresse", "vague de froid"]},
     "lt": {"q": "Kaip vadinamas užsitęsęs itin karšto oro laikotarpis?", "a": ["karščio banga"], "w": ["pūga", "musonas", "sausra", "šalčio banga"]},
     "ru": {"q": "Как называется продолжительный период чрезмерно жаркой погоды?", "a": ["волна жары", "жара"], "w": ["метель", "муссон", "засуха", "похолодание"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Gulf country recorded one of Asia's highest temperatures at Mitribah?", "a": ["kuwait"], "w": ["qatar", "bahrain", "oman", "yemen"]},
     "de": {"q": "Welches Golfland verzeichnete in Mitribah eine der höchsten Temperaturen Asiens?", "a": ["kuwait"], "w": ["katar", "bahrain", "oman", "jemen"]},
     "es": {"q": "¿Qué país del Golfo registró una de las temperaturas más altas de Asia en Mitribah?", "a": ["kuwait"], "w": ["catar", "baréin", "omán", "yemen"]},
     "fr": {"q": "Quel pays du Golfe a enregistré à Mitribah l'une des températures les plus élevées d'Asie ?", "a": ["koweït"], "w": ["qatar", "bahreïn", "oman", "yémen"]},
     "lt": {"q": "Kuri Persijos įlankos šalis Mitriboje užfiksavo vieną aukščiausių temperatūrų Azijoje?", "a": ["kuveitas"], "w": ["kataras", "bahreinas", "omanas", "jemenas"]},
     "ru": {"q": "Какая страна Персидского залива зафиксировала в Митрибе одну из самых высоких температур Азии?", "a": ["кувейт"], "w": ["катар", "бахрейн", "оман", "йемен"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Venus is the hottest planet mainly because of which effect trapping heat?", "a": ["greenhouse effect", "the greenhouse effect"], "w": ["coriolis effect", "doppler effect", "tidal effect", "magnetic effect"]},
     "de": {"q": "Venus ist der heißeste Planet vor allem wegen welchem wärmespeichernden Effekt?", "a": ["treibhauseffekt", "der treibhauseffekt"], "w": ["corioliskraft", "doppler-effekt", "gezeiteneffekt", "magnetischer effekt"]},
     "es": {"q": "Venus es el planeta más caliente principalmente por qué efecto que atrapa el calor?", "a": ["efecto invernadero", "el efecto invernadero"], "w": ["efecto coriolis", "efecto doppler", "efecto de marea", "efecto magnético"]},
     "fr": {"q": "Vénus est la planète la plus chaude surtout à cause de quel effet piégeant la chaleur ?", "a": ["effet de serre", "l'effet de serre"], "w": ["effet coriolis", "effet doppler", "effet de marée", "effet magnétique"]},
     "lt": {"q": "Venera yra karščiausia planeta daugiausia dėl kurio šilumą sulaikančio efekto?", "a": ["šiltnamio efektas"], "w": ["koriolio efektas", "doplerio efektas", "potvynių efektas", "magnetinis efektas"]},
     "ru": {"q": "Венера — самая горячая планета главным образом из-за какого эффекта, удерживающего тепло?", "a": ["парниковый эффект"], "w": ["эффект кориолиса", "эффект доплера", "приливный эффект", "магнитный эффект"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which gas is the main cause of the greenhouse effect that warms the planet?", "a": ["carbon dioxide", "co2"], "w": ["oxygen", "nitrogen", "helium", "hydrogen"]},
     "de": {"q": "Welches Gas ist die Hauptursache des Treibhauseffekts, der den Planeten erwärmt?", "a": ["kohlendioxid", "co2", "kohlenstoffdioxid"], "w": ["sauerstoff", "stickstoff", "helium", "wasserstoff"]},
     "es": {"q": "¿Qué gas es la principal causa del efecto invernadero que calienta el planeta?", "a": ["dióxido de carbono", "co2"], "w": ["oxígeno", "nitrógeno", "helio", "hidrógeno"]},
     "fr": {"q": "Quel gaz est la principale cause de l'effet de serre qui réchauffe la planète ?", "a": ["dioxyde de carbone", "co2", "gaz carbonique"], "w": ["oxygène", "azote", "hélium", "hydrogène"]},
     "lt": {"q": "Kokios dujos yra pagrindinė šiltnamio efekto, šildančio planetą, priežastis?", "a": ["anglies dioksidas", "co2"], "w": ["deguonis", "azotas", "helis", "vandenilis"]},
     "ru": {"q": "Какой газ является главной причиной парникового эффекта, нагревающего планету?", "a": ["углекислый газ", "co2", "диоксид углерода"], "w": ["кислород", "азот", "гелий", "водород"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The northern tropic line, marking the hot zone's edge, is called what?", "a": ["tropic of cancer", "the tropic of cancer"], "w": ["tropic of capricorn", "equator", "arctic circle", "prime meridian"]},
     "de": {"q": "Wie heißt der nördliche Wendekreis, der den Rand der heißen Zone markiert?", "a": ["wendekreis des krebses", "nördlicher wendekreis"], "w": ["wendekreis des steinbocks", "äquator", "polarkreis", "nullmeridian"]},
     "es": {"q": "¿Cómo se llama el trópico del norte, que marca el borde de la zona cálida?", "a": ["trópico de cáncer", "el trópico de cáncer"], "w": ["trópico de capricornio", "ecuador", "círculo polar ártico", "meridiano de greenwich"]},
     "fr": {"q": "Comment appelle-t-on le tropique nord, qui marque la limite de la zone chaude ?", "a": ["tropique du cancer", "le tropique du cancer"], "w": ["tropique du capricorne", "équateur", "cercle polaire arctique", "méridien de greenwich"]},
     "lt": {"q": "Kaip vadinama šiaurinė atogrąža, žyminti karštosios zonos kraštą?", "a": ["vėžio atogrąža", "šiaurės atogrąža"], "w": ["ožiaragio atogrąža", "pusiaujas", "šiaurės poliaratis", "grinvičo dienovidinis"]},
     "ru": {"q": "Как называется северная тропическая линия, обозначающая край жаркой зоны?", "a": ["тропик рака", "северный тропик"], "w": ["тропик козерога", "экватор", "северный полярный круг", "нулевой меридиан"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The southern tropic line bounding the hot zone is called what?", "a": ["tropic of capricorn", "the tropic of capricorn"], "w": ["tropic of cancer", "equator", "antarctic circle", "date line"]},
     "de": {"q": "Wie heißt der südliche Wendekreis, der die heiße Zone begrenzt?", "a": ["wendekreis des steinbocks", "südlicher wendekreis"], "w": ["wendekreis des krebses", "äquator", "südlicher polarkreis", "datumsgrenze"]},
     "es": {"q": "¿Cómo se llama el trópico del sur que limita la zona cálida?", "a": ["trópico de capricornio", "el trópico de capricornio"], "w": ["trópico de cáncer", "ecuador", "círculo polar antártico", "línea de cambio de fecha"]},
     "fr": {"q": "Comment appelle-t-on le tropique sud qui délimite la zone chaude ?", "a": ["tropique du capricorne", "le tropique du capricorne"], "w": ["tropique du cancer", "équateur", "cercle polaire antarctique", "ligne de changement de date"]},
     "lt": {"q": "Kaip vadinama pietinė atogrąža, ribojanti karštąją zoną?", "a": ["ožiaragio atogrąža", "pietų atogrąža"], "w": ["vėžio atogrąža", "pusiaujas", "pietų poliaratis", "datos keitimo linija"]},
     "ru": {"q": "Как называется южная тропическая линия, ограничивающая жаркую зону?", "a": ["тропик козерога", "южный тропик"], "w": ["тропик рака", "экватор", "южный полярный круг", "линия перемены дат"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is a violent desert windstorm that carries huge amounts of sand called?", "a": ["sandstorm", "a sandstorm"], "w": ["blizzard", "monsoon", "hurricane", "hailstorm"]},
     "de": {"q": "Wie nennt man einen heftigen Wüstensturm, der riesige Mengen Sand mit sich trägt?", "a": ["sandsturm", "ein sandsturm"], "w": ["schneesturm", "monsun", "hurrikan", "hagelsturm"]},
     "es": {"q": "¿Cómo se llama una violenta tormenta de viento del desierto que arrastra enormes cantidades de arena?", "a": ["tormenta de arena"], "w": ["ventisca", "monzón", "huracán", "granizada"]},
     "fr": {"q": "Comment appelle-t-on une violente tempête de vent du désert qui transporte d'énormes quantités de sable ?", "a": ["tempête de sable"], "w": ["blizzard", "mousson", "ouragan", "tempête de grêle"]},
     "lt": {"q": "Kaip vadinama smarki dykumos vėjo audra, nešanti didžiulius kiekius smėlio?", "a": ["smėlio audra"], "w": ["pūga", "musonas", "uraganas", "krušos audra"]},
     "ru": {"q": "Как называется сильная пустынная буря, несущая огромное количество песка?", "a": ["песчаная буря"], "w": ["метель", "муссон", "ураган", "град"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Roughly how much of North Africa does the Sahara Desert cover in area?", "a": ["most", "most of it", "the majority"], "w": ["a tenth", "a quarter", "none", "half a percent"]},
     "de": {"q": "Wie viel von Nordafrika bedeckt die Sahara ungefähr flächenmäßig?", "a": ["das meiste", "den größten teil"], "w": ["ein zehntel", "ein viertel", "nichts", "ein halbes prozent"]},
     "es": {"q": "¿Aproximadamente qué parte del norte de África cubre en superficie el desierto del Sahara?", "a": ["la mayor parte", "casi todo"], "w": ["una décima parte", "un cuarto", "nada", "medio por ciento"]},
     "fr": {"q": "Quelle proportion de l'Afrique du Nord le Sahara couvre-t-il environ en superficie ?", "a": ["la plus grande partie", "la majeure partie"], "w": ["un dixième", "un quart", "rien", "un demi pour cent"]},
     "lt": {"q": "Maždaug kokią Šiaurės Afrikos dalį pagal plotą dengia Sacharos dykuma?", "a": ["didžiąją dalį", "daugumą"], "w": ["dešimtadalį", "ketvirtadalį", "nieko", "pusę procento"]},
     "ru": {"q": "Примерно какую часть Северной Африки по площади покрывает пустыня Сахара?", "a": ["большую часть", "бо́льшую часть"], "w": ["десятую часть", "четверть", "нисколько", "половину процента"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "El Azizia, which once held a disputed world heat record, is in which country?", "a": ["libya"], "w": ["tunisia", "algeria", "egypt", "morocco"]},
     "de": {"q": "El Azizia, das einst einen umstrittenen Hitzerekord hielt, liegt in welchem Land?", "a": ["libyen"], "w": ["tunesien", "algerien", "ägypten", "marokko"]},
     "es": {"q": "El Aziziya, que una vez tuvo un disputado récord mundial de calor, ¿en qué país está?", "a": ["libia"], "w": ["túnez", "argelia", "egipto", "marruecos"]},
     "fr": {"q": "El Azizia, qui détenait autrefois un record de chaleur contesté, se trouve dans quel pays ?", "a": ["libye"], "w": ["tunisie", "algérie", "égypte", "maroc"]},
     "lt": {"q": "El Azizija, kadaise turėjusi ginčytiną pasaulio karščio rekordą, yra kurioje šalyje?", "a": ["libija"], "w": ["tunisas", "alžyras", "egiptas", "marokas"]},
     "ru": {"q": "Эль-Азизия, некогда владевшая спорным мировым рекордом жары, находится в какой стране?", "a": ["ливия"], "w": ["тунис", "алжир", "египет", "марокко"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What dangerous condition results from the body losing too much water in the heat?", "a": ["dehydration"], "w": ["hypothermia", "frostbite", "inflammation", "concussion"]},
     "de": {"q": "Welcher gefährliche Zustand entsteht, wenn der Körper in der Hitze zu viel Wasser verliert?", "a": ["dehydration", "dehydrierung", "austrocknung"], "w": ["unterkühlung", "erfrierung", "entzündung", "gehirnerschütterung"]},
     "es": {"q": "¿Qué condición peligrosa resulta de que el cuerpo pierda demasiada agua con el calor?", "a": ["deshidratación"], "w": ["hipotermia", "congelación", "inflamación", "conmoción cerebral"]},
     "fr": {"q": "Quelle affection dangereuse résulte d'une perte d'eau excessive du corps dans la chaleur ?", "a": ["déshydratation"], "w": ["hypothermie", "gelure", "inflammation", "commotion cérébrale"]},
     "lt": {"q": "Kokia pavojinga būklė atsiranda, kai kūnas karštyje netenka per daug vandens?", "a": ["dehidratacija", "dehidracija"], "w": ["hipotermija", "nušalimas", "uždegimas", "smegenų sukrėtimas"]},
     "ru": {"q": "Какое опасное состояние возникает, когда организм теряет слишком много воды в жару?", "a": ["обезвоживание", "дегидратация"], "w": ["переохлаждение", "обморожение", "воспаление", "сотрясение мозга"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Chilean desert is one of the driest and hottest places on Earth?", "a": ["atacama", "atacama desert"], "w": ["patagonia", "sahara", "mojave", "sonora"]},
     "de": {"q": "Welche chilenische Wüste ist einer der trockensten und heißesten Orte der Erde?", "a": ["atacama", "atacama-wüste"], "w": ["patagonien", "sahara", "mojave", "sonora"]},
     "es": {"q": "¿Qué desierto chileno es uno de los lugares más secos y calurosos de la Tierra?", "a": ["atacama", "desierto de atacama"], "w": ["patagonia", "sahara", "mojave", "sonora"]},
     "fr": {"q": "Quel désert chilien est l'un des endroits les plus secs et les plus chauds de la Terre ?", "a": ["atacama", "désert d'atacama"], "w": ["patagonie", "sahara", "mojave", "sonora"]},
     "lt": {"q": "Kuri Čilės dykuma yra viena sausiausių ir karščiausių vietų Žemėje?", "a": ["atakama", "atakamos dykuma"], "w": ["patagonija", "sachara", "modžavė", "sonora"]},
     "ru": {"q": "Какая чилийская пустыня является одним из самых сухих и жарких мест на Земле?", "a": ["атакама", "пустыня атакама"], "w": ["патагония", "сахара", "мохаве", "сонора"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the natural cooling response the body produces when it gets too hot?", "a": ["sweating", "sweat", "perspiration"], "w": ["shivering", "blushing", "yawning", "sneezing"]},
     "de": {"q": "Welche natürliche Kühlreaktion produziert der Körper, wenn ihm zu heiß wird?", "a": ["schwitzen", "schweiß"], "w": ["zittern", "erröten", "gähnen", "niesen"]},
     "es": {"q": "¿Cuál es la respuesta natural de enfriamiento que produce el cuerpo cuando tiene demasiado calor?", "a": ["sudar", "sudor", "transpiración"], "w": ["temblar", "sonrojarse", "bostezar", "estornudar"]},
     "fr": {"q": "Quelle est la réaction naturelle de refroidissement du corps lorsqu'il a trop chaud ?", "a": ["transpiration", "sueur", "transpirer"], "w": ["frissons", "rougir", "bâiller", "éternuer"]},
     "lt": {"q": "Kokia natūrali vėsinimo reakcija atsiranda, kai kūnui tampa per karšta?", "a": ["prakaitavimas", "prakaitas"], "w": ["drebulys", "raudonavimas", "žiovulys", "čiaudulys"]},
     "ru": {"q": "Какая естественная охлаждающая реакция возникает у тела, когда ему становится слишком жарко?", "a": ["потоотделение", "пот", "потение"], "w": ["дрожь", "покраснение", "зевота", "чихание"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What temperature scale, common in the United States, sets water's boiling point at 212 degrees?", "a": ["fahrenheit"], "w": ["celsius", "kelvin", "réaumur", "rankine"]},
     "de": {"q": "Welche in den USA gebräuchliche Temperaturskala setzt den Siedepunkt von Wasser auf 212 Grad?", "a": ["fahrenheit"], "w": ["celsius", "kelvin", "réaumur", "rankine"]},
     "es": {"q": "¿Qué escala de temperatura, común en Estados Unidos, fija el punto de ebullición del agua en 212 grados?", "a": ["fahrenheit"], "w": ["celsius", "kelvin", "réaumur", "rankine"]},
     "fr": {"q": "Quelle échelle de température, courante aux États-Unis, fixe le point d'ébullition de l'eau à 212 degrés ?", "a": ["fahrenheit"], "w": ["celsius", "kelvin", "réaumur", "rankine"]},
     "lt": {"q": "Kokia temperatūros skalė, paplitusi JAV, nustato vandens virimo tašką ties 212 laipsnių?", "a": ["farenheitas"], "w": ["celsijus", "kelvinas", "reomiuras", "rankinas"]},
     "ru": {"q": "Какая температурная шкала, распространённая в США, устанавливает точку кипения воды на 212 градусах?", "a": ["фаренгейт"], "w": ["цельсий", "кельвин", "реомюр", "ранкин"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The long-term warming of Earth's climate is commonly called what?", "a": ["global warming"], "w": ["global cooling", "ice age", "el niño", "ozone hole"]},
     "de": {"q": "Wie nennt man üblicherweise die langfristige Erwärmung des Erdklimas?", "a": ["globale erwärmung", "erderwärmung"], "w": ["globale abkühlung", "eiszeit", "el niño", "ozonloch"]},
     "es": {"q": "¿Cómo se llama comúnmente el calentamiento a largo plazo del clima de la Tierra?", "a": ["calentamiento global"], "w": ["enfriamiento global", "edad de hielo", "el niño", "agujero de ozono"]},
     "fr": {"q": "Comment appelle-t-on couramment le réchauffement à long terme du climat de la Terre ?", "a": ["réchauffement climatique", "réchauffement de la planète"], "w": ["refroidissement global", "âge glaciaire", "el niño", "trou d'ozone"]},
     "lt": {"q": "Kaip įprastai vadinamas ilgalaikis Žemės klimato šiltėjimas?", "a": ["visuotinis atšilimas", "globalinis atšilimas"], "w": ["visuotinis atšalimas", "ledynmetis", "el ninjas", "ozono skylė"]},
     "ru": {"q": "Как обычно называют долгосрочное потепление климата Земли?", "a": ["глобальное потепление"], "w": ["глобальное похолодание", "ледниковый период", "эль-ниньо", "озоновая дыра"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The hot, wet forests near the equator with heavy rainfall are called what?", "a": ["rainforests", "tropical rainforests", "rainforest"], "w": ["deserts", "grasslands", "tundras", "wetlands"]},
     "de": {"q": "Wie nennt man die heißen, feuchten Wälder nahe dem Äquator mit starkem Regen?", "a": ["regenwälder", "tropische regenwälder", "regenwald"], "w": ["wüsten", "grasländer", "tundren", "feuchtgebiete"]},
     "es": {"q": "¿Cómo se llaman los bosques cálidos y húmedos cerca del ecuador con fuertes lluvias?", "a": ["selvas tropicales", "selvas", "selva tropical"], "w": ["desiertos", "praderas", "tundras", "humedales"]},
     "fr": {"q": "Comment appelle-t-on les forêts chaudes et humides près de l'équateur avec de fortes pluies ?", "a": ["forêts tropicales", "forêt tropicale humide", "forêts tropicales humides"], "w": ["déserts", "prairies", "toundras", "zones humides"]},
     "lt": {"q": "Kaip vadinami karšti, drėgni miškai prie pusiaujo su gausiais krituliais?", "a": ["atogrąžų miškai", "atogrąžų miškas"], "w": ["dykumos", "pievos", "tundros", "pelkės"]},
     "ru": {"q": "Как называются жаркие влажные леса у экватора с обильными дождями?", "a": ["тропические леса", "дождевые леса", "тропический лес"], "w": ["пустыни", "степи", "тундры", "болота"]}},

    # ---------------- BUFFER candidates (used only if dedup drops some above) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "The hot, treeless grassland of Africa home to lions and zebras is called what?", "a": ["savanna", "savannah", "the savanna"], "w": ["tundra", "taiga", "prairie", "steppe"]},
     "de": {"q": "Wie nennt man das heiße, baumlose Grasland Afrikas, in dem Löwen und Zebras leben?", "a": ["savanne", "die savanne"], "w": ["tundra", "taiga", "prärie", "steppe"]},
     "es": {"q": "¿Cómo se llama la cálida pradera sin árboles de África donde viven leones y cebras?", "a": ["sabana", "la sabana"], "w": ["tundra", "taiga", "pradera", "estepa"]},
     "fr": {"q": "Comment appelle-t-on la chaude prairie sans arbres d'Afrique où vivent lions et zèbres ?", "a": ["savane", "la savane"], "w": ["toundra", "taïga", "prairie", "steppe"]},
     "lt": {"q": "Kaip vadinama karšta, bemedė Afrikos lyguma, kurioje gyvena liūtai ir zebrai?", "a": ["savana"], "w": ["tundra", "taiga", "prerija", "stepė"]},
     "ru": {"q": "Как называется жаркая безлесная равнина Африки, где живут львы и зебры?", "a": ["саванна"], "w": ["тундра", "тайга", "прерия", "степь"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which African river valley experiences intense desert heat as it flows through Egypt?", "a": ["nile", "the nile", "nile valley"], "w": ["amazon", "congo", "danube", "mekong"]},
     "de": {"q": "Welches afrikanische Flusstal erlebt intensive Wüstenhitze, während es durch Ägypten fließt?", "a": ["nil", "der nil", "niltal"], "w": ["amazonas", "kongo", "donau", "mekong"]},
     "es": {"q": "¿Qué valle fluvial africano experimenta un calor desértico intenso al atravesar Egipto?", "a": ["nilo", "el nilo", "valle del nilo"], "w": ["amazonas", "congo", "danubio", "mekong"]},
     "fr": {"q": "Quelle vallée fluviale africaine subit une chaleur désertique intense en traversant l'Égypte ?", "a": ["nil", "le nil", "vallée du nil"], "w": ["amazone", "congo", "danube", "mékong"]},
     "lt": {"q": "Kuris Afrikos upės slėnis patiria intensyvų dykumos karštį tekėdamas per Egiptą?", "a": ["nilas", "nilo slėnis"], "w": ["amazonė", "kongas", "dunojus", "mekongas"]},
     "ru": {"q": "Какая африканская речная долина испытывает сильную пустынную жару, проходя через Египет?", "a": ["нил", "долина нила"], "w": ["амазонка", "конго", "дунай", "меконг"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the very hot, molten rock beneath the Earth's surface called?", "a": ["magma"], "w": ["lava", "granite", "basalt", "sediment"]},
     "de": {"q": "Wie nennt man das sehr heiße, geschmolzene Gestein unter der Erdoberfläche?", "a": ["magma"], "w": ["lava", "granit", "basalt", "sediment"]},
     "es": {"q": "¿Cómo se llama la roca fundida y muy caliente que hay bajo la superficie terrestre?", "a": ["magma"], "w": ["lava", "granito", "basalto", "sedimento"]},
     "fr": {"q": "Comment appelle-t-on la roche en fusion très chaude sous la surface de la Terre ?", "a": ["magma"], "w": ["lave", "granite", "basalte", "sédiment"]},
     "lt": {"q": "Kaip vadinama labai karšta, išsilydžiusi uoliena po Žemės paviršiumi?", "a": ["magma"], "w": ["lava", "granitas", "bazaltas", "nuosėdos"]},
     "ru": {"q": "Как называется очень горячая расплавленная порода под поверхностью Земли?", "a": ["магма"], "w": ["лава", "гранит", "базальт", "осадок"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which African country is almost entirely covered by the hot Sahara Desert?", "a": ["libya", "algeria"], "w": ["kenya", "ghana", "uganda", "senegal"]},
     "de": {"q": "Welches afrikanische Land ist fast vollständig von der heißen Sahara bedeckt?", "a": ["libyen", "algerien"], "w": ["kenia", "ghana", "uganda", "senegal"]},
     "es": {"q": "¿Qué país africano está casi totalmente cubierto por el caluroso desierto del Sahara?", "a": ["libia", "argelia"], "w": ["kenia", "ghana", "uganda", "senegal"]},
     "fr": {"q": "Quel pays africain est presque entièrement couvert par le chaud désert du Sahara ?", "a": ["libye", "algérie"], "w": ["kenya", "ghana", "ouganda", "sénégal"]},
     "lt": {"q": "Kuri Afrikos šalis beveik visiškai padengta karštąja Sacharos dykuma?", "a": ["libija", "alžyras"], "w": ["kenija", "gana", "uganda", "senegalas"]},
     "ru": {"q": "Какая африканская страна почти полностью покрыта жаркой пустыней Сахара?", "a": ["ливия", "алжир"], "w": ["кения", "гана", "уганда", "сенегал"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "A serious illness caused by the body overheating in extreme heat is called what?", "a": ["heatstroke", "heat stroke"], "w": ["hypothermia", "sunburn", "frostbite", "migraine"]},
     "de": {"q": "Wie nennt man eine ernste Erkrankung, die durch Überhitzung des Körpers bei extremer Hitze entsteht?", "a": ["hitzschlag"], "w": ["unterkühlung", "sonnenbrand", "erfrierung", "migräne"]},
     "es": {"q": "¿Cómo se llama una enfermedad grave causada por el sobrecalentamiento del cuerpo con calor extremo?", "a": ["golpe de calor", "insolación"], "w": ["hipotermia", "quemadura solar", "congelación", "migraña"]},
     "fr": {"q": "Comment appelle-t-on une maladie grave causée par la surchauffe du corps en cas de chaleur extrême ?", "a": ["coup de chaleur"], "w": ["hypothermie", "coup de soleil", "gelure", "migraine"]},
     "lt": {"q": "Kaip vadinama rimta liga, kurią sukelia kūno perkaitimas esant ekstremaliam karščiui?", "a": ["šilumos smūgis", "karščio smūgis"], "w": ["hipotermija", "saulės nudegimas", "nušalimas", "migrena"]},
     "ru": {"q": "Как называется серьёзное заболевание, вызванное перегревом тела при экстремальной жаре?", "a": ["тепловой удар"], "w": ["переохлаждение", "солнечный ожог", "обморожение", "мигрень"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the hot molten rock that erupts and flows from a volcano called?", "a": ["lava"], "w": ["magma", "ash", "lahar", "pumice"]},
     "de": {"q": "Wie nennt man das heiße, geschmolzene Gestein, das aus einem Vulkan ausbricht und fließt?", "a": ["lava"], "w": ["magma", "asche", "lahar", "bimsstein"]},
     "es": {"q": "¿Cómo se llama la roca fundida y caliente que brota y fluye de un volcán?", "a": ["lava"], "w": ["magma", "ceniza", "lahar", "piedra pómez"]},
     "fr": {"q": "Comment appelle-t-on la roche en fusion chaude qui jaillit et s'écoule d'un volcan ?", "a": ["lave"], "w": ["magma", "cendre", "lahar", "pierre ponce"]},
     "lt": {"q": "Kaip vadinama karšta išsilydžiusi uoliena, kuri išsiveržia ir teka iš ugnikalnio?", "a": ["lava"], "w": ["magma", "pelenai", "laharas", "pemza"]},
     "ru": {"q": "Как называется горячая расплавленная порода, которая извергается и течёт из вулкана?", "a": ["лава"], "w": ["магма", "пепел", "лахар", "пемза"]}},
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

#!/usr/bin/env python3
"""
Batch add: 40 new questions about the coldest places in the world, across the
6 active languages (en, de, es, fr, lt, ru). Follows QUESTIONS_AUTHORING.md.

  - id = md5(english question text)  (join key across all languages)
  - answers lowercase; wrong_answers proper/Title case
  - category = "geography"; difficulty easy (700) / normal (800)
  - semantic dedup vs embeddings.json at DEDUP_THRESHOLD (default 0.92),
    including within this batch (new embeddings are added as we go)
  - idempotent: ids already present are skipped; caps additions at TARGET_NEW

A few buffer candidates are included after the core set so that, if dedup drops
some, we can still reach TARGET_NEW. Additions stop once TARGET_NEW is reached.

Usage:
    python add_cold_questions.py [--dry-run]
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
QUESTIONS = [
    # ---------------- EASY (700 pts) ----------------
    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the coldest continent on Earth?", "a": ["antarctica"], "w": ["Africa", "Asia", "Europe", "Australia"]},
     "de": {"q": "Was ist der kälteste Kontinent der Erde?", "a": ["antarktis", "antarktika"], "w": ["Afrika", "Asien", "Europa", "Australien"]},
     "es": {"q": "¿Cuál es el continente más frío de la Tierra?", "a": ["antártida"], "w": ["África", "Asia", "Europa", "Australia"]},
     "fr": {"q": "Quel est le continent le plus froid de la Terre ?", "a": ["antarctique"], "w": ["Afrique", "Asie", "Europe", "Australie"]},
     "lt": {"q": "Koks yra šalčiausias žemynas Žemėje?", "a": ["antarktida"], "w": ["Afrika", "Azija", "Europa", "Australija"]},
     "ru": {"q": "Какой самый холодный континент на Земле?", "a": ["антарктида"], "w": ["Африка", "Азия", "Европа", "Австралия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the coldest ocean on Earth?", "a": ["arctic ocean", "the arctic"], "w": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Southern Ocean"]},
     "de": {"q": "Was ist der kälteste Ozean der Erde?", "a": ["arktischer ozean", "nordpolarmeer"], "w": ["Pazifischer Ozean", "Atlantischer Ozean", "Indischer Ozean", "Südlicher Ozean"]},
     "es": {"q": "¿Cuál es el océano más frío de la Tierra?", "a": ["océano ártico", "ártico"], "w": ["Océano Pacífico", "Océano Atlántico", "Océano Índico", "Océano Antártico"]},
     "fr": {"q": "Quel est l'océan le plus froid de la Terre ?", "a": ["océan arctique", "arctique"], "w": ["Océan Pacifique", "Océan Atlantique", "Océan Indien", "Océan Austral"]},
     "lt": {"q": "Koks yra šalčiausias vandenynas Žemėje?", "a": ["arkties vandenynas", "arktis"], "w": ["Ramusis vandenynas", "Atlanto vandenynas", "Indijos vandenynas", "Pietų vandenynas"]},
     "ru": {"q": "Какой самый холодный океан на Земле?", "a": ["северный ледовитый океан"], "w": ["Тихий океан", "Атлантический океан", "Индийский океан", "Южный океан"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the freezing point of water in degrees Celsius?", "a": ["0", "zero", "0 degrees"], "w": ["32", "-10", "100", "10"]},
     "de": {"q": "Was ist der Gefrierpunkt von Wasser in Grad Celsius?", "a": ["0", "null", "0 grad"], "w": ["32", "-10", "100", "10"]},
     "es": {"q": "¿Cuál es el punto de congelación del agua en grados Celsius?", "a": ["0", "cero", "0 grados"], "w": ["32", "-10", "100", "10"]},
     "fr": {"q": "Quel est le point de congélation de l'eau en degrés Celsius ?", "a": ["0", "zéro", "0 degré"], "w": ["32", "-10", "100", "10"]},
     "lt": {"q": "Kokia yra vandens užšalimo temperatūra Celsijaus laipsniais?", "a": ["0", "nulis", "0 laipsnių"], "w": ["32", "-10", "100", "10"]},
     "ru": {"q": "Какова температура замерзания воды в градусах Цельсия?", "a": ["0", "ноль", "0 градусов"], "w": ["32", "-10", "100", "10"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the freezing point of water in degrees Fahrenheit?", "a": ["32", "32 degrees"], "w": ["0", "100", "212", "50"]},
     "de": {"q": "Was ist der Gefrierpunkt von Wasser in Grad Fahrenheit?", "a": ["32", "32 grad"], "w": ["0", "100", "212", "50"]},
     "es": {"q": "¿Cuál es el punto de congelación del agua en grados Fahrenheit?", "a": ["32", "32 grados"], "w": ["0", "100", "212", "50"]},
     "fr": {"q": "Quel est le point de congélation de l'eau en degrés Fahrenheit ?", "a": ["32", "32 degrés"], "w": ["0", "100", "212", "50"]},
     "lt": {"q": "Kokia yra vandens užšalimo temperatūra Farenheito laipsniais?", "a": ["32", "32 laipsniai"], "w": ["0", "100", "212", "50"]},
     "ru": {"q": "Какова температура замерзания воды в градусах Фаренгейта?", "a": ["32", "32 градуса"], "w": ["0", "100", "212", "50"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the coldest season of the year?", "a": ["winter"], "w": ["Summer", "Spring", "Autumn", "Monsoon"]},
     "de": {"q": "Was ist die kälteste Jahreszeit?", "a": ["winter"], "w": ["Sommer", "Frühling", "Herbst", "Monsun"]},
     "es": {"q": "¿Cuál es la estación más fría del año?", "a": ["invierno"], "w": ["Verano", "Primavera", "Otoño", "Monzón"]},
     "fr": {"q": "Quelle est la saison la plus froide de l'année ?", "a": ["hiver"], "w": ["Été", "Printemps", "Automne", "Mousson"]},
     "lt": {"q": "Koks yra šalčiausias metų laikas?", "a": ["žiema"], "w": ["Vasara", "Pavasaris", "Ruduo", "Musonas"]},
     "ru": {"q": "Какое самое холодное время года?", "a": ["зима"], "w": ["Лето", "Весна", "Осень", "Муссон"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is frozen water that falls from the sky in white flakes called?", "a": ["snow"], "w": ["Rain", "Hail", "Sleet", "Frost"]},
     "de": {"q": "Wie nennt man gefrorenes Wasser, das in weißen Flocken vom Himmel fällt?", "a": ["schnee"], "w": ["Regen", "Hagel", "Schneeregen", "Frost"]},
     "es": {"q": "¿Cómo se llama el agua congelada que cae del cielo en copos blancos?", "a": ["nieve"], "w": ["Lluvia", "Granizo", "Aguanieve", "Escarcha"]},
     "fr": {"q": "Comment appelle-t-on l'eau gelée qui tombe du ciel en flocons blancs ?", "a": ["neige"], "w": ["Pluie", "Grêle", "Grésil", "Givre"]},
     "lt": {"q": "Kaip vadinamas užšalęs vanduo, krentantis iš dangaus baltomis snaigėmis?", "a": ["sniegas"], "w": ["Lietus", "Kruša", "Šlapdriba", "Šerkšnas"]},
     "ru": {"q": "Как называется замёрзшая вода, падающая с неба белыми хлопьями?", "a": ["снег"], "w": ["Дождь", "Град", "Мокрый снег", "Иней"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a large floating chunk of ice in the ocean called?", "a": ["iceberg", "an iceberg"], "w": ["Glacier", "Ice sheet", "Snowflake", "Avalanche"]},
     "de": {"q": "Wie nennt man einen großen schwimmenden Eisbrocken im Meer?", "a": ["eisberg"], "w": ["Gletscher", "Eisschild", "Schneeflocke", "Lawine"]},
     "es": {"q": "¿Cómo se llama un gran bloque de hielo que flota en el océano?", "a": ["iceberg"], "w": ["Glaciar", "Capa de hielo", "Copo de nieve", "Avalancha"]},
     "fr": {"q": "Comment appelle-t-on un gros bloc de glace qui flotte dans l'océan ?", "a": ["iceberg"], "w": ["Glacier", "Calotte glaciaire", "Flocon de neige", "Avalanche"]},
     "lt": {"q": "Kaip vadinamas didelis plūduriuojantis ledo luitas vandenyne?", "a": ["ledkalnis"], "w": ["Ledynas", "Ledo skydas", "Snaigė", "Lavina"]},
     "ru": {"q": "Как называется большая плавающая глыба льда в океане?", "a": ["айсберг"], "w": ["Ледник", "Ледяной щит", "Снежинка", "Лавина"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a slowly moving mass of ice on land called?", "a": ["glacier", "a glacier"], "w": ["Iceberg", "Avalanche", "Blizzard", "Fjord"]},
     "de": {"q": "Wie nennt man eine sich langsam bewegende Eismasse an Land?", "a": ["gletscher"], "w": ["Eisberg", "Lawine", "Schneesturm", "Fjord"]},
     "es": {"q": "¿Cómo se llama una masa de hielo que se mueve lentamente sobre la tierra?", "a": ["glaciar"], "w": ["Iceberg", "Avalancha", "Ventisca", "Fiordo"]},
     "fr": {"q": "Comment appelle-t-on une masse de glace qui se déplace lentement sur terre ?", "a": ["glacier"], "w": ["Iceberg", "Avalanche", "Blizzard", "Fjord"]},
     "lt": {"q": "Kaip vadinama lėtai judanti ledo masė sausumoje?", "a": ["ledynas"], "w": ["Ledkalnis", "Lavina", "Pūga", "Fjordas"]},
     "ru": {"q": "Как называется медленно движущаяся масса льда на суше?", "a": ["ледник"], "w": ["Айсберг", "Лавина", "Метель", "Фьорд"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is a snowstorm with strong winds and poor visibility called?", "a": ["blizzard", "a blizzard"], "w": ["Hurricane", "Tornado", "Monsoon", "Drizzle"]},
     "de": {"q": "Wie nennt man einen Schneesturm mit starkem Wind und schlechter Sicht?", "a": ["schneesturm", "blizzard"], "w": ["Hurrikan", "Tornado", "Monsun", "Nieselregen"]},
     "es": {"q": "¿Cómo se llama una tormenta de nieve con fuertes vientos y poca visibilidad?", "a": ["ventisca", "tormenta de nieve"], "w": ["Huracán", "Tornado", "Monzón", "Llovizna"]},
     "fr": {"q": "Comment appelle-t-on une tempête de neige avec des vents forts et une faible visibilité ?", "a": ["blizzard", "tempête de neige"], "w": ["Ouragan", "Tornade", "Mousson", "Bruine"]},
     "lt": {"q": "Kaip vadinama sniego audra su stipriu vėju ir prastu matomumu?", "a": ["pūga"], "w": ["Uraganas", "Viesulas", "Musonas", "Dulksna"]},
     "ru": {"q": "Как называется снежная буря с сильным ветром и плохой видимостью?", "a": ["метель", "буран", "вьюга"], "w": ["Ураган", "Торнадо", "Муссон", "Морось"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which US state is the coldest?", "a": ["alaska"], "w": ["Texas", "Florida", "Hawaii", "Arizona"]},
     "de": {"q": "Welcher US-Bundesstaat ist der kälteste?", "a": ["alaska"], "w": ["Texas", "Florida", "Hawaii", "Arizona"]},
     "es": {"q": "¿Cuál es el estado más frío de Estados Unidos?", "a": ["alaska"], "w": ["Texas", "Florida", "Hawái", "Arizona"]},
     "fr": {"q": "Quel est l'État américain le plus froid ?", "a": ["alaska"], "w": ["Texas", "Floride", "Hawaï", "Arizona"]},
     "lt": {"q": "Kuri JAV valstija yra šalčiausia?", "a": ["aliaska"], "w": ["Teksasas", "Florida", "Havajai", "Arizona"]},
     "ru": {"q": "Какой штат США самый холодный?", "a": ["аляска"], "w": ["Техас", "Флорида", "Гавайи", "Аризона"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the largest island in the world, mostly covered in ice?", "a": ["greenland"], "w": ["Iceland", "Madagascar", "Borneo", "New Guinea"]},
     "de": {"q": "Was ist die größte Insel der Welt, die größtenteils von Eis bedeckt ist?", "a": ["grönland"], "w": ["Island", "Madagaskar", "Borneo", "Neuguinea"]},
     "es": {"q": "¿Cuál es la isla más grande del mundo, cubierta en su mayoría de hielo?", "a": ["groenlandia"], "w": ["Islandia", "Madagascar", "Borneo", "Nueva Guinea"]},
     "fr": {"q": "Quelle est la plus grande île du monde, recouverte en grande partie de glace ?", "a": ["groenland"], "w": ["Islande", "Madagascar", "Bornéo", "Nouvelle-Guinée"]},
     "lt": {"q": "Kokia yra didžiausia pasaulio sala, didžiąja dalimi padengta ledu?", "a": ["grenlandija"], "w": ["Islandija", "Madagaskaras", "Borneo", "Naujoji Gvinėja"]},
     "ru": {"q": "Какой самый большой остров в мире, покрытый в основном льдом?", "a": ["гренландия"], "w": ["Исландия", "Мадагаскар", "Борнео", "Новая Гвинея"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which is the largest country in the world by land area?", "a": ["russia"], "w": ["Canada", "China", "United States", "Kazakhstan"]},
     "de": {"q": "Welches ist das größte Land der Welt nach Fläche?", "a": ["russland"], "w": ["Kanada", "China", "Vereinigte Staaten", "Kasachstan"]},
     "es": {"q": "¿Cuál es el país más grande del mundo por superficie?", "a": ["rusia"], "w": ["Canadá", "China", "Estados Unidos", "Kazajistán"]},
     "fr": {"q": "Quel est le plus grand pays du monde par superficie ?", "a": ["russie"], "w": ["Canada", "Chine", "États-Unis", "Kazakhstan"]},
     "lt": {"q": "Kuri šalis yra didžiausia pasaulyje pagal plotą?", "a": ["rusija"], "w": ["Kanada", "Kinija", "Jungtinės Valstijos", "Kazachstanas"]},
     "ru": {"q": "Какая страна самая большая в мире по площади?", "a": ["россия"], "w": ["Канада", "Китай", "США", "Казахстан"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which frozen, treeless biome is found in the far north?", "a": ["tundra", "the tundra"], "w": ["Rainforest", "Savanna", "Desert", "Prairie"]},
     "de": {"q": "Welches gefrorene, baumlose Biom findet man im hohen Norden?", "a": ["tundra"], "w": ["Regenwald", "Savanne", "Wüste", "Prärie"]},
     "es": {"q": "¿Qué bioma helado y sin árboles se encuentra en el extremo norte?", "a": ["tundra"], "w": ["Selva tropical", "Sabana", "Desierto", "Pradera"]},
     "fr": {"q": "Quel biome gelé et sans arbres trouve-t-on dans le grand nord ?", "a": ["toundra"], "w": ["Forêt tropicale", "Savane", "Désert", "Prairie"]},
     "lt": {"q": "Koks užšalęs, bemedis biomas randamas tolimoje šiaurėje?", "a": ["tundra"], "w": ["Atogrąžų miškas", "Savana", "Dykuma", "Prerija"]},
     "ru": {"q": "Какой мёрзлый безлесный биом встречается на крайнем севере?", "a": ["тундра"], "w": ["Тропический лес", "Саванна", "Пустыня", "Прерия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do we call permanently frozen ground?", "a": ["permafrost"], "w": ["Bedrock", "Topsoil", "Quicksand", "Clay"]},
     "de": {"q": "Wie nennt man dauerhaft gefrorenen Boden?", "a": ["permafrost", "dauerfrostboden"], "w": ["Grundgestein", "Mutterboden", "Treibsand", "Ton"]},
     "es": {"q": "¿Cómo llamamos al suelo permanentemente congelado?", "a": ["permafrost", "permagel"], "w": ["Lecho rocoso", "Capa superior del suelo", "Arenas movedizas", "Arcilla"]},
     "fr": {"q": "Comment appelle-t-on un sol gelé en permanence ?", "a": ["pergélisol", "permafrost"], "w": ["Substrat rocheux", "Terre arable", "Sables mouvants", "Argile"]},
     "lt": {"q": "Kaip vadinama nuolat įšalusi žemė?", "a": ["amžinasis įšalas"], "w": ["Uoliena", "Dirvožemis", "Liūnas", "Molis"]},
     "ru": {"q": "Как называется постоянно мёрзлый грунт?", "a": ["вечная мерзлота", "многолетняя мерзлота"], "w": ["Скальная порода", "Почва", "Зыбучий песок", "Глина"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which pole is located in Antarctica?", "a": ["south pole", "the south pole"], "w": ["North Pole", "Magnetic pole", "Equator", "Tropic of Cancer"]},
     "de": {"q": "Welcher Pol liegt in der Antarktis?", "a": ["südpol"], "w": ["Nordpol", "Magnetpol", "Äquator", "Wendekreis des Krebses"]},
     "es": {"q": "¿Qué polo se encuentra en la Antártida?", "a": ["polo sur"], "w": ["Polo Norte", "Polo magnético", "Ecuador", "Trópico de Cáncer"]},
     "fr": {"q": "Quel pôle se trouve en Antarctique ?", "a": ["pôle sud"], "w": ["Pôle Nord", "Pôle magnétique", "Équateur", "Tropique du Cancer"]},
     "lt": {"q": "Kuris polius yra Antarktidoje?", "a": ["pietų polius"], "w": ["Šiaurės ašigalis", "Magnetinis polius", "Pusiaujas", "Vėžio atogrąža"]},
     "ru": {"q": "Какой полюс находится в Антарктиде?", "a": ["южный полюс"], "w": ["Северный полюс", "Магнитный полюс", "Экватор", "Тропик Рака"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What imaginary line marks the boundary of the cold northern polar region?", "a": ["arctic circle", "the arctic circle"], "w": ["Equator", "Prime Meridian", "Tropic of Capricorn", "International Date Line"]},
     "de": {"q": "Welche gedachte Linie markiert die Grenze der kalten nördlichen Polarregion?", "a": ["nördlicher polarkreis", "polarkreis"], "w": ["Äquator", "Nullmeridian", "Wendekreis des Steinbocks", "Datumsgrenze"]},
     "es": {"q": "¿Qué línea imaginaria marca el límite de la fría región polar del norte?", "a": ["círculo polar ártico"], "w": ["Ecuador", "Meridiano de Greenwich", "Trópico de Capricornio", "Línea internacional de cambio de fecha"]},
     "fr": {"q": "Quelle ligne imaginaire marque la limite de la froide région polaire nord ?", "a": ["cercle polaire arctique", "cercle arctique"], "w": ["Équateur", "Méridien de Greenwich", "Tropique du Capricorne", "Ligne de changement de date"]},
     "lt": {"q": "Kuri įsivaizduojama linija žymi šaltojo šiaurės poliarinio regiono ribą?", "a": ["šiaurės poliaratis", "poliaratis"], "w": ["Pusiaujas", "Grinvičo dienovidinis", "Ožiaragio atogrąža", "Datos keitimo linija"]},
     "ru": {"q": "Какая воображаемая линия обозначает границу холодной северной полярной области?", "a": ["северный полярный круг", "полярный круг"], "w": ["Экватор", "Нулевой меридиан", "Тропик Козерога", "Линия перемены дат"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the coldest capital city in the world?", "a": ["ulaanbaatar", "ulan bator"], "w": ["Moscow", "Helsinki", "Reykjavik", "Ottawa"]},
     "de": {"q": "Was ist die kälteste Hauptstadt der Welt?", "a": ["ulaanbaatar", "ulan bator"], "w": ["Moskau", "Helsinki", "Reykjavík", "Ottawa"]},
     "es": {"q": "¿Cuál es la capital más fría del mundo?", "a": ["ulán bator", "ulaanbaatar"], "w": ["Moscú", "Helsinki", "Reikiavik", "Ottawa"]},
     "fr": {"q": "Quelle est la capitale la plus froide du monde ?", "a": ["oulan-bator", "ulaanbaatar"], "w": ["Moscou", "Helsinki", "Reykjavik", "Ottawa"]},
     "lt": {"q": "Koks yra šalčiausias pasaulio sostinės miestas?", "a": ["ulan batoras", "ulanbatoras"], "w": ["Maskva", "Helsinkis", "Reikjavikas", "Otava"]},
     "ru": {"q": "Какая самая холодная столица в мире?", "a": ["улан-батор"], "w": ["Москва", "Хельсинки", "Рейкьявик", "Оттава"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Ulaanbaatar is the capital of which country?", "a": ["mongolia"], "w": ["Russia", "Kazakhstan", "China", "Nepal"]},
     "de": {"q": "Ulaanbaatar ist die Hauptstadt welches Landes?", "a": ["mongolei"], "w": ["Russland", "Kasachstan", "China", "Nepal"]},
     "es": {"q": "¿Ulán Bator es la capital de qué país?", "a": ["mongolia"], "w": ["Rusia", "Kazajistán", "China", "Nepal"]},
     "fr": {"q": "Oulan-Bator est la capitale de quel pays ?", "a": ["mongolie"], "w": ["Russie", "Kazakhstan", "Chine", "Népal"]},
     "lt": {"q": "Ulan Batoras yra kurios šalies sostinė?", "a": ["mongolija"], "w": ["Rusija", "Kazachstanas", "Kinija", "Nepalas"]},
     "ru": {"q": "Улан-Батор — столица какой страны?", "a": ["монголия"], "w": ["Россия", "Казахстан", "Китай", "Непал"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which Nordic region inside the Arctic Circle is famous for snow and reindeer?", "a": ["lapland"], "w": ["Bavaria", "Tuscany", "Andalusia", "Provence"]},
     "de": {"q": "Welche nordische Region innerhalb des Polarkreises ist für Schnee und Rentiere bekannt?", "a": ["lappland"], "w": ["Bayern", "Toskana", "Andalusien", "Provence"]},
     "es": {"q": "¿Qué región nórdica dentro del Círculo Polar Ártico es famosa por la nieve y los renos?", "a": ["laponia"], "w": ["Baviera", "Toscana", "Andalucía", "Provenza"]},
     "fr": {"q": "Quelle région nordique située dans le cercle arctique est célèbre pour la neige et les rennes ?", "a": ["laponie"], "w": ["Bavière", "Toscane", "Andalousie", "Provence"]},
     "lt": {"q": "Kuris Šiaurės regionas Šiaurės poliaratyje garsėja sniegu ir šiaurės elniais?", "a": ["laplandija"], "w": ["Bavarija", "Toskana", "Andalūzija", "Provansas"]},
     "ru": {"q": "Какой скандинавский регион за полярным кругом известен снегом и северными оленями?", "a": ["лапландия"], "w": ["Бавария", "Тоскана", "Андалусия", "Прованс"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Antarctica is mostly covered by what?", "a": ["ice", "an ice sheet", "ice sheet"], "w": ["Sand", "Forest", "Grassland", "Volcanic rock"]},
     "de": {"q": "Womit ist die Antarktis größtenteils bedeckt?", "a": ["eis", "einem eisschild"], "w": ["Sand", "Wald", "Grasland", "Vulkangestein"]},
     "es": {"q": "¿De qué está cubierta la Antártida en su mayor parte?", "a": ["hielo", "una capa de hielo"], "w": ["Arena", "Bosque", "Pradera", "Roca volcánica"]},
     "fr": {"q": "De quoi l'Antarctique est-il principalement recouvert ?", "a": ["glace", "une calotte glaciaire"], "w": ["Sable", "Forêt", "Prairie", "Roche volcanique"]},
     "lt": {"q": "Kuo daugiausia padengta Antarktida?", "a": ["ledu", "ledo skydu"], "w": ["Smėliu", "Mišku", "Pievomis", "Vulkanine uoliena"]},
     "ru": {"q": "Чем в основном покрыта Антарктида?", "a": ["льдом", "ледяным щитом"], "w": ["Песком", "Лесом", "Травой", "Вулканической породой"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which large white bear lives in the cold Arctic?", "a": ["polar bear"], "w": ["Grizzly bear", "Panda", "Sloth bear", "Sun bear"]},
     "de": {"q": "Welcher große weiße Bär lebt in der kalten Arktis?", "a": ["eisbär"], "w": ["Grizzlybär", "Panda", "Lippenbär", "Malaienbär"]},
     "es": {"q": "¿Qué gran oso blanco vive en el frío Ártico?", "a": ["oso polar"], "w": ["Oso pardo", "Panda", "Oso bezudo", "Oso malayo"]},
     "fr": {"q": "Quel grand ours blanc vit dans l'Arctique froid ?", "a": ["ours polaire"], "w": ["Grizzly", "Panda", "Ours lippu", "Ours malais"]},
     "lt": {"q": "Koks didelis baltas lokys gyvena šaltoje Arktyje?", "a": ["baltasis lokys", "poliarinis lokys"], "w": ["Grizlis", "Panda", "Lūpūnas", "Malajinis lokys"]},
     "ru": {"q": "Какой большой белый медведь живёт в холодной Арктике?", "a": ["белый медведь"], "w": ["Гризли", "Панда", "Медведь-губач", "Малайский медведь"]}},

    # ---------------- NORMAL (800 pts) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which research station recorded the coldest natural temperature on Earth?", "a": ["vostok station", "vostok"], "w": ["McMurdo Station", "Amundsen-Scott Station", "Palmer Station", "Casey Station"]},
     "de": {"q": "Welche Forschungsstation hat die kälteste natürliche Temperatur der Erde gemessen?", "a": ["wostok-station", "wostok"], "w": ["McMurdo-Station", "Amundsen-Scott-Station", "Palmer-Station", "Casey-Station"]},
     "es": {"q": "¿Qué estación de investigación registró la temperatura natural más fría de la Tierra?", "a": ["estación vostok", "vostok"], "w": ["Estación McMurdo", "Estación Amundsen-Scott", "Estación Palmer", "Estación Casey"]},
     "fr": {"q": "Quelle station de recherche a enregistré la température naturelle la plus froide sur Terre ?", "a": ["station vostok", "vostok"], "w": ["Station McMurdo", "Station Amundsen-Scott", "Station Palmer", "Station Casey"]},
     "lt": {"q": "Kuri tyrimų stotis užfiksavo šalčiausią natūralią temperatūrą Žemėje?", "a": ["vostok stotis", "vostok"], "w": ["McMurdo stotis", "Amundsen-Scott stotis", "Palmer stotis", "Casey stotis"]},
     "ru": {"q": "Какая научная станция зафиксировала самую низкую естественную температуру на Земле?", "a": ["станция восток", "восток"], "w": ["Станция Мак-Мердо", "Станция Амундсен-Скотт", "Станция Палмер", "Станция Кейси"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Russian village is often called the coldest permanently inhabited place on Earth?", "a": ["oymyakon"], "w": ["Norilsk", "Yakutsk", "Magadan", "Irkutsk"]},
     "de": {"q": "Welches russische Dorf wird oft als der kälteste dauerhaft bewohnte Ort der Erde bezeichnet?", "a": ["oimjakon"], "w": ["Norilsk", "Jakutsk", "Magadan", "Irkutsk"]},
     "es": {"q": "¿Qué aldea rusa suele llamarse el lugar habitado permanentemente más frío de la Tierra?", "a": ["oimiakón"], "w": ["Norilsk", "Yakutsk", "Magadán", "Irkutsk"]},
     "fr": {"q": "Quel village russe est souvent appelé l'endroit habité en permanence le plus froid de la Terre ?", "a": ["oïmiakon"], "w": ["Norilsk", "Iakoutsk", "Magadan", "Irkoutsk"]},
     "lt": {"q": "Kuris Rusijos kaimas dažnai vadinamas šalčiausia nuolat gyvenama vieta Žemėje?", "a": ["oimiakonas"], "w": ["Norilskas", "Jakutskas", "Magadanas", "Irkutskas"]},
     "ru": {"q": "Какое российское село часто называют самым холодным постоянно населённым местом на Земле?", "a": ["оймякон"], "w": ["Норильск", "Якутск", "Магадан", "Иркутск"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In which country are the cold towns of Oymyakon and Verkhoyansk located?", "a": ["russia"], "w": ["Mongolia", "Canada", "Kazakhstan", "Finland"]},
     "de": {"q": "In welchem Land liegen die kalten Orte Oimjakon und Werchojansk?", "a": ["russland"], "w": ["Mongolei", "Kanada", "Kasachstan", "Finnland"]},
     "es": {"q": "¿En qué país se encuentran las frías localidades de Oimiakón y Verjoyansk?", "a": ["rusia"], "w": ["Mongolia", "Canadá", "Kazajistán", "Finlandia"]},
     "fr": {"q": "Dans quel pays se trouvent les villes froides d'Oïmiakon et de Verkhoïansk ?", "a": ["russie"], "w": ["Mongolie", "Canada", "Kazakhstan", "Finlande"]},
     "lt": {"q": "Kurioje šalyje yra šaltieji Oimiakono ir Verchojansko miestai?", "a": ["rusija"], "w": ["Mongolija", "Kanada", "Kazachstanas", "Suomija"]},
     "ru": {"q": "В какой стране находятся холодные посёлки Оймякон и Верхоянск?", "a": ["россия"], "w": ["Монголия", "Канада", "Казахстан", "Финляндия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which large freshwater lake in Siberia freezes over every winter?", "a": ["lake baikal", "baikal"], "w": ["Lake Victoria", "Caspian Sea", "Lake Titicaca", "Great Bear Lake"]},
     "de": {"q": "Welcher große Süßwassersee in Sibirien friert jeden Winter zu?", "a": ["baikalsee", "baikal"], "w": ["Viktoriasee", "Kaspisches Meer", "Titicacasee", "Großer Bärensee"]},
     "es": {"q": "¿Qué gran lago de agua dulce en Siberia se congela cada invierno?", "a": ["lago baikal", "baikal"], "w": ["Lago Victoria", "Mar Caspio", "Lago Titicaca", "Gran Lago del Oso"]},
     "fr": {"q": "Quel grand lac d'eau douce de Sibérie gèle chaque hiver ?", "a": ["lac baïkal", "baïkal"], "w": ["Lac Victoria", "Mer Caspienne", "Lac Titicaca", "Grand lac de l'Ours"]},
     "lt": {"q": "Kuris didelis gėlavandenis ežeras Sibire užšąla kiekvieną žiemą?", "a": ["baikalo ežeras", "baikalas"], "w": ["Viktorijos ežeras", "Kaspijos jūra", "Titikakos ežeras", "Didysis Meškos ežeras"]},
     "ru": {"q": "Какое большое пресноводное озеро в Сибири замерзает каждую зиму?", "a": ["озеро байкал", "байкал"], "w": ["Озеро Виктория", "Каспийское море", "Озеро Титикака", "Большое Медвежье озеро"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Vostok Station in Antarctica is operated by which country?", "a": ["russia"], "w": ["United States", "Norway", "Australia", "United Kingdom"]},
     "de": {"q": "Die Wostok-Station in der Antarktis wird von welchem Land betrieben?", "a": ["russland"], "w": ["Vereinigte Staaten", "Norwegen", "Australien", "Vereinigtes Königreich"]},
     "es": {"q": "¿Qué país opera la estación Vostok en la Antártida?", "a": ["rusia"], "w": ["Estados Unidos", "Noruega", "Australia", "Reino Unido"]},
     "fr": {"q": "La station Vostok en Antarctique est exploitée par quel pays ?", "a": ["russie"], "w": ["États-Unis", "Norvège", "Australie", "Royaume-Uni"]},
     "lt": {"q": "Kuri šalis valdo Vostok stotį Antarktidoje?", "a": ["rusija"], "w": ["Jungtinės Valstijos", "Norvegija", "Australija", "Jungtinė Karalystė"]},
     "ru": {"q": "Какая страна управляет станцией Восток в Антарктиде?", "a": ["россия"], "w": ["США", "Норвегия", "Австралия", "Великобритания"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which country does the cold territory of Greenland belong to?", "a": ["denmark"], "w": ["Norway", "Iceland", "Canada", "Sweden"]},
     "de": {"q": "Zu welchem Land gehört das kalte Territorium Grönland?", "a": ["dänemark"], "w": ["Norwegen", "Island", "Kanada", "Schweden"]},
     "es": {"q": "¿A qué país pertenece el frío territorio de Groenlandia?", "a": ["dinamarca"], "w": ["Noruega", "Islandia", "Canadá", "Suecia"]},
     "fr": {"q": "À quel pays appartient le froid territoire du Groenland ?", "a": ["danemark"], "w": ["Norvège", "Islande", "Canada", "Suède"]},
     "lt": {"q": "Kuriai šaliai priklauso šaltoji Grenlandijos teritorija?", "a": ["danija"], "w": ["Norvegija", "Islandija", "Kanada", "Švedija"]},
     "ru": {"q": "Какой стране принадлежит холодная территория Гренландии?", "a": ["дания"], "w": ["Норвегия", "Исландия", "Канада", "Швеция"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Canadian territory in the Arctic experiences extreme cold?", "a": ["nunavut"], "w": ["Ontario", "Quebec", "Alberta", "Manitoba"]},
     "de": {"q": "Welches kanadische Territorium in der Arktis erlebt extreme Kälte?", "a": ["nunavut"], "w": ["Ontario", "Québec", "Alberta", "Manitoba"]},
     "es": {"q": "¿Qué territorio canadiense en el Ártico experimenta un frío extremo?", "a": ["nunavut"], "w": ["Ontario", "Quebec", "Alberta", "Manitoba"]},
     "fr": {"q": "Quel territoire canadien de l'Arctique connaît un froid extrême ?", "a": ["nunavut"], "w": ["Ontario", "Québec", "Alberta", "Manitoba"]},
     "lt": {"q": "Kuri Kanados teritorija Arktyje patiria ekstremalų šaltį?", "a": ["nunavutas"], "w": ["Ontarijas", "Kvebekas", "Alberta", "Manitoba"]},
     "ru": {"q": "Какая канадская территория в Арктике испытывает экстремальный холод?", "a": ["нунавут"], "w": ["Онтарио", "Квебек", "Альберта", "Манитоба"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the coldest type of desert on Earth?", "a": ["polar desert", "antarctic desert"], "w": ["Sahara", "Gobi", "Atacama", "Arabian"]},
     "de": {"q": "Was ist die kälteste Wüstenart der Erde?", "a": ["polarwüste", "kältewüste"], "w": ["Sahara", "Gobi", "Atacama", "Arabische Wüste"]},
     "es": {"q": "¿Cuál es el tipo de desierto más frío de la Tierra?", "a": ["desierto polar", "desierto antártico"], "w": ["Sahara", "Gobi", "Atacama", "Desierto arábigo"]},
     "fr": {"q": "Quel est le type de désert le plus froid de la Terre ?", "a": ["désert polaire", "désert antarctique"], "w": ["Sahara", "Gobi", "Atacama", "Désert d'Arabie"]},
     "lt": {"q": "Kokia yra šalčiausia dykumos rūšis Žemėje?", "a": ["poliarinė dykuma", "antarktinė dykuma"], "w": ["Sachara", "Gobis", "Atakama", "Arabijos dykuma"]},
     "ru": {"q": "Какой самый холодный тип пустыни на Земле?", "a": ["полярная пустыня", "арктическая пустыня"], "w": ["Сахара", "Гоби", "Атакама", "Аравийская пустыня"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "On which continent is the South Pole located?", "a": ["antarctica"], "w": ["South America", "Australia", "Africa", "Asia"]},
     "de": {"q": "Auf welchem Kontinent liegt der Südpol?", "a": ["antarktis", "antarktika"], "w": ["Südamerika", "Australien", "Afrika", "Asien"]},
     "es": {"q": "¿En qué continente se encuentra el Polo Sur?", "a": ["antártida"], "w": ["América del Sur", "Australia", "África", "Asia"]},
     "fr": {"q": "Sur quel continent se trouve le pôle Sud ?", "a": ["antarctique"], "w": ["Amérique du Sud", "Australie", "Afrique", "Asie"]},
     "lt": {"q": "Kuriame žemyne yra Pietų polius?", "a": ["antarktida"], "w": ["Pietų Amerika", "Australija", "Afrika", "Azija"]},
     "ru": {"q": "На каком континенте находится Южный полюс?", "a": ["антарктида"], "w": ["Южная Америка", "Австралия", "Африка", "Азия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Approximately what was the coldest natural temperature ever recorded on Earth, in Celsius?", "a": ["-89", "-89.2", "minus 89"], "w": ["-50", "-70", "-100", "-120"]},
     "de": {"q": "Wie hoch war ungefähr die kälteste jemals auf der Erde gemessene natürliche Temperatur in Celsius?", "a": ["-89", "-89,2", "minus 89"], "w": ["-50", "-70", "-100", "-120"]},
     "es": {"q": "¿Cuál fue aproximadamente la temperatura natural más fría jamás registrada en la Tierra, en Celsius?", "a": ["-89", "-89,2", "menos 89"], "w": ["-50", "-70", "-100", "-120"]},
     "fr": {"q": "Quelle a été approximativement la température naturelle la plus froide jamais enregistrée sur Terre, en Celsius ?", "a": ["-89", "-89,2", "moins 89"], "w": ["-50", "-70", "-100", "-120"]},
     "lt": {"q": "Kokia buvo maždaug šalčiausia kada nors Žemėje užfiksuota natūrali temperatūra Celsijaus laipsniais?", "a": ["-89", "-89,2", "minus 89"], "w": ["-50", "-70", "-100", "-120"]},
     "ru": {"q": "Какой примерно была самая низкая естественная температура, зафиксированная на Земле, в градусах Цельсия?", "a": ["-89", "-89,2", "минус 89"], "w": ["-50", "-70", "-100", "-120"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is absolute zero, approximately, in degrees Celsius?", "a": ["-273", "-273.15", "minus 273"], "w": ["0", "-100", "-173", "-373"]},
     "de": {"q": "Was ist der absolute Nullpunkt ungefähr in Grad Celsius?", "a": ["-273", "-273,15", "minus 273"], "w": ["0", "-100", "-173", "-373"]},
     "es": {"q": "¿Cuál es el cero absoluto, aproximadamente, en grados Celsius?", "a": ["-273", "-273,15", "menos 273"], "w": ["0", "-100", "-173", "-373"]},
     "fr": {"q": "Quel est le zéro absolu, approximativement, en degrés Celsius ?", "a": ["-273", "-273,15", "moins 273"], "w": ["0", "-100", "-173", "-373"]},
     "lt": {"q": "Kokia yra absoliutaus nulio temperatūra maždaug Celsijaus laipsniais?", "a": ["-273", "-273,15", "minus 273"], "w": ["0", "-100", "-173", "-373"]},
     "ru": {"q": "Чему примерно равен абсолютный ноль в градусах Цельсия?", "a": ["-273", "-273,15", "минус 273"], "w": ["0", "-100", "-173", "-373"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which temperature scale starts at absolute zero?", "a": ["kelvin"], "w": ["Celsius", "Fahrenheit", "Newton", "Réaumur"]},
     "de": {"q": "Welche Temperaturskala beginnt beim absoluten Nullpunkt?", "a": ["kelvin"], "w": ["Celsius", "Fahrenheit", "Newton", "Réaumur"]},
     "es": {"q": "¿Qué escala de temperatura comienza en el cero absoluto?", "a": ["kelvin"], "w": ["Celsius", "Fahrenheit", "Newton", "Réaumur"]},
     "fr": {"q": "Quelle échelle de température commence au zéro absolu ?", "a": ["kelvin"], "w": ["Celsius", "Fahrenheit", "Newton", "Réaumur"]},
     "lt": {"q": "Kuri temperatūros skalė prasideda nuo absoliutaus nulio?", "a": ["kelvinas"], "w": ["Celsijus", "Farenheitas", "Niutonas", "Reomiuras"]},
     "ru": {"q": "Какая температурная шкала начинается с абсолютного нуля?", "a": ["кельвин"], "w": ["Цельсий", "Фаренгейт", "Ньютон", "Реомюр"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which US city in Minnesota is nicknamed the 'Icebox of the Nation'?", "a": ["international falls"], "w": ["Duluth", "Minneapolis", "Fargo", "Bismarck"]},
     "de": {"q": "Welche US-Stadt in Minnesota trägt den Spitznamen 'Icebox of the Nation'?", "a": ["international falls"], "w": ["Duluth", "Minneapolis", "Fargo", "Bismarck"]},
     "es": {"q": "¿Qué ciudad de Minnesota, en EE. UU., es apodada la 'Nevera de la Nación'?", "a": ["international falls"], "w": ["Duluth", "Mineápolis", "Fargo", "Bismarck"]},
     "fr": {"q": "Quelle ville américaine du Minnesota est surnommée la « glacière de la nation » ?", "a": ["international falls"], "w": ["Duluth", "Minneapolis", "Fargo", "Bismarck"]},
     "lt": {"q": "Kuris JAV Minesotos miestas pramintas 'Tautos šaldytuvu'?", "a": ["international falls"], "w": ["Dulutas", "Mineapolis", "Fargas", "Bismarkas"]},
     "ru": {"q": "Какой город США в Миннесоте прозвали 'холодильником нации'?", "a": ["интернешнл-фолс"], "w": ["Дулут", "Миннеаполис", "Фарго", "Бисмарк"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Alaskan city is known for extremely cold winters near the interior?", "a": ["fairbanks"], "w": ["Anchorage", "Juneau", "Sitka", "Kodiak"]},
     "de": {"q": "Welche Stadt in Alaska ist für extrem kalte Winter im Landesinneren bekannt?", "a": ["fairbanks"], "w": ["Anchorage", "Juneau", "Sitka", "Kodiak"]},
     "es": {"q": "¿Qué ciudad de Alaska es conocida por sus inviernos extremadamente fríos en el interior?", "a": ["fairbanks"], "w": ["Anchorage", "Juneau", "Sitka", "Kodiak"]},
     "fr": {"q": "Quelle ville d'Alaska est connue pour ses hivers extrêmement froids à l'intérieur des terres ?", "a": ["fairbanks"], "w": ["Anchorage", "Juneau", "Sitka", "Kodiak"]},
     "lt": {"q": "Kuris Aliaskos miestas garsėja itin šaltomis žiemomis krašto viduje?", "a": ["fērbanksas", "fairbanks"], "w": ["Ankoridžas", "Džuno", "Sitka", "Kodiakas"]},
     "ru": {"q": "Какой город Аляски известен крайне холодными зимами во внутренней части?", "a": ["фэрбанкс"], "w": ["Анкоридж", "Джуно", "Ситка", "Кадьяк"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the frozen water that covers the surface of the Arctic Ocean called?", "a": ["sea ice"], "w": ["Icebergs", "Glaciers", "Permafrost", "Snowpack"]},
     "de": {"q": "Wie nennt man das gefrorene Wasser, das die Oberfläche des Arktischen Ozeans bedeckt?", "a": ["meereis"], "w": ["Eisberge", "Gletscher", "Permafrost", "Schneedecke"]},
     "es": {"q": "¿Cómo se llama el agua congelada que cubre la superficie del océano Ártico?", "a": ["hielo marino", "banquisa"], "w": ["Icebergs", "Glaciares", "Permafrost", "Manto de nieve"]},
     "fr": {"q": "Comment appelle-t-on l'eau gelée qui recouvre la surface de l'océan Arctique ?", "a": ["banquise", "glace de mer"], "w": ["Icebergs", "Glaciers", "Pergélisol", "Manteau neigeux"]},
     "lt": {"q": "Kaip vadinamas užšalęs vanduo, dengiantis Arkties vandenyno paviršių?", "a": ["jūros ledas"], "w": ["Ledkalniai", "Ledynai", "Amžinasis įšalas", "Sniego danga"]},
     "ru": {"q": "Как называется замёрзшая вода, покрывающая поверхность Северного Ледовитого океана?", "a": ["морской лёд"], "w": ["Айсберги", "Ледники", "Вечная мерзлота", "Снежный покров"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is a sudden slide of snow down a mountain slope called?", "a": ["avalanche", "an avalanche"], "w": ["Landslide", "Blizzard", "Rockfall", "Tsunami"]},
     "de": {"q": "Wie nennt man ein plötzliches Abrutschen von Schnee einen Berghang hinunter?", "a": ["lawine"], "w": ["Erdrutsch", "Schneesturm", "Steinschlag", "Tsunami"]},
     "es": {"q": "¿Cómo se llama un deslizamiento repentino de nieve por la ladera de una montaña?", "a": ["avalancha", "alud"], "w": ["Deslizamiento de tierra", "Ventisca", "Desprendimiento de rocas", "Tsunami"]},
     "fr": {"q": "Comment appelle-t-on une chute soudaine de neige le long d'une pente de montagne ?", "a": ["avalanche"], "w": ["Glissement de terrain", "Blizzard", "Chute de pierres", "Tsunami"]},
     "lt": {"q": "Kaip vadinamas staigus sniego nuošliauža kalno šlaitu?", "a": ["lavina", "sniego griūtis"], "w": ["Nuošliauža", "Pūga", "Uolų nuošliauža", "Cunamis"]},
     "ru": {"q": "Как называется внезапный сход снега по склону горы?", "a": ["лавина"], "w": ["Оползень", "Метель", "Камнепад", "Цунами"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the northern polar region centered on the North Pole called?", "a": ["the arctic", "arctic"], "w": ["Antarctic", "Tundra", "Siberia", "Scandinavia"]},
     "de": {"q": "Wie nennt man die nördliche Polarregion rund um den Nordpol?", "a": ["arktis", "die arktis"], "w": ["Antarktis", "Tundra", "Sibirien", "Skandinavien"]},
     "es": {"q": "¿Cómo se llama la región polar norte centrada en el Polo Norte?", "a": ["el ártico", "ártico"], "w": ["Antártico", "Tundra", "Siberia", "Escandinavia"]},
     "fr": {"q": "Comment appelle-t-on la région polaire nord centrée sur le pôle Nord ?", "a": ["l'arctique", "arctique"], "w": ["Antarctique", "Toundra", "Sibérie", "Scandinavie"]},
     "lt": {"q": "Kaip vadinamas šiaurinis poliarinis regionas aplink Šiaurės ašigalį?", "a": ["arktis"], "w": ["Antarktis", "Tundra", "Sibiras", "Skandinavija"]},
     "ru": {"q": "Как называется северная полярная область вокруг Северного полюса?", "a": ["арктика"], "w": ["Антарктика", "Тундра", "Сибирь", "Скандинавия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the process by which liquid water turns into solid ice called?", "a": ["freezing"], "w": ["Melting", "Boiling", "Condensation", "Evaporation"]},
     "de": {"q": "Wie nennt man den Vorgang, bei dem flüssiges Wasser zu festem Eis wird?", "a": ["gefrieren", "erstarren"], "w": ["Schmelzen", "Sieden", "Kondensation", "Verdunstung"]},
     "es": {"q": "¿Cómo se llama el proceso por el cual el agua líquida se convierte en hielo sólido?", "a": ["congelación", "solidificación"], "w": ["Fusión", "Ebullición", "Condensación", "Evaporación"]},
     "fr": {"q": "Comment appelle-t-on le processus par lequel l'eau liquide se transforme en glace solide ?", "a": ["congélation", "solidification"], "w": ["Fusion", "Ébullition", "Condensation", "Évaporation"]},
     "lt": {"q": "Kaip vadinamas procesas, kai skystas vanduo virsta kietu ledu?", "a": ["užšalimas", "kietėjimas"], "w": ["Tirpimas", "Virimas", "Kondensacija", "Garavimas"]},
     "ru": {"q": "Как называется процесс превращения жидкой воды в твёрдый лёд?", "a": ["замерзание", "кристаллизация"], "w": ["Плавление", "Кипение", "Конденсация", "Испарение"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is a deep crack in a glacier called?", "a": ["crevasse", "a crevasse"], "w": ["Canyon", "Fjord", "Gorge", "Ravine"]},
     "de": {"q": "Wie nennt man einen tiefen Spalt in einem Gletscher?", "a": ["gletscherspalte"], "w": ["Canyon", "Fjord", "Schlucht", "Klamm"]},
     "es": {"q": "¿Cómo se llama una grieta profunda en un glaciar?", "a": ["grieta", "grieta glaciar"], "w": ["Cañón", "Fiordo", "Garganta", "Barranco"]},
     "fr": {"q": "Comment appelle-t-on une fissure profonde dans un glacier ?", "a": ["crevasse"], "w": ["Canyon", "Fjord", "Gorge", "Ravin"]},
     "lt": {"q": "Kaip vadinamas gilus plyšys ledyne?", "a": ["ledyno plyšys"], "w": ["Kanjonas", "Fjordas", "Tarpeklis", "Griova"]},
     "ru": {"q": "Как называется глубокая трещина в леднике?", "a": ["ледниковая трещина", "трещина"], "w": ["Каньон", "Фьорд", "Ущелье", "Овраг"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is a narrow sea inlet carved by glaciers, common in Norway, called?", "a": ["fjord", "a fjord"], "w": ["Bay", "Lagoon", "Strait", "Delta"]},
     "de": {"q": "Wie nennt man eine schmale, von Gletschern geformte Meeresbucht, die in Norwegen häufig vorkommt?", "a": ["fjord"], "w": ["Bucht", "Lagune", "Meerenge", "Delta"]},
     "es": {"q": "¿Cómo se llama una estrecha entrada de mar formada por glaciares, común en Noruega?", "a": ["fiordo"], "w": ["Bahía", "Laguna", "Estrecho", "Delta"]},
     "fr": {"q": "Comment appelle-t-on une étroite entrée de mer creusée par les glaciers, fréquente en Norvège ?", "a": ["fjord"], "w": ["Baie", "Lagune", "Détroit", "Delta"]},
     "lt": {"q": "Kaip vadinamas siauras, ledynų išraižytas jūros įlankos ruožas, dažnas Norvegijoje?", "a": ["fjordas"], "w": ["Įlanka", "Lagūna", "Sąsiauris", "Delta"]},
     "ru": {"q": "Как называется узкий морской залив, образованный ледниками и распространённый в Норвегии?", "a": ["фьорд"], "w": ["Бухта", "Лагуна", "Пролив", "Дельта"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Siberia, one of the coldest inhabited regions, is part of which country?", "a": ["russia"], "w": ["Mongolia", "China", "Kazakhstan", "Canada"]},
     "de": {"q": "Sibirien, eine der kältesten bewohnten Regionen, gehört zu welchem Land?", "a": ["russland"], "w": ["Mongolei", "China", "Kasachstan", "Kanada"]},
     "es": {"q": "Siberia, una de las regiones habitadas más frías, forma parte de qué país?", "a": ["rusia"], "w": ["Mongolia", "China", "Kazajistán", "Canadá"]},
     "fr": {"q": "La Sibérie, l'une des régions habitées les plus froides, fait partie de quel pays ?", "a": ["russie"], "w": ["Mongolie", "Chine", "Kazakhstan", "Canada"]},
     "lt": {"q": "Sibiras, vienas šalčiausių apgyvendintų regionų, priklauso kuriai šaliai?", "a": ["rusija"], "w": ["Mongolija", "Kinija", "Kazachstanas", "Kanada"]},
     "ru": {"q": "Сибирь, один из самых холодных населённых регионов, входит в состав какой страны?", "a": ["россия"], "w": ["Монголия", "Китай", "Казахстан", "Канада"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which flightless black-and-white bird lives in the cold Antarctic?", "a": ["penguin"], "w": ["Polar bear", "Puffin", "Albatross", "Arctic tern"]},
     "de": {"q": "Welcher flugunfähige schwarz-weiße Vogel lebt in der kalten Antarktis?", "a": ["pinguin"], "w": ["Eisbär", "Papageitaucher", "Albatros", "Küstenseeschwalbe"]},
     "es": {"q": "¿Qué ave blanca y negra no voladora vive en la fría Antártida?", "a": ["pingüino"], "w": ["Oso polar", "Frailecillo", "Albatros", "Charrán ártico"]},
     "fr": {"q": "Quel oiseau noir et blanc incapable de voler vit dans l'Antarctique froid ?", "a": ["manchot", "pingouin"], "w": ["Ours polaire", "Macareux", "Albatros", "Sterne arctique"]},
     "lt": {"q": "Koks neskraidantis juodai baltas paukštis gyvena šaltoje Antarktidoje?", "a": ["pingvinas"], "w": ["Baltasis lokys", "Šarkis", "Albatrosas", "Poliarinė žuvėdra"]},
     "ru": {"q": "Какая нелетающая чёрно-белая птица живёт в холодной Антарктиде?", "a": ["пингвин"], "w": ["Белый медведь", "Тупик", "Альбатрос", "Полярная крачка"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the mixture of rain and snow falling together called?", "a": ["sleet"], "w": ["Hail", "Frost", "Drizzle", "Mist"]},
     "de": {"q": "Wie nennt man die Mischung aus Regen und Schnee, die zusammen fällt?", "a": ["schneeregen"], "w": ["Hagel", "Frost", "Nieselregen", "Nebel"]},
     "es": {"q": "¿Cómo se llama la mezcla de lluvia y nieve que cae junta?", "a": ["aguanieve"], "w": ["Granizo", "Escarcha", "Llovizna", "Neblina"]},
     "fr": {"q": "Comment appelle-t-on le mélange de pluie et de neige qui tombe ensemble ?", "a": ["grésil", "neige fondue"], "w": ["Grêle", "Givre", "Bruine", "Brume"]},
     "lt": {"q": "Kaip vadinamas kartu krentantis lietaus ir sniego mišinys?", "a": ["šlapdriba"], "w": ["Kruša", "Šerkšnas", "Dulksna", "Rūkas"]},
     "ru": {"q": "Как называется смесь дождя и снега, выпадающая вместе?", "a": ["мокрый снег"], "w": ["Град", "Иней", "Морось", "Туман"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is frozen dew that forms a thin white layer on cold surfaces called?", "a": ["frost"], "w": ["Snow", "Hail", "Dew", "Mist"]},
     "de": {"q": "Wie nennt man gefrorenen Tau, der eine dünne weiße Schicht auf kalten Oberflächen bildet?", "a": ["frost", "raureif"], "w": ["Schnee", "Hagel", "Tau", "Nebel"]},
     "es": {"q": "¿Cómo se llama el rocío congelado que forma una fina capa blanca sobre superficies frías?", "a": ["escarcha"], "w": ["Nieve", "Granizo", "Rocío", "Neblina"]},
     "fr": {"q": "Comment appelle-t-on la rosée gelée qui forme une fine couche blanche sur les surfaces froides ?", "a": ["givre", "gelée blanche"], "w": ["Neige", "Grêle", "Rosée", "Brume"]},
     "lt": {"q": "Kaip vadinama užšalusi rasa, ant šaltų paviršių sudaranti ploną baltą sluoksnį?", "a": ["šerkšnas"], "w": ["Sniegas", "Kruša", "Rasa", "Rūkas"]},
     "ru": {"q": "Как называется замёрзшая роса, образующая тонкий белый слой на холодных поверхностях?", "a": ["иней"], "w": ["Снег", "Град", "Роса", "Туман"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which hard balls of ice that fall during storms are called what?", "a": ["hail", "hailstones"], "w": ["Snow", "Sleet", "Frost", "Drizzle"]},
     "de": {"q": "Wie nennt man die harten Eiskugeln, die bei Gewittern fallen?", "a": ["hagel"], "w": ["Schnee", "Schneeregen", "Frost", "Nieselregen"]},
     "es": {"q": "¿Cómo se llaman las duras bolas de hielo que caen durante las tormentas?", "a": ["granizo"], "w": ["Nieve", "Aguanieve", "Escarcha", "Llovizna"]},
     "fr": {"q": "Comment appelle-t-on les dures billes de glace qui tombent pendant les orages ?", "a": ["grêle", "grêlons"], "w": ["Neige", "Grésil", "Givre", "Bruine"]},
     "lt": {"q": "Kaip vadinami kieti ledo rutuliukai, krentantys per audras?", "a": ["kruša"], "w": ["Sniegas", "Šlapdriba", "Šerkšnas", "Dulksna"]},
     "ru": {"q": "Как называются твёрдые ледяные шарики, выпадающие во время гроз?", "a": ["град"], "w": ["Снег", "Мокрый снег", "Иней", "Морось"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which large ice mass covering most of a continent is Antarctica's defining feature?", "a": ["ice sheet", "antarctic ice sheet"], "w": ["Coral reef", "Sand dune", "Rainforest", "Volcano"]},
     "de": {"q": "Welche große Eismasse, die den größten Teil eines Kontinents bedeckt, ist das prägende Merkmal der Antarktis?", "a": ["eisschild", "antarktischer eisschild"], "w": ["Korallenriff", "Sanddüne", "Regenwald", "Vulkan"]},
     "es": {"q": "¿Qué gran masa de hielo que cubre la mayor parte de un continente es el rasgo característico de la Antártida?", "a": ["capa de hielo", "manto de hielo antártico"], "w": ["Arrecife de coral", "Duna de arena", "Selva tropical", "Volcán"]},
     "fr": {"q": "Quelle grande masse de glace couvrant la majeure partie d'un continent est la caractéristique de l'Antarctique ?", "a": ["calotte glaciaire", "inlandsis antarctique"], "w": ["Récif de corail", "Dune de sable", "Forêt tropicale", "Volcan"]},
     "lt": {"q": "Kokia didelė ledo masė, dengianti didžiąją žemyno dalį, yra būdingiausias Antarktidos bruožas?", "a": ["ledo skydas", "antarktidos ledo skydas"], "w": ["Koralų rifas", "Smėlio kopa", "Atogrąžų miškas", "Ugnikalnis"]},
     "ru": {"q": "Какая крупная ледяная масса, покрывающая большую часть материка, является главной чертой Антарктиды?", "a": ["ледяной щит", "антарктический ледяной щит"], "w": ["Коралловый риф", "Песчаная дюна", "Тропический лес", "Вулкан"]}},

    # ---------------- BUFFER candidates (used only if dedup drops some above) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "What are the colourful lights sometimes seen in cold Arctic skies called?", "a": ["aurora borealis", "northern lights"], "w": ["Rainbow", "Sunbeam", "Comet", "Meteor shower"]},
     "de": {"q": "Wie nennt man die bunten Lichter, die manchmal am kalten arktischen Himmel zu sehen sind?", "a": ["polarlicht", "nordlicht", "aurora borealis"], "w": ["Regenbogen", "Sonnenstrahl", "Komet", "Meteorschauer"]},
     "es": {"q": "¿Cómo se llaman las luces de colores que a veces se ven en el frío cielo ártico?", "a": ["aurora boreal"], "w": ["Arcoíris", "Rayo de sol", "Cometa", "Lluvia de meteoros"]},
     "fr": {"q": "Comment appelle-t-on les lumières colorées parfois visibles dans le ciel arctique froid ?", "a": ["aurore boréale"], "w": ["Arc-en-ciel", "Rayon de soleil", "Comète", "Pluie de météores"]},
     "lt": {"q": "Kaip vadinamos spalvingos šviesos, kartais matomos šaltame Arkties danguje?", "a": ["šiaurės pašvaistė", "aurora borealis"], "w": ["Vaivorykštė", "Saulės spindulys", "Kometa", "Meteorų lietus"]},
     "ru": {"q": "Как называются цветные огни, которые иногда видны в холодном арктическом небе?", "a": ["северное сияние", "полярное сияние"], "w": ["Радуга", "Солнечный луч", "Комета", "Метеорный поток"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "A dome-shaped shelter built from blocks of snow by Arctic peoples is called what?", "a": ["igloo", "an igloo"], "w": ["Yurt", "Tepee", "Cabin", "Bungalow"]},
     "de": {"q": "Wie nennt man eine kuppelförmige Unterkunft, die von arktischen Völkern aus Schneeblöcken gebaut wird?", "a": ["iglu"], "w": ["Jurte", "Tipi", "Hütte", "Bungalow"]},
     "es": {"q": "¿Cómo se llama un refugio en forma de cúpula construido con bloques de nieve por los pueblos árticos?", "a": ["iglú"], "w": ["Yurta", "Tipi", "Cabaña", "Bungaló"]},
     "fr": {"q": "Comment appelle-t-on un abri en forme de dôme construit avec des blocs de neige par les peuples arctiques ?", "a": ["igloo"], "w": ["Yourte", "Tipi", "Cabane", "Bungalow"]},
     "lt": {"q": "Kaip vadinamas kupolo formos pastogė, arkties tautų statoma iš sniego blokų?", "a": ["iglu"], "w": ["Jurta", "Tipi", "Trobelė", "Bungalas"]},
     "ru": {"q": "Как называется куполообразное жилище из снежных блоков, которое строят арктические народы?", "a": ["иглу"], "w": ["Юрта", "Типи", "Хижина", "Бунгало"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which cold sea between Russia and Alaska is named after an explorer?", "a": ["bering sea", "bering"], "w": ["Red Sea", "Black Sea", "Coral Sea", "Yellow Sea"]},
     "de": {"q": "Welches kalte Meer zwischen Russland und Alaska ist nach einem Entdecker benannt?", "a": ["beringmeer", "bering"], "w": ["Rotes Meer", "Schwarzes Meer", "Korallenmeer", "Gelbes Meer"]},
     "es": {"q": "¿Qué mar frío entre Rusia y Alaska lleva el nombre de un explorador?", "a": ["mar de bering", "bering"], "w": ["Mar Rojo", "Mar Negro", "Mar del Coral", "Mar Amarillo"]},
     "fr": {"q": "Quelle mer froide entre la Russie et l'Alaska porte le nom d'un explorateur ?", "a": ["mer de béring", "béring"], "w": ["Mer Rouge", "Mer Noire", "Mer de Corail", "Mer Jaune"]},
     "lt": {"q": "Kuri šalta jūra tarp Rusijos ir Aliaskos pavadinta tyrinėtojo vardu?", "a": ["beringo jūra", "beringas"], "w": ["Raudonoji jūra", "Juodoji jūra", "Koralų jūra", "Geltonoji jūra"]},
     "ru": {"q": "Какое холодное море между Россией и Аляской названо в честь исследователя?", "a": ["берингово море", "беринг"], "w": ["Красное море", "Чёрное море", "Коралловое море", "Жёлтое море"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the coldest inhabited town of Verkhoyansk located in, region-wise?", "a": ["siberia"], "w": ["Scandinavia", "Patagonia", "Alaska", "Tibet"]},
     "de": {"q": "In welcher Region liegt die kalte bewohnte Stadt Werchojansk?", "a": ["sibirien"], "w": ["Skandinavien", "Patagonien", "Alaska", "Tibet"]},
     "es": {"q": "¿En qué región se encuentra la fría localidad habitada de Verjoyansk?", "a": ["siberia"], "w": ["Escandinavia", "Patagonia", "Alaska", "Tíbet"]},
     "fr": {"q": "Dans quelle région se trouve la froide ville habitée de Verkhoïansk ?", "a": ["sibérie"], "w": ["Scandinavie", "Patagonie", "Alaska", "Tibet"]},
     "lt": {"q": "Kuriame regione yra šaltas apgyvendintas Verchojansko miestas?", "a": ["sibiras"], "w": ["Skandinavija", "Patagonija", "Aliaska", "Tibetas"]},
     "ru": {"q": "В каком регионе находится холодный населённый город Верхоянск?", "a": ["сибирь"], "w": ["Скандинавия", "Патагония", "Аляска", "Тибет"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The chilly southern ocean surrounding Antarctica is called what?", "a": ["southern ocean", "antarctic ocean"], "w": ["Arctic Ocean", "Indian Ocean", "Baltic Sea", "Caribbean Sea"]},
     "de": {"q": "Wie heißt der kalte südliche Ozean, der die Antarktis umgibt?", "a": ["südlicher ozean", "südpolarmeer"], "w": ["Arktischer Ozean", "Indischer Ozean", "Ostsee", "Karibisches Meer"]},
     "es": {"q": "¿Cómo se llama el frío océano del sur que rodea la Antártida?", "a": ["océano antártico", "océano austral"], "w": ["Océano Ártico", "Océano Índico", "Mar Báltico", "Mar Caribe"]},
     "fr": {"q": "Comment s'appelle le froid océan sud qui entoure l'Antarctique ?", "a": ["océan austral", "océan antarctique"], "w": ["Océan Arctique", "Océan Indien", "Mer Baltique", "Mer des Caraïbes"]},
     "lt": {"q": "Kaip vadinamas šaltas pietinis vandenynas, supantis Antarktidą?", "a": ["pietų vandenynas", "antarkties vandenynas"], "w": ["Arkties vandenynas", "Indijos vandenynas", "Baltijos jūra", "Karibų jūra"]},
     "ru": {"q": "Как называется холодный южный океан, окружающий Антарктиду?", "a": ["южный океан", "антарктический океан"], "w": ["Северный Ледовитый океан", "Индийский океан", "Балтийское море", "Карибское море"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which cold-climate herding animal is central to life in Arctic Lapland?", "a": ["reindeer"], "w": ["Camel", "Kangaroo", "Llama", "Buffalo"]},
     "de": {"q": "Welches an kaltes Klima angepasste Herdentier ist im arktischen Lappland von zentraler Bedeutung?", "a": ["rentier"], "w": ["Kamel", "Känguru", "Lama", "Büffel"]},
     "es": {"q": "¿Qué animal de pastoreo de clima frío es fundamental en la Laponia ártica?", "a": ["reno"], "w": ["Camello", "Canguro", "Llama", "Búfalo"]},
     "fr": {"q": "Quel animal d'élevage adapté au froid est central dans la Laponie arctique ?", "a": ["renne"], "w": ["Chameau", "Kangourou", "Lama", "Buffle"]},
     "lt": {"q": "Koks šaltam klimatui pritaikytas ganomas gyvūnas yra svarbiausias arktinėje Laplandijoje?", "a": ["šiaurės elnias"], "w": ["Kupranugaris", "Kengūra", "Lama", "Buivolas"]},
     "ru": {"q": "Какое пасущееся животное холодного климата играет ключевую роль в арктической Лапландии?", "a": ["северный олень"], "w": ["Верблюд", "Кенгуру", "Лама", "Буйвол"]}},
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

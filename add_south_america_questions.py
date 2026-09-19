#!/usr/bin/env python3
"""
Batch add: 40 new questions about South America, across the 6 active
languages (en, de, es, fr, lt, ru). Follows QUESTIONS_AUTHORING.md.

  - id = md5(english question text)  (join key across all languages)
  - answers AND wrong_answers lowercase (current standard - both fields)
  - category = "geography"; difficulty easy (700) / normal (800)
  - semantic dedup vs embeddings.json at DEDUP_THRESHOLD (default 0.92),
    including within this batch (new embeddings are added as we go)
  - idempotent: ids already present are skipped; caps additions at TARGET_NEW

The corpus already contains geography questions, so a large buffer with a mix
of easy and normal items follows the core set (so the difficulty split survives
dedup drops). Additions stop once TARGET_NEW is reached.

Usage:
    python add_south_america_questions.py [--dry-run]
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
     "en": {"q": "Which mountain range runs along the western edge of South America?", "a": ["the andes", "andes"], "w": ["the alps", "the rockies", "the himalayas", "the urals"]},
     "de": {"q": "Welches Gebirge verläuft entlang des westlichen Randes Südamerikas?", "a": ["die anden", "anden"], "w": ["die alpen", "die rocky mountains", "der himalaya", "der ural"]},
     "es": {"q": "¿Qué cordillera recorre el borde occidental de Sudamérica?", "a": ["los andes", "andes"], "w": ["los alpes", "las montañas rocosas", "el himalaya", "los urales"]},
     "fr": {"q": "Quelle chaîne de montagnes longe la bordure ouest de l'Amérique du Sud ?", "a": ["les andes", "andes"], "w": ["les alpes", "les rocheuses", "l'himalaya", "l'oural"]},
     "lt": {"q": "Kuri kalnų grandinė driekiasi vakariniu Pietų Amerikos pakraščiu?", "a": ["andai"], "w": ["alpės", "uolieji kalnai", "himalajai", "uralas"]},
     "ru": {"q": "Какая горная цепь тянется вдоль западного края Южной Америки?", "a": ["анды"], "w": ["альпы", "скалистые горы", "гималаи", "урал"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the capital city of Argentina?", "a": ["buenos aires"], "w": ["santiago", "montevideo", "lima", "asunción"]},
     "de": {"q": "Was ist die Hauptstadt von Argentinien?", "a": ["buenos aires"], "w": ["santiago", "montevideo", "lima", "asunción"]},
     "es": {"q": "¿Cuál es la capital de Argentina?", "a": ["buenos aires"], "w": ["santiago", "montevideo", "lima", "asunción"]},
     "fr": {"q": "Quelle est la capitale de l'Argentine ?", "a": ["buenos aires"], "w": ["santiago", "montevideo", "lima", "asunción"]},
     "lt": {"q": "Koks yra Argentinos sostinė?", "a": ["buenos airės"], "w": ["santjagas", "montevidėjas", "lima", "asunsjonas"]},
     "ru": {"q": "Какая столица Аргентины?", "a": ["буэнос-айрес"], "w": ["сантьяго", "монтевидео", "лима", "асунсьон"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the capital city of Peru?", "a": ["lima"], "w": ["quito", "la paz", "bogotá", "santiago"]},
     "de": {"q": "Was ist die Hauptstadt von Peru?", "a": ["lima"], "w": ["quito", "la paz", "bogotá", "santiago"]},
     "es": {"q": "¿Cuál es la capital de Perú?", "a": ["lima"], "w": ["quito", "la paz", "bogotá", "santiago"]},
     "fr": {"q": "Quelle est la capitale du Pérou ?", "a": ["lima"], "w": ["quito", "la paz", "bogotá", "santiago"]},
     "lt": {"q": "Koks yra Peru sostinė?", "a": ["lima"], "w": ["kitas", "la pasas", "bogota", "santjagas"]},
     "ru": {"q": "Какая столица Перу?", "a": ["лима"], "w": ["кито", "ла-пас", "богота", "сантьяго"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which language is most widely spoken in Brazil?", "a": ["portuguese"], "w": ["spanish", "english", "french", "italian"]},
     "de": {"q": "Welche Sprache wird in Brasilien am meisten gesprochen?", "a": ["portugiesisch"], "w": ["spanisch", "englisch", "französisch", "italienisch"]},
     "es": {"q": "¿Qué idioma se habla más en Brasil?", "a": ["portugués"], "w": ["español", "inglés", "francés", "italiano"]},
     "fr": {"q": "Quelle langue est la plus parlée au Brésil ?", "a": ["le portugais", "portugais"], "w": ["l'espagnol", "l'anglais", "le français", "l'italien"]},
     "lt": {"q": "Kuria kalba daugiausia kalbama Brazilijoje?", "a": ["portugalų"], "w": ["ispanų", "anglų", "prancūzų", "italų"]},
     "ru": {"q": "На каком языке больше всего говорят в Бразилии?", "a": ["португальский"], "w": ["испанский", "английский", "французский", "итальянский"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In which South American country is Machu Picchu located?", "a": ["peru"], "w": ["bolivia", "chile", "ecuador", "colombia"]},
     "de": {"q": "In welchem südamerikanischen Land liegt Machu Picchu?", "a": ["peru"], "w": ["bolivien", "chile", "ecuador", "kolumbien"]},
     "es": {"q": "¿En qué país sudamericano se encuentra Machu Picchu?", "a": ["perú"], "w": ["bolivia", "chile", "ecuador", "colombia"]},
     "fr": {"q": "Dans quel pays d'Amérique du Sud se trouve le Machu Picchu ?", "a": ["pérou"], "w": ["bolivie", "chili", "équateur", "colombie"]},
     "lt": {"q": "Kurioje Pietų Amerikos šalyje yra Maču Pikču?", "a": ["peru"], "w": ["bolivija", "čilė", "ekvadoras", "kolumbija"]},
     "ru": {"q": "В какой южноамериканской стране находится Мачу-Пикчу?", "a": ["перу"], "w": ["боливия", "чили", "эквадор", "колумбия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which long, narrow country stretches down the west coast of South America?", "a": ["chile"], "w": ["peru", "argentina", "ecuador", "colombia"]},
     "de": {"q": "Welches lange, schmale Land erstreckt sich entlang der Westküste Südamerikas?", "a": ["chile"], "w": ["peru", "argentinien", "ecuador", "kolumbien"]},
     "es": {"q": "¿Qué país largo y estrecho se extiende por la costa oeste de Sudamérica?", "a": ["chile"], "w": ["perú", "argentina", "ecuador", "colombia"]},
     "fr": {"q": "Quel pays long et étroit s'étend le long de la côte ouest de l'Amérique du Sud ?", "a": ["chili"], "w": ["pérou", "argentine", "équateur", "colombie"]},
     "lt": {"q": "Kuri ilga ir siaura šalis driekiasi Pietų Amerikos vakarų pakrante?", "a": ["čilė"], "w": ["peru", "argentina", "ekvadoras", "kolumbija"]},
     "ru": {"q": "Какая длинная и узкая страна тянется вдоль западного побережья Южной Америки?", "a": ["чили"], "w": ["перу", "аргентина", "эквадор", "колумбия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country is named after the equator that crosses it?", "a": ["ecuador"], "w": ["colombia", "peru", "brazil", "venezuela"]},
     "de": {"q": "Welches südamerikanische Land ist nach dem Äquator benannt, der es durchquert?", "a": ["ecuador"], "w": ["kolumbien", "peru", "brasilien", "venezuela"]},
     "es": {"q": "¿Qué país sudamericano lleva el nombre del ecuador que lo atraviesa?", "a": ["ecuador"], "w": ["colombia", "perú", "brasil", "venezuela"]},
     "fr": {"q": "Quel pays d'Amérique du Sud porte le nom de l'équateur qui le traverse ?", "a": ["équateur"], "w": ["colombie", "pérou", "brésil", "venezuela"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis pavadinta ją kertančio pusiaujo vardu?", "a": ["ekvadoras"], "w": ["kolumbija", "peru", "brazilija", "venesuela"]},
     "ru": {"q": "Какая южноамериканская страна названа в честь пересекающего её экватора?", "a": ["эквадор"], "w": ["колумбия", "перу", "бразилия", "венесуэла"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which country is famous for the tango dance and gaucho cowboys?", "a": ["argentina"], "w": ["brazil", "peru", "chile", "colombia"]},
     "de": {"q": "Welches Land ist für den Tango und die Gaucho-Cowboys berühmt?", "a": ["argentinien"], "w": ["brasilien", "peru", "chile", "kolumbien"]},
     "es": {"q": "¿Qué país es famoso por el baile del tango y los gauchos?", "a": ["argentina"], "w": ["brasil", "perú", "chile", "colombia"]},
     "fr": {"q": "Quel pays est célèbre pour la danse du tango et les gauchos ?", "a": ["argentine"], "w": ["brésil", "pérou", "chili", "colombie"]},
     "lt": {"q": "Kuri šalis garsėja tango šokiu ir gaučais kaubojais?", "a": ["argentina"], "w": ["brazilija", "peru", "čilė", "kolumbija"]},
     "ru": {"q": "Какая страна знаменита танцем танго и ковбоями-гаучо?", "a": ["аргентина"], "w": ["бразилия", "перу", "чили", "колумбия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "The statue of Christ the Redeemer overlooks which city?", "a": ["rio de janeiro", "rio"], "w": ["são paulo", "buenos aires", "lima", "bogotá"]},
     "de": {"q": "Die Christus-Erlöser-Statue überblickt welche Stadt?", "a": ["rio de janeiro", "rio"], "w": ["são paulo", "buenos aires", "lima", "bogotá"]},
     "es": {"q": "¿La estatua del Cristo Redentor domina qué ciudad?", "a": ["río de janeiro", "río"], "w": ["são paulo", "buenos aires", "lima", "bogotá"]},
     "fr": {"q": "La statue du Christ Rédempteur surplombe quelle ville ?", "a": ["rio de janeiro", "rio"], "w": ["são paulo", "buenos aires", "lima", "bogotá"]},
     "lt": {"q": "Kristaus Atpirkėjo statula stūkso virš kurio miesto?", "a": ["rio de žaneiro", "rijas"], "w": ["san paulas", "buenos airės", "lima", "bogota"]},
     "ru": {"q": "Статуя Христа-Искупителя возвышается над каким городом?", "a": ["рио-де-жанейро", "рио"], "w": ["сан-паулу", "буэнос-айрес", "лима", "богота"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which large rainforest covers much of northern South America?", "a": ["the amazon", "amazon rainforest", "amazon"], "w": ["the congo", "the taiga", "borneo rainforest", "the everglades"]},
     "de": {"q": "Welcher große Regenwald bedeckt einen Großteil des nördlichen Südamerikas?", "a": ["der amazonas", "amazonas-regenwald", "amazonas"], "w": ["der kongo", "die taiga", "borneo-regenwald", "die everglades"]},
     "es": {"q": "¿Qué gran selva cubre gran parte del norte de Sudamérica?", "a": ["el amazonas", "la amazonia", "amazonia"], "w": ["el congo", "la taiga", "la selva de borneo", "los everglades"]},
     "fr": {"q": "Quelle grande forêt tropicale couvre une grande partie du nord de l'Amérique du Sud ?", "a": ["l'amazonie", "amazonie"], "w": ["le congo", "la taïga", "la forêt de bornéo", "les everglades"]},
     "lt": {"q": "Koks didelis atogrąžų miškas dengia didelę šiaurinės Pietų Amerikos dalį?", "a": ["amazonė", "amazonės miškas"], "w": ["kongas", "taiga", "borneo miškas", "everglades"]},
     "ru": {"q": "Какой большой тропический лес покрывает значительную часть севера Южной Америки?", "a": ["амазония", "амазонский лес"], "w": ["конго", "тайга", "лес борнео", "эверглейдс"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which colourful bird with a huge beak lives in South American rainforests?", "a": ["toucan", "a toucan"], "w": ["penguin", "ostrich", "flamingo", "owl"]},
     "de": {"q": "Welcher bunte Vogel mit einem riesigen Schnabel lebt in südamerikanischen Regenwäldern?", "a": ["tukan"], "w": ["pinguin", "strauß", "flamingo", "eule"]},
     "es": {"q": "¿Qué ave colorida con un pico enorme vive en las selvas sudamericanas?", "a": ["tucán"], "w": ["pingüino", "avestruz", "flamenco", "búho"]},
     "fr": {"q": "Quel oiseau coloré au bec énorme vit dans les forêts tropicales d'Amérique du Sud ?", "a": ["toucan"], "w": ["manchot", "autruche", "flamant", "hibou"]},
     "lt": {"q": "Koks spalvingas paukštis su didžiuliu snapu gyvena Pietų Amerikos atogrąžų miškuose?", "a": ["tukanas"], "w": ["pingvinas", "strutis", "flamingas", "pelėda"]},
     "ru": {"q": "Какая яркая птица с огромным клювом живёт в тропических лесах Южной Америки?", "a": ["тукан"], "w": ["пингвин", "страус", "фламинго", "сова"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which woolly animal from the Andes is kept for its soft wool?", "a": ["llama", "alpaca"], "w": ["camel", "goat", "yak", "donkey"]},
     "de": {"q": "Welches wollige Tier aus den Anden wird wegen seiner weichen Wolle gehalten?", "a": ["lama", "alpaka"], "w": ["kamel", "ziege", "yak", "esel"]},
     "es": {"q": "¿Qué animal lanudo de los Andes se cría por su suave lana?", "a": ["llama", "alpaca"], "w": ["camello", "cabra", "yak", "burro"]},
     "fr": {"q": "Quel animal laineux des Andes est élevé pour sa laine douce ?", "a": ["lama", "alpaga"], "w": ["chameau", "chèvre", "yak", "âne"]},
     "lt": {"q": "Koks vilnonis Andų gyvūnas laikomas dėl savo minkštos vilnos?", "a": ["lama", "alpaka"], "w": ["kupranugaris", "ožka", "jakas", "asilas"]},
     "ru": {"q": "Какое шерстистое животное из Анд разводят ради мягкой шерсти?", "a": ["лама", "альпака"], "w": ["верблюд", "коза", "як", "осёл"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country is famous for coffee and the city of Medellín?", "a": ["colombia"], "w": ["venezuela", "ecuador", "peru", "bolivia"]},
     "de": {"q": "Welches südamerikanische Land ist für Kaffee und die Stadt Medellín bekannt?", "a": ["kolumbien"], "w": ["venezuela", "ecuador", "peru", "bolivien"]},
     "es": {"q": "¿Qué país sudamericano es famoso por el café y la ciudad de Medellín?", "a": ["colombia"], "w": ["venezuela", "ecuador", "perú", "bolivia"]},
     "fr": {"q": "Quel pays d'Amérique du Sud est célèbre pour le café et la ville de Medellín ?", "a": ["colombie"], "w": ["venezuela", "équateur", "pérou", "bolivie"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis garsėja kava ir Medeljino miestu?", "a": ["kolumbija"], "w": ["venesuela", "ekvadoras", "peru", "bolivija"]},
     "ru": {"q": "Какая южноамериканская страна знаменита кофе и городом Медельин?", "a": ["колумбия"], "w": ["венесуэла", "эквадор", "перу", "боливия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the capital city of Chile?", "a": ["santiago"], "w": ["valparaíso", "lima", "buenos aires", "montevideo"]},
     "de": {"q": "Was ist die Hauptstadt von Chile?", "a": ["santiago"], "w": ["valparaíso", "lima", "buenos aires", "montevideo"]},
     "es": {"q": "¿Cuál es la capital de Chile?", "a": ["santiago"], "w": ["valparaíso", "lima", "buenos aires", "montevideo"]},
     "fr": {"q": "Quelle est la capitale du Chili ?", "a": ["santiago"], "w": ["valparaíso", "lima", "buenos aires", "montevideo"]},
     "lt": {"q": "Koks yra Čilės sostinė?", "a": ["santjagas"], "w": ["valparaisas", "lima", "buenos airės", "montevidėjas"]},
     "ru": {"q": "Какая столица Чили?", "a": ["сантьяго"], "w": ["вальпараисо", "лима", "буэнос-айрес", "монтевидео"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which ocean lies along the eastern coast of South America?", "a": ["atlantic ocean", "the atlantic"], "w": ["pacific ocean", "indian ocean", "arctic ocean", "southern ocean"]},
     "de": {"q": "Welcher Ozean liegt an der Ostküste Südamerikas?", "a": ["atlantischer ozean", "der atlantik"], "w": ["pazifischer ozean", "indischer ozean", "arktischer ozean", "südlicher ozean"]},
     "es": {"q": "¿Qué océano se encuentra a lo largo de la costa este de Sudamérica?", "a": ["océano atlántico", "el atlántico"], "w": ["océano pacífico", "océano índico", "océano ártico", "océano antártico"]},
     "fr": {"q": "Quel océan borde la côte est de l'Amérique du Sud ?", "a": ["océan atlantique", "l'atlantique"], "w": ["océan pacifique", "océan indien", "océan arctique", "océan austral"]},
     "lt": {"q": "Kuris vandenynas plyti palei rytinę Pietų Amerikos pakrantę?", "a": ["atlanto vandenynas", "atlantas"], "w": ["ramusis vandenynas", "indijos vandenynas", "arkties vandenynas", "pietų vandenynas"]},
     "ru": {"q": "Какой океан омывает восточное побережье Южной Америки?", "a": ["атлантический океан", "атлантика"], "w": ["тихий океан", "индийский океан", "северный ледовитый океан", "южный океан"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country hosted and won the first football World Cup?", "a": ["uruguay"], "w": ["brazil", "argentina", "chile", "peru"]},
     "de": {"q": "Welches südamerikanische Land richtete die erste Fußball-Weltmeisterschaft aus und gewann sie?", "a": ["uruguay"], "w": ["brasilien", "argentinien", "chile", "peru"]},
     "es": {"q": "¿Qué país sudamericano organizó y ganó la primera Copa Mundial de fútbol?", "a": ["uruguay"], "w": ["brasil", "argentina", "chile", "perú"]},
     "fr": {"q": "Quel pays d'Amérique du Sud a organisé et remporté la première Coupe du monde de football ?", "a": ["uruguay"], "w": ["brésil", "argentine", "chili", "pérou"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis surengė ir laimėjo pirmąjį futbolo pasaulio čempionatą?", "a": ["urugvajus"], "w": ["brazilija", "argentina", "čilė", "peru"]},
     "ru": {"q": "Какая южноамериканская страна провела и выиграла первый чемпионат мира по футболу?", "a": ["уругвай"], "w": ["бразилия", "аргентина", "чили", "перу"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the capital city of Colombia?", "a": ["bogotá", "bogota"], "w": ["medellín", "cali", "caracas", "quito"]},
     "de": {"q": "Was ist die Hauptstadt von Kolumbien?", "a": ["bogotá", "bogota"], "w": ["medellín", "cali", "caracas", "quito"]},
     "es": {"q": "¿Cuál es la capital de Colombia?", "a": ["bogotá"], "w": ["medellín", "cali", "caracas", "quito"]},
     "fr": {"q": "Quelle est la capitale de la Colombie ?", "a": ["bogotá", "bogota"], "w": ["medellín", "cali", "caracas", "quito"]},
     "lt": {"q": "Koks yra Kolumbijos sostinė?", "a": ["bogota"], "w": ["medeljinas", "kalis", "karakasas", "kitas"]},
     "ru": {"q": "Какая столица Колумбии?", "a": ["богота"], "w": ["медельин", "кали", "каракас", "кито"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which islands famous for unique wildlife belong to Ecuador?", "a": ["galápagos", "galapagos islands", "the galápagos"], "w": ["falkland islands", "canary islands", "azores", "easter island"]},
     "de": {"q": "Welche für ihre einzigartige Tierwelt berühmten Inseln gehören zu Ecuador?", "a": ["galápagos", "galápagos-inseln"], "w": ["falklandinseln", "kanarische inseln", "azoren", "osterinsel"]},
     "es": {"q": "¿Qué islas famosas por su fauna única pertenecen a Ecuador?", "a": ["galápagos", "islas galápagos"], "w": ["islas malvinas", "islas canarias", "azores", "isla de pascua"]},
     "fr": {"q": "Quelles îles célèbres pour leur faune unique appartiennent à l'Équateur ?", "a": ["galápagos", "îles galápagos"], "w": ["îles malouines", "îles canaries", "açores", "île de pâques"]},
     "lt": {"q": "Kurios unikalia gyvūnija garsėjančios salos priklauso Ekvadorui?", "a": ["galapagai", "galapagų salos"], "w": ["folklando salos", "kanarų salos", "azorai", "velykų sala"]},
     "ru": {"q": "Какие острова, известные уникальной фауной, принадлежат Эквадору?", "a": ["галапагосские острова", "галапагосы"], "w": ["фолклендские острова", "канарские острова", "азорские острова", "остров пасхи"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which country is the largest in South America by area?", "a": ["brazil"], "w": ["argentina", "peru", "colombia", "bolivia"]},
     "de": {"q": "Welches Land ist das größte Südamerikas nach Fläche?", "a": ["brasilien"], "w": ["argentinien", "peru", "kolumbien", "bolivien"]},
     "es": {"q": "¿Qué país es el más grande de Sudamérica por superficie?", "a": ["brasil"], "w": ["argentina", "perú", "colombia", "bolivia"]},
     "fr": {"q": "Quel pays est le plus grand d'Amérique du Sud par superficie ?", "a": ["brésil"], "w": ["argentine", "pérou", "colombie", "bolivie"]},
     "lt": {"q": "Kuri šalis yra didžiausia Pietų Amerikoje pagal plotą?", "a": ["brazilija"], "w": ["argentina", "peru", "kolumbija", "bolivija"]},
     "ru": {"q": "Какая страна самая большая в Южной Америке по площади?", "a": ["бразилия"], "w": ["аргентина", "перу", "колумбия", "боливия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which colourful festival with parades and samba is held every year in Brazil?", "a": ["carnival", "carnaval", "rio carnival"], "w": ["oktoberfest", "diwali", "holi", "mardi gras"]},
     "de": {"q": "Welches bunte Fest mit Umzügen und Samba findet jedes Jahr in Brasilien statt?", "a": ["karneval", "der karneval"], "w": ["oktoberfest", "diwali", "holi", "mardi gras"]},
     "es": {"q": "¿Qué colorido festival con desfiles y samba se celebra cada año en Brasil?", "a": ["carnaval", "el carnaval"], "w": ["oktoberfest", "diwali", "holi", "martes de carnaval"]},
     "fr": {"q": "Quelle fête colorée avec défilés et samba a lieu chaque année au Brésil ?", "a": ["carnaval", "le carnaval"], "w": ["oktoberfest", "diwali", "holi", "mardi gras"]},
     "lt": {"q": "Kokia spalvinga šventė su eitynėmis ir samba kasmet vyksta Brazilijoje?", "a": ["karnavalas"], "w": ["oktoberfestas", "divalis", "holis", "užgavėnės"]},
     "ru": {"q": "Какой яркий фестиваль с парадами и самбой ежегодно проходит в Бразилии?", "a": ["карнавал"], "w": ["октоберфест", "дивали", "холи", "марди гра"]}},

    # ---------------- NORMAL (800 pts) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the highest waterfall in the world, found in Venezuela?", "a": ["angel falls", "salto ángel"], "w": ["niagara falls", "iguazu falls", "victoria falls", "tugela falls"]},
     "de": {"q": "Was ist der höchste Wasserfall der Welt, der in Venezuela liegt?", "a": ["angel-wasserfall", "salto ángel"], "w": ["niagarafälle", "iguazú-wasserfälle", "victoriafälle", "tugela-fälle"]},
     "es": {"q": "¿Cuál es la cascada más alta del mundo, situada en Venezuela?", "a": ["salto ángel", "el salto ángel"], "w": ["cataratas del niágara", "cataratas del iguazú", "cataratas victoria", "cataratas tugela"]},
     "fr": {"q": "Quelle est la plus haute chute d'eau du monde, située au Venezuela ?", "a": ["le salto angel", "salto ángel", "chutes angel"], "w": ["chutes du niagara", "chutes d'iguazú", "chutes victoria", "chutes tugela"]},
     "lt": {"q": "Koks yra aukščiausias pasaulio krioklys, esantis Venesueloje?", "a": ["andželo krioklys", "salto ángel"], "w": ["niagaros krioklys", "iguasu kriokliai", "viktorijos krioklys", "tugelos krioklys"]},
     "ru": {"q": "Какой самый высокий водопад в мире, находящийся в Венесуэле?", "a": ["анхель", "водопад анхель"], "w": ["ниагарский водопад", "игуасу", "виктория", "тугела"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which ancient empire built Machu Picchu high in the Andes?", "a": ["the inca", "inca empire", "incas"], "w": ["the aztec", "the maya", "the olmec", "the roman empire"]},
     "de": {"q": "Welches antike Reich erbaute Machu Picchu hoch in den Anden?", "a": ["die inka", "das inkareich", "inkas"], "w": ["die azteken", "die maya", "die olmeken", "das römische reich"]},
     "es": {"q": "¿Qué antiguo imperio construyó Machu Picchu en lo alto de los Andes?", "a": ["los incas", "el imperio inca", "inca"], "w": ["los aztecas", "los mayas", "los olmecas", "el imperio romano"]},
     "fr": {"q": "Quel ancien empire a construit le Machu Picchu au sommet des Andes ?", "a": ["les incas", "l'empire inca", "inca"], "w": ["les aztèques", "les mayas", "les olmèques", "l'empire romain"]},
     "lt": {"q": "Kuri senovės imperija pastatė Maču Pikču aukštai Anduose?", "a": ["inkai", "inkų imperija"], "w": ["actekai", "majai", "olmekai", "romos imperija"]},
     "ru": {"q": "Какая древняя империя построила Мачу-Пикчу высоко в Андах?", "a": ["инки", "империя инков"], "w": ["ацтеки", "майя", "ольмеки", "римская империя"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which lake high in the Andes is the highest large navigable lake in the world?", "a": ["lake titicaca", "titicaca"], "w": ["lake baikal", "lake victoria", "lake maracaibo", "lake poopó"]},
     "de": {"q": "Welcher See hoch in den Anden ist der höchstgelegene große schiffbare See der Welt?", "a": ["titicacasee", "titicaca"], "w": ["baikalsee", "viktoriasee", "maracaibo-see", "poopó-see"]},
     "es": {"q": "¿Qué lago en lo alto de los Andes es el lago navegable grande más alto del mundo?", "a": ["lago titicaca", "titicaca"], "w": ["lago baikal", "lago victoria", "lago maracaibo", "lago poopó"]},
     "fr": {"q": "Quel lac situé haut dans les Andes est le plus haut grand lac navigable du monde ?", "a": ["lac titicaca", "titicaca"], "w": ["lac baïkal", "lac victoria", "lac maracaibo", "lac poopó"]},
     "lt": {"q": "Kuris ežeras aukštai Anduose yra aukščiausiai esantis didelis laivuojamas ežeras pasaulyje?", "a": ["titikakos ežeras", "titikaka"], "w": ["baikalo ežeras", "viktorijos ežeras", "marakaibo ežeras", "poopo ežeras"]},
     "ru": {"q": "Какое озеро высоко в Андах является самым высокогорным крупным судоходным озером в мире?", "a": ["титикака", "озеро титикака"], "w": ["байкал", "виктория", "маракайбо", "поопо"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which two landlocked countries are found in South America?", "a": ["bolivia and paraguay", "paraguay and bolivia"], "w": ["chile and peru", "ecuador and uruguay", "brazil and guyana", "colombia and venezuela"]},
     "de": {"q": "Welche zwei Binnenstaaten liegen in Südamerika?", "a": ["bolivien und paraguay", "paraguay und bolivien"], "w": ["chile und peru", "ecuador und uruguay", "brasilien und guyana", "kolumbien und venezuela"]},
     "es": {"q": "¿Qué dos países sin salida al mar se encuentran en Sudamérica?", "a": ["bolivia y paraguay", "paraguay y bolivia"], "w": ["chile y perú", "ecuador y uruguay", "brasil y guyana", "colombia y venezuela"]},
     "fr": {"q": "Quels deux pays sans accès à la mer se trouvent en Amérique du Sud ?", "a": ["la bolivie et le paraguay", "bolivie et paraguay"], "w": ["chili et pérou", "équateur et uruguay", "brésil et guyana", "colombie et venezuela"]},
     "lt": {"q": "Kurios dvi šalys Pietų Amerikoje neturi priėjimo prie jūros?", "a": ["bolivija ir paragvajus", "paragvajus ir bolivija"], "w": ["čilė ir peru", "ekvadoras ir urugvajus", "brazilija ir gajana", "kolumbija ir venesuela"]},
     "ru": {"q": "Какие две страны Южной Америки не имеют выхода к морю?", "a": ["боливия и парагвай", "парагвай и боливия"], "w": ["чили и перу", "эквадор и уругвай", "бразилия и гайана", "колумбия и венесуэла"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the highest mountain in South America?", "a": ["aconcagua", "mount aconcagua"], "w": ["chimborazo", "huascarán", "ojos del salado", "illimani"]},
     "de": {"q": "Was ist der höchste Berg Südamerikas?", "a": ["aconcagua", "der aconcagua"], "w": ["chimborazo", "huascarán", "ojos del salado", "illimani"]},
     "es": {"q": "¿Cuál es la montaña más alta de Sudamérica?", "a": ["aconcagua", "el aconcagua"], "w": ["chimborazo", "huascarán", "ojos del salado", "illimani"]},
     "fr": {"q": "Quelle est la plus haute montagne d'Amérique du Sud ?", "a": ["aconcagua", "l'aconcagua"], "w": ["chimborazo", "huascarán", "ojos del salado", "illimani"]},
     "lt": {"q": "Koks yra aukščiausias Pietų Amerikos kalnas?", "a": ["akonkagva"], "w": ["čimborasas", "huaskaranas", "ochos del saladas", "ilimanis"]},
     "ru": {"q": "Какая самая высокая гора в Южной Америке?", "a": ["аконкагуа"], "w": ["чимборасо", "уаскаран", "охос-дель-саладо", "ильимани"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Bolivia's Salar de Uyuni is the world's largest what?", "a": ["salt flat", "salt flats"], "w": ["sand desert", "glacier", "crater", "swamp"]},
     "de": {"q": "Boliviens Salar de Uyuni ist die größte was der Welt?", "a": ["salzwüste", "salzsee", "salzpfanne"], "w": ["sandwüste", "gletscher", "krater", "sumpf"]},
     "es": {"q": "El Salar de Uyuni de Bolivia es el mayor del mundo, ¿de qué?", "a": ["salar", "desierto de sal"], "w": ["desierto de arena", "glaciar", "cráter", "pantano"]},
     "fr": {"q": "Le Salar de Uyuni en Bolivie est le plus grand du monde, de quoi ?", "a": ["désert de sel", "salar"], "w": ["désert de sable", "glacier", "cratère", "marais"]},
     "lt": {"q": "Bolivijos Salar de Uyuni yra didžiausias pasaulyje kas?", "a": ["druskožemis", "druskos dykuma"], "w": ["smėlio dykuma", "ledynas", "krateris", "pelkė"]},
     "ru": {"q": "Боливийский Салар-де-Уюни — крупнейший в мире что?", "a": ["солончак", "соляная пустыня"], "w": ["песчаная пустыня", "ледник", "кратер", "болото"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which southern region shared by Chile and Argentina is known for glaciers and steppe?", "a": ["patagonia"], "w": ["amazonia", "pampas", "gran chaco", "altiplano"]},
     "de": {"q": "Welche südliche Region, die sich Chile und Argentinien teilen, ist für Gletscher und Steppe bekannt?", "a": ["patagonien"], "w": ["amazonien", "pampa", "gran chaco", "altiplano"]},
     "es": {"q": "¿Qué región sureña compartida por Chile y Argentina es conocida por sus glaciares y estepa?", "a": ["patagonia", "la patagonia"], "w": ["amazonia", "la pampa", "gran chaco", "altiplano"]},
     "fr": {"q": "Quelle région méridionale partagée par le Chili et l'Argentine est connue pour ses glaciers et sa steppe ?", "a": ["patagonie", "la patagonie"], "w": ["amazonie", "la pampa", "gran chaco", "altiplano"]},
     "lt": {"q": "Kuris pietinis regionas, kurį dalijasi Čilė ir Argentina, garsėja ledynais ir stepe?", "a": ["patagonija"], "w": ["amazonija", "pampa", "gran čakas", "altiplanas"]},
     "ru": {"q": "Какой южный регион, разделяемый Чили и Аргентиной, известен ледниками и степью?", "a": ["патагония"], "w": ["амазония", "пампасы", "гран-чако", "альтиплано"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What are the vast fertile grasslands of Argentina called?", "a": ["the pampas", "pampas"], "w": ["the prairies", "the steppes", "the savanna", "the outback"]},
     "de": {"q": "Wie heißen die weiten fruchtbaren Grasländer Argentiniens?", "a": ["die pampa", "pampa"], "w": ["die prärien", "die steppen", "die savanne", "das outback"]},
     "es": {"q": "¿Cómo se llaman las vastas llanuras fértiles de Argentina?", "a": ["la pampa", "las pampas"], "w": ["las praderas", "las estepas", "la sabana", "el outback"]},
     "fr": {"q": "Comment appelle-t-on les vastes plaines fertiles de l'Argentine ?", "a": ["la pampa", "les pampas"], "w": ["les prairies", "les steppes", "la savane", "l'outback"]},
     "lt": {"q": "Kaip vadinamos plačios derlingos Argentinos lygumos?", "a": ["pampa", "pampos"], "w": ["prerijos", "stepės", "savana", "autbekas"]},
     "ru": {"q": "Как называются обширные плодородные равнины Аргентины?", "a": ["пампасы", "пампа"], "w": ["прерии", "степи", "саванна", "аутбэк"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The Iguazu Falls lie on the border between which two countries?", "a": ["argentina and brazil", "brazil and argentina"], "w": ["chile and peru", "bolivia and paraguay", "colombia and ecuador", "uruguay and argentina"]},
     "de": {"q": "Die Iguazú-Wasserfälle liegen an der Grenze zwischen welchen beiden Ländern?", "a": ["argentinien und brasilien", "brasilien und argentinien"], "w": ["chile und peru", "bolivien und paraguay", "kolumbien und ecuador", "uruguay und argentinien"]},
     "es": {"q": "¿Las cataratas del Iguazú están en la frontera entre qué dos países?", "a": ["argentina y brasil", "brasil y argentina"], "w": ["chile y perú", "bolivia y paraguay", "colombia y ecuador", "uruguay y argentina"]},
     "fr": {"q": "Les chutes d'Iguazú se trouvent à la frontière entre quels deux pays ?", "a": ["l'argentine et le brésil", "argentine et brésil"], "w": ["chili et pérou", "bolivie et paraguay", "colombie et équateur", "uruguay et argentine"]},
     "lt": {"q": "Iguasu kriokliai yra pasienyje tarp kurių dviejų šalių?", "a": ["argentinos ir brazilijos", "brazilijos ir argentinos"], "w": ["čilės ir peru", "bolivijos ir paragvajaus", "kolumbijos ir ekvadoro", "urugvajaus ir argentinos"]},
     "ru": {"q": "Водопады Игуасу находятся на границе каких двух стран?", "a": ["аргентины и бразилии", "бразилии и аргентины"], "w": ["чили и перу", "боливии и парагвая", "колумбии и эквадора", "уругвая и аргентины"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which desert in northern Chile is one of the driest places on Earth?", "a": ["atacama", "atacama desert"], "w": ["patagonian desert", "sechura", "sahara", "gobi"]},
     "de": {"q": "Welche Wüste im Norden Chiles ist einer der trockensten Orte der Erde?", "a": ["atacama", "atacama-wüste"], "w": ["patagonische wüste", "sechura", "sahara", "gobi"]},
     "es": {"q": "¿Qué desierto del norte de Chile es uno de los lugares más secos de la Tierra?", "a": ["atacama", "desierto de atacama"], "w": ["desierto patagónico", "sechura", "sahara", "gobi"]},
     "fr": {"q": "Quel désert du nord du Chili est l'un des endroits les plus secs de la Terre ?", "a": ["atacama", "désert d'atacama"], "w": ["désert de patagonie", "sechura", "sahara", "gobi"]},
     "lt": {"q": "Kuri dykuma šiaurės Čilėje yra viena sausiausių vietų Žemėje?", "a": ["atakama", "atakamos dykuma"], "w": ["patagonijos dykuma", "sečura", "sachara", "gobis"]},
     "ru": {"q": "Какая пустыня на севере Чили является одним из самых сухих мест на Земле?", "a": ["атакама", "пустыня атакама"], "w": ["патагонская пустыня", "сечура", "сахара", "гоби"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which country has the highest capital city in the world at over 3600 metres?", "a": ["bolivia"], "w": ["peru", "ecuador", "colombia", "chile"]},
     "de": {"q": "Welches Land hat mit über 3600 Metern die höchstgelegene Hauptstadt der Welt?", "a": ["bolivien"], "w": ["peru", "ecuador", "kolumbien", "chile"]},
     "es": {"q": "¿Qué país tiene la capital más alta del mundo, a más de 3600 metros?", "a": ["bolivia"], "w": ["perú", "ecuador", "colombia", "chile"]},
     "fr": {"q": "Quel pays possède la capitale la plus haute du monde, à plus de 3600 mètres ?", "a": ["bolivie"], "w": ["pérou", "équateur", "colombie", "chili"]},
     "lt": {"q": "Kuri šalis turi aukščiausiai pasaulyje esančią sostinę – virš 3600 metrų?", "a": ["bolivija"], "w": ["peru", "ekvadoras", "kolumbija", "čilė"]},
     "ru": {"q": "У какой страны самая высокогорная столица в мире — выше 3600 метров?", "a": ["боливия"], "w": ["перу", "эквадор", "колумбия", "чили"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the capital city of Venezuela?", "a": ["caracas"], "w": ["maracaibo", "bogotá", "georgetown", "quito"]},
     "de": {"q": "Was ist die Hauptstadt von Venezuela?", "a": ["caracas"], "w": ["maracaibo", "bogotá", "georgetown", "quito"]},
     "es": {"q": "¿Cuál es la capital de Venezuela?", "a": ["caracas"], "w": ["maracaibo", "bogotá", "georgetown", "quito"]},
     "fr": {"q": "Quelle est la capitale du Venezuela ?", "a": ["caracas"], "w": ["maracaibo", "bogotá", "georgetown", "quito"]},
     "lt": {"q": "Koks yra Venesuelos sostinė?", "a": ["karakasas"], "w": ["marakaibas", "bogota", "džordžtaunas", "kitas"]},
     "ru": {"q": "Какая столица Венесуэлы?", "a": ["каракас"], "w": ["маракайбо", "богота", "джорджтаун", "кито"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which large snake of South American swamps is among the heaviest in the world?", "a": ["anaconda", "green anaconda"], "w": ["python", "cobra", "boa constrictor", "viper"]},
     "de": {"q": "Welche große Schlange der südamerikanischen Sümpfe gehört zu den schwersten der Welt?", "a": ["anakonda", "große anakonda"], "w": ["python", "kobra", "boa constrictor", "viper"]},
     "es": {"q": "¿Qué gran serpiente de los pantanos sudamericanos está entre las más pesadas del mundo?", "a": ["anaconda", "anaconda verde"], "w": ["pitón", "cobra", "boa constrictora", "víbora"]},
     "fr": {"q": "Quel grand serpent des marais d'Amérique du Sud est parmi les plus lourds du monde ?", "a": ["anaconda", "anaconda vert"], "w": ["python", "cobra", "boa constrictor", "vipère"]},
     "lt": {"q": "Kuri didelė Pietų Amerikos pelkių gyvatė yra viena sunkiausių pasaulyje?", "a": ["anakonda"], "w": ["pitonas", "kobra", "smauglys", "gyvatė angis"]},
     "ru": {"q": "Какая крупная змея южноамериканских болот входит в число самых тяжёлых в мире?", "a": ["анаконда"], "w": ["питон", "кобра", "удав", "гадюка"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which South American country was named after the explorer Christopher Columbus?", "a": ["colombia"], "w": ["venezuela", "bolivia", "ecuador", "peru"]},
     "de": {"q": "Welches südamerikanische Land wurde nach dem Entdecker Christoph Kolumbus benannt?", "a": ["kolumbien"], "w": ["venezuela", "bolivien", "ecuador", "peru"]},
     "es": {"q": "¿Qué país sudamericano fue nombrado en honor al explorador Cristóbal Colón?", "a": ["colombia"], "w": ["venezuela", "bolivia", "ecuador", "perú"]},
     "fr": {"q": "Quel pays d'Amérique du Sud a été nommé d'après l'explorateur Christophe Colomb ?", "a": ["colombie"], "w": ["venezuela", "bolivie", "équateur", "pérou"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis pavadinta tyrinėtojo Kristupo Kolumbo vardu?", "a": ["kolumbija"], "w": ["venesuela", "bolivija", "ekvadoras", "peru"]},
     "ru": {"q": "Какая южноамериканская страна названа в честь исследователя Христофора Колумба?", "a": ["колумбия"], "w": ["венесуэла", "боливия", "эквадор", "перу"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which country is Bolivia named after?", "a": ["after simón bolívar", "simón bolívar", "bolívar"], "w": ["after columbus", "after pizarro", "after magellan", "after cortés"]},
     "de": {"q": "Nach wem ist Bolivien benannt?", "a": ["nach simón bolívar", "simón bolívar", "bolívar"], "w": ["nach kolumbus", "nach pizarro", "nach magellan", "nach cortés"]},
     "es": {"q": "¿En honor a quién recibe su nombre Bolivia?", "a": ["simón bolívar", "bolívar"], "w": ["colón", "pizarro", "magallanes", "cortés"]},
     "fr": {"q": "En l'honneur de qui la Bolivie est-elle nommée ?", "a": ["simón bolívar", "bolívar"], "w": ["colomb", "pizarro", "magellan", "cortés"]},
     "lt": {"q": "Kieno garbei pavadinta Bolivija?", "a": ["simono bolivaro", "bolivaro"], "w": ["kolumbo", "pisaro", "magelano", "koreso"]},
     "ru": {"q": "В честь кого названа Боливия?", "a": ["симона боливара", "боливара"], "w": ["колумба", "писарро", "магеллана", "кортеса"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the capital city of Uruguay?", "a": ["montevideo"], "w": ["asunción", "buenos aires", "santiago", "la paz"]},
     "de": {"q": "Was ist die Hauptstadt von Uruguay?", "a": ["montevideo"], "w": ["asunción", "buenos aires", "santiago", "la paz"]},
     "es": {"q": "¿Cuál es la capital de Uruguay?", "a": ["montevideo"], "w": ["asunción", "buenos aires", "santiago", "la paz"]},
     "fr": {"q": "Quelle est la capitale de l'Uruguay ?", "a": ["montevideo"], "w": ["asunción", "buenos aires", "santiago", "la paz"]},
     "lt": {"q": "Koks yra Urugvajaus sostinė?", "a": ["montevidėjas"], "w": ["asunsjonas", "buenos airės", "santjagas", "la pasas"]},
     "ru": {"q": "Какая столица Уругвая?", "a": ["монтевидео"], "w": ["асунсьон", "буэнос-айрес", "сантьяго", "ла-пас"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which small fish with sharp teeth is famous in Amazon rivers?", "a": ["piranha"], "w": ["shark", "catfish", "salmon", "trout"]},
     "de": {"q": "Welcher kleine Fisch mit scharfen Zähnen ist in den Flüssen des Amazonas berühmt?", "a": ["piranha"], "w": ["hai", "wels", "lachs", "forelle"]},
     "es": {"q": "¿Qué pequeño pez de dientes afilados es famoso en los ríos del Amazonas?", "a": ["piraña"], "w": ["tiburón", "bagre", "salmón", "trucha"]},
     "fr": {"q": "Quel petit poisson aux dents acérées est célèbre dans les rivières de l'Amazone ?", "a": ["piranha"], "w": ["requin", "poisson-chat", "saumon", "truite"]},
     "lt": {"q": "Kuri maža aštriadantė žuvis garsėja Amazonės upėse?", "a": ["piranija"], "w": ["ryklys", "šamas", "lašiša", "upėtakis"]},
     "ru": {"q": "Какая маленькая рыба с острыми зубами знаменита в реках Амазонки?", "a": ["пиранья"], "w": ["акула", "сом", "лосось", "форель"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which South American country has Georgetown as its capital?", "a": ["guyana"], "w": ["suriname", "venezuela", "brazil", "paraguay"]},
     "de": {"q": "Welches südamerikanische Land hat Georgetown als Hauptstadt?", "a": ["guyana"], "w": ["suriname", "venezuela", "brasilien", "paraguay"]},
     "es": {"q": "¿Qué país sudamericano tiene a Georgetown como capital?", "a": ["guyana"], "w": ["surinam", "venezuela", "brasil", "paraguay"]},
     "fr": {"q": "Quel pays d'Amérique du Sud a Georgetown pour capitale ?", "a": ["guyana"], "w": ["suriname", "venezuela", "brésil", "paraguay"]},
     "lt": {"q": "Kurios Pietų Amerikos šalies sostinė yra Džordžtaunas?", "a": ["gajana"], "w": ["surinamas", "venesuela", "brazilija", "paragvajus"]},
     "ru": {"q": "У какой южноамериканской страны столица Джорджтаун?", "a": ["гайана"], "w": ["суринам", "венесуэла", "бразилия", "парагвай"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which country is the largest producer of coffee in South America?", "a": ["brazil"], "w": ["colombia", "peru", "ecuador", "bolivia"]},
     "de": {"q": "Welches Land ist der größte Kaffeeproduzent Südamerikas?", "a": ["brasilien"], "w": ["kolumbien", "peru", "ecuador", "bolivien"]},
     "es": {"q": "¿Qué país es el mayor productor de café de Sudamérica?", "a": ["brasil"], "w": ["colombia", "perú", "ecuador", "bolivia"]},
     "fr": {"q": "Quel pays est le plus grand producteur de café d'Amérique du Sud ?", "a": ["brésil"], "w": ["colombie", "pérou", "équateur", "bolivie"]},
     "lt": {"q": "Kuri šalis yra didžiausia kavos gamintoja Pietų Amerikoje?", "a": ["brazilija"], "w": ["kolumbija", "peru", "ekvadoras", "bolivija"]},
     "ru": {"q": "Какая страна является крупнейшим производителем кофе в Южной Америке?", "a": ["бразилия"], "w": ["колумбия", "перу", "эквадор", "боливия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The mysterious Nazca Lines are giant drawings found in which country?", "a": ["peru"], "w": ["chile", "bolivia", "mexico", "brazil"]},
     "de": {"q": "Die geheimnisvollen Nazca-Linien sind riesige Zeichnungen in welchem Land?", "a": ["peru"], "w": ["chile", "bolivien", "mexiko", "brasilien"]},
     "es": {"q": "Las misteriosas Líneas de Nazca son dibujos gigantes que se encuentran en qué país?", "a": ["perú"], "w": ["chile", "bolivia", "méxico", "brasil"]},
     "fr": {"q": "Les mystérieuses lignes de Nazca sont des dessins géants situés dans quel pays ?", "a": ["pérou"], "w": ["chili", "bolivie", "mexique", "brésil"]},
     "lt": {"q": "Paslaptingos Naskos linijos yra milžiniški piešiniai kurioje šalyje?", "a": ["peru"], "w": ["čilė", "bolivija", "meksika", "brazilija"]},
     "ru": {"q": "Загадочные линии Наска — гигантские рисунки, находящиеся в какой стране?", "a": ["перу"], "w": ["чили", "боливия", "мексика", "бразилия"]}},

    # ---------------- BUFFER candidates (mixed easy/normal) ----------------
    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country is shaped like a long chilli pepper along the Pacific?", "a": ["chile"], "w": ["peru", "ecuador", "colombia", "brazil"]},
     "de": {"q": "Welches südamerikanische Land hat die Form einer langen Chilischote entlang des Pazifiks?", "a": ["chile"], "w": ["peru", "ecuador", "kolumbien", "brasilien"]},
     "es": {"q": "¿Qué país sudamericano tiene forma de un largo chile a lo largo del Pacífico?", "a": ["chile"], "w": ["perú", "ecuador", "colombia", "brasil"]},
     "fr": {"q": "Quel pays d'Amérique du Sud a la forme d'un long piment le long du Pacifique ?", "a": ["chili"], "w": ["pérou", "équateur", "colombie", "brésil"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis primena ilgą aitriąją papriką palei Ramųjį vandenyną?", "a": ["čilė"], "w": ["peru", "ekvadoras", "kolumbija", "brazilija"]},
     "ru": {"q": "Какая южноамериканская страна по форме напоминает длинный перец чили вдоль Тихого океана?", "a": ["чили"], "w": ["перу", "эквадор", "колумбия", "бразилия"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the most popular sport in South America?", "a": ["football", "soccer"], "w": ["cricket", "ice hockey", "baseball", "rugby"]},
     "de": {"q": "Was ist die beliebteste Sportart in Südamerika?", "a": ["fußball"], "w": ["cricket", "eishockey", "baseball", "rugby"]},
     "es": {"q": "¿Cuál es el deporte más popular de Sudamérica?", "a": ["fútbol"], "w": ["críquet", "hockey sobre hielo", "béisbol", "rugby"]},
     "fr": {"q": "Quel est le sport le plus populaire en Amérique du Sud ?", "a": ["le football", "football"], "w": ["le cricket", "le hockey sur glace", "le baseball", "le rugby"]},
     "lt": {"q": "Koks populiariausias sportas Pietų Amerikoje?", "a": ["futbolas"], "w": ["kriketas", "ledo ritulys", "beisbolas", "regbis"]},
     "ru": {"q": "Какой самый популярный вид спорта в Южной Америке?", "a": ["футбол"], "w": ["крикет", "хоккей", "бейсбол", "регби"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the capital city of Ecuador?", "a": ["quito"], "w": ["guayaquil", "lima", "bogotá", "caracas"]},
     "de": {"q": "Was ist die Hauptstadt von Ecuador?", "a": ["quito"], "w": ["guayaquil", "lima", "bogotá", "caracas"]},
     "es": {"q": "¿Cuál es la capital de Ecuador?", "a": ["quito"], "w": ["guayaquil", "lima", "bogotá", "caracas"]},
     "fr": {"q": "Quelle est la capitale de l'Équateur ?", "a": ["quito"], "w": ["guayaquil", "lima", "bogotá", "caracas"]},
     "lt": {"q": "Koks yra Ekvadoro sostinė?", "a": ["kitas"], "w": ["gvajakilis", "lima", "bogota", "karakasas"]},
     "ru": {"q": "Какая столица Эквадора?", "a": ["кито"], "w": ["гуаякиль", "лима", "богота", "каракас"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country is famous for beaches like Copacabana?", "a": ["brazil"], "w": ["argentina", "chile", "peru", "uruguay"]},
     "de": {"q": "Welches südamerikanische Land ist für Strände wie Copacabana berühmt?", "a": ["brasilien"], "w": ["argentinien", "chile", "peru", "uruguay"]},
     "es": {"q": "¿Qué país sudamericano es famoso por playas como Copacabana?", "a": ["brasil"], "w": ["argentina", "chile", "perú", "uruguay"]},
     "fr": {"q": "Quel pays d'Amérique du Sud est célèbre pour des plages comme Copacabana ?", "a": ["brésil"], "w": ["argentine", "chili", "pérou", "uruguay"]},
     "lt": {"q": "Kuri Pietų Amerikos šalis garsėja tokiais paplūdimiais kaip Kopakabana?", "a": ["brazilija"], "w": ["argentina", "čilė", "peru", "urugvajus"]},
     "ru": {"q": "Какая южноамериканская страна знаменита пляжами вроде Копакабаны?", "a": ["бразилия"], "w": ["аргентина", "чили", "перу", "уругвай"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which South American country has Paramaribo as its capital?", "a": ["suriname"], "w": ["guyana", "venezuela", "paraguay", "ecuador"]},
     "de": {"q": "Welches südamerikanische Land hat Paramaribo als Hauptstadt?", "a": ["suriname"], "w": ["guyana", "venezuela", "paraguay", "ecuador"]},
     "es": {"q": "¿Qué país sudamericano tiene a Paramaribo como capital?", "a": ["surinam"], "w": ["guyana", "venezuela", "paraguay", "ecuador"]},
     "fr": {"q": "Quel pays d'Amérique du Sud a Paramaribo pour capitale ?", "a": ["suriname"], "w": ["guyana", "venezuela", "paraguay", "équateur"]},
     "lt": {"q": "Kurios Pietų Amerikos šalies sostinė yra Paramaribas?", "a": ["surinamas"], "w": ["gajana", "venesuela", "paragvajus", "ekvadoras"]},
     "ru": {"q": "У какой южноамериканской страны столица Парамарибо?", "a": ["суринам"], "w": ["гайана", "венесуэла", "парагвай", "эквадор"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Potatoes were first grown by people in which mountain region of South America?", "a": ["the andes", "andes"], "w": ["the amazon", "patagonia", "the pampas", "the atacama"]},
     "de": {"q": "Kartoffeln wurden zuerst von Menschen in welcher Bergregion Südamerikas angebaut?", "a": ["die anden", "anden"], "w": ["der amazonas", "patagonien", "die pampa", "die atacama"]},
     "es": {"q": "¿Las papas fueron cultivadas por primera vez en qué región montañosa de Sudamérica?", "a": ["los andes", "andes"], "w": ["la amazonia", "la patagonia", "la pampa", "el atacama"]},
     "fr": {"q": "Les pommes de terre ont d'abord été cultivées dans quelle région montagneuse d'Amérique du Sud ?", "a": ["les andes", "andes"], "w": ["l'amazonie", "la patagonie", "la pampa", "l'atacama"]},
     "lt": {"q": "Bulvės pirmiausia buvo auginamos kuriame Pietų Amerikos kalnų regione?", "a": ["anduose", "andai"], "w": ["amazonėje", "patagonijoje", "pampoje", "atakamoje"]},
     "ru": {"q": "Картофель впервые начали выращивать в каком горном регионе Южной Америки?", "a": ["анды", "андах"], "w": ["амазония", "патагония", "пампасы", "атакама"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which strait at the southern tip of South America is named after a Portuguese explorer?", "a": ["strait of magellan", "magellan strait"], "w": ["bering strait", "strait of gibraltar", "drake passage", "bosphorus"]},
     "de": {"q": "Welche Meerenge an der Südspitze Südamerikas ist nach einem portugiesischen Entdecker benannt?", "a": ["magellanstraße"], "w": ["beringstraße", "straße von gibraltar", "drakestraße", "bosporus"]},
     "es": {"q": "¿Qué estrecho en el extremo sur de Sudamérica lleva el nombre de un explorador portugués?", "a": ["estrecho de magallanes"], "w": ["estrecho de bering", "estrecho de gibraltar", "paso de drake", "bósforo"]},
     "fr": {"q": "Quel détroit à la pointe sud de l'Amérique du Sud porte le nom d'un explorateur portugais ?", "a": ["détroit de magellan"], "w": ["détroit de béring", "détroit de gibraltar", "passage de drake", "bosphore"]},
     "lt": {"q": "Kuris sąsiauris pietiniame Pietų Amerikos gale pavadintas portugalų tyrinėtojo vardu?", "a": ["magelano sąsiauris"], "w": ["beringo sąsiauris", "gibraltaro sąsiauris", "dreiko sąsiauris", "bosforas"]},
     "ru": {"q": "Какой пролив на южной оконечности Южной Америки назван в честь португальского исследователя?", "a": ["магелланов пролив"], "w": ["берингов пролив", "гибралтарский пролив", "пролив дрейка", "босфор"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the capital city of Paraguay?", "a": ["asunción", "asuncion"], "w": ["montevideo", "la paz", "santiago", "lima"]},
     "de": {"q": "Was ist die Hauptstadt von Paraguay?", "a": ["asunción", "asuncion"], "w": ["montevideo", "la paz", "santiago", "lima"]},
     "es": {"q": "¿Cuál es la capital de Paraguay?", "a": ["asunción"], "w": ["montevideo", "la paz", "santiago", "lima"]},
     "fr": {"q": "Quelle est la capitale du Paraguay ?", "a": ["asunción", "asuncion"], "w": ["montevideo", "la paz", "santiago", "lima"]},
     "lt": {"q": "Koks yra Paragvajaus sostinė?", "a": ["asunsjonas"], "w": ["montevidėjas", "la pasas", "santjagas", "lima"]},
     "ru": {"q": "Какая столица Парагвая?", "a": ["асунсьон"], "w": ["монтевидео", "ла-пас", "сантьяго", "лима"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which archipelago at South America's southern tip is called Tierra del Fuego?", "a": ["land of fire", "tierra del fuego"], "w": ["land of ice", "land of gold", "land of storms", "land of winds"]},
     "de": {"q": "Was bedeutet der Name des Archipels Tierra del Fuego an der Südspitze Südamerikas?", "a": ["feuerland", "land des feuers"], "w": ["eisland", "goldland", "sturmland", "windland"]},
     "es": {"q": "¿Qué significa el nombre del archipiélago Tierra del Fuego en el extremo sur de Sudamérica?", "a": ["tierra del fuego", "tierra de fuego"], "w": ["tierra de hielo", "tierra de oro", "tierra de tormentas", "tierra de vientos"]},
     "fr": {"q": "Que signifie le nom de l'archipel Tierra del Fuego à la pointe sud de l'Amérique du Sud ?", "a": ["terre de feu", "la terre de feu"], "w": ["terre de glace", "terre d'or", "terre des tempêtes", "terre des vents"]},
     "lt": {"q": "Ką reiškia salyno Tierra del Fuego pavadinimas pietiniame Pietų Amerikos gale?", "a": ["ugnies žemė"], "w": ["ledo žemė", "aukso žemė", "audrų žemė", "vėjų žemė"]},
     "ru": {"q": "Что означает название архипелага Огненная Земля на юге Южной Америки?", "a": ["огненная земля", "земля огня"], "w": ["ледяная земля", "золотая земля", "земля штормов", "земля ветров"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which European country colonised Brazil?", "a": ["portugal"], "w": ["spain", "france", "netherlands", "england"]},
     "de": {"q": "Welches europäische Land kolonisierte Brasilien?", "a": ["portugal"], "w": ["spanien", "frankreich", "niederlande", "england"]},
     "es": {"q": "¿Qué país europeo colonizó Brasil?", "a": ["portugal"], "w": ["españa", "francia", "países bajos", "inglaterra"]},
     "fr": {"q": "Quel pays européen a colonisé le Brésil ?", "a": ["le portugal", "portugal"], "w": ["l'espagne", "la france", "les pays-bas", "l'angleterre"]},
     "lt": {"q": "Kuri Europos šalis kolonizavo Braziliją?", "a": ["portugalija"], "w": ["ispanija", "prancūzija", "nyderlandai", "anglija"]},
     "ru": {"q": "Какая европейская страна колонизировала Бразилию?", "a": ["португалия"], "w": ["испания", "франция", "нидерланды", "англия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which big cat is the largest predator of the Amazon rainforest?", "a": ["jaguar"], "w": ["lion", "tiger", "leopard", "cheetah"]},
     "de": {"q": "Welche Großkatze ist das größte Raubtier des Amazonas-Regenwaldes?", "a": ["jaguar"], "w": ["löwe", "tiger", "leopard", "gepard"]},
     "es": {"q": "¿Qué gran felino es el mayor depredador de la selva amazónica?", "a": ["jaguar"], "w": ["león", "tigre", "leopardo", "guepardo"]},
     "fr": {"q": "Quel grand félin est le plus grand prédateur de la forêt amazonienne ?", "a": ["jaguar", "le jaguar"], "w": ["lion", "tigre", "léopard", "guépard"]},
     "lt": {"q": "Kuri didžioji katė yra didžiausias Amazonės miško plėšrūnas?", "a": ["jaguaras"], "w": ["liūtas", "tigras", "leopardas", "gepardas"]},
     "ru": {"q": "Какая большая кошка является крупнейшим хищником амазонского леса?", "a": ["ягуар"], "w": ["лев", "тигр", "леопард", "гепард"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The ancient Inca capital of Cusco is located in which modern country?", "a": ["peru"], "w": ["bolivia", "ecuador", "chile", "colombia"]},
     "de": {"q": "Die antike Inka-Hauptstadt Cusco liegt in welchem heutigen Land?", "a": ["peru"], "w": ["bolivien", "ecuador", "chile", "kolumbien"]},
     "es": {"q": "La antigua capital inca de Cusco se encuentra en qué país actual?", "a": ["perú"], "w": ["bolivia", "ecuador", "chile", "colombia"]},
     "fr": {"q": "L'ancienne capitale inca de Cusco se situe dans quel pays actuel ?", "a": ["pérou"], "w": ["bolivie", "équateur", "chili", "colombie"]},
     "lt": {"q": "Senovės inkų sostinė Kuskas yra kurioje šiuolaikinėje šalyje?", "a": ["peru"], "w": ["bolivija", "ekvadoras", "čilė", "kolumbija"]},
     "ru": {"q": "Древняя столица инков Куско находится в какой современной стране?", "a": ["перу"], "w": ["боливия", "эквадор", "чили", "колумбия"]}},
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

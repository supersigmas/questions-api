#!/usr/bin/env python3
"""
Batch add: 100 new Halloween-themed questions across the 6 active languages
(en, de, es, fr, lt, ru). Follows QUESTIONS_AUTHORING.md.

  - id = md5(english question text)  (join key across all languages)
  - answers AND wrong_answers lowercase
  - category = "halloween"; difficulty easy (700) / normal (800, 900 for
    harder items)
  - semantic dedup vs embeddings.json at DEDUP_THRESHOLD (default 0.92),
    including within this batch (new embeddings are added as we go)
  - idempotent: ids already present are skipped; caps additions at TARGET_NEW

A buffer of extra questions follows the core set so dedup skips don't leave
the batch short. Additions stop once TARGET_NEW is reached.

Usage:
    python add_halloween_questions.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import tempfile
import time

LANGS = ["en", "de", "es", "fr", "lt", "ru"]
CATEGORY = "halloween"
QFILE = "translations/questions_{}.json"
EMBEDDINGS_FILE = "embeddings.json"
THRESHOLD = float(os.environ.get("DEDUP_THRESHOLD", "0.92"))
TARGET_NEW = 100


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


# Each entry: difficulty, points, and per-language
# {q, a (answers), w (wrong)}. All answer strings are lowercase.
QUESTIONS = [
    # ---------------- EASY (700 pts) ----------------
    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is traditionally carved into a jack-o'-lantern?", "a": ["pumpkin", "a pumpkin"], "w": ["watermelon", "apple", "coconut", "cabbage"]},
     "de": {"q": "Was wird traditionell zu einer Halloween-Laterne geschnitzt?", "a": ["kürbis", "ein kürbis"], "w": ["wassermelone", "apfel", "kokosnuss", "kohl"]},
     "es": {"q": "¿Qué se talla tradicionalmente para hacer un farol de Halloween?", "a": ["calabaza", "una calabaza"], "w": ["sandía", "manzana", "coco", "repollo"]},
     "fr": {"q": "Que sculpte-t-on traditionnellement pour faire une lanterne d'Halloween ?", "a": ["citrouille", "une citrouille"], "w": ["pastèque", "pomme", "noix de coco", "chou"]},
     "lt": {"q": "Kas tradiciškai išskaptuojamas Helovino žibintui?", "a": ["moliūgas"], "w": ["arbūzas", "obuolys", "kokosas", "kopūstas"]},
     "ru": {"q": "Что традиционно вырезают, чтобы сделать фонарь на Хэллоуин?", "a": ["тыква", "тыкву"], "w": ["арбуз", "яблоко", "кокос", "капуста"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "On what date is Halloween celebrated?", "a": ["october 31", "31 october", "oct 31", "31st october"], "w": ["october 13", "november 1", "october 30", "december 31"]},
     "de": {"q": "An welchem Datum wird Halloween gefeiert?", "a": ["31. oktober", "31 oktober"], "w": ["13. oktober", "1. november", "30. oktober", "31. dezember"]},
     "es": {"q": "¿En qué fecha se celebra Halloween?", "a": ["31 de octubre", "el 31 de octubre"], "w": ["13 de octubre", "1 de noviembre", "30 de octubre", "31 de diciembre"]},
     "fr": {"q": "À quelle date fête-t-on Halloween ?", "a": ["31 octobre", "le 31 octobre"], "w": ["13 octobre", "1er novembre", "30 octobre", "31 décembre"]},
     "lt": {"q": "Kurią dieną švenčiamas Helovinas?", "a": ["spalio 31", "spalio 31 d.", "spalio 31-ąją"], "w": ["spalio 13", "lapkričio 1", "spalio 30", "gruodžio 31"]},
     "ru": {"q": "Какого числа отмечают Хэллоуин?", "a": ["31 октября"], "w": ["13 октября", "1 ноября", "30 октября", "31 декабря"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do children mainly collect when they go trick-or-treating?", "a": ["candy", "sweets", "treats"], "w": ["coins", "toys", "flowers", "stickers"]},
     "de": {"q": "Was sammeln Kinder hauptsächlich, wenn sie an Halloween von Tür zu Tür gehen?", "a": ["süßigkeiten", "bonbons"], "w": ["münzen", "spielzeug", "blumen", "aufkleber"]},
     "es": {"q": "¿Qué recogen principalmente los niños cuando piden «truco o trato»?", "a": ["caramelos", "dulces", "golosinas"], "w": ["monedas", "juguetes", "flores", "pegatinas"]},
     "fr": {"q": "Que récoltent surtout les enfants quand ils font du porte-à-porte à Halloween ?", "a": ["des bonbons", "bonbons", "friandises"], "w": ["des pièces", "des jouets", "des fleurs", "des autocollants"]},
     "lt": {"q": "Ką vaikai daugiausia renka, Helovino vakarą eidami nuo durų prie durų?", "a": ["saldainius", "saldainiai", "saldumynus"], "w": ["monetas", "žaislus", "gėles", "lipdukus"]},
     "ru": {"q": "Что в основном собирают дети, обходя дома на Хэллоуин?", "a": ["конфеты", "сладости"], "w": ["монеты", "игрушки", "цветы", "наклейки"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which nocturnal flying mammal is a classic Halloween symbol?", "a": ["bat", "the bat"], "w": ["owl", "crow", "moth", "raven"]},
     "de": {"q": "Welches nachtaktive fliegende Säugetier ist ein klassisches Halloween-Symbol?", "a": ["fledermaus", "die fledermaus"], "w": ["eule", "krähe", "motte", "rabe"]},
     "es": {"q": "¿Qué mamífero volador nocturno es un símbolo clásico de Halloween?", "a": ["murciélago", "el murciélago"], "w": ["búho", "cuervo", "polilla", "grajo"]},
     "fr": {"q": "Quel mammifère volant nocturne est un symbole classique d'Halloween ?", "a": ["chauve-souris", "la chauve-souris"], "w": ["hibou", "corneille", "papillon de nuit", "corbeau"]},
     "lt": {"q": "Koks naktinis skraidantis žinduolis yra klasikinis Helovino simbolis?", "a": ["šikšnosparnis"], "w": ["pelėda", "varna", "kandis", "varnas"]},
     "ru": {"q": "Какое ночное летающее млекопитающее — классический символ Хэллоуина?", "a": ["летучая мышь"], "w": ["сова", "ворона", "мотылёк", "ворон"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which color is traditionally paired with orange as a Halloween color?", "a": ["black"], "w": ["green", "blue", "pink", "white"]},
     "de": {"q": "Welche Farbe bildet traditionell zusammen mit Orange die Halloween-Farben?", "a": ["schwarz"], "w": ["grün", "blau", "rosa", "weiß"]},
     "es": {"q": "¿Qué color acompaña tradicionalmente al naranja como color de Halloween?", "a": ["negro", "el negro"], "w": ["verde", "azul", "rosa", "blanco"]},
     "fr": {"q": "Quelle couleur est traditionnellement associée à l'orange pour Halloween ?", "a": ["noir", "le noir"], "w": ["vert", "bleu", "rose", "blanc"]},
     "lt": {"q": "Kokia spalva kartu su oranžine tradiciškai yra Helovino spalva?", "a": ["juoda"], "w": ["žalia", "mėlyna", "rožinė", "balta"]},
     "ru": {"q": "Какой цвет вместе с оранжевым традиционно считается цветом Хэллоуина?", "a": ["чёрный", "черный"], "w": ["зелёный", "синий", "розовый", "белый"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which mythical creature turns into a wolf during a full moon?", "a": ["werewolf", "a werewolf"], "w": ["vampire", "zombie", "mummy", "ghoul"]},
     "de": {"q": "Welches Fabelwesen verwandelt sich bei Vollmond in einen Wolf?", "a": ["werwolf", "der werwolf"], "w": ["vampir", "zombie", "mumie", "ghul"]},
     "es": {"q": "¿Qué criatura mítica se convierte en lobo durante la luna llena?", "a": ["hombre lobo", "el hombre lobo"], "w": ["vampiro", "zombi", "momia", "necrófago"]},
     "fr": {"q": "Quelle créature mythique se transforme en loup les soirs de pleine lune ?", "a": ["loup-garou", "le loup-garou"], "w": ["vampire", "zombie", "momie", "goule"]},
     "lt": {"q": "Kuri mitinė būtybė per pilnatį virsta vilku?", "a": ["vilkolakis"], "w": ["vampyras", "zombis", "mumija", "vaiduoklis"]},
     "ru": {"q": "Какое мифическое существо превращается в волка в полнолуние?", "a": ["оборотень", "волколак"], "w": ["вампир", "зомби", "мумия", "упырь"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do vampires famously drink?", "a": ["blood"], "w": ["milk", "wine", "water", "tea"]},
     "de": {"q": "Was trinken Vampire bekanntlich?", "a": ["blut"], "w": ["milch", "wein", "wasser", "tee"]},
     "es": {"q": "¿Qué beben los vampiros, según la tradición?", "a": ["sangre"], "w": ["leche", "vino", "agua", "té"]},
     "fr": {"q": "Que boivent les vampires, selon la légende ?", "a": ["du sang", "sang"], "w": ["du lait", "du vin", "de l'eau", "du thé"]},
     "lt": {"q": "Ką, kaip žinoma, geria vampyrai?", "a": ["kraują", "kraujas"], "w": ["pieną", "vyną", "vandenį", "arbatą"]},
     "ru": {"q": "Что, как известно, пьют вампиры?", "a": ["кровь"], "w": ["молоко", "вино", "воду", "чай"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What does a witch traditionally ride through the night sky?", "a": ["broomstick", "a broomstick", "broom", "a broom"], "w": ["flying carpet", "cloud", "dragon", "horse"]},
     "de": {"q": "Worauf reitet eine Hexe traditionell durch den Nachthimmel?", "a": ["besen", "einem besen", "besenstiel"], "w": ["fliegender teppich", "wolke", "drache", "pferd"]},
     "es": {"q": "¿En qué vuela tradicionalmente una bruja por el cielo nocturno?", "a": ["escoba", "una escoba"], "w": ["alfombra mágica", "nube", "dragón", "caballo"]},
     "fr": {"q": "Sur quoi une sorcière vole-t-elle traditionnellement dans le ciel nocturne ?", "a": ["balai", "un balai"], "w": ["tapis volant", "nuage", "dragon", "cheval"]},
     "lt": {"q": "Kuo ragana tradiciškai skraido naktiniame danguje?", "a": ["šluota", "ant šluotos"], "w": ["skraidančiu kilimu", "debesiu", "drakonu", "arkliu"]},
     "ru": {"q": "На чём ведьма традиционно летает по ночному небу?", "a": ["на метле", "метла"], "w": ["на ковре-самолёте", "на облаке", "на драконе", "на коне"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which monster is usually shown wrapped from head to toe in bandages?", "a": ["mummy", "the mummy", "a mummy"], "w": ["zombie", "ghost", "vampire", "werewolf"]},
     "de": {"q": "Welches Monster wird meist von Kopf bis Fuß in Binden gewickelt dargestellt?", "a": ["mumie", "die mumie"], "w": ["zombie", "gespenst", "vampir", "werwolf"]},
     "es": {"q": "¿Qué monstruo suele aparecer envuelto en vendas de pies a cabeza?", "a": ["momia", "la momia"], "w": ["zombi", "fantasma", "vampiro", "hombre lobo"]},
     "fr": {"q": "Quel monstre est généralement représenté entouré de bandelettes de la tête aux pieds ?", "a": ["momie", "la momie"], "w": ["zombie", "fantôme", "vampire", "loup-garou"]},
     "lt": {"q": "Kuris monstras dažniausiai vaizduojamas nuo galvos iki kojų apvyniotas tvarsčiais?", "a": ["mumija"], "w": ["zombis", "vaiduoklis", "vampyras", "vilkolakis"]},
     "ru": {"q": "Какого монстра обычно изображают обмотанным бинтами с головы до ног?", "a": ["мумия"], "w": ["зомби", "призрак", "вампир", "оборотень"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which animal, especially a black one, is the classic companion of a witch?", "a": ["cat", "a cat", "black cat"], "w": ["dog", "rabbit", "mouse", "horse"]},
     "de": {"q": "Welches Tier, besonders ein schwarzes, ist der klassische Begleiter einer Hexe?", "a": ["katze", "kater", "schwarze katze"], "w": ["hund", "kaninchen", "maus", "pferd"]},
     "es": {"q": "¿Qué animal, sobre todo si es negro, es el compañero clásico de una bruja?", "a": ["gato", "el gato", "gato negro"], "w": ["perro", "conejo", "ratón", "caballo"]},
     "fr": {"q": "Quel animal, surtout s'il est noir, est le compagnon classique d'une sorcière ?", "a": ["chat", "le chat", "chat noir"], "w": ["chien", "lapin", "souris", "cheval"]},
     "lt": {"q": "Koks gyvūnas, ypač juodas, yra klasikinis raganos palydovas?", "a": ["katė", "katinas", "juoda katė"], "w": ["šuo", "triušis", "pelė", "arklys"]},
     "ru": {"q": "Какое животное, особенно чёрное, — классический спутник ведьмы?", "a": ["кошка", "кот", "чёрный кот"], "w": ["собака", "кролик", "мышь", "лошадь"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In what large pot does a witch traditionally brew her potions?", "a": ["cauldron", "a cauldron"], "w": ["teapot", "bucket", "frying pan", "barrel"]},
     "de": {"q": "In welchem großen Topf braut eine Hexe traditionell ihre Tränke?", "a": ["kessel", "hexenkessel", "einem kessel"], "w": ["teekanne", "eimer", "bratpfanne", "fass"]},
     "es": {"q": "¿En qué gran recipiente prepara tradicionalmente una bruja sus pociones?", "a": ["caldero", "un caldero"], "w": ["tetera", "cubo", "sartén", "barril"]},
     "fr": {"q": "Dans quel grand récipient une sorcière prépare-t-elle traditionnellement ses potions ?", "a": ["chaudron", "un chaudron"], "w": ["théière", "seau", "poêle", "tonneau"]},
     "lt": {"q": "Kokiame dideliame inde ragana tradiciškai verda savo eliksyrus?", "a": ["katile", "katilas"], "w": ["arbatinuke", "kibire", "keptuvėje", "statinėje"]},
     "ru": {"q": "В каком большом сосуде ведьма традиционно варит зелья?", "a": ["в котле", "котёл", "котел"], "w": ["в чайнике", "в ведре", "в сковороде", "в бочке"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In the fairy tale 'Hansel and Gretel', what is the witch's house made of?", "a": ["gingerbread", "candy", "sweets", "cake"], "w": ["straw", "bricks", "ice", "stone"]},
     "de": {"q": "Woraus besteht im Märchen 'Hänsel und Gretel' das Haus der Hexe?", "a": ["lebkuchen", "süßigkeiten", "kuchen"], "w": ["stroh", "ziegelsteinen", "eis", "stein"]},
     "es": {"q": "En el cuento 'Hansel y Gretel', ¿de qué está hecha la casa de la bruja?", "a": ["pan de jengibre", "dulces", "golosinas", "caramelo"], "w": ["paja", "ladrillos", "hielo", "piedra"]},
     "fr": {"q": "Dans le conte 'Hansel et Gretel', en quoi est faite la maison de la sorcière ?", "a": ["pain d'épices", "bonbons", "friandises", "gâteau"], "w": ["paille", "briques", "glace", "pierre"]},
     "lt": {"q": "Iš ko pasakoje 'Jonukas ir Grytutė' pastatytas raganos namelis?", "a": ["meduolių", "saldainių", "saldumynų", "pyrago"], "w": ["šiaudų", "plytų", "ledo", "akmens"]},
     "ru": {"q": "Из чего сделан домик ведьмы в сказке «Гензель и Гретель»?", "a": ["из пряников", "пряники", "из сладостей", "из конфет"], "w": ["из соломы", "из кирпича", "изо льда", "из камня"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of the famous friendly cartoon ghost?", "a": ["casper"], "w": ["slimer", "boo", "blinky", "spooky"]},
     "de": {"q": "Wie heißt das berühmte freundliche Zeichentrick-Gespenst?", "a": ["casper"], "w": ["slimer", "boo", "blinky", "spooky"]},
     "es": {"q": "¿Cómo se llama el famoso fantasma amigable de dibujos animados?", "a": ["casper", "gasparín"], "w": ["slimer", "boo", "blinky", "spooky"]},
     "fr": {"q": "Comment s'appelle le célèbre gentil fantôme de dessin animé ?", "a": ["casper"], "w": ["slimer", "boo", "blinky", "spooky"]},
     "lt": {"q": "Kaip vadinamas garsus draugiškas animacinis vaiduokliukas?", "a": ["kasperis", "casper"], "w": ["slimeris", "bu", "blinkis", "spukis"]},
     "ru": {"q": "Как зовут знаменитого дружелюбного мультяшного привидения?", "a": ["каспер"], "w": ["лизун", "бу", "блинки", "спуки"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Who is the 'Pumpkin King' in 'The Nightmare Before Christmas'?", "a": ["jack skellington", "jack"], "w": ["oogie boogie", "sally", "zero", "lock"]},
     "de": {"q": "Wer ist der 'Kürbiskönig' in 'Nightmare Before Christmas'?", "a": ["jack skellington", "jack"], "w": ["oogie boogie", "sally", "zero", "lock"]},
     "es": {"q": "¿Quién es el 'Rey Calabaza' en 'Pesadilla antes de Navidad'?", "a": ["jack skellington", "jack"], "w": ["oogie boogie", "sally", "zero", "lock"]},
     "fr": {"q": "Qui est le 'Roi des citrouilles' dans 'L'Étrange Noël de monsieur Jack' ?", "a": ["jack skellington", "jack"], "w": ["oogie boogie", "sally", "zéro", "am"]},
     "lt": {"q": "Kas yra 'Moliūgų karalius' filme 'Košmaras prieš Kalėdas'?", "a": ["džekas skelingtonas", "džekas", "jack"], "w": ["ugis bugis", "sali", "zero", "lokas"]},
     "ru": {"q": "Кто такой «Король тыкв» в мультфильме «Кошмар перед Рождеством»?", "a": ["джек скеллингтон", "джек"], "w": ["уги буги", "салли", "зеро", "шито"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Who wrote the 1897 novel 'Dracula'?", "a": ["bram stoker", "stoker"], "w": ["mary shelley", "edgar allan poe", "stephen king", "h. p. lovecraft"]},
     "de": {"q": "Wer schrieb den Roman 'Dracula' von 1897?", "a": ["bram stoker", "stoker"], "w": ["mary shelley", "edgar allan poe", "stephen king", "h. p. lovecraft"]},
     "es": {"q": "¿Quién escribió la novela 'Drácula' de 1897?", "a": ["bram stoker", "stoker"], "w": ["mary shelley", "edgar allan poe", "stephen king", "h. p. lovecraft"]},
     "fr": {"q": "Qui a écrit le roman 'Dracula' paru en 1897 ?", "a": ["bram stoker", "stoker"], "w": ["mary shelley", "edgar allan poe", "stephen king", "h. p. lovecraft"]},
     "lt": {"q": "Kas parašė 1897 m. romaną 'Drakula'?", "a": ["bramas stokeris", "stokeris", "bram stoker"], "w": ["mary shelley", "edgaras alanas po", "stephenas kingas", "h. p. lovecraftas"]},
     "ru": {"q": "Кто написал роман «Дракула» 1897 года?", "a": ["брэм стокер", "стокер"], "w": ["мэри шелли", "эдгар аллан по", "стивен кинг", "говард лавкрафт"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In which region of Romania does Bram Stoker place Count Dracula's castle?", "a": ["transylvania"], "w": ["wallachia", "moldavia", "bavaria", "bohemia"]},
     "de": {"q": "In welcher Region Rumäniens liegt bei Bram Stoker das Schloss von Graf Dracula?", "a": ["transsilvanien", "siebenbürgen"], "w": ["walachei", "moldau", "bayern", "böhmen"]},
     "es": {"q": "¿En qué región de Rumanía sitúa Bram Stoker el castillo del conde Drácula?", "a": ["transilvania"], "w": ["valaquia", "moldavia", "baviera", "bohemia"]},
     "fr": {"q": "Dans quelle région de Roumanie Bram Stoker situe-t-il le château du comte Dracula ?", "a": ["transylvanie", "la transylvanie"], "w": ["valachie", "moldavie", "bavière", "bohême"]},
     "lt": {"q": "Kuriame Rumunijos regione Bramas Stokeris įkurdino grafo Drakulos pilį?", "a": ["transilvanijoje", "transilvanija"], "w": ["valakijoje", "moldavijoje", "bavarijoje", "bohemijoje"]},
     "ru": {"q": "В каком регионе Румынии Брэм Стокер поместил замок графа Дракулы?", "a": ["в трансильвании", "трансильвания"], "w": ["в валахии", "в молдавии", "в баварии", "в богемии"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Who wrote the famous dark poem 'The Raven'?", "a": ["edgar allan poe", "poe", "edgar poe"], "w": ["bram stoker", "mary shelley", "stephen king", "charles dickens"]},
     "de": {"q": "Wer schrieb das berühmte düstere Gedicht 'Der Rabe'?", "a": ["edgar allan poe", "poe", "edgar poe"], "w": ["bram stoker", "mary shelley", "stephen king", "charles dickens"]},
     "es": {"q": "¿Quién escribió el famoso poema sombrío 'El cuervo'?", "a": ["edgar allan poe", "poe", "edgar poe"], "w": ["bram stoker", "mary shelley", "stephen king", "charles dickens"]},
     "fr": {"q": "Qui a écrit le célèbre poème sombre 'Le Corbeau' ?", "a": ["edgar allan poe", "poe", "edgar poe"], "w": ["bram stoker", "mary shelley", "stephen king", "charles dickens"]},
     "lt": {"q": "Kas parašė garsią niūrią poemą 'Varnas'?", "a": ["edgaras alanas po", "po", "edgar allan poe"], "w": ["bramas stokeris", "mary shelley", "stephenas kingas", "charlesas dickensas"]},
     "ru": {"q": "Кто написал знаменитое мрачное стихотворение «Ворон»?", "a": ["эдгар аллан по", "эдгар по", "по"], "w": ["брэм стокер", "мэри шелли", "стивен кинг", "чарльз диккенс"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which 1978 horror film introduced the masked killer Michael Myers?", "a": ["halloween"], "w": ["scream", "friday the 13th", "the shining", "psycho"]},
     "de": {"q": "Welcher Horrorfilm von 1978 führte den maskierten Killer Michael Myers ein?", "a": ["halloween"], "w": ["scream", "freitag der 13.", "shining", "psycho"]},
     "es": {"q": "¿Qué película de terror de 1978 presentó al asesino enmascarado Michael Myers?", "a": ["halloween", "la noche de halloween"], "w": ["scream", "viernes 13", "el resplandor", "psicosis"]},
     "fr": {"q": "Quel film d'horreur de 1978 a introduit le tueur masqué Michael Myers ?", "a": ["halloween"], "w": ["scream", "vendredi 13", "shining", "psychose"]},
     "lt": {"q": "Kuris 1978 m. siaubo filmas pristatė kaukėtą žudiką Michaelą Myersą?", "a": ["helovinas", "halloween"], "w": ["klyksmas", "penktadienis, 13-oji", "švytėjimas", "psichopatas"]},
     "ru": {"q": "В каком фильме ужасов 1978 года впервые появился убийца в маске Майкл Майерс?", "a": ["хэллоуин", "halloween"], "w": ["крик", "пятница, 13-е", "сияние", "психо"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which Michael Jackson music video features him dancing with zombies?", "a": ["thriller"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]},
     "de": {"q": "In welchem Musikvideo von Michael Jackson tanzt er mit Zombies?", "a": ["thriller"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]},
     "es": {"q": "¿En qué videoclip de Michael Jackson baila con zombis?", "a": ["thriller"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]},
     "fr": {"q": "Dans quel clip de Michael Jackson danse-t-il avec des zombies ?", "a": ["thriller"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]},
     "lt": {"q": "Kuriame Michaelo Jacksono muzikiniame vaizdo klipe jis šoka su zombiais?", "a": ["thriller"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]},
     "ru": {"q": "В каком клипе Майкла Джексона он танцует с зомби?", "a": ["thriller", "триллер"], "w": ["beat it", "bad", "billie jean", "smooth criminal"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which 1984 comedy asks 'Who you gonna call?'", "a": ["ghostbusters"], "w": ["gremlins", "beetlejuice", "poltergeist", "the goonies"]},
     "de": {"q": "Welche Komödie von 1984 fragt 'Who you gonna call?'", "a": ["ghostbusters", "die geisterjäger"], "w": ["gremlins", "beetlejuice", "poltergeist", "die goonies"]},
     "es": {"q": "¿Qué comedia de 1984 pregunta 'Who you gonna call?'", "a": ["los cazafantasmas", "cazafantasmas", "ghostbusters"], "w": ["gremlins", "bitelchús", "poltergeist", "los goonies"]},
     "fr": {"q": "Quelle comédie de 1984 demande 'Who you gonna call?' ?", "a": ["s.o.s. fantômes", "sos fantômes", "ghostbusters"], "w": ["gremlins", "beetlejuice", "poltergeist", "les goonies"]},
     "lt": {"q": "Kurioje 1984 m. komedijoje klausiama 'Who you gonna call?'", "a": ["vaiduoklių medžiotojai", "ghostbusters"], "w": ["gremlinai", "beetlejuice", "poltergeistas", "gunai"]},
     "ru": {"q": "В какой комедии 1984 года звучит вопрос 'Who you gonna call?'", "a": ["охотники за привидениями", "ghostbusters"], "w": ["гремлины", "битлджус", "полтергейст", "балбесы"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of the green, slimy ghost in 'Ghostbusters'?", "a": ["slimer"], "w": ["casper", "stay puft", "zuul", "blinky"]},
     "de": {"q": "Wie heißt das grüne, schleimige Gespenst in 'Ghostbusters'?", "a": ["slimer"], "w": ["casper", "stay puft", "zuul", "blinky"]},
     "es": {"q": "¿Cómo se llama el fantasma verde y viscoso de 'Los cazafantasmas'?", "a": ["slimer", "moquete"], "w": ["casper", "stay puft", "zuul", "blinky"]},
     "fr": {"q": "Comment s'appelle le fantôme vert et visqueux de 'S.O.S. Fantômes' ?", "a": ["slimer", "bouffe-tout"], "w": ["casper", "stay puft", "zuul", "blinky"]},
     "lt": {"q": "Kaip vadinamas žalias, gleivėtas vaiduoklis filme 'Vaiduoklių medžiotojai'?", "a": ["slimeris", "slimer"], "w": ["kasperis", "stay puft", "zulas", "blinkis"]},
     "ru": {"q": "Как зовут зелёное слизкое привидение в «Охотниках за привидениями»?", "a": ["лизун", "slimer"], "w": ["каспер", "зефирный человек", "зуул", "блинки"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which 1988 Tim Burton film features a mischievous 'bio-exorcist' ghost?", "a": ["beetlejuice"], "w": ["edward scissorhands", "ghostbusters", "gremlins", "batman"]},
     "de": {"q": "In welchem Tim-Burton-Film von 1988 treibt ein schelmischer 'Bio-Exorzist' sein Unwesen?", "a": ["beetlejuice"], "w": ["edward mit den scherenhänden", "ghostbusters", "gremlins", "batman"]},
     "es": {"q": "¿Qué película de Tim Burton de 1988 tiene como protagonista a un fantasma 'bioexorcista'?", "a": ["bitelchús", "beetlejuice"], "w": ["eduardo manostijeras", "los cazafantasmas", "gremlins", "batman"]},
     "fr": {"q": "Quel film de Tim Burton de 1988 met en scène un fantôme 'bio-exorciste' farceur ?", "a": ["beetlejuice"], "w": ["edward aux mains d'argent", "s.o.s. fantômes", "gremlins", "batman"]},
     "lt": {"q": "Kuriame 1988 m. Timo Burtono filme siaučia išdykęs vaiduoklis 'bioegzorcistas'?", "a": ["beetlejuice", "bitlždiusas"], "w": ["edvardas žirklarankis", "vaiduoklių medžiotojai", "gremlinai", "betmenas"]},
     "ru": {"q": "В каком фильме Тима Бёртона 1988 года действует озорной призрак-«биоэкзорцист»?", "a": ["битлджус", "beetlejuice"], "w": ["эдвард руки-ножницы", "охотники за привидениями", "гремлины", "бэтмен"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "How many times must you say 'Beetlejuice' to summon him?", "a": ["3", "three"], "w": ["1", "2", "5", "7"]},
     "de": {"q": "Wie oft muss man 'Beetlejuice' sagen, um ihn herbeizurufen?", "a": ["3", "drei", "dreimal"], "w": ["1", "2", "5", "7"]},
     "es": {"q": "¿Cuántas veces hay que decir 'Bitelchús' para invocarlo?", "a": ["3", "tres"], "w": ["1", "2", "5", "7"]},
     "fr": {"q": "Combien de fois faut-il dire 'Beetlejuice' pour l'invoquer ?", "a": ["3", "trois"], "w": ["1", "2", "5", "7"]},
     "lt": {"q": "Kiek kartų reikia ištarti 'Beetlejuice', kad jį iškviestum?", "a": ["3", "tris", "tris kartus"], "w": ["1", "2", "5", "7"]},
     "ru": {"q": "Сколько раз нужно произнести «Битлджус», чтобы его вызвать?", "a": ["3", "три", "трижды"], "w": ["1", "2", "5", "7"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "How many Sanderson sisters are there in 'Hocus Pocus'?", "a": ["3", "three"], "w": ["2", "4", "5", "7"]},
     "de": {"q": "Wie viele Sanderson-Schwestern gibt es in 'Hocus Pocus'?", "a": ["3", "drei"], "w": ["2", "4", "5", "7"]},
     "es": {"q": "¿Cuántas hermanas Sanderson hay en 'El retorno de las brujas'?", "a": ["3", "tres"], "w": ["2", "4", "5", "7"]},
     "fr": {"q": "Combien y a-t-il de sœurs Sanderson dans 'Hocus Pocus' ?", "a": ["3", "trois"], "w": ["2", "4", "5", "7"]},
     "lt": {"q": "Kiek seserų Sanderson yra filme 'Hocus Pocus'?", "a": ["3", "trys"], "w": ["2", "4", "5", "7"]},
     "ru": {"q": "Сколько сестёр Сандерсон в фильме «Фокус-покус»?", "a": ["3", "три"], "w": ["2", "4", "5", "7"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'The Addams Family', what is the name of the disembodied hand?", "a": ["thing"], "w": ["lurch", "itt", "fester", "pugsley"]},
     "de": {"q": "Wie heißt in der 'Addams Family' die körperlose Hand?", "a": ["das eiskalte händchen", "eiskaltes händchen", "thing"], "w": ["lurch", "itt", "fester", "pugsley"]},
     "es": {"q": "En 'La familia Addams', ¿cómo se llama la mano sin cuerpo?", "a": ["dedos", "cosa", "la cosa", "thing"], "w": ["largo", "tío cosa", "fétido", "pericles"]},
     "fr": {"q": "Dans 'La Famille Addams', comment s'appelle la main sans corps ?", "a": ["la chose", "chose", "thing"], "w": ["max", "cousin machin", "fétide", "pugsley"]},
     "lt": {"q": "Kaip filme 'Adamsų šeimynėlė' vadinama ranka be kūno?", "a": ["daiktas", "thing", "ranka"], "w": ["lerčas", "itas", "festeris", "pagslis"]},
     "ru": {"q": "Как зовут живую руку без тела в «Семейке Аддамс»?", "a": ["вещь", "thing"], "w": ["ларч", "ит", "фестер", "пагсли"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of the gloomy daughter in 'The Addams Family'?", "a": ["wednesday", "wednesday addams"], "w": ["morticia", "sabrina", "lily", "elvira"]},
     "de": {"q": "Wie heißt die düstere Tochter in der 'Addams Family'?", "a": ["wednesday", "wednesday addams"], "w": ["morticia", "sabrina", "lily", "elvira"]},
     "es": {"q": "¿Cómo se llama la sombría hija de 'La familia Addams'?", "a": ["miércoles", "merlina", "wednesday"], "w": ["morticia", "sabrina", "lily", "elvira"]},
     "fr": {"q": "Comment s'appelle la fille lugubre de 'La Famille Addams' ?", "a": ["mercredi", "wednesday"], "w": ["morticia", "sabrina", "lily", "elvira"]},
     "lt": {"q": "Kaip vadinasi niūrioji 'Adamsų šeimynėlės' dukra?", "a": ["wednesday", "trečiadienė", "venzdei"], "w": ["mortiša", "sabrina", "lili", "elvyra"]},
     "ru": {"q": "Как зовут мрачную дочь в «Семейке Аддамс»?", "a": ["уэнсдэй", "уэнсдей", "wednesday"], "w": ["мортиша", "сабрина", "лили", "эльвира"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which horror villain from 'Friday the 13th' wears a hockey mask?", "a": ["jason", "jason voorhees"], "w": ["freddy krueger", "michael myers", "leatherface", "chucky"]},
     "de": {"q": "Welcher Horror-Bösewicht aus 'Freitag der 13.' trägt eine Eishockeymaske?", "a": ["jason", "jason voorhees"], "w": ["freddy krueger", "michael myers", "leatherface", "chucky"]},
     "es": {"q": "¿Qué villano de terror de 'Viernes 13' lleva una máscara de hockey?", "a": ["jason", "jason voorhees"], "w": ["freddy krueger", "michael myers", "leatherface", "chucky"]},
     "fr": {"q": "Quel méchant de 'Vendredi 13' porte un masque de hockey ?", "a": ["jason", "jason voorhees"], "w": ["freddy krueger", "michael myers", "leatherface", "chucky"]},
     "lt": {"q": "Kuris siaubo filmo 'Penktadienis, 13-oji' piktadarys dėvi ledo ritulio kaukę?", "a": ["džeisonas", "jason", "džeisonas vurhizas"], "w": ["fredis krugeris", "maiklas maiersas", "odinis veidas", "čakis"]},
     "ru": {"q": "Какой злодей из «Пятницы, 13-е» носит хоккейную маску?", "a": ["джейсон", "джейсон вурхиз"], "w": ["фредди крюгер", "майкл майерс", "кожаное лицо", "чаки"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which horror villain wears a glove with razor-sharp blades?", "a": ["freddy krueger", "freddy"], "w": ["jason voorhees", "michael myers", "chucky", "ghostface"]},
     "de": {"q": "Welcher Horror-Bösewicht trägt einen Handschuh mit messerscharfen Klingen?", "a": ["freddy krueger", "freddy"], "w": ["jason voorhees", "michael myers", "chucky", "ghostface"]},
     "es": {"q": "¿Qué villano de terror lleva un guante con cuchillas afiladas?", "a": ["freddy krueger", "freddy"], "w": ["jason voorhees", "michael myers", "chucky", "ghostface"]},
     "fr": {"q": "Quel méchant de film d'horreur porte un gant muni de lames tranchantes ?", "a": ["freddy krueger", "freddy"], "w": ["jason voorhees", "michael myers", "chucky", "ghostface"]},
     "lt": {"q": "Kuris siaubo filmų piktadarys mūvi pirštinę su aštriais ašmenimis?", "a": ["fredis krugeris", "fredis", "freddy krueger"], "w": ["džeisonas vurhizas", "maiklas maiersas", "čakis", "vaiduoklio veidas"]},
     "ru": {"q": "Какой злодей из фильмов ужасов носит перчатку с острыми лезвиями?", "a": ["фредди крюгер", "фредди"], "w": ["джейсон вурхиз", "майкл майерс", "чаки", "призрачное лицо"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is the name of the killer doll in the 'Child's Play' films?", "a": ["chucky"], "w": ["annabelle", "slappy", "billy", "m3gan"]},
     "de": {"q": "Wie heißt die Mörderpuppe in den 'Chucky'-Filmen ('Child's Play')?", "a": ["chucky"], "w": ["annabelle", "slappy", "billy", "m3gan"]},
     "es": {"q": "¿Cómo se llama el muñeco asesino de la saga 'Muñeco diabólico'?", "a": ["chucky"], "w": ["annabelle", "slappy", "billy", "m3gan"]},
     "fr": {"q": "Comment s'appelle la poupée tueuse de la saga 'Jeu d'enfant' ?", "a": ["chucky"], "w": ["annabelle", "slappy", "billy", "m3gan"]},
     "lt": {"q": "Kaip vadinama lėlė žudikė iš filmų 'Vaikų žaidimas'?", "a": ["čakis", "chucky"], "w": ["anabelė", "slepis", "bilis", "m3gan"]},
     "ru": {"q": "Как зовут куклу-убийцу из фильмов «Детские игры»?", "a": ["чаки"], "w": ["аннабель", "слэппи", "билли", "м3ган"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which Stephen King novel features the evil clown Pennywise?", "a": ["it"], "w": ["carrie", "misery", "cujo", "the shining"]},
     "de": {"q": "In welchem Roman von Stephen King kommt der böse Clown Pennywise vor?", "a": ["es", "it"], "w": ["carrie", "sie", "cujo", "shining"]},
     "es": {"q": "¿En qué novela de Stephen King aparece el payaso malvado Pennywise?", "a": ["it", "eso"], "w": ["carrie", "misery", "cujo", "el resplandor"]},
     "fr": {"q": "Dans quel roman de Stephen King apparaît le clown maléfique Pennywise ?", "a": ["ça", "it"], "w": ["carrie", "misery", "cujo", "shining"]},
     "lt": {"q": "Kuriame Stepheno Kingo romane veikia piktasis klounas Pennywise?", "a": ["tai", "it"], "w": ["kerė", "kančia", "kudžo", "švytėjimas"]},
     "ru": {"q": "В каком романе Стивена Кинга действует злой клоун Пеннивайз?", "a": ["оно", "it"], "w": ["кэрри", "мизери", "куджо", "сияние"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What does Pennywise the clown famously hold to lure children?", "a": ["red balloon", "balloon", "a balloon"], "w": ["lollipop", "umbrella", "teddy bear", "kite"]},
     "de": {"q": "Was hält der Clown Pennywise bekanntlich in der Hand, um Kinder anzulocken?", "a": ["roter luftballon", "luftballon", "ballon"], "w": ["lutscher", "regenschirm", "teddybär", "drachen"]},
     "es": {"q": "¿Qué sostiene famosamente el payaso Pennywise para atraer a los niños?", "a": ["globo rojo", "un globo", "globo"], "w": ["piruleta", "paraguas", "osito de peluche", "cometa"]},
     "fr": {"q": "Que tient le clown Pennywise pour attirer les enfants ?", "a": ["ballon rouge", "un ballon", "ballon"], "w": ["sucette", "parapluie", "ours en peluche", "cerf-volant"]},
     "lt": {"q": "Ką klounas Pennywise laiko rankoje, kad priviliotų vaikus?", "a": ["raudoną balioną", "balioną", "balionas"], "w": ["ledinuką", "skėtį", "pliušinį meškiuką", "aitvarą"]},
     "ru": {"q": "Что держит в руке клоун Пеннивайз, чтобы заманивать детей?", "a": ["красный шарик", "шарик", "воздушный шар"], "w": ["леденец", "зонтик", "плюшевого мишку", "воздушного змея"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which fruit do players try to grab with their teeth in a classic Halloween party game?", "a": ["apple", "apples", "an apple"], "w": ["orange", "pear", "plum", "banana"]},
     "de": {"q": "Welches Obst versucht man bei einem klassischen Halloween-Partyspiel mit den Zähnen zu schnappen?", "a": ["apfel", "äpfel"], "w": ["orange", "birne", "pflaume", "banane"]},
     "es": {"q": "¿Qué fruta intentan atrapar con los dientes en un clásico juego de fiesta de Halloween?", "a": ["manzana", "manzanas"], "w": ["naranja", "pera", "ciruela", "plátano"]},
     "fr": {"q": "Quel fruit essaie-t-on d'attraper avec les dents lors d'un jeu classique des fêtes d'Halloween ?", "a": ["pomme", "pommes", "la pomme"], "w": ["orange", "poire", "prune", "banane"]},
     "lt": {"q": "Kokį vaisių klasikiniame Helovino vakarėlio žaidime bandoma sugriebti dantimis?", "a": ["obuolį", "obuolys", "obuolius"], "w": ["apelsiną", "kriaušę", "slyvą", "bananą"]},
     "ru": {"q": "Какой фрукт пытаются схватить зубами в классической игре на вечеринке в Хэллоуин?", "a": ["яблоко", "яблоки"], "w": ["апельсин", "грушу", "сливу", "банан"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which tri-colored, kernel-shaped candy is a Halloween favorite in the US?", "a": ["candy corn"], "w": ["jelly beans", "gummy bears", "licorice", "marshmallows"]},
     "de": {"q": "Welche dreifarbige Süßigkeit in Form eines Maiskorns ist in den USA zu Halloween beliebt?", "a": ["candy corn", "zuckermais"], "w": ["jelly beans", "gummibärchen", "lakritz", "marshmallows"]},
     "es": {"q": "¿Qué caramelo tricolor con forma de grano de maíz es un favorito de Halloween en EE. UU.?", "a": ["candy corn", "maíz dulce"], "w": ["gominolas", "ositos de goma", "regaliz", "nubes"]},
     "fr": {"q": "Quelle confiserie tricolore en forme de grain de maïs est très populaire à Halloween aux États-Unis ?", "a": ["candy corn", "maïs bonbon"], "w": ["dragibus", "oursons en gélatine", "réglisse", "guimauves"]},
     "lt": {"q": "Koks trispalvis kukurūzo grūdo formos saldainis JAV mėgstamas per Heloviną?", "a": ["candy corn", "saldūs kukurūzai"], "w": ["želė pupelės", "guminukai meškiukai", "saldymedis", "zefyrai"]},
     "ru": {"q": "Какая трёхцветная конфета в форме кукурузного зерна популярна в США на Хэллоуин?", "a": ["candy corn", "конфетная кукуруза"], "w": ["джелли белли", "мармеладные мишки", "лакрица", "маршмеллоу"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What is traditionally placed inside a carved pumpkin to make it glow?", "a": ["candle", "a candle"], "w": ["flashlight", "firefly", "glow stick", "lightbulb"]},
     "de": {"q": "Was stellt man traditionell in einen geschnitzten Kürbis, damit er leuchtet?", "a": ["kerze", "eine kerze"], "w": ["taschenlampe", "glühwürmchen", "knicklicht", "glühbirne"]},
     "es": {"q": "¿Qué se coloca tradicionalmente dentro de una calabaza tallada para que brille?", "a": ["vela", "una vela"], "w": ["linterna", "luciérnaga", "barra luminosa", "bombilla"]},
     "fr": {"q": "Que place-t-on traditionnellement dans une citrouille sculptée pour la faire briller ?", "a": ["bougie", "une bougie"], "w": ["lampe de poche", "luciole", "bâton lumineux", "ampoule"]},
     "lt": {"q": "Kas tradiciškai dedama į išskaptuotą moliūgą, kad jis švytėtų?", "a": ["žvakė", "žvakę"], "w": ["žibintuvėlis", "jonvabalis", "šviečianti lazdelė", "lemputė"]},
     "ru": {"q": "Что традиционно ставят внутрь вырезанной тыквы, чтобы она светилась?", "a": ["свечу", "свеча"], "w": ["фонарик", "светлячка", "светящуюся палочку", "лампочку"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "According to folklore, which strong-smelling bulb keeps vampires away?", "a": ["garlic"], "w": ["onion", "ginger", "leek", "shallot"]},
     "de": {"q": "Welche stark riechende Knolle hält laut Volksglauben Vampire fern?", "a": ["knoblauch"], "w": ["zwiebel", "ingwer", "lauch", "schalotte"]},
     "es": {"q": "Según el folclore, ¿qué bulbo de olor fuerte ahuyenta a los vampiros?", "a": ["ajo", "el ajo"], "w": ["cebolla", "jengibre", "puerro", "chalota"]},
     "fr": {"q": "Selon le folklore, quel bulbe à l'odeur forte éloigne les vampires ?", "a": ["ail", "l'ail"], "w": ["oignon", "gingembre", "poireau", "échalote"]},
     "lt": {"q": "Kuris aštraus kvapo augalas, pasak tautosakos, atbaido vampyrus?", "a": ["česnakas", "česnakai"], "w": ["svogūnas", "imbieras", "poras", "askaloninis česnakas"]},
     "ru": {"q": "Какое растение с резким запахом, по поверьям, отпугивает вампиров?", "a": ["чеснок"], "w": ["лук", "имбирь", "лук-порей", "шалот"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "According to legend, in what can a vampire not see their own reflection?", "a": ["mirror", "a mirror", "mirrors"], "w": ["candle", "book", "clock", "painting"]},
     "de": {"q": "Worin kann ein Vampir laut Legende sein eigenes Spiegelbild nicht sehen?", "a": ["spiegel", "im spiegel"], "w": ["kerze", "buch", "uhr", "gemälde"]},
     "es": {"q": "Según la leyenda, ¿en qué no puede ver un vampiro su propio reflejo?", "a": ["espejo", "en el espejo", "espejos"], "w": ["vela", "libro", "reloj", "cuadro"]},
     "fr": {"q": "Selon la légende, dans quoi un vampire ne peut-il pas voir son reflet ?", "a": ["miroir", "dans un miroir", "le miroir"], "w": ["bougie", "livre", "horloge", "tableau"]},
     "lt": {"q": "Pasak legendos, kur vampyras negali pamatyti savo atspindžio?", "a": ["veidrodyje", "veidrodis"], "w": ["žvakėje", "knygoje", "laikrodyje", "paveiksle"]},
     "ru": {"q": "Согласно легенде, в чём вампир не видит своего отражения?", "a": ["в зеркале", "зеркало"], "w": ["в свече", "в книге", "в часах", "в картине"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What wooden object driven through the heart is said to kill a vampire?", "a": ["stake", "a stake", "wooden stake"], "w": ["spoon", "arrow", "nail", "club"]},
     "de": {"q": "Welcher Holzgegenstand soll einen Vampir töten, wenn man ihn ins Herz treibt?", "a": ["pflock", "holzpflock", "pfahl"], "w": ["löffel", "pfeil", "nagel", "keule"]},
     "es": {"q": "¿Qué objeto de madera clavado en el corazón mata a un vampiro, según la leyenda?", "a": ["estaca", "una estaca"], "w": ["cuchara", "flecha", "clavo", "garrote"]},
     "fr": {"q": "Quel objet en bois, planté dans le cœur, tuerait un vampire ?", "a": ["pieu", "un pieu"], "w": ["cuillère", "flèche", "clou", "massue"]},
     "lt": {"q": "Koks medinis daiktas, įsmeigtas į širdį, pasak legendos, nužudo vampyrą?", "a": ["kuolas", "drebulės kuolas", "kuolą"], "w": ["šaukštas", "strėlė", "vinis", "vėzdas"]},
     "ru": {"q": "Какой деревянный предмет, вбитый в сердце, по преданию убивает вампира?", "a": ["кол", "осиновый кол"], "w": ["ложка", "стрела", "гвоздь", "дубина"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Bullets made of which metal are said to kill werewolves?", "a": ["silver"], "w": ["gold", "iron", "copper", "lead"]},
     "de": {"q": "Kugeln aus welchem Metall sollen Werwölfe töten?", "a": ["silber"], "w": ["gold", "eisen", "kupfer", "blei"]},
     "es": {"q": "¿Las balas de qué metal matan a los hombres lobo, según la leyenda?", "a": ["plata", "de plata"], "w": ["oro", "hierro", "cobre", "plomo"]},
     "fr": {"q": "Les balles de quel métal tueraient les loups-garous ?", "a": ["argent", "en argent"], "w": ["or", "fer", "cuivre", "plomb"]},
     "lt": {"q": "Kokio metalo kulkos, pasak legendų, nužudo vilkolakius?", "a": ["sidabro", "sidabras", "sidabrinės"], "w": ["aukso", "geležies", "vario", "švino"]},
     "ru": {"q": "Пули из какого металла, по легендам, убивают оборотней?", "a": ["серебро", "серебряные", "из серебра"], "w": ["золото", "железо", "медь", "свинец"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which mythical creature is a reanimated corpse that craves brains?", "a": ["zombie", "a zombie"], "w": ["vampire", "ghost", "werewolf", "goblin"]},
     "de": {"q": "Welches Fabelwesen ist eine wiederbelebte Leiche, die nach Gehirnen giert?", "a": ["zombie"], "w": ["vampir", "gespenst", "werwolf", "kobold"]},
     "es": {"q": "¿Qué criatura es un cadáver reanimado que ansía comer cerebros?", "a": ["zombi", "zombie"], "w": ["vampiro", "fantasma", "hombre lobo", "duende"]},
     "fr": {"q": "Quelle créature est un cadavre réanimé avide de cerveaux ?", "a": ["zombie", "un zombie"], "w": ["vampire", "fantôme", "loup-garou", "lutin"]},
     "lt": {"q": "Kuri būtybė yra atgaivintas lavonas, trokštantis smegenų?", "a": ["zombis"], "w": ["vampyras", "vaiduoklis", "vilkolakis", "goblinas"]},
     "ru": {"q": "Какое существо — это оживший мертвец, жаждущий мозгов?", "a": ["зомби"], "w": ["вампир", "призрак", "оборотень", "гоблин"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which ancient civilization is most famous for mummifying its dead?", "a": ["egypt", "ancient egypt", "egyptians", "the egyptians"], "w": ["rome", "greece", "the vikings", "the aztecs"]},
     "de": {"q": "Welche antike Zivilisation ist am bekanntesten für die Mumifizierung ihrer Toten?", "a": ["ägypten", "altes ägypten", "die ägypter", "ägypter"], "w": ["rom", "griechenland", "die wikinger", "die azteken"]},
     "es": {"q": "¿Qué civilización antigua es la más famosa por momificar a sus muertos?", "a": ["egipto", "antiguo egipto", "los egipcios", "egipcios"], "w": ["roma", "grecia", "los vikingos", "los aztecas"]},
     "fr": {"q": "Quelle civilisation antique est la plus célèbre pour avoir momifié ses morts ?", "a": ["égypte", "l'égypte", "les égyptiens", "égypte antique"], "w": ["rome", "la grèce", "les vikings", "les aztèques"]},
     "lt": {"q": "Kuri senovės civilizacija labiausiai garsėja savo mirusiųjų mumifikavimu?", "a": ["egiptas", "senovės egiptas", "egiptiečiai"], "w": ["roma", "graikija", "vikingai", "actekai"]},
     "ru": {"q": "Какая древняя цивилизация больше всего известна мумифицированием умерших?", "a": ["египет", "древний египет", "египтяне"], "w": ["рим", "греция", "викинги", "ацтеки"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What straw-stuffed figure is placed in fields to frighten birds away?", "a": ["scarecrow", "a scarecrow"], "w": ["snowman", "garden gnome", "totem pole", "mannequin"]},
     "de": {"q": "Welche mit Stroh gefüllte Figur stellt man auf Felder, um Vögel zu verscheuchen?", "a": ["vogelscheuche"], "w": ["schneemann", "gartenzwerg", "totempfahl", "schaufensterpuppe"]},
     "es": {"q": "¿Qué figura rellena de paja se coloca en los campos para ahuyentar a los pájaros?", "a": ["espantapájaros", "un espantapájaros"], "w": ["muñeco de nieve", "gnomo de jardín", "tótem", "maniquí"]},
     "fr": {"q": "Quelle figure rembourrée de paille place-t-on dans les champs pour effrayer les oiseaux ?", "a": ["épouvantail", "un épouvantail"], "w": ["bonhomme de neige", "nain de jardin", "totem", "mannequin"]},
     "lt": {"q": "Kokia šiaudais prikimšta figūra statoma laukuose paukščiams baidyti?", "a": ["kaliausė", "baidyklė"], "w": ["sniego senis", "sodo nykštukas", "totemas", "manekenas"]},
     "ru": {"q": "Какую набитую соломой фигуру ставят в поле, чтобы отпугивать птиц?", "a": ["пугало", "чучело"], "w": ["снеговик", "садовый гном", "тотем", "манекен"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What glass sphere does a fortune teller gaze into to see the future?", "a": ["crystal ball", "a crystal ball"], "w": ["snow globe", "marble", "fishbowl", "lantern"]},
     "de": {"q": "In welche Glaskugel blickt eine Wahrsagerin, um die Zukunft zu sehen?", "a": ["kristallkugel", "glaskugel"], "w": ["schneekugel", "murmel", "goldfischglas", "laterne"]},
     "es": {"q": "¿En qué esfera de cristal mira una adivina para ver el futuro?", "a": ["bola de cristal", "una bola de cristal"], "w": ["bola de nieve", "canica", "pecera", "farol"]},
     "fr": {"q": "Dans quelle sphère de verre une voyante regarde-t-elle pour voir l'avenir ?", "a": ["boule de cristal", "une boule de cristal"], "w": ["boule à neige", "bille", "bocal à poisson", "lanterne"]},
     "lt": {"q": "Į kokį stiklinį rutulį žiūri būrėja, norėdama išvysti ateitį?", "a": ["krištolinis rutulys", "krištolinį rutulį"], "w": ["sniego gaublys", "stiklinis kamuoliukas", "akvariumas", "žibintas"]},
     "ru": {"q": "В какой стеклянный шар смотрит гадалка, чтобы увидеть будущее?", "a": ["хрустальный шар", "магический шар"], "w": ["снежный шар", "стеклянный шарик", "аквариум", "фонарь"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "According to superstition, which animal crossing your path brings bad luck?", "a": ["black cat", "a black cat"], "w": ["white dog", "red fox", "brown rabbit", "grey mouse"]},
     "de": {"q": "Welches Tier bringt laut Aberglauben Unglück, wenn es einem über den Weg läuft?", "a": ["schwarze katze", "eine schwarze katze"], "w": ["weißer hund", "roter fuchs", "brauner hase", "graue maus"]},
     "es": {"q": "Según la superstición, ¿qué animal trae mala suerte si se cruza en tu camino?", "a": ["gato negro", "un gato negro"], "w": ["perro blanco", "zorro rojo", "conejo marrón", "ratón gris"]},
     "fr": {"q": "Selon la superstition, quel animal porte malheur s'il croise votre chemin ?", "a": ["chat noir", "un chat noir"], "w": ["chien blanc", "renard roux", "lapin brun", "souris grise"]},
     "lt": {"q": "Pasak prietarų, koks gyvūnas, perbėgęs kelią, atneša nelaimę?", "a": ["juoda katė", "juodas katinas"], "w": ["baltas šuo", "rudoji lapė", "rudas triušis", "pilka pelė"]},
     "ru": {"q": "Согласно суеверию, какое животное приносит несчастье, перебегая дорогу?", "a": ["чёрная кошка", "черная кошка", "чёрный кот"], "w": ["белая собака", "рыжая лиса", "бурый кролик", "серая мышь"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "According to superstition, how many years of bad luck follow breaking a mirror?", "a": ["7", "seven"], "w": ["3", "5", "10", "13"]},
     "de": {"q": "Wie viele Jahre Pech bringt laut Aberglauben ein zerbrochener Spiegel?", "a": ["7", "sieben"], "w": ["3", "5", "10", "13"]},
     "es": {"q": "Según la superstición, ¿cuántos años de mala suerte trae romper un espejo?", "a": ["7", "siete"], "w": ["3", "5", "10", "13"]},
     "fr": {"q": "Selon la superstition, combien d'années de malheur suivent un miroir brisé ?", "a": ["7", "sept"], "w": ["3", "5", "10", "13"]},
     "lt": {"q": "Pasak prietarų, kiek metų nesėkmės atneša sudaužytas veidrodis?", "a": ["7", "septynerius", "septyneri"], "w": ["3", "5", "10", "13"]},
     "ru": {"q": "Согласно суеверию, сколько лет несчастий приносит разбитое зеркало?", "a": ["7", "семь"], "w": ["3", "5", "10", "13"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'The Nightmare Before Christmas', which holiday does Jack Skellington try to take over?", "a": ["christmas"], "w": ["easter", "thanksgiving", "valentine's day", "new year"]},
     "de": {"q": "Welches Fest versucht Jack Skellington in 'Nightmare Before Christmas' zu übernehmen?", "a": ["weihnachten"], "w": ["ostern", "thanksgiving", "valentinstag", "neujahr"]},
     "es": {"q": "En 'Pesadilla antes de Navidad', ¿qué fiesta intenta apropiarse Jack Skellington?", "a": ["navidad", "la navidad"], "w": ["pascua", "acción de gracias", "san valentín", "año nuevo"]},
     "fr": {"q": "Dans 'L'Étrange Noël de monsieur Jack', quelle fête Jack tente-t-il de s'approprier ?", "a": ["noël"], "w": ["pâques", "thanksgiving", "la saint-valentin", "nouvel an"]},
     "lt": {"q": "Kurią šventę filme 'Košmaras prieš Kalėdas' bando perimti Džekas Skelingtonas?", "a": ["kalėdas", "kalėdos"], "w": ["velykas", "padėkos dieną", "valentino dieną", "naujuosius metus"]},
     "ru": {"q": "Какой праздник пытается захватить Джек Скеллингтон в «Кошмаре перед Рождеством»?", "a": ["рождество"], "w": ["пасху", "день благодарения", "день святого валентина", "новый год"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which 2017 Pixar film is set during Mexico's Day of the Dead?", "a": ["coco"], "w": ["encanto", "luca", "up", "soul"]},
     "de": {"q": "Welcher Pixar-Film von 2017 spielt während des mexikanischen Tags der Toten?", "a": ["coco"], "w": ["encanto", "luca", "oben", "soul"]},
     "es": {"q": "¿Qué película de Pixar de 2017 transcurre durante el Día de Muertos en México?", "a": ["coco"], "w": ["encanto", "luca", "up", "soul"]},
     "fr": {"q": "Quel film Pixar de 2017 se déroule pendant le Jour des morts au Mexique ?", "a": ["coco"], "w": ["encanto", "luca", "là-haut", "soul"]},
     "lt": {"q": "Kuris 2017 m. Pixar filmas vyksta per Meksikos Mirusiųjų dieną?", "a": ["koko", "coco"], "w": ["užkerėtieji", "luka", "aukštyn", "siela"]},
     "ru": {"q": "Действие какого мультфильма Pixar 2017 года происходит в мексиканский День мёртвых?", "a": ["тайна коко", "коко"], "w": ["энканто", "лука", "вверх", "душа"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'Hotel Transylvania', which famous monster runs the hotel?", "a": ["dracula", "count dracula"], "w": ["frankenstein", "the mummy", "a werewolf", "the invisible man"]},
     "de": {"q": "Welches berühmte Monster führt in 'Hotel Transsilvanien' das Hotel?", "a": ["dracula", "graf dracula"], "w": ["frankenstein", "die mumie", "ein werwolf", "der unsichtbare"]},
     "es": {"q": "En 'Hotel Transilvania', ¿qué famoso monstruo dirige el hotel?", "a": ["drácula", "el conde drácula"], "w": ["frankenstein", "la momia", "un hombre lobo", "el hombre invisible"]},
     "fr": {"q": "Dans 'Hôtel Transylvanie', quel monstre célèbre dirige l'hôtel ?", "a": ["dracula", "le comte dracula"], "w": ["frankenstein", "la momie", "un loup-garou", "l'homme invisible"]},
     "lt": {"q": "Kuris garsus monstras vadovauja viešbučiui filme 'Viešbutis Transilvanija'?", "a": ["drakula", "grafas drakula"], "w": ["frankenšteinas", "mumija", "vilkolakis", "nematomas žmogus"]},
     "ru": {"q": "Какой знаменитый монстр управляет отелем в мультфильме «Монстры на каникулах»?", "a": ["дракула", "граф дракула"], "w": ["франкенштейн", "мумия", "оборотень", "человек-невидимка"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'Monsters, Inc.', what do the monsters collect from children to power their city?", "a": ["screams", "scream"], "w": ["tears", "snores", "dreams", "teeth"]},
     "de": {"q": "Was sammeln die Monster in 'Die Monster AG' von Kindern, um ihre Stadt mit Energie zu versorgen?", "a": ["schreie", "schrei", "kinderschreie"], "w": ["tränen", "schnarcher", "träume", "zähne"]},
     "es": {"q": "En 'Monstruos, S.A.', ¿qué recogen los monstruos de los niños para dar energía a su ciudad?", "a": ["gritos", "grito"], "w": ["lágrimas", "ronquidos", "sueños", "dientes"]},
     "fr": {"q": "Dans 'Monstres & Cie', que récoltent les monstres auprès des enfants pour alimenter leur ville ?", "a": ["cris", "les cris", "des cris"], "w": ["larmes", "ronflements", "rêves", "dents"]},
     "lt": {"q": "Ką filme 'Pabaisų bendrovė' pabaisos renka iš vaikų, kad tiektų energiją savo miestui?", "a": ["riksmus", "klyksmus", "riksmai"], "w": ["ašaras", "knarkimą", "sapnus", "dantis"]},
     "ru": {"q": "Что монстры в «Корпорации монстров» собирают у детей, чтобы снабжать город энергией?", "a": ["крики", "детские крики"], "w": ["слёзы", "храп", "сны", "зубы"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'Monsters, Inc.', what nickname does Sulley give the little girl?", "a": ["boo"], "w": ["lily", "dot", "rose", "kitty"]},
     "de": {"q": "Welchen Spitznamen gibt Sulley in 'Die Monster AG' dem kleinen Mädchen?", "a": ["buh", "boo"], "w": ["lily", "dot", "rose", "kitty"]},
     "es": {"q": "En 'Monstruos, S.A.', ¿qué apodo le pone Sulley a la niña pequeña?", "a": ["boo"], "w": ["lily", "dot", "rose", "kitty"]},
     "fr": {"q": "Dans 'Monstres & Cie', quel surnom Sulli donne-t-il à la petite fille ?", "a": ["bouh", "boo"], "w": ["lily", "dot", "rose", "kitty"]},
     "lt": {"q": "Kokią pravardę filme 'Pabaisų bendrovė' Saulis duoda mažajai mergaitei?", "a": ["bu", "boo"], "w": ["lilė", "dot", "rožė", "kiti"]},
     "ru": {"q": "Какое прозвище Салли даёт маленькой девочке в «Корпорации монстров»?", "a": ["бу", "boo"], "w": ["лили", "дот", "роуз", "китти"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'Scooby-Doo', what is the name of the gang's van?", "a": ["mystery machine", "the mystery machine"], "w": ["ghost mobile", "spooky bus", "monster truck", "clue cruiser"]},
     "de": {"q": "Wie heißt in 'Scooby-Doo' der Van der Bande?", "a": ["mystery machine", "die mystery machine"], "w": ["geistermobil", "gruselbus", "monstertruck", "spurenflitzer"]},
     "es": {"q": "En 'Scooby-Doo', ¿cómo se llama la furgoneta de la pandilla?", "a": ["la máquina del misterio", "máquina del misterio", "mystery machine"], "w": ["fantasmóvil", "autobús tenebroso", "monster truck", "pista móvil"]},
     "fr": {"q": "Dans 'Scooby-Doo', comment s'appelle le van de la bande ?", "a": ["la mystery machine", "mystery machine", "la machine à mystères"], "w": ["la fantômobile", "le bus hanté", "le monster truck", "la cluemobile"]},
     "lt": {"q": "Kaip animaciniame seriale 'Skubis Du' vadinamas gaujos furgonas?", "a": ["paslapčių mašina", "mystery machine"], "w": ["vaiduoklių mobilis", "baisusis autobusas", "monstrų sunkvežimis", "įkalčių ekspresas"]},
     "ru": {"q": "Как называется фургон команды в «Скуби-Ду»?", "a": ["машина загадок", "мистическая машина", "mystery machine"], "w": ["призракомобиль", "жуткий автобус", "монстр-трак", "фургон улик"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What breed of dog is Scooby-Doo?", "a": ["great dane"], "w": ["beagle", "boxer", "labrador", "saint bernard"]},
     "de": {"q": "Welcher Hunderasse gehört Scooby-Doo an?", "a": ["deutsche dogge", "dogge"], "w": ["beagle", "boxer", "labrador", "bernhardiner"]},
     "es": {"q": "¿De qué raza es el perro Scooby-Doo?", "a": ["gran danés", "dogo alemán"], "w": ["beagle", "bóxer", "labrador", "san bernardo"]},
     "fr": {"q": "De quelle race est le chien Scooby-Doo ?", "a": ["dogue allemand", "danois", "grand danois"], "w": ["beagle", "boxer", "labrador", "saint-bernard"]},
     "lt": {"q": "Kokios veislės šuo yra Skubis Du?", "a": ["vokiečių dogas", "dogas"], "w": ["biglis", "bokseris", "labradoras", "senbernaras"]},
     "ru": {"q": "Какой породы собака Скуби-Ду?", "a": ["немецкий дог", "дог"], "w": ["бигль", "боксёр", "лабрадор", "сенбернар"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'Peanuts', which character waits all Halloween night for the Great Pumpkin?", "a": ["linus", "linus van pelt"], "w": ["snoopy", "charlie brown", "lucy", "schroeder"]},
     "de": {"q": "Welche 'Peanuts'-Figur wartet die ganze Halloween-Nacht auf den Großen Kürbis?", "a": ["linus", "linus van pelt"], "w": ["snoopy", "charlie brown", "lucy", "schroeder"]},
     "es": {"q": "En 'Peanuts', ¿qué personaje espera toda la noche de Halloween a la Gran Calabaza?", "a": ["linus", "linus van pelt"], "w": ["snoopy", "charlie brown", "lucy", "schroeder"]},
     "fr": {"q": "Dans 'Peanuts', quel personnage attend toute la nuit d'Halloween la Grande Citrouille ?", "a": ["linus", "linus van pelt"], "w": ["snoopy", "charlie brown", "lucy", "schroeder"]},
     "lt": {"q": "Kuris 'Peanuts' veikėjas visą Helovino naktį laukia Didžiojo Moliūgo?", "a": ["lainusas", "linus", "linusas"], "w": ["snupis", "čarlis braunas", "liusė", "šrioderis"]},
     "ru": {"q": "Какой персонаж «Peanuts» всю ночь Хэллоуина ждёт Великую Тыкву?", "a": ["лайнус", "линус"], "w": ["снупи", "чарли браун", "люси", "шрёдер"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In Shakespeare's 'Macbeth', how many witches prophesy Macbeth's future?", "a": ["3", "three"], "w": ["2", "4", "5", "7"]},
     "de": {"q": "Wie viele Hexen sagen in Shakespeares 'Macbeth' Macbeths Zukunft voraus?", "a": ["3", "drei"], "w": ["2", "4", "5", "7"]},
     "es": {"q": "En 'Macbeth' de Shakespeare, ¿cuántas brujas profetizan el futuro de Macbeth?", "a": ["3", "tres"], "w": ["2", "4", "5", "7"]},
     "fr": {"q": "Dans 'Macbeth' de Shakespeare, combien de sorcières prédisent l'avenir de Macbeth ?", "a": ["3", "trois"], "w": ["2", "4", "5", "7"]},
     "lt": {"q": "Kiek raganų Shakespeare'o 'Makbete' išpranašauja Makbeto ateitį?", "a": ["3", "trys"], "w": ["2", "4", "5", "7"]},
     "ru": {"q": "Сколько ведьм предсказывают будущее Макбету в пьесе Шекспира «Макбет»?", "a": ["3", "три"], "w": ["2", "4", "5", "7"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "In 'The Wizard of Oz', what makes the Wicked Witch of the West melt?", "a": ["water", "a bucket of water"], "w": ["fire", "sunlight", "salt", "milk"]},
     "de": {"q": "Wodurch schmilzt in 'Der Zauberer von Oz' die Böse Hexe des Westens?", "a": ["wasser", "einen eimer wasser"], "w": ["feuer", "sonnenlicht", "salz", "milch"]},
     "es": {"q": "En 'El mago de Oz', ¿qué hace que la Malvada Bruja del Oeste se derrita?", "a": ["agua", "un cubo de agua"], "w": ["fuego", "luz del sol", "sal", "leche"]},
     "fr": {"q": "Dans 'Le Magicien d'Oz', qu'est-ce qui fait fondre la Méchante Sorcière de l'Ouest ?", "a": ["l'eau", "eau", "un seau d'eau"], "w": ["le feu", "le soleil", "le sel", "le lait"]},
     "lt": {"q": "Kas filme 'Ozo šalies burtininkas' ištirpdo Piktąją Vakarų raganą?", "a": ["vanduo", "vandens kibiras"], "w": ["ugnis", "saulės šviesa", "druska", "pienas"]},
     "ru": {"q": "Отчего тает Злая Ведьма Запада в фильме «Волшебник страны Оз»?", "a": ["от воды", "вода", "ведро воды"], "w": ["от огня", "от солнца", "от соли", "от молока"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which Roald Dahl book is about witches who plan to turn children into mice?", "a": ["the witches", "witches"], "w": ["matilda", "the bfg", "the twits", "danny"]},
     "de": {"q": "In welchem Buch von Roald Dahl planen Hexen, Kinder in Mäuse zu verwandeln?", "a": ["hexen hexen", "die hexen"], "w": ["matilda", "sophiechen und der riese", "die zwicks", "danny"]},
     "es": {"q": "¿Qué libro de Roald Dahl trata de brujas que quieren convertir a los niños en ratones?", "a": ["las brujas", "brujas"], "w": ["matilda", "el gran gigante bonachón", "los cretinos", "danny"]},
     "fr": {"q": "Quel livre de Roald Dahl parle de sorcières qui veulent changer les enfants en souris ?", "a": ["sacrées sorcières", "les sorcières"], "w": ["matilda", "le bon gros géant", "les deux gredins", "danny"]},
     "lt": {"q": "Kurioje Roaldo Dahlo knygoje raganos planuoja paversti vaikus pelėmis?", "a": ["raganos"], "w": ["matilda", "didysis gerasis milžinas", "tvitai", "denis"]},
     "ru": {"q": "В какой книге Роальда Даля ведьмы хотят превратить детей в мышей?", "a": ["ведьмы"], "w": ["матильда", "большой и добрый великан", "свинтусы", "дэнни"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "What do bats mainly use to find their way in the dark?", "a": ["echolocation", "sound", "echoes"], "w": ["smell", "magnetism", "starlight", "heat"]},
     "de": {"q": "Womit finden sich Fledermäuse im Dunkeln hauptsächlich zurecht?", "a": ["echoortung", "ultraschall", "echolot"], "w": ["geruch", "magnetismus", "sternenlicht", "wärme"]},
     "es": {"q": "¿Qué usan principalmente los murciélagos para orientarse en la oscuridad?", "a": ["ecolocalización", "ecos", "sonido"], "w": ["el olfato", "el magnetismo", "la luz de las estrellas", "el calor"]},
     "fr": {"q": "Qu'utilisent principalement les chauves-souris pour se repérer dans le noir ?", "a": ["écholocalisation", "l'écholocalisation", "ultrasons"], "w": ["l'odorat", "le magnétisme", "la lumière des étoiles", "la chaleur"]},
     "lt": {"q": "Kuo šikšnosparniai daugiausia naudojasi orientuodamiesi tamsoje?", "a": ["echolokacija", "ultragarsu", "aidu"], "w": ["uosle", "magnetizmu", "žvaigždžių šviesa", "šiluma"]},
     "ru": {"q": "Что в основном используют летучие мыши, чтобы ориентироваться в темноте?", "a": ["эхолокацию", "эхолокация", "ультразвук"], "w": ["обоняние", "магнетизм", "свет звёзд", "тепло"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which popular autumn coffee drink did Starbucks launch in 2003?", "a": ["pumpkin spice latte", "psl"], "w": ["caramel macchiato", "flat white", "mocha", "chai latte"]},
     "de": {"q": "Welches beliebte Herbst-Kaffeegetränk brachte Starbucks 2003 heraus?", "a": ["pumpkin spice latte", "psl", "kürbis-latte"], "w": ["caramel macchiato", "flat white", "mokka", "chai latte"]},
     "es": {"q": "¿Qué popular bebida de café otoñal lanzó Starbucks en 2003?", "a": ["pumpkin spice latte", "psl", "latte de calabaza"], "w": ["caramel macchiato", "flat white", "moca", "chai latte"]},
     "fr": {"q": "Quelle boisson automnale au café Starbucks a-t-il lancée en 2003 ?", "a": ["pumpkin spice latte", "psl", "latte à la citrouille"], "w": ["caramel macchiato", "flat white", "moka", "chai latte"]},
     "lt": {"q": "Kokį populiarų rudens kavos gėrimą Starbucks pristatė 2003 m.?", "a": ["pumpkin spice latte", "psl", "moliūgų latte"], "w": ["karamelinis makiatas", "flat white", "moka", "chai latte"]},
     "ru": {"q": "Какой популярный осенний кофейный напиток Starbucks выпустил в 2003 году?", "a": ["pumpkin spice latte", "тыквенный латте", "psl"], "w": ["карамельный макиато", "флэт уайт", "мокко", "чай латте"]}},

    {"difficulty": "easy", "points": 700,
     "en": {"q": "Which nocturnal bird can turn its head about 270 degrees?", "a": ["owl", "an owl", "the owl"], "w": ["hawk", "crow", "parrot", "eagle"]},
     "de": {"q": "Welcher nachtaktive Vogel kann seinen Kopf um etwa 270 Grad drehen?", "a": ["eule", "die eule"], "w": ["falke", "krähe", "papagei", "adler"]},
     "es": {"q": "¿Qué ave nocturna puede girar la cabeza unos 270 grados?", "a": ["búho", "lechuza", "el búho"], "w": ["halcón", "cuervo", "loro", "águila"]},
     "fr": {"q": "Quel oiseau nocturne peut tourner la tête d'environ 270 degrés ?", "a": ["hibou", "chouette", "le hibou"], "w": ["faucon", "corneille", "perroquet", "aigle"]},
     "lt": {"q": "Kuris naktinis paukštis gali pasukti galvą maždaug 270 laipsnių?", "a": ["pelėda"], "w": ["vanagas", "varna", "papūga", "erelis"]},
     "ru": {"q": "Какая ночная птица может поворачивать голову примерно на 270 градусов?", "a": ["сова"], "w": ["ястреб", "ворона", "попугай", "орёл"]}},

    # ---------------- NORMAL (800 / 900 pts) ----------------
    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which ancient Celtic festival is Halloween believed to have grown out of?", "a": ["samhain"], "w": ["beltane", "yule", "imbolc", "lughnasadh"]},
     "de": {"q": "Aus welchem alten keltischen Fest soll sich Halloween entwickelt haben?", "a": ["samhain"], "w": ["beltane", "jul", "imbolc", "lughnasadh"]},
     "es": {"q": "¿De qué antigua festividad celta se cree que surgió Halloween?", "a": ["samhain"], "w": ["beltane", "yule", "imbolc", "lughnasadh"]},
     "fr": {"q": "De quelle ancienne fête celtique Halloween serait-il issu ?", "a": ["samhain"], "w": ["beltane", "yule", "imbolc", "lugnasad"]},
     "lt": {"q": "Iš kurios senovės keltų šventės, manoma, kilo Helovinas?", "a": ["samhainas", "samhain"], "w": ["beltainas", "julis", "imbolkas", "lugnasadas"]},
     "ru": {"q": "Из какого древнего кельтского праздника, как считается, вырос Хэллоуин?", "a": ["самайн"], "w": ["белтейн", "йоль", "имболк", "лугнасад"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In which country did Halloween traditions largely originate?", "a": ["ireland"], "w": ["usa", "england", "mexico", "germany"]},
     "de": {"q": "In welchem Land haben die Halloween-Bräuche größtenteils ihren Ursprung?", "a": ["irland"], "w": ["usa", "england", "mexiko", "deutschland"]},
     "es": {"q": "¿En qué país se originaron en gran parte las tradiciones de Halloween?", "a": ["irlanda"], "w": ["ee. uu.", "inglaterra", "méxico", "alemania"]},
     "fr": {"q": "Dans quel pays les traditions d'Halloween sont-elles en grande partie nées ?", "a": ["irlande", "l'irlande"], "w": ["états-unis", "angleterre", "mexique", "allemagne"]},
     "lt": {"q": "Kurioje šalyje daugiausia atsirado Helovino tradicijos?", "a": ["airijoje", "airija"], "w": ["jav", "anglijoje", "meksikoje", "vokietijoje"]},
     "ru": {"q": "В какой стране в основном зародились традиции Хэллоуина?", "a": ["в ирландии", "ирландия"], "w": ["в сша", "в англии", "в мексике", "в германии"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of the Mexican holiday in early November that honors deceased loved ones?", "a": ["day of the dead", "dia de los muertos", "día de muertos"], "w": ["cinco de mayo", "las posadas", "carnival", "candlemas"]},
     "de": {"q": "Wie heißt der mexikanische Feiertag Anfang November, an dem man verstorbener Angehöriger gedenkt?", "a": ["tag der toten", "día de muertos", "dia de los muertos"], "w": ["cinco de mayo", "las posadas", "karneval", "lichtmess"]},
     "es": {"q": "¿Cómo se llama la festividad mexicana de principios de noviembre que honra a los seres queridos fallecidos?", "a": ["día de muertos", "día de los muertos", "dia de muertos"], "w": ["cinco de mayo", "las posadas", "carnaval", "la candelaria"]},
     "fr": {"q": "Comment s'appelle la fête mexicaine de début novembre qui honore les proches disparus ?", "a": ["jour des morts", "le jour des morts", "día de muertos"], "w": ["cinco de mayo", "las posadas", "carnaval", "chandeleur"]},
     "lt": {"q": "Kaip vadinama lapkričio pradžios Meksikos šventė, kuria pagerbiami mirę artimieji?", "a": ["mirusiųjų diena", "día de muertos"], "w": ["cinco de mayo", "las posadas", "karnavalas", "grabnyčios"]},
     "ru": {"q": "Как называется мексиканский праздник в начале ноября, посвящённый умершим близким?", "a": ["день мёртвых", "день мертвых", "día de muertos"], "w": ["синко де майо", "лас посадас", "карнавал", "сретение"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of Jack Skellington's ghost dog in 'The Nightmare Before Christmas'?", "a": ["zero"], "w": ["sparky", "bones", "spot", "casper"]},
     "de": {"q": "Wie heißt Jack Skellingtons Geisterhund in 'Nightmare Before Christmas'?", "a": ["zero"], "w": ["sparky", "bones", "spot", "casper"]},
     "es": {"q": "¿Cómo se llama el perro fantasma de Jack Skellington en 'Pesadilla antes de Navidad'?", "a": ["zero", "cero"], "w": ["sparky", "huesos", "manchas", "casper"]},
     "fr": {"q": "Comment s'appelle le chien fantôme de Jack dans 'L'Étrange Noël de monsieur Jack' ?", "a": ["zéro", "zero"], "w": ["sparky", "os", "tache", "casper"]},
     "lt": {"q": "Kaip vadinamas Džeko Skelingtono šuo vaiduoklis filme 'Košmaras prieš Kalėdas'?", "a": ["zero", "nulis"], "w": ["sparkis", "kaulas", "taškis", "kasperis"]},
     "ru": {"q": "Как зовут собаку-призрака Джека Скеллингтона в «Кошмаре перед Рождеством»?", "a": ["зеро", "ноль"], "w": ["спарки", "косточка", "пятнышко", "каспер"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Mary Shelley's novel, what is the first name of the scientist Frankenstein?", "a": ["victor"], "w": ["igor", "william", "albert", "edgar"]},
     "de": {"q": "Wie lautet in Mary Shelleys Roman der Vorname des Wissenschaftlers Frankenstein?", "a": ["victor", "viktor"], "w": ["igor", "william", "albert", "edgar"]},
     "es": {"q": "En la novela de Mary Shelley, ¿cuál es el nombre de pila del científico Frankenstein?", "a": ["víctor", "victor"], "w": ["igor", "william", "alberto", "edgar"]},
     "fr": {"q": "Dans le roman de Mary Shelley, quel est le prénom du savant Frankenstein ?", "a": ["victor"], "w": ["igor", "william", "albert", "edgar"]},
     "lt": {"q": "Koks Mary Shelley romane yra mokslininko Frankenšteino vardas?", "a": ["viktoras", "victor"], "w": ["igoris", "viljamas", "albertas", "edgaras"]},
     "ru": {"q": "Как зовут учёного Франкенштейна в романе Мэри Шелли?", "a": ["виктор"], "w": ["игорь", "уильям", "альберт", "эдгар"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'The Legend of Sleepy Hollow', what does the Headless Horseman throw at Ichabod Crane?", "a": ["pumpkin", "a pumpkin"], "w": ["rock", "axe", "lantern", "skull"]},
     "de": {"q": "Was wirft der kopflose Reiter in 'Die Sage von der schläfrigen Schlucht' nach Ichabod Crane?", "a": ["kürbis", "einen kürbis"], "w": ["stein", "axt", "laterne", "schädel"]},
     "es": {"q": "En 'La leyenda de Sleepy Hollow', ¿qué le lanza el Jinete sin Cabeza a Ichabod Crane?", "a": ["calabaza", "una calabaza"], "w": ["piedra", "hacha", "farol", "calavera"]},
     "fr": {"q": "Dans 'La Légende de Sleepy Hollow', que lance le Cavalier sans tête sur Ichabod Crane ?", "a": ["citrouille", "une citrouille"], "w": ["pierre", "hache", "lanterne", "crâne"]},
     "lt": {"q": "Ką apsakyme 'Mieguistosios daubos legenda' Raitelis be galvos sviedžia į Ichabodą Kreiną?", "a": ["moliūgą", "moliūgas"], "w": ["akmenį", "kirvį", "žibintą", "kaukolę"]},
     "ru": {"q": "Что Всадник без головы бросает в Икабода Крейна в «Легенде о Сонной Лощине»?", "a": ["тыкву", "тыква"], "w": ["камень", "топор", "фонарь", "череп"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Edgar Allan Poe's 'The Raven', what single word does the raven repeat?", "a": ["nevermore"], "w": ["forever", "goodbye", "tomorrow", "lenore"]},
     "de": {"q": "Welches einzelne Wort wiederholt der Rabe in Edgar Allan Poes 'Der Rabe'?", "a": ["nimmermehr", "nevermore"], "w": ["für immer", "lebwohl", "morgen", "lenore"]},
     "es": {"q": "En 'El cuervo' de Edgar Allan Poe, ¿qué palabra repite el cuervo?", "a": ["nunca más", "nevermore"], "w": ["por siempre", "adiós", "mañana", "leonora"]},
     "fr": {"q": "Dans 'Le Corbeau' d'Edgar Allan Poe, quel mot le corbeau répète-t-il ?", "a": ["jamais plus", "nevermore"], "w": ["toujours", "adieu", "demain", "lénore"]},
     "lt": {"q": "Kokį vieną žodį kartoja varnas Edgaro Alano Po poemoje 'Varnas'?", "a": ["niekada", "nevermore", "niekados"], "w": ["amžinai", "sudie", "rytoj", "lenora"]},
     "ru": {"q": "Какое слово повторяет ворон в стихотворении Эдгара По «Ворон»?", "a": ["никогда", "nevermore", "больше никогда"], "w": ["навеки", "прощай", "завтра", "ленор"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which 1962 novelty song by Bobby 'Boris' Pickett is a Halloween party classic?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]},
     "de": {"q": "Welcher Spaßsong von Bobby 'Boris' Pickett aus dem Jahr 1962 ist ein Halloween-Partyklassiker?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]},
     "es": {"q": "¿Qué canción humorística de 1962 de Bobby 'Boris' Pickett es un clásico de las fiestas de Halloween?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]},
     "fr": {"q": "Quelle chanson humoristique de 1962 de Bobby 'Boris' Pickett est un classique des fêtes d'Halloween ?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]},
     "lt": {"q": "Kuri 1962 m. Bobby 'Boris' Pickett humoristinė daina yra Helovino vakarėlių klasika?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]},
     "ru": {"q": "Какая шуточная песня Бобби «Бориса» Пикетта 1962 года — классика вечеринок на Хэллоуин?", "a": ["monster mash", "the monster mash"], "w": ["thriller", "ghostbusters", "the time warp", "purple people eater"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'Ghostbusters' (1984), what giant monster stomps through New York at the climax?", "a": ["stay puft marshmallow man", "stay puft", "marshmallow man"], "w": ["slimer", "zuul", "godzilla", "vigo"]},
     "de": {"q": "Welches Riesenmonster stapft im Finale von 'Ghostbusters' (1984) durch New York?", "a": ["marshmallow-mann", "stay puft", "marshmallow man"], "w": ["slimer", "zuul", "godzilla", "vigo"]},
     "es": {"q": "En 'Los cazafantasmas' (1984), ¿qué monstruo gigante arrasa Nueva York en el clímax?", "a": ["hombre de malvavisco", "stay puft", "muñeco de malvavisco"], "w": ["slimer", "zuul", "godzilla", "vigo"]},
     "fr": {"q": "Dans 'S.O.S. Fantômes' (1984), quel monstre géant piétine New York lors du final ?", "a": ["bibendum chamallow", "stay puft", "marshmallow man"], "w": ["slimer", "zuul", "godzilla", "vigo"]},
     "lt": {"q": "Koks milžiniškas monstras filmo 'Vaiduoklių medžiotojai' (1984) finale žygiuoja per Niujorką?", "a": ["zefyrų žmogus", "stay puft", "zefyrinis žmogus"], "w": ["slimeris", "zulas", "godzila", "vigo"]},
     "ru": {"q": "Какой гигантский монстр шагает по Нью-Йорку в финале «Охотников за привидениями» (1984)?", "a": ["зефирный человек", "stay puft", "зефирный великан"], "w": ["лизун", "зуул", "годзилла", "виго"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Before pumpkins, which root vegetable did the Irish carve into lanterns?", "a": ["turnip", "turnips", "swede"], "w": ["potato", "beetroot", "carrot", "onion"]},
     "de": {"q": "Welches Wurzelgemüse schnitzten die Iren zu Laternen, bevor es Kürbisse gab?", "a": ["rübe", "steckrübe", "rüben"], "w": ["kartoffel", "rote bete", "karotte", "zwiebel"]},
     "es": {"q": "Antes de las calabazas, ¿qué tubérculo tallaban los irlandeses como farol?", "a": ["nabo", "nabos", "colinabo"], "w": ["patata", "remolacha", "zanahoria", "cebolla"]},
     "fr": {"q": "Avant les citrouilles, quel légume-racine les Irlandais creusaient-ils pour en faire des lanternes ?", "a": ["navet", "le navet", "rutabaga"], "w": ["pomme de terre", "betterave", "carotte", "oignon"]},
     "lt": {"q": "Kokią šakniavaisę daržovę airiai skaptuodavo žibintams dar prieš moliūgus?", "a": ["ropę", "ropė", "griežtis", "sėtinė ropė"], "w": ["bulvę", "burokėlį", "morką", "svogūną"]},
     "ru": {"q": "Какой корнеплод ирландцы вырезали в виде фонарей до появления тыкв?", "a": ["репа", "репу", "брюква"], "w": ["картофель", "свёкла", "морковь", "лук"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Irish legend, what nickname is given to the man the jack-o'-lantern is named after?", "a": ["stingy jack"], "w": ["jumping jack", "lazy jack", "jolly jack", "black jack"]},
     "de": {"q": "Welchen Spitznamen trägt in der irischen Sage der Mann, nach dem die Kürbislaterne benannt ist?", "a": ["stingy jack", "geiziger jack", "der geizige jack"], "w": ["springender jack", "fauler jack", "fröhlicher jack", "schwarzer jack"]},
     "es": {"q": "En la leyenda irlandesa, ¿qué apodo tiene el hombre que da nombre al farol de calabaza?", "a": ["stingy jack", "jack el tacaño"], "w": ["jack el saltarín", "jack el perezoso", "jack el alegre", "jack el negro"]},
     "fr": {"q": "Dans la légende irlandaise, quel surnom porte l'homme qui a donné son nom à la citrouille-lanterne ?", "a": ["stingy jack", "jack le radin", "jack l'avare"], "w": ["jack le sauteur", "jack le paresseux", "jack le joyeux", "jack le noir"]},
     "lt": {"q": "Kokią pravardę airių legendoje turi vyras, kurio vardu pavadintas moliūgo žibintas?", "a": ["šykštusis džekas", "stingy jack"], "w": ["šokinėjantis džekas", "tinginys džekas", "linksmasis džekas", "juodasis džekas"]},
     "ru": {"q": "Какое прозвище в ирландской легенде носит человек, в честь которого назван фонарь из тыквы?", "a": ["скупой джек", "stingy jack"], "w": ["прыгучий джек", "ленивый джек", "весёлый джек", "чёрный джек"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "What is the fear of Halloween called?", "a": ["samhainophobia"], "w": ["arachnophobia", "claustrophobia", "coulrophobia", "nyctophobia"]},
     "de": {"q": "Wie nennt man die Angst vor Halloween?", "a": ["samhainophobie"], "w": ["arachnophobie", "klaustrophobie", "coulrophobie", "nyktophobie"]},
     "es": {"q": "¿Cómo se llama el miedo a Halloween?", "a": ["samhainofobia"], "w": ["aracnofobia", "claustrofobia", "coulrofobia", "nictofobia"]},
     "fr": {"q": "Comment appelle-t-on la peur d'Halloween ?", "a": ["samhainophobie"], "w": ["arachnophobie", "claustrophobie", "coulrophobie", "nyctophobie"]},
     "lt": {"q": "Kaip vadinama Helovino baimė?", "a": ["samhainofobija"], "w": ["arachnofobija", "klaustrofobija", "kulrofobija", "niktofobija"]},
     "ru": {"q": "Как называется страх перед Хэллоуином?", "a": ["самайнофобия"], "w": ["арахнофобия", "клаустрофобия", "коулрофобия", "никтофобия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the collective name for a group of witches?", "a": ["coven", "a coven"], "w": ["flock", "pack", "swarm", "herd"]},
     "de": {"q": "Wie nennt man im Englischen eine Gruppe von Hexen ('a ... of witches')?", "a": ["coven", "zirkel", "hexenzirkel"], "w": ["flock", "pack", "swarm", "herd"]},
     "es": {"q": "¿Cómo se llama un grupo de brujas?", "a": ["aquelarre", "un aquelarre", "coven"], "w": ["bandada", "manada", "enjambre", "rebaño"]},
     "fr": {"q": "Comment appelle-t-on un groupe de sorcières ?", "a": ["un covent", "covent", "coven", "un cercle"], "w": ["une volée", "une meute", "un essaim", "un troupeau"]},
     "lt": {"q": "Kaip angliškai vadinama raganų grupė ('a ... of witches')?", "a": ["coven", "kovenas"], "w": ["flock", "pack", "swarm", "herd"]},
     "ru": {"q": "Как по-английски называется группа ведьм ('a ... of witches')?", "a": ["coven", "ковен"], "w": ["flock", "pack", "swarm", "herd"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which venomous spider is known for the red hourglass mark on its belly?", "a": ["black widow", "the black widow"], "w": ["tarantula", "wolf spider", "brown recluse", "huntsman spider"]},
     "de": {"q": "Welche giftige Spinne ist für die rote Sanduhr-Markierung an ihrem Bauch bekannt?", "a": ["schwarze witwe", "die schwarze witwe"], "w": ["vogelspinne", "wolfsspinne", "braune einsiedlerspinne", "riesenkrabbenspinne"]},
     "es": {"q": "¿Qué araña venenosa es conocida por la marca roja en forma de reloj de arena en su abdomen?", "a": ["viuda negra", "la viuda negra"], "w": ["tarántula", "araña lobo", "araña reclusa parda", "araña cazadora"]},
     "fr": {"q": "Quelle araignée venimeuse est connue pour la tache rouge en forme de sablier sur son ventre ?", "a": ["veuve noire", "la veuve noire"], "w": ["tarentule", "araignée-loup", "recluse brune", "araignée chasseuse"]},
     "lt": {"q": "Kuris nuodingas voras garsėja raudona smėlio laikrodžio formos dėme ant pilvelio?", "a": ["juodoji našlė"], "w": ["tarantulas", "vilkvoris", "rudasis atsiskyrėlis", "voras medžiotojas"]},
     "ru": {"q": "Какой ядовитый паук известен красной отметиной в форме песочных часов на брюшке?", "a": ["чёрная вдова", "черная вдова"], "w": ["тарантул", "паук-волк", "коричневый отшельник", "паук-охотник"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Pumpkins belong to the same plant family as which of these?", "a": ["cucumber", "cucumbers"], "w": ["potato", "carrot", "tomato", "onion"]},
     "de": {"q": "Kürbisse gehören zur selben Pflanzenfamilie wie welches dieser Gemüse?", "a": ["gurke", "gurken"], "w": ["kartoffel", "karotte", "tomate", "zwiebel"]},
     "es": {"q": "¿Las calabazas pertenecen a la misma familia de plantas que cuál de estos?", "a": ["pepino", "pepinos"], "w": ["patata", "zanahoria", "tomate", "cebolla"]},
     "fr": {"q": "Les citrouilles appartiennent à la même famille de plantes que lequel de ces légumes ?", "a": ["concombre", "le concombre"], "w": ["pomme de terre", "carotte", "tomate", "oignon"]},
     "lt": {"q": "Su kuria iš šių daržovių moliūgai priklauso tai pačiai augalų šeimai?", "a": ["agurku", "agurkas"], "w": ["bulve", "morka", "pomidoru", "svogūnu"]},
     "ru": {"q": "К одному семейству растений с тыквой относится какой из этих овощей?", "a": ["огурец"], "w": ["картофель", "морковь", "помидор", "лук"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "Which US state grows the most pumpkins?", "a": ["illinois"], "w": ["california", "texas", "ohio", "florida"]},
     "de": {"q": "Welcher US-Bundesstaat baut die meisten Kürbisse an?", "a": ["illinois"], "w": ["kalifornien", "texas", "ohio", "florida"]},
     "es": {"q": "¿Qué estado de EE. UU. cultiva más calabazas?", "a": ["illinois"], "w": ["california", "texas", "ohio", "florida"]},
     "fr": {"q": "Quel État américain cultive le plus de citrouilles ?", "a": ["illinois", "l'illinois"], "w": ["californie", "texas", "ohio", "floride"]},
     "lt": {"q": "Kurioje JAV valstijoje užauginama daugiausia moliūgų?", "a": ["ilinojuje", "ilinojus", "illinois"], "w": ["kalifornijoje", "teksase", "ohajuje", "floridoje"]},
     "ru": {"q": "В каком штате США выращивают больше всего тыкв?", "a": ["иллинойс", "в иллинойсе"], "w": ["калифорния", "техас", "огайо", "флорида"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which bright orange flower is used to decorate altars on Mexico's Day of the Dead?", "a": ["marigold", "marigolds", "cempasúchil"], "w": ["rose", "tulip", "lily", "sunflower"]},
     "de": {"q": "Welche leuchtend orangefarbene Blume schmückt in Mexiko am Tag der Toten die Altäre?", "a": ["studentenblume", "tagetes", "studentenblumen"], "w": ["rose", "tulpe", "lilie", "sonnenblume"]},
     "es": {"q": "¿Qué flor de color naranja intenso se usa para decorar los altares del Día de Muertos?", "a": ["cempasúchil", "flor de muerto", "cempasúchitl"], "w": ["rosa", "tulipán", "lirio", "girasol"]},
     "fr": {"q": "Quelle fleur orange vif décore les autels lors du Jour des morts au Mexique ?", "a": ["œillet d'inde", "tagète", "souci", "rose d'inde"], "w": ["rose", "tulipe", "lys", "tournesol"]},
     "lt": {"q": "Kokia ryškiai oranžinė gėlė puošia altorius per Meksikos Mirusiųjų dieną?", "a": ["serentis", "serenčiai", "serenčių"], "w": ["rožė", "tulpė", "lelija", "saulėgrąža"]},
     "ru": {"q": "Какой ярко-оранжевый цветок украшает алтари в мексиканский День мёртвых?", "a": ["бархатцы", "тагетес"], "w": ["роза", "тюльпан", "лилия", "подсолнух"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Alfred Hitchcock horror film features the Bates Motel?", "a": ["psycho"], "w": ["the birds", "vertigo", "rear window", "rebecca"]},
     "de": {"q": "In welchem Horrorfilm von Alfred Hitchcock kommt das Bates Motel vor?", "a": ["psycho"], "w": ["die vögel", "vertigo", "das fenster zum hof", "rebecca"]},
     "es": {"q": "¿En qué película de terror de Alfred Hitchcock aparece el motel Bates?", "a": ["psicosis"], "w": ["los pájaros", "vértigo", "la ventana indiscreta", "rebeca"]},
     "fr": {"q": "Dans quel film d'horreur d'Alfred Hitchcock apparaît le motel Bates ?", "a": ["psychose"], "w": ["les oiseaux", "sueurs froides", "fenêtre sur cour", "rebecca"]},
     "lt": {"q": "Kuriame Alfredo Hitchcocko siaubo filme yra Beitsų motelis?", "a": ["psichopatas", "psycho"], "w": ["paukščiai", "svaigulys", "galinis langas", "rebeka"]},
     "ru": {"q": "В каком фильме ужасов Альфреда Хичкока есть мотель Бейтса?", "a": ["психо", "психоз"], "w": ["птицы", "головокружение", "окно во двор", "ребекка"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which 1973 horror film is about a girl possessed by a demon named Pazuzu?", "a": ["the exorcist", "exorcist"], "w": ["the omen", "carrie", "poltergeist", "rosemary's baby"]},
     "de": {"q": "In welchem Horrorfilm von 1973 ist ein Mädchen von einem Dämon namens Pazuzu besessen?", "a": ["der exorzist", "exorzist"], "w": ["das omen", "carrie", "poltergeist", "rosemaries baby"]},
     "es": {"q": "¿Qué película de terror de 1973 trata de una niña poseída por un demonio llamado Pazuzu?", "a": ["el exorcista", "exorcista"], "w": ["la profecía", "carrie", "poltergeist", "la semilla del diablo"]},
     "fr": {"q": "Quel film d'horreur de 1973 raconte l'histoire d'une fillette possédée par le démon Pazuzu ?", "a": ["l'exorciste", "exorciste"], "w": ["la malédiction", "carrie", "poltergeist", "rosemary's baby"]},
     "lt": {"q": "Kuris 1973 m. siaubo filmas pasakoja apie mergaitę, apsėstą demono Pazuzu?", "a": ["egzorcistas"], "w": ["ženklas", "kerė", "poltergeistas", "rouzmari kūdikis"]},
     "ru": {"q": "Какой фильм ужасов 1973 года рассказывает о девочке, одержимой демоном Пазузу?", "a": ["изгоняющий дьявола", "экзорцист"], "w": ["омен", "кэрри", "полтергейст", "ребёнок розмари"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'The Shining', what is the name of the haunted hotel?", "a": ["overlook hotel", "the overlook", "overlook"], "w": ["bates motel", "grand budapest", "continental", "hotel california"]},
     "de": {"q": "Wie heißt in 'Shining' das Spukhotel?", "a": ["overlook hotel", "overlook", "das overlook"], "w": ["bates motel", "grand budapest", "continental", "hotel california"]},
     "es": {"q": "En 'El resplandor', ¿cómo se llama el hotel encantado?", "a": ["hotel overlook", "overlook", "el overlook"], "w": ["motel bates", "gran hotel budapest", "continental", "hotel california"]},
     "fr": {"q": "Dans 'Shining', comment s'appelle l'hôtel hanté ?", "a": ["overlook hotel", "l'overlook", "overlook"], "w": ["motel bates", "grand budapest", "continental", "hotel california"]},
     "lt": {"q": "Kaip filme 'Švytėjimas' vadinamas vaiduoklių apsėstas viešbutis?", "a": ["overlook", "overlook viešbutis", "overlukas"], "w": ["beitsų motelis", "grand budapest", "continental", "hotel california"]},
     "ru": {"q": "Как называется отель с привидениями в фильме «Сияние»?", "a": ["оверлук", "отель оверлук"], "w": ["мотель бейтса", "гранд будапешт", "континенталь", "отель калифорния"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which 1984 film warns never to feed its creatures after midnight?", "a": ["gremlins"], "w": ["critters", "ghostbusters", "the goonies", "e.t."]},
     "de": {"q": "Welcher Film von 1984 warnt davor, seine Wesen nach Mitternacht zu füttern?", "a": ["gremlins", "gremlins – kleine monster"], "w": ["critters", "ghostbusters", "die goonies", "e.t."]},
     "es": {"q": "¿Qué película de 1984 advierte que nunca hay que alimentar a sus criaturas después de medianoche?", "a": ["gremlins"], "w": ["critters", "los cazafantasmas", "los goonies", "e.t."]},
     "fr": {"q": "Quel film de 1984 interdit de nourrir ses créatures après minuit ?", "a": ["gremlins"], "w": ["critters", "s.o.s. fantômes", "les goonies", "e.t."]},
     "lt": {"q": "Kuris 1984 m. filmas įspėja niekada nešerti jo būtybių po vidurnakčio?", "a": ["gremlinai", "gremlins"], "w": ["kriteriai", "vaiduoklių medžiotojai", "gunai", "ateivis"]},
     "ru": {"q": "Какой фильм 1984 года предупреждает: никогда не кормите этих существ после полуночи?", "a": ["гремлины"], "w": ["зубастики", "охотники за привидениями", "балбесы", "инопланетянин"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In the film 'Coraline', what does the Other Mother have instead of eyes?", "a": ["buttons", "black buttons"], "w": ["coins", "marbles", "beads", "stones"]},
     "de": {"q": "Was hat die Andere Mutter im Film 'Coraline' anstelle von Augen?", "a": ["knöpfe", "schwarze knöpfe"], "w": ["münzen", "murmeln", "perlen", "steine"]},
     "es": {"q": "En la película 'Los mundos de Coraline', ¿qué tiene la Otra Madre en lugar de ojos?", "a": ["botones", "botones negros"], "w": ["monedas", "canicas", "cuentas", "piedras"]},
     "fr": {"q": "Dans le film 'Coraline', qu'a l'Autre Mère à la place des yeux ?", "a": ["des boutons", "boutons", "boutons noirs"], "w": ["des pièces", "des billes", "des perles", "des pierres"]},
     "lt": {"q": "Ką filme 'Koralina' Kitoji mama turi vietoj akių?", "a": ["sagas", "sagos", "juodas sagas"], "w": ["monetas", "stiklinius rutuliukus", "karoliukus", "akmenukus"]},
     "ru": {"q": "Что у Другой Мамы вместо глаз в мультфильме «Коралина в Стране Кошмаров»?", "a": ["пуговицы", "чёрные пуговицы"], "w": ["монеты", "стеклянные шарики", "бусины", "камешки"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Mary Shelley's 'Frankenstein' is subtitled 'The Modern' who?", "a": ["prometheus"], "w": ["hercules", "icarus", "zeus", "odysseus"]},
     "de": {"q": "Mary Shelleys 'Frankenstein' trägt den Untertitel 'Der moderne' wer?", "a": ["prometheus"], "w": ["herkules", "ikarus", "zeus", "odysseus"]},
     "es": {"q": "El subtítulo de 'Frankenstein' de Mary Shelley es 'El moderno' ¿quién?", "a": ["prometeo"], "w": ["hércules", "ícaro", "zeus", "odiseo"]},
     "fr": {"q": "Le 'Frankenstein' de Mary Shelley a pour sous-titre 'Le ... moderne'. Quel nom manque ?", "a": ["prométhée"], "w": ["hercule", "icare", "zeus", "ulysse"]},
     "lt": {"q": "Mary Shelley romanas 'Frankenšteinas' turi paantraštę 'Šiuolaikinis...' kas?", "a": ["prometėjas"], "w": ["heraklis", "ikaras", "dzeusas", "odisėjas"]},
     "ru": {"q": "Роман Мэри Шелли «Франкенштейн» имеет подзаголовок «Современный...» кто?", "a": ["прометей"], "w": ["геракл", "икар", "зевс", "одиссей"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Bram Stoker's 'Dracula', which Dutch professor leads the hunt for the Count?", "a": ["van helsing", "abraham van helsing"], "w": ["dr. jekyll", "dr. moreau", "sherlock holmes", "dr. frankenstein"]},
     "de": {"q": "Welcher niederländische Professor führt in Bram Stokers 'Dracula' die Jagd auf den Grafen an?", "a": ["van helsing", "abraham van helsing"], "w": ["dr. jekyll", "dr. moreau", "sherlock holmes", "dr. frankenstein"]},
     "es": {"q": "En 'Drácula' de Bram Stoker, ¿qué profesor holandés dirige la caza del conde?", "a": ["van helsing", "abraham van helsing"], "w": ["dr. jekyll", "dr. moreau", "sherlock holmes", "dr. frankenstein"]},
     "fr": {"q": "Dans 'Dracula' de Bram Stoker, quel professeur néerlandais mène la traque du comte ?", "a": ["van helsing", "abraham van helsing"], "w": ["dr jekyll", "dr moreau", "sherlock holmes", "dr frankenstein"]},
     "lt": {"q": "Kuris olandų profesorius Bramo Stokerio 'Drakuloje' vadovauja grafo medžioklei?", "a": ["van helsingas", "van helsing"], "w": ["daktaras džekilas", "daktaras moro", "šerlokas holmsas", "daktaras frankenšteinas"]},
     "ru": {"q": "Какой голландский профессор возглавляет охоту на графа в «Дракуле» Брэма Стокера?", "a": ["ван хельсинг", "абрахам ван хельсинг"], "w": ["доктор джекил", "доктор моро", "шерлок холмс", "доктор франкенштейн"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Robert Louis Stevenson's story, what is the name of Dr. Jekyll's evil alter ego?", "a": ["mr hyde", "mr. hyde", "hyde"], "w": ["mr smith", "mr hood", "mr jones", "mr grey"]},
     "de": {"q": "Wie heißt in der Erzählung von Robert Louis Stevenson das böse Alter Ego von Dr. Jekyll?", "a": ["mr. hyde", "mr hyde", "hyde"], "w": ["mr. smith", "mr. hood", "mr. jones", "mr. grey"]},
     "es": {"q": "En el relato de Robert Louis Stevenson, ¿cómo se llama el malvado alter ego del Dr. Jekyll?", "a": ["mr. hyde", "señor hyde", "hyde"], "w": ["señor smith", "señor hood", "señor jones", "señor grey"]},
     "fr": {"q": "Dans le récit de Robert Louis Stevenson, comment s'appelle le double maléfique du Dr Jekyll ?", "a": ["mr hyde", "m. hyde", "hyde"], "w": ["mr smith", "mr hood", "mr jones", "mr grey"]},
     "lt": {"q": "Kaip Roberto Louiso Stevensono apysakoje vadinamas piktasis daktaro Džekilo antrininkas?", "a": ["misteris haidas", "haidas", "hyde"], "w": ["misteris smitas", "misteris hudas", "misteris džounsas", "misteris grėjus"]},
     "ru": {"q": "Как зовут злое альтер эго доктора Джекила в повести Роберта Льюиса Стивенсона?", "a": ["мистер хайд", "хайд"], "w": ["мистер смит", "мистер худ", "мистер джонс", "мистер грей"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'Harry Potter and the Philosopher's Stone', what creature gets loose in Hogwarts on Halloween?", "a": ["troll", "a troll", "mountain troll"], "w": ["dragon", "basilisk", "werewolf", "giant spider"]},
     "de": {"q": "Welches Wesen läuft in 'Harry Potter und der Stein der Weisen' an Halloween frei in Hogwarts herum?", "a": ["troll", "ein troll", "bergtroll"], "w": ["drache", "basilisk", "werwolf", "riesenspinne"]},
     "es": {"q": "En 'Harry Potter y la piedra filosofal', ¿qué criatura se escapa en Hogwarts en Halloween?", "a": ["trol", "un trol", "troll"], "w": ["dragón", "basilisco", "hombre lobo", "araña gigante"]},
     "fr": {"q": "Dans 'Harry Potter à l'école des sorciers', quelle créature s'échappe dans Poudlard le soir d'Halloween ?", "a": ["troll", "un troll", "troll des montagnes"], "w": ["dragon", "basilic", "loup-garou", "araignée géante"]},
     "lt": {"q": "Kokia būtybė knygoje 'Haris Poteris ir išminties akmuo' Helovino dieną paspruko Hogvartse?", "a": ["trolis", "kalnų trolis"], "w": ["drakonas", "baziliskas", "vilkolakis", "milžiniškas voras"]},
     "ru": {"q": "Какое существо вырвалось на свободу в Хогвартсе в Хэллоуин в книге «Гарри Поттер и философский камень»?", "a": ["тролль", "горный тролль"], "w": ["дракон", "василиск", "оборотень", "гигантский паук"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the nickname of Gryffindor's house ghost in 'Harry Potter'?", "a": ["nearly headless nick", "nick"], "w": ["the bloody baron", "the fat friar", "moaning myrtle", "the grey lady"]},
     "de": {"q": "Wie lautet der Spitzname des Hausgeists von Gryffindor in 'Harry Potter'?", "a": ["der fast kopflose nick", "fast kopfloser nick", "nick"], "w": ["der blutige baron", "der fette mönch", "die maulende myrte", "die graue dame"]},
     "es": {"q": "¿Cuál es el apodo del fantasma de la casa Gryffindor en 'Harry Potter'?", "a": ["nick casi decapitado", "nick"], "w": ["el barón sanguinario", "el fraile gordo", "myrtle la llorona", "la dama gris"]},
     "fr": {"q": "Quel est le surnom du fantôme de la maison Gryffondor dans 'Harry Potter' ?", "a": ["nick quasi-sans-tête", "nick"], "w": ["le baron sanglant", "le moine gras", "mimi geignarde", "la dame grise"]},
     "lt": {"q": "Kokia 'Hario Poterio' Grifų Gūžtos namų vaiduoklio pravardė?", "a": ["beveik begalvis nikas", "nikas"], "w": ["kruvinasis baronas", "storasis vienuolis", "verksnė mirta", "pilkoji ponia"]},
     "ru": {"q": "Какое прозвище у привидения факультета Гриффиндор в «Гарри Поттере»?", "a": ["почти безголовый ник", "ник"], "w": ["кровавый барон", "толстый монах", "плакса миртл", "серая дама"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which classic monster did Boris Karloff play in the 1931 film by James Whale?", "a": ["frankenstein's monster", "the monster", "frankenstein"], "w": ["dracula", "the wolf man", "the invisible man", "the phantom"]},
     "de": {"q": "Welches klassische Monster spielte Boris Karloff 1931 im Film von James Whale?", "a": ["frankensteins monster", "das monster", "frankenstein"], "w": ["dracula", "den wolfsmenschen", "den unsichtbaren", "das phantom"]},
     "es": {"q": "¿Qué monstruo clásico interpretó Boris Karloff en la película de James Whale de 1931?", "a": ["el monstruo de frankenstein", "frankenstein", "el monstruo"], "w": ["drácula", "el hombre lobo", "el hombre invisible", "el fantasma"]},
     "fr": {"q": "Quel monstre classique Boris Karloff a-t-il incarné dans le film de James Whale de 1931 ?", "a": ["la créature de frankenstein", "frankenstein", "la créature"], "w": ["dracula", "le loup-garou", "l'homme invisible", "le fantôme"]},
     "lt": {"q": "Kurį klasikinį monstrą Borisas Karloffas suvaidino 1931 m. Jameso Whale'o filme?", "a": ["frankenšteino monstrą", "frankenšteinas", "monstrą"], "w": ["drakulą", "vilkžmogį", "nematomą žmogų", "fantomą"]},
     "ru": {"q": "Какого классического монстра сыграл Борис Карлофф в фильме Джеймса Уэйла 1931 года?", "a": ["монстра франкенштейна", "франкенштейн", "монстра"], "w": ["дракулу", "человека-волка", "человека-невидимку", "призрака"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Hungarian-born actor played Count Dracula in the 1931 Universal film?", "a": ["bela lugosi", "lugosi"], "w": ["boris karloff", "lon chaney", "vincent price", "peter lorre"]},
     "de": {"q": "Welcher in Ungarn geborene Schauspieler spielte 1931 im Universal-Film den Grafen Dracula?", "a": ["bela lugosi", "lugosi"], "w": ["boris karloff", "lon chaney", "vincent price", "peter lorre"]},
     "es": {"q": "¿Qué actor nacido en Hungría interpretó al conde Drácula en la película de Universal de 1931?", "a": ["bela lugosi", "lugosi"], "w": ["boris karloff", "lon chaney", "vincent price", "peter lorre"]},
     "fr": {"q": "Quel acteur d'origine hongroise a joué le comte Dracula dans le film Universal de 1931 ?", "a": ["bela lugosi", "lugosi"], "w": ["boris karloff", "lon chaney", "vincent price", "peter lorre"]},
     "lt": {"q": "Kuris Vengrijoje gimęs aktorius suvaidino grafą Drakulą 1931 m. Universal filme?", "a": ["bela lugosi", "lugosi"], "w": ["borisas karloffas", "lonas chaney", "vincentas price'as", "peteris lorre"]},
     "ru": {"q": "Какой актёр венгерского происхождения сыграл графа Дракулу в фильме Universal 1931 года?", "a": ["бела лугоши", "лугоши"], "w": ["борис карлофф", "лон чейни", "винсент прайс", "петер лорре"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which 1922 German silent film features the vampire Count Orlok?", "a": ["nosferatu"], "w": ["metropolis", "faust", "the golem", "dr. caligari"]},
     "de": {"q": "In welchem deutschen Stummfilm von 1922 tritt der Vampir Graf Orlok auf?", "a": ["nosferatu"], "w": ["metropolis", "faust", "der golem", "dr. caligari"]},
     "es": {"q": "¿Qué película muda alemana de 1922 presenta al vampiro conde Orlok?", "a": ["nosferatu"], "w": ["metrópolis", "fausto", "el golem", "dr. caligari"]},
     "fr": {"q": "Quel film muet allemand de 1922 met en scène le vampire comte Orlok ?", "a": ["nosferatu"], "w": ["metropolis", "faust", "le golem", "dr caligari"]},
     "lt": {"q": "Kuriame 1922 m. vokiečių nebyliajame filme pasirodo vampyras grafas Orlokas?", "a": ["nosferatu"], "w": ["metropolis", "faustas", "golemas", "daktaras kaligaris"]},
     "ru": {"q": "В каком немецком немом фильме 1922 года появляется вампир граф Орлок?", "a": ["носферату"], "w": ["метрополис", "фауст", "голем", "доктор калигари"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "Which horror film legend performed the spoken rap in Michael Jackson's 'Thriller'?", "a": ["vincent price", "price"], "w": ["boris karloff", "bela lugosi", "christopher lee", "peter cushing"]},
     "de": {"q": "Welche Horrorfilm-Legende spricht den Rap in Michael Jacksons 'Thriller'?", "a": ["vincent price", "price"], "w": ["boris karloff", "bela lugosi", "christopher lee", "peter cushing"]},
     "es": {"q": "¿Qué leyenda del cine de terror recita el rap de 'Thriller' de Michael Jackson?", "a": ["vincent price", "price"], "w": ["boris karloff", "bela lugosi", "christopher lee", "peter cushing"]},
     "fr": {"q": "Quelle légende du cinéma d'horreur récite le rap de 'Thriller' de Michael Jackson ?", "a": ["vincent price", "price"], "w": ["boris karloff", "bela lugosi", "christopher lee", "peter cushing"]},
     "lt": {"q": "Kuri siaubo filmų legenda deklamuoja repą Michaelo Jacksono dainoje 'Thriller'?", "a": ["vincentas price'as", "vincent price", "price"], "w": ["borisas karloffas", "bela lugosi", "christopheris lee", "peteris cushingas"]},
     "ru": {"q": "Какая легенда фильмов ужасов читает рэп в песне Майкла Джексона «Thriller»?", "a": ["винсент прайс", "прайс"], "w": ["борис карлофф", "бела лугоши", "кристофер ли", "питер кушинг"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Who sang the hit theme song for the 1984 film 'Ghostbusters'?", "a": ["ray parker jr.", "ray parker jr", "ray parker"], "w": ["huey lewis", "lionel richie", "phil collins", "prince"]},
     "de": {"q": "Wer sang den Hit-Titelsong des Films 'Ghostbusters' von 1984?", "a": ["ray parker jr.", "ray parker jr", "ray parker"], "w": ["huey lewis", "lionel richie", "phil collins", "prince"]},
     "es": {"q": "¿Quién cantó la exitosa canción principal de 'Los cazafantasmas' de 1984?", "a": ["ray parker jr.", "ray parker jr", "ray parker"], "w": ["huey lewis", "lionel richie", "phil collins", "prince"]},
     "fr": {"q": "Qui a chanté le tube du générique de 'S.O.S. Fantômes' en 1984 ?", "a": ["ray parker jr.", "ray parker jr", "ray parker"], "w": ["huey lewis", "lionel richie", "phil collins", "prince"]},
     "lt": {"q": "Kas atliko 1984 m. filmo 'Vaiduoklių medžiotojai' hitu tapusią titulinę dainą?", "a": ["ray parker jr.", "ray parker jr", "ray parker"], "w": ["huey lewis", "lionel richie", "phil collins", "prince"]},
     "ru": {"q": "Кто исполнил хитовую заглавную песню фильма «Охотники за привидениями» 1984 года?", "a": ["рэй паркер-младший", "рэй паркер", "ray parker jr."], "w": ["хьюи льюис", "лайонел ричи", "фил коллинз", "принс"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which actress played Laurie Strode in John Carpenter's 'Halloween' (1978)?", "a": ["jamie lee curtis", "curtis"], "w": ["sigourney weaver", "neve campbell", "drew barrymore", "sissy spacek"]},
     "de": {"q": "Welche Schauspielerin spielte Laurie Strode in John Carpenters 'Halloween' (1978)?", "a": ["jamie lee curtis", "curtis"], "w": ["sigourney weaver", "neve campbell", "drew barrymore", "sissy spacek"]},
     "es": {"q": "¿Qué actriz interpretó a Laurie Strode en 'Halloween' (1978) de John Carpenter?", "a": ["jamie lee curtis", "curtis"], "w": ["sigourney weaver", "neve campbell", "drew barrymore", "sissy spacek"]},
     "fr": {"q": "Quelle actrice a joué Laurie Strode dans 'Halloween' (1978) de John Carpenter ?", "a": ["jamie lee curtis", "curtis"], "w": ["sigourney weaver", "neve campbell", "drew barrymore", "sissy spacek"]},
     "lt": {"q": "Kuri aktorė suvaidino Laurie Strode Johno Carpenterio filme 'Helovinas' (1978)?", "a": ["jamie lee curtis", "curtis"], "w": ["sigourney weaver", "neve campbell", "drew barrymore", "sissy spacek"]},
     "ru": {"q": "Какая актриса сыграла Лори Строуд в фильме Джона Карпентера «Хэллоуин» (1978)?", "a": ["джейми ли кёртис", "джейми ли кертис", "кёртис"], "w": ["сигурни уивер", "нив кэмпбелл", "дрю бэрримор", "сисси спейсек"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of the masked killer persona in the 'Scream' films?", "a": ["ghostface", "ghost face"], "w": ["jigsaw", "leatherface", "pinhead", "candyman"]},
     "de": {"q": "Wie heißt die maskierte Killerfigur in den 'Scream'-Filmen?", "a": ["ghostface", "ghost face"], "w": ["jigsaw", "leatherface", "pinhead", "candyman"]},
     "es": {"q": "¿Cómo se llama el asesino enmascarado de las películas de 'Scream'?", "a": ["ghostface", "ghost face", "cara de fantasma"], "w": ["jigsaw", "leatherface", "pinhead", "candyman"]},
     "fr": {"q": "Comment s'appelle le tueur masqué des films 'Scream' ?", "a": ["ghostface", "ghost face"], "w": ["jigsaw", "leatherface", "pinhead", "candyman"]},
     "lt": {"q": "Kaip vadinamas kaukėtas žudikas filmuose 'Klyksmas'?", "a": ["ghostface", "vaiduoklio veidas"], "w": ["jigsaw", "odinis veidas", "smeigtukų galva", "saldainių žmogus"]},
     "ru": {"q": "Как зовут убийцу в маске из фильмов «Крик»?", "a": ["призрачное лицо", "гоустфейс", "ghostface"], "w": ["конструктор", "кожаное лицо", "пинхед", "кэндимен"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which horror franchise features a creepy puppet named Billy riding a tricycle?", "a": ["saw"], "w": ["scream", "the conjuring", "insidious", "annabelle"]},
     "de": {"q": "In welcher Horrorreihe fährt eine gruselige Puppe namens Billy Dreirad?", "a": ["saw"], "w": ["scream", "conjuring", "insidious", "annabelle"]},
     "es": {"q": "¿Qué saga de terror presenta a un siniestro muñeco llamado Billy que monta en triciclo?", "a": ["saw", "juego macabro", "el juego del miedo"], "w": ["scream", "expediente warren", "insidious", "annabelle"]},
     "fr": {"q": "Quelle saga d'horreur met en scène une marionnette inquiétante nommée Billy sur un tricycle ?", "a": ["saw"], "w": ["scream", "conjuring", "insidious", "annabelle"]},
     "lt": {"q": "Kurioje siaubo filmų serijoje triračiu važinėja baugi lėlė, vardu Bilis?", "a": ["pjūklas", "saw"], "w": ["klyksmas", "išvarymas", "astralas", "anabelė"]},
     "ru": {"q": "В какой серии фильмов ужасов жуткая кукла по имени Билли катается на трёхколёсном велосипеде?", "a": ["пила", "saw"], "w": ["крик", "заклятие", "астрал", "проклятие аннабель"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which famous escape artist died on Halloween in 1926?", "a": ["harry houdini", "houdini"], "w": ["david copperfield", "harry blackstone", "howard thurston", "chung ling soo"]},
     "de": {"q": "Welcher berühmte Entfesselungskünstler starb an Halloween 1926?", "a": ["harry houdini", "houdini"], "w": ["david copperfield", "harry blackstone", "howard thurston", "chung ling soo"]},
     "es": {"q": "¿Qué famoso escapista murió el día de Halloween de 1926?", "a": ["harry houdini", "houdini"], "w": ["david copperfield", "harry blackstone", "howard thurston", "chung ling soo"]},
     "fr": {"q": "Quel célèbre artiste de l'évasion est mort le jour d'Halloween 1926 ?", "a": ["harry houdini", "houdini"], "w": ["david copperfield", "harry blackstone", "howard thurston", "chung ling soo"]},
     "lt": {"q": "Kuris garsus išsilaisvinimo meistras mirė per Heloviną 1926 m.?", "a": ["haris hudinis", "hudinis", "houdini"], "w": ["davidas copperfieldas", "haris blekstounas", "hovardas terstonas", "čungas lingas su"]},
     "ru": {"q": "Какой знаменитый мастер освобождения от оков умер в Хэллоуин 1926 года?", "a": ["гарри гудини", "гудини"], "w": ["дэвид копперфильд", "гарри блэкстоун", "говард терстон", "чунг линг су"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Orson Welles's panic-inducing 1938 Halloween-eve radio broadcast adapted which novel?", "a": ["the war of the worlds", "war of the worlds"], "w": ["the time machine", "dracula", "frankenstein", "the invisible man"]},
     "de": {"q": "Welchen Roman adaptierte Orson Welles in seiner Panik auslösenden Radiosendung am Vorabend von Halloween 1938?", "a": ["krieg der welten", "der krieg der welten"], "w": ["die zeitmaschine", "dracula", "frankenstein", "der unsichtbare"]},
     "es": {"q": "¿Qué novela adaptó Orson Welles en su alarmante emisión de radio de la víspera de Halloween de 1938?", "a": ["la guerra de los mundos", "guerra de los mundos"], "w": ["la máquina del tiempo", "drácula", "frankenstein", "el hombre invisible"]},
     "fr": {"q": "Quel roman Orson Welles a-t-il adapté dans sa célèbre émission radio de la veille d'Halloween 1938 ?", "a": ["la guerre des mondes", "guerre des mondes"], "w": ["la machine temporelle", "dracula", "frankenstein", "l'homme invisible"]},
     "lt": {"q": "Kurį romaną Orsonas Wellesas adaptavo paniką sukėlusioje 1938 m. Helovino išvakarių radijo laidoje?", "a": ["pasaulių karas"], "w": ["laiko mašina", "drakula", "frankenšteinas", "nematomas žmogus"]},
     "ru": {"q": "Какой роман Орсон Уэллс адаптировал в радиопостановке накануне Хэллоуина 1938 года, вызвавшей панику?", "a": ["война миров"], "w": ["машина времени", "дракула", "франкенштейн", "человек-невидимка"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In which US state did the Salem witch trials take place?", "a": ["massachusetts"], "w": ["virginia", "new york", "connecticut", "pennsylvania"]},
     "de": {"q": "In welchem US-Bundesstaat fanden die Hexenprozesse von Salem statt?", "a": ["massachusetts"], "w": ["virginia", "new york", "connecticut", "pennsylvania"]},
     "es": {"q": "¿En qué estado de EE. UU. tuvieron lugar los juicios de brujas de Salem?", "a": ["massachusetts"], "w": ["virginia", "nueva york", "connecticut", "pensilvania"]},
     "fr": {"q": "Dans quel État américain se sont déroulés les procès des sorcières de Salem ?", "a": ["massachusetts", "le massachusetts"], "w": ["virginie", "new york", "connecticut", "pennsylvanie"]},
     "lt": {"q": "Kurioje JAV valstijoje vyko Salemo raganų teismai?", "a": ["masačusetse", "masačusetsas", "massachusetts"], "w": ["virdžinijoje", "niujorke", "konektikute", "pensilvanijoje"]},
     "ru": {"q": "В каком штате США проходили Салемские процессы над ведьмами?", "a": ["массачусетс", "в массачусетсе"], "w": ["виргиния", "нью-йорк", "коннектикут", "пенсильвания"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "In which year did the Salem witch trials begin?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]},
     "de": {"q": "In welchem Jahr begannen die Hexenprozesse von Salem?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]},
     "es": {"q": "¿En qué año comenzaron los juicios de brujas de Salem?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]},
     "fr": {"q": "En quelle année ont commencé les procès des sorcières de Salem ?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]},
     "lt": {"q": "Kuriais metais prasidėjo Salemo raganų teismai?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]},
     "ru": {"q": "В каком году начались Салемские процессы над ведьмами?", "a": ["1692"], "w": ["1620", "1776", "1588", "1812"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Arthur Miller play is set during the Salem witch trials?", "a": ["the crucible", "crucible"], "w": ["death of a salesman", "all my sons", "a view from the bridge", "our town"]},
     "de": {"q": "Welches Theaterstück von Arthur Miller spielt während der Hexenprozesse von Salem?", "a": ["hexenjagd", "the crucible"], "w": ["tod eines handlungsreisenden", "alle meine söhne", "blick von der brücke", "unsere kleine stadt"]},
     "es": {"q": "¿Qué obra de Arthur Miller está ambientada durante los juicios de brujas de Salem?", "a": ["las brujas de salem", "el crisol", "the crucible"], "w": ["muerte de un viajante", "todos eran mis hijos", "panorama desde el puente", "nuestro pueblo"]},
     "fr": {"q": "Quelle pièce d'Arthur Miller se déroule pendant les procès des sorcières de Salem ?", "a": ["les sorcières de salem", "the crucible"], "w": ["mort d'un commis voyageur", "ils étaient tous mes fils", "vu du pont", "notre petite ville"]},
     "lt": {"q": "Kurios Arthuro Millerio pjesės veiksmas vyksta per Salemo raganų teismus?", "a": ["salemo raganos", "the crucible", "sunkus išbandymas"], "w": ["komivojažieriaus mirtis", "visi mano sūnūs", "vaizdas nuo tilto", "mūsų miestelis"]},
     "ru": {"q": "Действие какой пьесы Артура Миллера происходит во время Салемских процессов над ведьмами?", "a": ["суровое испытание", "салемские ведьмы", "the crucible"], "w": ["смерть коммивояжёра", "все мои сыновья", "вид с моста", "наш городок"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Disney villain transforms into a dragon in 'Sleeping Beauty'?", "a": ["maleficent"], "w": ["ursula", "cruella", "jafar", "the evil queen"]},
     "de": {"q": "Welche Disney-Schurkin verwandelt sich in 'Dornröschen' in einen Drachen?", "a": ["malefiz", "maleficent"], "w": ["ursula", "cruella", "dschafar", "die böse königin"]},
     "es": {"q": "¿Qué villana de Disney se transforma en dragón en 'La bella durmiente'?", "a": ["maléfica"], "w": ["úrsula", "cruella", "jafar", "la reina malvada"]},
     "fr": {"q": "Quelle méchante de Disney se transforme en dragon dans 'La Belle au bois dormant' ?", "a": ["maléfique"], "w": ["ursula", "cruella", "jafar", "la méchante reine"]},
     "lt": {"q": "Kuri Disnėjaus piktadarė filme 'Miegančioji gražuolė' virsta drakonu?", "a": ["piktadarė", "maleficent", "malefisenta"], "w": ["ursula", "krūela", "džafaras", "piktoji karalienė"]},
     "ru": {"q": "Какая злодейка Disney превращается в дракона в мультфильме «Спящая красавица»?", "a": ["малефисента"], "w": ["урсула", "круэлла", "джафар", "злая королева"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'The Nightmare Before Christmas', what is the name of the town where Jack lives?", "a": ["halloween town", "halloweentown"], "w": ["christmas town", "spooky town", "nightmare city", "pumpkin hollow"]},
     "de": {"q": "Wie heißt in 'Nightmare Before Christmas' die Stadt, in der Jack lebt?", "a": ["halloween town", "halloweenstadt"], "w": ["weihnachtsstadt", "gruselstadt", "albtraumstadt", "kürbistal"]},
     "es": {"q": "En 'Pesadilla antes de Navidad', ¿cómo se llama la ciudad donde vive Jack?", "a": ["ciudad halloween", "halloween town", "pueblo de halloween"], "w": ["ciudad navidad", "ciudad tenebrosa", "ciudad pesadilla", "valle calabaza"]},
     "fr": {"q": "Dans 'L'Étrange Noël de monsieur Jack', comment s'appelle la ville où vit Jack ?", "a": ["halloween town", "halloweenville", "la ville d'halloween"], "w": ["noëlville", "la ville hantée", "cauchemarville", "citrouilleville"]},
     "lt": {"q": "Kaip filme 'Košmaras prieš Kalėdas' vadinamas miestas, kuriame gyvena Džekas?", "a": ["helovino miestas", "halloween town"], "w": ["kalėdų miestas", "baisusis miestas", "košmarų miestas", "moliūgų slėnis"]},
     "ru": {"q": "Как называется город, где живёт Джек, в «Кошмаре перед Рождеством»?", "a": ["город хэллоуина", "хэллоуинтаун"], "w": ["город рождества", "жуткий город", "город кошмаров", "тыквенная долина"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "What is the traditional Irish Halloween fruit bread with a ring baked inside?", "a": ["barmbrack", "brack"], "w": ["soda bread", "stollen", "panettone", "scone"]},
     "de": {"q": "Wie heißt das traditionelle irische Halloween-Früchtebrot, in das ein Ring eingebacken wird?", "a": ["barmbrack", "brack"], "w": ["sodabrot", "stollen", "panettone", "scone"]},
     "es": {"q": "¿Cómo se llama el pan de frutas irlandés tradicional de Halloween con un anillo horneado dentro?", "a": ["barmbrack", "brack"], "w": ["pan de soda", "stollen", "panettone", "scone"]},
     "fr": {"q": "Comment s'appelle le pain aux fruits irlandais d'Halloween dans lequel on cache une bague ?", "a": ["barmbrack", "brack"], "w": ["pain au bicarbonate", "stollen", "panettone", "scone"]},
     "lt": {"q": "Kaip vadinama tradicinė airiška Helovino vaisių duona su įkeptu žiedu?", "a": ["barmbrack", "brakas", "barmbrakas"], "w": ["sodos duona", "štolenas", "panetonas", "sconas"]},
     "ru": {"q": "Как называется традиционный ирландский фруктовый хлеб на Хэллоуин с запечённым внутри кольцом?", "a": ["бармбрэк", "barmbrack", "брэк"], "w": ["содовый хлеб", "штоллен", "панеттоне", "скон"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which 15th-century Wallachian prince is often cited as an inspiration for Dracula?", "a": ["vlad the impaler", "vlad tepes", "vlad iii", "vlad"], "w": ["ivan the terrible", "attila the hun", "genghis khan", "stephen the great"]},
     "de": {"q": "Welcher walachische Fürst des 15. Jahrhunderts gilt oft als Vorbild für Dracula?", "a": ["vlad der pfähler", "vlad tepes", "vlad iii.", "vlad"], "w": ["iwan der schreckliche", "attila", "dschingis khan", "stefan der große"]},
     "es": {"q": "¿Qué príncipe de Valaquia del siglo XV se cita a menudo como inspiración de Drácula?", "a": ["vlad el empalador", "vlad tepes", "vlad iii", "vlad"], "w": ["iván el terrible", "atila", "gengis kan", "esteban el grande"]},
     "fr": {"q": "Quel prince valaque du XVe siècle est souvent cité comme source d'inspiration de Dracula ?", "a": ["vlad l'empaleur", "vlad tepes", "vlad iii", "vlad"], "w": ["ivan le terrible", "attila", "gengis khan", "étienne le grand"]},
     "lt": {"q": "Kuris XV a. Valakijos kunigaikštis dažnai laikomas Drakulos prototipu?", "a": ["vladas smeigėjas", "vladas iii", "vladas", "vlad tepes"], "w": ["ivanas rūstusis", "atila", "čingischanas", "steponas didysis"]},
     "ru": {"q": "Какой валашский князь XV века считается одним из прообразов Дракулы?", "a": ["влад цепеш", "влад iii", "влад", "влад колосажатель"], "w": ["иван грозный", "аттила", "чингисхан", "стефан великий"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Bran Castle, often marketed as 'Dracula's Castle', is in which country?", "a": ["romania"], "w": ["hungary", "bulgaria", "serbia", "slovakia"]},
     "de": {"q": "In welchem Land steht Schloss Bran, das oft als 'Draculas Schloss' vermarktet wird?", "a": ["rumänien"], "w": ["ungarn", "bulgarien", "serbien", "slowakei"]},
     "es": {"q": "¿En qué país se encuentra el castillo de Bran, conocido como el 'castillo de Drácula'?", "a": ["rumanía", "rumania"], "w": ["hungría", "bulgaria", "serbia", "eslovaquia"]},
     "fr": {"q": "Dans quel pays se trouve le château de Bran, souvent présenté comme le 'château de Dracula' ?", "a": ["roumanie", "la roumanie"], "w": ["hongrie", "bulgarie", "serbie", "slovaquie"]},
     "lt": {"q": "Kurioje šalyje yra Brano pilis, dažnai vadinama 'Drakulos pilimi'?", "a": ["rumunijoje", "rumunija"], "w": ["vengrijoje", "bulgarijoje", "serbijoje", "slovakijoje"]},
     "ru": {"q": "В какой стране находится замок Бран, который часто называют «замком Дракулы»?", "a": ["румыния", "в румынии"], "w": ["венгрия", "болгария", "сербия", "словакия"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "What is the term for the supposed ability of a human to turn into a wolf?", "a": ["lycanthropy"], "w": ["misanthropy", "entropy", "anthropology", "philanthropy"]},
     "de": {"q": "Wie nennt man die angebliche Fähigkeit eines Menschen, sich in einen Wolf zu verwandeln?", "a": ["lykanthropie"], "w": ["misanthropie", "entropie", "anthropologie", "philanthropie"]},
     "es": {"q": "¿Cómo se llama la supuesta capacidad de un ser humano para convertirse en lobo?", "a": ["licantropía"], "w": ["misantropía", "entropía", "antropología", "filantropía"]},
     "fr": {"q": "Comment appelle-t-on la prétendue capacité d'un humain à se transformer en loup ?", "a": ["lycanthropie", "la lycanthropie"], "w": ["misanthropie", "entropie", "anthropologie", "philanthropie"]},
     "lt": {"q": "Kaip vadinamas tariamas žmogaus gebėjimas pavirsti vilku?", "a": ["likantropija"], "w": ["mizantropija", "entropija", "antropologija", "filantropija"]},
     "ru": {"q": "Как называется предполагаемая способность человека превращаться в волка?", "a": ["ликантропия"], "w": ["мизантропия", "энтропия", "антропология", "филантропия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The word 'Halloween' is a shortened form of which phrase?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]},
     "de": {"q": "Von welchem englischen Ausdruck ist das Wort 'Halloween' eine Kurzform?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]},
     "es": {"q": "¿De qué expresión inglesa es una forma abreviada la palabra 'Halloween'?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]},
     "fr": {"q": "Le mot 'Halloween' est une forme abrégée de quelle expression anglaise ?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]},
     "lt": {"q": "Kokios angliškos frazės sutrumpinimas yra žodis 'Halloween'?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]},
     "ru": {"q": "Сокращением какого английского выражения является слово «Halloween»?", "a": ["all hallows' eve", "all hallows eve", "hallows' eve"], "w": ["all saints' night", "holy evening", "harvest eve", "all souls' night"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which Christian feast is celebrated on November 1, the day after Halloween?", "a": ["all saints' day", "all saints day", "all hallows"], "w": ["easter", "pentecost", "epiphany", "ascension day"]},
     "de": {"q": "Welches christliche Fest wird am 1. November, dem Tag nach Halloween, gefeiert?", "a": ["allerheiligen"], "w": ["ostern", "pfingsten", "dreikönigstag", "christi himmelfahrt"]},
     "es": {"q": "¿Qué fiesta cristiana se celebra el 1 de noviembre, el día después de Halloween?", "a": ["día de todos los santos", "todos los santos"], "w": ["pascua", "pentecostés", "epifanía", "la ascensión"]},
     "fr": {"q": "Quelle fête chrétienne est célébrée le 1er novembre, le lendemain d'Halloween ?", "a": ["la toussaint", "toussaint"], "w": ["pâques", "la pentecôte", "l'épiphanie", "l'ascension"]},
     "lt": {"q": "Kokia krikščionių šventė švenčiama lapkričio 1 d., kitą dieną po Helovino?", "a": ["visų šventųjų diena", "visi šventieji"], "w": ["velykos", "sekminės", "trys karaliai", "žolinė"]},
     "ru": {"q": "Какой христианский праздник отмечают 1 ноября, на следующий день после Хэллоуина?", "a": ["день всех святых"], "w": ["пасха", "троица", "крещение", "вознесение"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which actress plays Wednesday Addams in the 2022 Netflix series 'Wednesday'?", "a": ["jenna ortega", "ortega"], "w": ["zendaya", "millie bobby brown", "emma myers", "florence pugh"]},
     "de": {"q": "Welche Schauspielerin spielt Wednesday Addams in der Netflix-Serie 'Wednesday' von 2022?", "a": ["jenna ortega", "ortega"], "w": ["zendaya", "millie bobby brown", "emma myers", "florence pugh"]},
     "es": {"q": "¿Qué actriz interpreta a Miércoles Addams en la serie de Netflix 'Miércoles' de 2022?", "a": ["jenna ortega", "ortega"], "w": ["zendaya", "millie bobby brown", "emma myers", "florence pugh"]},
     "fr": {"q": "Quelle actrice incarne Mercredi Addams dans la série Netflix 'Mercredi' de 2022 ?", "a": ["jenna ortega", "ortega"], "w": ["zendaya", "millie bobby brown", "emma myers", "florence pugh"]},
     "lt": {"q": "Kuri aktorė vaidina Wednesday Addams 2022 m. Netflix seriale 'Wednesday'?", "a": ["jenna ortega", "ortega"], "w": ["zendaya", "millie bobby brown", "emma myers", "florence pugh"]},
     "ru": {"q": "Какая актриса играет Уэнсдэй Аддамс в сериале Netflix «Уэнсдэй» 2022 года?", "a": ["дженна ортега", "ортега"], "w": ["зендея", "милли бобби браун", "эмма майерс", "флоренс пью"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In the Netflix series 'Wednesday', which academy does Wednesday attend?", "a": ["nevermore academy", "nevermore"], "w": ["hogwarts", "ravenwood", "blackthorn", "crimson hall"]},
     "de": {"q": "Welche Akademie besucht Wednesday in der Netflix-Serie 'Wednesday'?", "a": ["nevermore academy", "nevermore", "nevermore-akademie"], "w": ["hogwarts", "ravenwood", "blackthorn", "crimson hall"]},
     "es": {"q": "En la serie de Netflix 'Miércoles', ¿a qué academia asiste Miércoles?", "a": ["academia nevermore", "nevermore"], "w": ["hogwarts", "ravenwood", "blackthorn", "crimson hall"]},
     "fr": {"q": "Dans la série Netflix 'Mercredi', quelle académie fréquente Mercredi ?", "a": ["nevermore academy", "nevermore", "académie nevermore"], "w": ["poudlard", "ravenwood", "blackthorn", "crimson hall"]},
     "lt": {"q": "Kurioje akademijoje Netflix seriale 'Wednesday' mokosi Wednesday?", "a": ["nevermore akademijoje", "nevermore"], "w": ["hogvartse", "ravenwood", "blackthorn", "crimson hall"]},
     "ru": {"q": "В какой академии учится Уэнсдэй в сериале Netflix «Уэнсдэй»?", "a": ["академия невермор", "невермор", "nevermore"], "w": ["хогвартс", "рэйвенвуд", "блэкторн", "кримсон-холл"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Tim Burton's 'Corpse Bride', what is the name of the corpse bride?", "a": ["emily"], "w": ["victoria", "sally", "lydia", "coraline"]},
     "de": {"q": "Wie heißt die Leichenbraut in Tim Burtons 'Corpse Bride'?", "a": ["emily"], "w": ["victoria", "sally", "lydia", "coraline"]},
     "es": {"q": "En 'La novia cadáver' de Tim Burton, ¿cómo se llama la novia cadáver?", "a": ["emily"], "w": ["victoria", "sally", "lydia", "coraline"]},
     "fr": {"q": "Dans 'Les Noces funèbres' de Tim Burton, comment s'appelle la mariée cadavre ?", "a": ["emily"], "w": ["victoria", "sally", "lydia", "coraline"]},
     "lt": {"q": "Kaip vadinasi nuotaka lavonas Timo Burtono filme 'Lavono nuotaka'?", "a": ["emilė", "emily"], "w": ["viktorija", "sali", "lidija", "koralina"]},
     "ru": {"q": "Как зовут невесту-труп в мультфильме Тима Бёртона «Труп невесты»?", "a": ["эмили"], "w": ["виктория", "салли", "лидия", "коралина"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "Which stop-motion animation studio made the 2009 film 'Coraline'?", "a": ["laika"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]},
     "de": {"q": "Welches Stop-Motion-Studio produzierte den Film 'Coraline' von 2009?", "a": ["laika"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]},
     "es": {"q": "¿Qué estudio de animación stop-motion hizo la película 'Los mundos de Coraline' de 2009?", "a": ["laika"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]},
     "fr": {"q": "Quel studio d'animation en stop-motion a réalisé le film 'Coraline' en 2009 ?", "a": ["laika"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]},
     "lt": {"q": "Kuri lėlinės animacijos studija sukūrė 2009 m. filmą 'Koralina'?", "a": ["laika"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]},
     "ru": {"q": "Какая студия кукольной анимации сняла мультфильм «Коралина в Стране Кошмаров» 2009 года?", "a": ["laika", "лайка"], "w": ["aardman", "pixar", "dreamworks", "studio ghibli"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Pixar's 'Coco', what is the name of Miguel's street dog?", "a": ["dante"], "w": ["chico", "pancho", "rocky", "diego"]},
     "de": {"q": "Wie heißt Miguels Straßenhund in Pixars 'Coco'?", "a": ["dante"], "w": ["chico", "pancho", "rocky", "diego"]},
     "es": {"q": "En 'Coco' de Pixar, ¿cómo se llama el perro callejero de Miguel?", "a": ["dante"], "w": ["chico", "pancho", "rocky", "diego"]},
     "fr": {"q": "Dans 'Coco' de Pixar, comment s'appelle le chien errant de Miguel ?", "a": ["dante"], "w": ["chico", "pancho", "rocky", "diego"]},
     "lt": {"q": "Kaip Pixar filme 'Koko' vadinamas Migelio benamis šuo?", "a": ["dantė", "dante"], "w": ["čikas", "pančas", "rokis", "diegas"]},
     "ru": {"q": "Как зовут бездомного пса Мигеля в мультфильме Pixar «Тайна Коко»?", "a": ["данте"], "w": ["чико", "панчо", "рокки", "диего"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In which Edgar Allan Poe story does a murderer hear his victim's heart beating under the floor?", "a": ["the tell-tale heart", "tell-tale heart"], "w": ["the black cat", "the raven", "the gold-bug", "the oval portrait"]},
     "de": {"q": "In welcher Erzählung von Edgar Allan Poe hört ein Mörder das Herz seines Opfers unter den Dielen schlagen?", "a": ["das verräterische herz", "verräterische herz"], "w": ["der schwarze kater", "der rabe", "der goldkäfer", "das ovale porträt"]},
     "es": {"q": "¿En qué relato de Edgar Allan Poe un asesino oye latir bajo el suelo el corazón de su víctima?", "a": ["el corazón delator", "corazón delator"], "w": ["el gato negro", "el cuervo", "el escarabajo de oro", "el retrato oval"]},
     "fr": {"q": "Dans quelle nouvelle d'Edgar Allan Poe un meurtrier entend-il battre sous le plancher le cœur de sa victime ?", "a": ["le cœur révélateur", "cœur révélateur"], "w": ["le chat noir", "le corbeau", "le scarabée d'or", "le portrait ovale"]},
     "lt": {"q": "Kuriame Edgaro Alano Po apsakyme žudikas girdi po grindimis plakančią aukos širdį?", "a": ["išdavikė širdis", "pasakojanti širdis"], "w": ["juodasis katinas", "varnas", "auksinis vabalas", "ovalus portretas"]},
     "ru": {"q": "В каком рассказе Эдгара По убийца слышит, как под полом бьётся сердце его жертвы?", "a": ["сердце-обличитель", "сердце обличитель"], "w": ["чёрный кот", "ворон", "золотой жук", "овальный портрет"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Bram Stoker's novel, to which country does Dracula travel from Transylvania?", "a": ["england", "britain"], "w": ["france", "italy", "america", "germany"]},
     "de": {"q": "In welches Land reist Dracula in Bram Stokers Roman aus Transsilvanien?", "a": ["england", "großbritannien"], "w": ["frankreich", "italien", "amerika", "deutschland"]},
     "es": {"q": "En la novela de Bram Stoker, ¿a qué país viaja Drácula desde Transilvania?", "a": ["inglaterra", "gran bretaña"], "w": ["francia", "italia", "américa", "alemania"]},
     "fr": {"q": "Dans le roman de Bram Stoker, dans quel pays Dracula se rend-il depuis la Transylvanie ?", "a": ["angleterre", "l'angleterre"], "w": ["france", "italie", "amérique", "allemagne"]},
     "lt": {"q": "Į kurią šalį Bramo Stokerio romane Drakula keliauja iš Transilvanijos?", "a": ["angliją", "anglija", "britaniją"], "w": ["prancūziją", "italiją", "ameriką", "vokietiją"]},
     "ru": {"q": "В какую страну отправляется Дракула из Трансильвании в романе Брэма Стокера?", "a": ["англия", "в англию"], "w": ["франция", "италия", "америка", "германия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of the schoolteacher pursued by the Headless Horseman in 'The Legend of Sleepy Hollow'?", "a": ["ichabod crane", "ichabod"], "w": ["brom bones", "rip van winkle", "baltus van tassel", "tom walker"]},
     "de": {"q": "Wie heißt der Lehrer, der in 'Die Sage von der schläfrigen Schlucht' vom kopflosen Reiter verfolgt wird?", "a": ["ichabod crane", "ichabod"], "w": ["brom bones", "rip van winkle", "baltus van tassel", "tom walker"]},
     "es": {"q": "¿Cómo se llama el maestro perseguido por el Jinete sin Cabeza en 'La leyenda de Sleepy Hollow'?", "a": ["ichabod crane", "ichabod"], "w": ["brom bones", "rip van winkle", "baltus van tassel", "tom walker"]},
     "fr": {"q": "Comment s'appelle l'instituteur poursuivi par le Cavalier sans tête dans 'La Légende de Sleepy Hollow' ?", "a": ["ichabod crane", "ichabod"], "w": ["brom bones", "rip van winkle", "baltus van tassel", "tom walker"]},
     "lt": {"q": "Kaip vadinasi mokytojas, kurį 'Mieguistosios daubos legendoje' persekioja Raitelis be galvos?", "a": ["ichabodas kreinas", "ichabodas", "ichabod crane"], "w": ["bromas bounsas", "ripas van vinklis", "baltusas van taselis", "tomas vokeris"]},
     "ru": {"q": "Как зовут учителя, которого преследует Всадник без головы в «Легенде о Сонной Лощине»?", "a": ["икабод крейн", "икабод"], "w": ["бром бонс", "рип ван винкль", "балтус ван тассель", "том уокер"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The discovery of which pharaoh's tomb in 1922 sparked tales of a 'mummy's curse'?", "a": ["tutankhamun", "king tut", "tutankhamen", "tut"], "w": ["ramses ii", "cleopatra", "khufu", "akhenaten"]},
     "de": {"q": "Die Entdeckung welchen Pharaonengrabs im Jahr 1922 löste Geschichten über einen 'Fluch der Mumie' aus?", "a": ["tutanchamun", "tut"], "w": ["ramses ii.", "kleopatra", "cheops", "echnaton"]},
     "es": {"q": "¿El descubrimiento de la tumba de qué faraón en 1922 dio origen a la 'maldición de la momia'?", "a": ["tutankamón", "tutankamon"], "w": ["ramsés ii", "cleopatra", "keops", "akenatón"]},
     "fr": {"q": "La découverte du tombeau de quel pharaon en 1922 a lancé la légende de la 'malédiction de la momie' ?", "a": ["toutânkhamon", "toutankhamon"], "w": ["ramsès ii", "cléopâtre", "khéops", "akhenaton"]},
     "lt": {"q": "Kurio faraono kapo atradimas 1922 m. pagimdė pasakojimus apie 'mumijos prakeiksmą'?", "a": ["tutanchamono", "tutanchamonas"], "w": ["ramzio ii", "kleopatros", "cheopso", "echnatono"]},
     "ru": {"q": "Открытие гробницы какого фараона в 1922 году породило легенды о «проклятии мумии»?", "a": ["тутанхамона", "тутанхамон"], "w": ["рамсеса ii", "клеопатры", "хеопса", "эхнатона"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "Which Roman goddess of fruit and orchards is linked to Halloween's apple customs?", "a": ["pomona"], "w": ["venus", "diana", "juno", "minerva"]},
     "de": {"q": "Welche römische Göttin der Früchte und Obstgärten wird mit den Apfelbräuchen an Halloween in Verbindung gebracht?", "a": ["pomona"], "w": ["venus", "diana", "juno", "minerva"]},
     "es": {"q": "¿Qué diosa romana de los frutos y los huertos se asocia con las costumbres de manzanas de Halloween?", "a": ["pomona"], "w": ["venus", "diana", "juno", "minerva"]},
     "fr": {"q": "Quelle déesse romaine des fruits et des vergers est liée aux coutumes des pommes d'Halloween ?", "a": ["pomone", "pomona"], "w": ["vénus", "diane", "junon", "minerve"]},
     "lt": {"q": "Kuri romėnų vaisių ir sodų deivė siejama su Helovino obuolių papročiais?", "a": ["pomona"], "w": ["venera", "diana", "junona", "minerva"]},
     "ru": {"q": "Какая римская богиня плодов и садов связана с яблочными обычаями Хэллоуина?", "a": ["помона"], "w": ["венера", "диана", "юнона", "минерва"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which legendary ghost ship is doomed to sail the oceans forever?", "a": ["the flying dutchman", "flying dutchman"], "w": ["the black pearl", "the nautilus", "the argo", "queen anne's revenge"]},
     "de": {"q": "Welches legendäre Geisterschiff ist dazu verdammt, ewig über die Meere zu segeln?", "a": ["der fliegende holländer", "fliegender holländer"], "w": ["die black pearl", "die nautilus", "die argo", "queen anne's revenge"]},
     "es": {"q": "¿Qué legendario barco fantasma está condenado a navegar los océanos para siempre?", "a": ["el holandés errante", "holandés errante"], "w": ["la perla negra", "el nautilus", "el argo", "la venganza de la reina ana"]},
     "fr": {"q": "Quel légendaire vaisseau fantôme est condamné à naviguer éternellement sur les océans ?", "a": ["le hollandais volant", "hollandais volant"], "w": ["le black pearl", "le nautilus", "l'argo", "le queen anne's revenge"]},
     "lt": {"q": "Kuris legendinis laivas vaiduoklis pasmerktas amžinai plaukioti vandenynais?", "a": ["skrajojantis olandas", "skraidantis olandas"], "w": ["juodasis perlas", "nautilas", "argas", "karalienės anos kerštas"]},
     "ru": {"q": "Какой легендарный корабль-призрак обречён вечно скитаться по океанам?", "a": ["летучий голландец"], "w": ["чёрная жемчужина", "наутилус", "арго", "месть королевы анны"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "On gravestones, the Latin R.I.P. stands for 'requiescat in' what?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]},
     "de": {"q": "Auf Grabsteinen steht das lateinische R.I.P. für 'requiescat in' was?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]},
     "es": {"q": "En las lápidas, la sigla latina R.I.P. significa 'requiescat in' ¿qué?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]},
     "fr": {"q": "Sur les pierres tombales, le latin R.I.P. signifie 'requiescat in' quoi ?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]},
     "lt": {"q": "Ant antkapių lotyniškas R.I.P. reiškia 'requiescat in' ką?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]},
     "ru": {"q": "Латинское R.I.P. на надгробиях означает «requiescat in» что?", "a": ["pace"], "w": ["aeternum", "domino", "caelo", "terra"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "The 1981 horror comedy is called 'An American Werewolf in' which city?", "a": ["london"], "w": ["paris", "berlin", "rome", "dublin"]},
     "de": {"q": "Die Horrorkomödie von 1981 heißt im Original 'An American Werewolf in' welcher Stadt?", "a": ["london"], "w": ["paris", "berlin", "rom", "dublin"]},
     "es": {"q": "La comedia de terror de 1981 se titula 'Un hombre lobo americano en' ¿qué ciudad?", "a": ["londres"], "w": ["parís", "berlín", "roma", "dublín"]},
     "fr": {"q": "La comédie horrifique de 1981 s'intitule en anglais 'An American Werewolf in' quelle ville ?", "a": ["londres", "london"], "w": ["paris", "berlin", "rome", "dublin"]},
     "lt": {"q": "1981 m. siaubo komedija vadinasi 'Amerikietis vilkolakis' kokiame mieste?", "a": ["londone", "londonas"], "w": ["paryžiuje", "berlyne", "romoje", "dubline"]},
     "ru": {"q": "Хоррор-комедия 1981 года называется «Американский оборотень в...» каком городе?", "a": ["лондоне", "лондон"], "w": ["париже", "берлине", "риме", "дублине"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In 'Hotel Transylvania', what is the name of Dracula's daughter?", "a": ["mavis"], "w": ["luna", "sally", "morticia", "lucy"]},
     "de": {"q": "Wie heißt in 'Hotel Transsilvanien' Draculas Tochter?", "a": ["mavis"], "w": ["luna", "sally", "morticia", "lucy"]},
     "es": {"q": "En 'Hotel Transilvania', ¿cómo se llama la hija de Drácula?", "a": ["mavis"], "w": ["luna", "sally", "morticia", "lucy"]},
     "fr": {"q": "Dans 'Hôtel Transylvanie', comment s'appelle la fille de Dracula ?", "a": ["mavis"], "w": ["luna", "sally", "morticia", "lucy"]},
     "lt": {"q": "Kaip filme 'Viešbutis Transilvanija' vadinasi Drakulos dukra?", "a": ["meivis", "mavis"], "w": ["luna", "sali", "mortiša", "liusė"]},
     "ru": {"q": "Как зовут дочь Дракулы в мультфильме «Монстры на каникулах»?", "a": ["мэвис", "мейвис"], "w": ["луна", "салли", "мортиша", "люси"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of the elegant mother in 'The Addams Family'?", "a": ["morticia", "morticia addams"], "w": ["lily", "elvira", "sabrina", "maleficent"]},
     "de": {"q": "Wie heißt die elegante Mutter in der 'Addams Family'?", "a": ["morticia", "morticia addams"], "w": ["lily", "elvira", "sabrina", "malefiz"]},
     "es": {"q": "¿Cómo se llama la elegante madre de 'La familia Addams'?", "a": ["morticia", "morticia addams"], "w": ["lily", "elvira", "sabrina", "maléfica"]},
     "fr": {"q": "Comment s'appelle l'élégante mère de 'La Famille Addams' ?", "a": ["morticia", "morticia addams"], "w": ["lily", "elvira", "sabrina", "maléfique"]},
     "lt": {"q": "Kaip vadinasi elegantiška 'Adamsų šeimynėlės' mama?", "a": ["mortiša", "morticia"], "w": ["lili", "elvyra", "sabrina", "piktadarė"]},
     "ru": {"q": "Как зовут элегантную мать в «Семейке Аддамс»?", "a": ["мортиша", "мортиша аддамс"], "w": ["лили", "эльвира", "сабрина", "малефисента"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What is the name of the hunchbacked lab assistant in many Frankenstein films?", "a": ["igor", "ygor"], "w": ["renfield", "lurch", "quasimodo", "gollum"]},
     "de": {"q": "Wie heißt der bucklige Laborassistent in vielen Frankenstein-Filmen?", "a": ["igor", "ygor"], "w": ["renfield", "lurch", "quasimodo", "gollum"]},
     "es": {"q": "¿Cómo se llama el ayudante jorobado de laboratorio en muchas películas de Frankenstein?", "a": ["igor", "ygor"], "w": ["renfield", "largo", "quasimodo", "gollum"]},
     "fr": {"q": "Comment s'appelle l'assistant bossu de laboratoire dans de nombreux films de Frankenstein ?", "a": ["igor", "ygor"], "w": ["renfield", "max", "quasimodo", "gollum"]},
     "lt": {"q": "Kaip daugelyje Frankenšteino filmų vadinamas kuprotas laboratorijos padėjėjas?", "a": ["igoris", "igor"], "w": ["renfildas", "lerčas", "kvazimodas", "golumas"]},
     "ru": {"q": "Как зовут горбатого лаборанта во многих фильмах о Франкенштейне?", "a": ["игорь"], "w": ["ренфилд", "ларч", "квазимодо", "голлум"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "In 'Dracula', what is the name of the asylum patient who eats flies and spiders?", "a": ["renfield", "r. m. renfield"], "w": ["igor", "harker", "lurch", "seward"]},
     "de": {"q": "Wie heißt in 'Dracula' der Anstaltspatient, der Fliegen und Spinnen isst?", "a": ["renfield"], "w": ["igor", "harker", "lurch", "seward"]},
     "es": {"q": "En 'Drácula', ¿cómo se llama el paciente del manicomio que come moscas y arañas?", "a": ["renfield"], "w": ["igor", "harker", "largo", "seward"]},
     "fr": {"q": "Dans 'Dracula', comment s'appelle le patient de l'asile qui mange des mouches et des araignées ?", "a": ["renfield"], "w": ["igor", "harker", "max", "seward"]},
     "lt": {"q": "Kaip 'Drakuloje' vadinamas psichiatrinės ligoninės pacientas, valgantis muses ir vorus?", "a": ["renfildas", "renfield"], "w": ["igoris", "harkeris", "lerčas", "sjuardas"]},
     "ru": {"q": "Как зовут пациента лечебницы, поедающего мух и пауков, в романе «Дракула»?", "a": ["ренфилд"], "w": ["игорь", "харкер", "ларч", "сьюард"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Deadly nightshade, a poisonous plant tied to witch lore, is also known as what?", "a": ["belladonna"], "w": ["foxglove", "hemlock", "mandrake", "wolfsbane"]},
     "de": {"q": "Wie wird die Tollkirsche, eine mit Hexenlegenden verbundene Giftpflanze, auch genannt?", "a": ["belladonna"], "w": ["fingerhut", "schierling", "alraune", "eisenhut"]},
     "es": {"q": "¿Con qué otro nombre se conoce a la 'hierba mora mortal', planta venenosa ligada a la brujería?", "a": ["belladona", "belladonna"], "w": ["dedalera", "cicuta", "mandrágora", "acónito"]},
     "fr": {"q": "Sous quel autre nom connaît-on la 'morelle mortelle', plante vénéneuse liée aux sorcières ?", "a": ["belladone", "belladonna"], "w": ["digitale", "ciguë", "mandragore", "aconit"]},
     "lt": {"q": "Kaip dar vadinama nuodingoji šunvyšnė, augalas, siejamas su raganų tautosaka?", "a": ["beladona", "belladonna"], "w": ["rusmenė", "nuokana", "mandragora", "kurpelė"]},
     "ru": {"q": "Как ещё называют красавку — ядовитое растение, связанное с ведьминскими преданиями?", "a": ["белладонна"], "w": ["наперстянка", "болиголов", "мандрагора", "аконит"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which plant with a human-shaped root is said in legend to scream when pulled up?", "a": ["mandrake", "mandragora"], "w": ["ginseng", "garlic", "hemlock", "wolfsbane"]},
     "de": {"q": "Welche Pflanze mit menschenähnlicher Wurzel soll der Legende nach schreien, wenn man sie herauszieht?", "a": ["alraune", "mandragora"], "w": ["ginseng", "knoblauch", "schierling", "eisenhut"]},
     "es": {"q": "¿Qué planta de raíz con forma humana, según la leyenda, grita al ser arrancada?", "a": ["mandrágora"], "w": ["ginseng", "ajo", "cicuta", "acónito"]},
     "fr": {"q": "Quelle plante à la racine de forme humaine crierait, selon la légende, quand on l'arrache ?", "a": ["mandragore", "la mandragore"], "w": ["ginseng", "ail", "ciguë", "aconit"]},
     "lt": {"q": "Kuris augalas su žmogaus formos šaknimi, pasak legendos, rėkia, kai yra išraunamas?", "a": ["mandragora"], "w": ["ženšenis", "česnakas", "nuokana", "kurpelė"]},
     "ru": {"q": "Какое растение с корнем в форме человека, по легенде, кричит, когда его выдёргивают?", "a": ["мандрагора"], "w": ["женьшень", "чеснок", "болиголов", "аконит"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "In English, a group of crows is called a what?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]},
     "de": {"q": "Wie nennt man im Englischen einen Schwarm Krähen ('a ... of crows')?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]},
     "es": {"q": "En inglés, ¿cómo se llama un grupo de cuervos ('a ... of crows')?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]},
     "fr": {"q": "En anglais, comment appelle-t-on un groupe de corneilles ('a ... of crows') ?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]},
     "lt": {"q": "Kaip angliškai vadinamas varnų būrys ('a ... of crows')?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]},
     "ru": {"q": "Как по-английски называется стая ворон ('a ... of crows')?", "a": ["murder", "a murder"], "w": ["parliament", "pride", "school", "gaggle"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "What is the folklore name for the eerie lights seen over marshes at night?", "a": ["will-o'-the-wisp", "will o the wisp", "ignis fatuus"], "w": ["northern lights", "st. elmo's fire", "ball lightning", "fireflies"]},
     "de": {"q": "Wie nennt die Volkssage die unheimlichen Lichter, die nachts über Sümpfen zu sehen sind?", "a": ["irrlicht", "irrlichter"], "w": ["nordlicht", "elmsfeuer", "kugelblitz", "glühwürmchen"]},
     "es": {"q": "¿Qué nombre da el folclore a las inquietantes luces que se ven de noche sobre los pantanos?", "a": ["fuego fatuo", "fuegos fatuos"], "w": ["aurora boreal", "fuego de san telmo", "rayo globular", "luciérnagas"]},
     "fr": {"q": "Quel nom le folklore donne-t-il aux lueurs étranges aperçues la nuit au-dessus des marais ?", "a": ["feu follet", "feux follets"], "w": ["aurore boréale", "feu de saint-elme", "foudre en boule", "lucioles"]},
     "lt": {"q": "Kaip tautosakoje vadinamos paslaptingos šviesos, naktį matomos virš pelkių?", "a": ["žaltvykslės", "žaltvykslė", "klystžiburiai"], "w": ["šiaurės pašvaistė", "šv. elmo ugnis", "kamuolinis žaibas", "jonvabaliai"]},
     "ru": {"q": "Как в фольклоре называют загадочные огни, которые видят ночью над болотами?", "a": ["блуждающие огни", "блуждающий огонёк"], "w": ["северное сияние", "огни святого эльма", "шаровая молния", "светлячки"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "What German-derived name is given to a noisy spirit that moves objects around?", "a": ["poltergeist"], "w": ["banshee", "gargoyle", "goblin", "golem"]},
     "de": {"q": "Wie nennt man einen lärmenden Geist, der Gegenstände bewegt?", "a": ["poltergeist"], "w": ["banshee", "wasserspeier", "kobold", "golem"]},
     "es": {"q": "¿Qué nombre de origen alemán recibe un espíritu ruidoso que mueve objetos?", "a": ["poltergeist"], "w": ["banshee", "gárgola", "duende", "gólem"]},
     "fr": {"q": "Quel nom d'origine allemande donne-t-on à un esprit bruyant qui déplace les objets ?", "a": ["poltergeist", "esprit frappeur"], "w": ["banshee", "gargouille", "lutin", "golem"]},
     "lt": {"q": "Koks vokiškos kilmės pavadinimas suteikiamas triukšmingai dvasiai, judinančiai daiktus?", "a": ["poltergeistas", "poltergeist"], "w": ["banšė", "chimera", "goblinas", "golemas"]},
     "ru": {"q": "Как называют шумного духа, передвигающего предметы (слово немецкого происхождения)?", "a": ["полтергейст"], "w": ["банши", "горгулья", "гоблин", "голем"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "In Irish folklore, which female spirit wails to warn that someone will soon die?", "a": ["banshee", "a banshee"], "w": ["siren", "mermaid", "harpy", "valkyrie"]},
     "de": {"q": "Welcher weibliche Geist der irischen Sage kündigt mit Wehklagen einen baldigen Tod an?", "a": ["banshee", "todesfee"], "w": ["sirene", "meerjungfrau", "harpyie", "walküre"]},
     "es": {"q": "En el folclore irlandés, ¿qué espíritu femenino lanza lamentos para anunciar una muerte próxima?", "a": ["banshee", "la banshee"], "w": ["sirena", "ondina", "arpía", "valquiria"]},
     "fr": {"q": "Dans le folklore irlandais, quel esprit féminin gémit pour annoncer une mort prochaine ?", "a": ["banshee", "la banshee"], "w": ["sirène", "ondine", "harpie", "walkyrie"]},
     "lt": {"q": "Kuri airių tautosakos moteriška dvasia aimanuodama praneša apie artėjančią mirtį?", "a": ["banšė", "banshee"], "w": ["sirena", "undinė", "harpija", "valkirija"]},
     "ru": {"q": "Какой женский дух ирландского фольклора своим плачем предвещает скорую смерть?", "a": ["банши"], "w": ["сирена", "русалка", "гарпия", "валькирия"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which witch from Slavic folklore lives in a hut that stands on chicken legs?", "a": ["baba yaga", "baba jaga"], "w": ["kikimora", "rusalka", "vasilisa", "koschei"]},
     "de": {"q": "Welche Hexe aus der slawischen Sage lebt in einer Hütte auf Hühnerbeinen?", "a": ["baba jaga", "baba yaga"], "w": ["kikimora", "rusalka", "wassilissa", "koschtschei"]},
     "es": {"q": "¿Qué bruja del folclore eslavo vive en una choza sobre patas de gallina?", "a": ["baba yaga", "baba jaga"], "w": ["kikimora", "rusalka", "vasilisa", "koschéi"]},
     "fr": {"q": "Quelle sorcière du folklore slave vit dans une cabane montée sur des pattes de poule ?", "a": ["baba yaga", "baba jaga"], "w": ["kikimora", "roussalka", "vassilissa", "kochtcheï"]},
     "lt": {"q": "Kuri slavų tautosakos ragana gyvena trobelėje ant vištos kojų?", "a": ["baba jaga", "baba yaga"], "w": ["kikimora", "rusalka", "vasilisa", "koščejus"]},
     "ru": {"q": "Какая ведьма из славянского фольклора живёт в избушке на курьих ножках?", "a": ["баба-яга", "баба яга"], "w": ["кикимора", "русалка", "василиса", "кощей"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which actor starred as the scientist who turns into a fly in David Cronenberg's 'The Fly' (1986)?", "a": ["jeff goldblum", "goldblum"], "w": ["tom hanks", "bill murray", "kurt russell", "michael keaton"]},
     "de": {"q": "Welcher Schauspieler spielte in David Cronenbergs 'Die Fliege' (1986) den Wissenschaftler, der zur Fliege wird?", "a": ["jeff goldblum", "goldblum"], "w": ["tom hanks", "bill murray", "kurt russell", "michael keaton"]},
     "es": {"q": "¿Qué actor protagonizó al científico que se convierte en mosca en 'La mosca' (1986) de David Cronenberg?", "a": ["jeff goldblum", "goldblum"], "w": ["tom hanks", "bill murray", "kurt russell", "michael keaton"]},
     "fr": {"q": "Quel acteur incarne le savant qui se transforme en mouche dans 'La Mouche' (1986) de David Cronenberg ?", "a": ["jeff goldblum", "goldblum"], "w": ["tom hanks", "bill murray", "kurt russell", "michael keaton"]},
     "lt": {"q": "Kuris aktorius suvaidino musę virstantį mokslininką Davido Cronenbergo filme 'Musė' (1986)?", "a": ["jeffas goldblumas", "jeff goldblum", "goldblumas"], "w": ["tomas hanksas", "billas murray", "kurtas russellas", "michaelas keatonas"]},
     "ru": {"q": "Какой актёр сыграл учёного, превращающегося в муху, в фильме Дэвида Кроненберга «Муха» (1986)?", "a": ["джефф голдблюм", "голдблюм"], "w": ["том хэнкс", "билл мюррей", "курт рассел", "майкл китон"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which actor played the title ghost in Tim Burton's 'Beetlejuice' (1988)?", "a": ["michael keaton", "keaton"], "w": ["jim carrey", "bill murray", "johnny depp", "danny devito"]},
     "de": {"q": "Welcher Schauspieler spielte den titelgebenden Geist in Tim Burtons 'Beetlejuice' (1988)?", "a": ["michael keaton", "keaton"], "w": ["jim carrey", "bill murray", "johnny depp", "danny devito"]},
     "es": {"q": "¿Qué actor interpretó al fantasma protagonista de 'Bitelchús' (1988) de Tim Burton?", "a": ["michael keaton", "keaton"], "w": ["jim carrey", "bill murray", "johnny depp", "danny devito"]},
     "fr": {"q": "Quel acteur a joué le fantôme éponyme dans 'Beetlejuice' (1988) de Tim Burton ?", "a": ["michael keaton", "keaton"], "w": ["jim carrey", "bill murray", "johnny depp", "danny devito"]},
     "lt": {"q": "Kuris aktorius suvaidino titulinį vaiduoklį Timo Burtono filme 'Beetlejuice' (1988)?", "a": ["michaelas keatonas", "michael keaton", "keatonas"], "w": ["jimas carrey", "billas murray", "johnny deppas", "danny devito"]},
     "ru": {"q": "Какой актёр сыграл заглавного призрака в фильме Тима Бёртона «Битлджус» (1988)?", "a": ["майкл китон", "китон"], "w": ["джим керри", "билл мюррей", "джонни депп", "дэнни де вито"]}},

    {"difficulty": "normal", "points": 900,
     "en": {"q": "Which organ did ancient Egyptian embalmers usually leave inside a mummy's body?", "a": ["heart", "the heart"], "w": ["brain", "liver", "lungs", "stomach"]},
     "de": {"q": "Welches Organ ließen altägyptische Einbalsamierer meist im Körper einer Mumie?", "a": ["herz", "das herz"], "w": ["gehirn", "leber", "lunge", "magen"]},
     "es": {"q": "¿Qué órgano solían dejar los embalsamadores del antiguo Egipto dentro del cuerpo de una momia?", "a": ["corazón", "el corazón"], "w": ["cerebro", "hígado", "pulmones", "estómago"]},
     "fr": {"q": "Quel organe les embaumeurs de l'Égypte antique laissaient-ils généralement dans le corps d'une momie ?", "a": ["cœur", "le cœur", "coeur"], "w": ["cerveau", "foie", "poumons", "estomac"]},
     "lt": {"q": "Kurį organą senovės Egipto balzamuotojai paprastai palikdavo mumijos kūne?", "a": ["širdį", "širdis"], "w": ["smegenis", "kepenis", "plaučius", "skrandį"]},
     "ru": {"q": "Какой орган древнеегипетские бальзамировщики обычно оставляли в теле мумии?", "a": ["сердце"], "w": ["мозг", "печень", "лёгкие", "желудок"]}},

    {"difficulty": "normal", "points": 800,
     "en": {"q": "Which American author wrote 'The Legend of Sleepy Hollow'?", "a": ["washington irving", "irving"], "w": ["edgar allan poe", "mark twain", "nathaniel hawthorne", "herman melville"]},
     "de": {"q": "Welcher amerikanische Autor schrieb 'Die Sage von der schläfrigen Schlucht'?", "a": ["washington irving", "irving"], "w": ["edgar allan poe", "mark twain", "nathaniel hawthorne", "herman melville"]},
     "es": {"q": "¿Qué autor estadounidense escribió 'La leyenda de Sleepy Hollow'?", "a": ["washington irving", "irving"], "w": ["edgar allan poe", "mark twain", "nathaniel hawthorne", "herman melville"]},
     "fr": {"q": "Quel auteur américain a écrit 'La Légende de Sleepy Hollow' ?", "a": ["washington irving", "irving"], "w": ["edgar allan poe", "mark twain", "nathaniel hawthorne", "herman melville"]},
     "lt": {"q": "Kuris amerikiečių rašytojas parašė 'Mieguistosios daubos legendą'?", "a": ["vašingtonas irvingas", "irvingas", "washington irving"], "w": ["edgaras alanas po", "markas tvenas", "natanielis hotornas", "hermanas melvilis"]},
     "ru": {"q": "Какой американский писатель написал «Легенду о Сонной Лощине»?", "a": ["вашингтон ирвинг", "ирвинг"], "w": ["эдгар аллан по", "марк твен", "натаниэль готорн", "герман мелвилл"]}},
]


def _validate():
    for entry in QUESTIONS:
        assert (entry["difficulty"], entry["points"]) in {("easy", 700), ("normal", 800), ("normal", 900)}, entry["en"]["q"]
        for lang in LANGS:
            assert lang in entry, f"missing {lang} in {entry['en']['q']}"
            rec = entry[lang]
            assert len(rec["q"]) <= 200, f"{lang} question too long: {rec['q']}"
            assert len(rec["a"]) >= 1 and len(rec["w"]) >= 3, f"{lang} answers: {rec['q']}"
            for s in rec["a"] + rec["w"]:
                assert s == s.lower(), f"{lang} not lowercase: {s!r}"
                assert len(s) < 30, f"{lang} answer too long: {s!r}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _validate()

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
        if added + skipped_exist >= TARGET_NEW:   # batch ids already in corpus count toward the cap
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

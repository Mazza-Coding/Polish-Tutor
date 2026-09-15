"""Teach Yourself Polish, M. Corbridge-Patkaniowska: lessons 1–7.

Transcribed from the user-supplied Roy Publishers scan. No PDF is redistributed.
Table rows: printed page | source item | English cue | Polish text/answer.
`reading` English cues are editorial glosses, NOT translations printed in the key.
`translation` answers are from the printed key, pp. 217–219. A double semicolon
separates alternatives; editorial alternatives are explicitly labelled. See SOURCE and lesson notes.
Vocabulary rows: first taught form | part of speech | gloss | recognized forms.
The form inventory is cumulative; it does not introduce later lessons early.
"""

from polish_tutor.data.lesson_01 import LESSON as LESSON_01
from polish_tutor.data.lesson_02 import LESSON as LESSON_02
from polish_tutor.data.lesson_03 import LESSON as LESSON_03
from polish_tutor.data.lesson_04 import LESSON as LESSON_04
from polish_tutor.data.lesson_05 import LESSON as LESSON_05
from polish_tutor.data.lesson_06 import LESSON as LESSON_06
from polish_tutor.data.lesson_07 import LESSON as LESSON_07

SOURCE = {
    "title": "Teach Yourself Polish",
    "author": "M. Corbridge-Patkaniowska",
    "publisher": "Roy Publishers, New York",
    "edition": "User-supplied scan; publication year not specified on title pages",
    "printed_pages": [7, 31],
    "pdf_pages": [15, 39],
    "key_printed_pages": [217, 219],
    "key_pdf_pages": [225, 227],
    "scope": "Lessons 1–7, ending before Lesson 8 on printed page 31",
    "adaptation": (
        "Original Polish readings are reversed for Polish typing; their English cues "
        "are editorial glosses. Published English-to-Polish answers are retained. "
        "Typography and line-break hyphenation are normalized. Exact-match practice "
        "uses the displayed model, not an exhaustive list of possible translations."
    ),
}
PROPER_NAMES = ("Staszek", "Stanisław", "Hania", "Anna", "Maryla", "Maria", "Zosia", "Zofia", "Rawicz", "Janek")

LESSONS = [LESSON_01, LESSON_02, LESSON_03, LESSON_04, LESSON_05, LESSON_06, LESSON_07]

# Explicit paradigms printed in the lessons; no generated forms from later chapters.
# lesson | page | verb label | six present forms in ja/ty/on-ona-ono/my/wy/oni-one order
PRESENT = """
2|10|kochać|kocham kochasz kocha kochamy kochacie kochają
2|10|czytać|czytam czytasz czyta czytamy czytacie czytają
2|10|zamykać|zamykam zamykasz zamyka zamykamy zamykacie zamykają
2|10|mieć|mam masz ma mamy macie mają
5|21|umieć|umiem umiesz umie umiemy umiecie umieją
5|21|rozumieć|rozumiem rozumiesz rozumie rozumiemy rozumiecie rozumieją
5|21|wiedzieć|wiem wiesz wie wiemy wiecie wiedzą
5|21|jeść|jem jesz je jemy jecie jedzą
"""
# page | verb label | familiar singular / let us / familiar plural
IMPERATIVE = """
29|kochać|kochaj kochajmy kochajcie
29|czytać|czytaj czytajmy czytajcie
29|pamiętać|pamiętaj pamiętajmy pamiętajcie
29|jeść|jedz jedzmy jedzcie
29|wiedzieć|wiedz wiedzmy wiedzcie
"""

# Other explicitly printed form tables: lesson | printed page | item | cue | answer.
TABLES = """
1|8|plural.okno|Plural of okno.|Okna.
1|8|plural.pioro|Plural of pióro.|Pióra.
1|8|plural.pole|Plural of pole.|Pola.
1|8|plural.morze|Plural of morze.|Morza.
1|8|plural.pudelko|Plural of pudełko.|Pudełka.
1|8|plural.dziecko|Plural of dziecko (irregular).|Dzieci.
1|8|plural.to|Plural of to (qualifying these neuter nouns).|Te.
1|8|plural.tamto|Plural of tamto (qualifying these neuter nouns).|Tamte.
4|19|gen.to|Genitive singular of to.|Tego.
4|19|gen.tamto|Genitive singular of tamto.|Tamtego.
4|19|gen.jedno|Genitive singular of jedno.|Jednego.
4|19|gen.duze|Genitive singular of duże.|Dużego.
4|19|gen.ladne|Genitive singular of ładne.|Ładnego.
4|19|gen.czyje|Genitive singular of czyje.|Czyjego.
4|19|gen.moje|Genitive singular of moje.|Mojego.
4|19|gen.wasze|Genitive singular of wasze.|Waszego.
4|19|gen.kto|Genitive of kto.|Kogo.
4|19|gen.co|Genitive of co.|Czego.
7|27|gen.dobre|Genitive plural of dobre.|Dobrych.
7|27|gen.duze|Genitive plural of duże.|Dużych.
7|27|gen.male|Genitive plural of małe.|Małych.
7|27|gen.ladne|Genitive plural of ładne.|Ładnych.
7|27|gen.nasze|Genitive plural of nasze.|Naszych.
7|27|gen.wasze|Genitive plural of wasze.|Waszych.
7|27|gen.to|Genitive plural of to.|Tych.
7|27|gen.tamto|Genitive plural of tamto.|Tamtych.
7|28|gen.tanie|Genitive plural of tanie.|Tanich.
7|28|gen.krotkie|Genitive plural of krótkie.|Krótkich.
7|28|gen.dlugie|Genitive plural of długie.|Długich.
7|28|gen.drogie|Genitive plural of drogie.|Drogich.
7|28|gen.jakie|Genitive plural of jakie.|Jakich.
7|28|gen.takie|Genitive plural of takie.|Takich.
7|28|gen.moje|Genitive plural of moje.|Moich.
7|28|gen.twoje|Genitive plural of twoje.|Twoich.
7|28|gen.czyje|Genitive plural of czyje.|Czyich.
7|28|gen.dwa|Genitive of dwa.|Dwu. ;; Dwóch.
7|28|gen.trzy|Genitive of trzy.|Trzech.
7|28|gen.cztery|Genitive of cztery.|Czterech.
7|28|gen.piec|Genitive of pięć.|Pięciu.
7|28|gen.szesc|Genitive of sześć.|Sześciu.
7|28|gen.siedem|Genitive of siedem.|Siedmiu.
7|28|gen.osiem|Genitive of osiem.|Ośmiu.
7|28|gen.dziewiec|Genitive of dziewięć.|Dziewięciu.
7|28|gen.dziesiec|Genitive of dziesięć.|Dziesięciu.
"""

EDITORIAL_NOTES = {
    (2, "examples", "c"): "The printed English adds new, absent from the Polish. This cue follows the Polish; the difference is not silently added to the answer.",
    (3, "translation", "3"): "The key ends this question with a full stop; punctuation is retained and final punctuation is ignored by the grader.",
    (6, "plural", "6"): "Printed prompt Szuka pióra is third-person singular, but the key gives first-person plural Szukamy piór. Szukają piór is an explicitly derived, person-preserving alternative, not a quotation from the key.",
}

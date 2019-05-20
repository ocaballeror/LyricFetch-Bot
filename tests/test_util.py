import sys

import pytest

sys.path.append('.')
from util import capwords
from util import process


@pytest.mark.parametrize(
    'words, expect',
    [
        ('', ''),
        ('1234', '1234'),
        ('hello', 'Hello'),
        ('hello world', 'Hello World'),
        ("apostrophe's", "Apostrophe's"),
        ('(bracketed)', '(Bracketed)'),
        ('...and justice', '...And Justice'),
        ('word,and,comma', 'Word,And,Comma'),
        ('roman numerals I', 'Roman Numerals I'),
        ('roman numerals II', 'Roman Numerals II'),
        ('roman numerals III', 'Roman Numerals III'),
        ('roman numerals IV', 'Roman Numerals IV'),
        ('roman numerals V', 'Roman Numerals V'),
        ('roman numerals VI', 'Roman Numerals VI'),
        ('roman numerals VII', 'Roman Numerals VII'),
        ('roman numerals VIII', 'Roman Numerals VIII'),
        ('roman numerals IX', 'Roman Numerals IX'),
        ('roman numerals X', 'Roman Numerals X'),
        ('roman numerals XI', 'Roman Numerals XI'),
    ],
)
def test_capwords(words, expect):
    assert capwords(words) == expect


@pytest.mark.parametrize(
    'name,expect',
    [
        ('äéìôçñ', 'aeiocn'),
        ('Mjölner, Hammer of Thor', 'mjolner hammer of thor'),
        ('Zero Tolerance - Demo', 'zero tolerance'),
        ('Zombie Ritual - Live in Germany April 13th 1993', 'Unknown'),
        ('Hit The Lights - Remastered', 'hit the lights'),
        ('Give Em War - Demo 2003', 'give em war'),
        ('Innocent Exile - 1998 Remastered Version', 'innocent exile'),
        ('Intro/Chapter Four - Live in Ventura', 'Unknown'),
        (
            'Scavenger of Human Sorrow - 1998 Demos',
            'scavenger of human sorrow',
        ),
        ('Walk Away (Live)', 'Unknown'),
        (
            'Overkill - BBC Live from Caister Great Yarmouth 13/10/84',
            'Unknown',
        ),
        (
            "If You Want Blood (You've Got It)",
            "if you want blood you've got it",
        ),
        ('Heart Shaped Box - 2013 Remix', 'heart shaped box'),
        ('(We Are) The Roadcrew', 'we are the roadcrew'),
        (
            'Where the Enemy Sleeps... - Remastered',
            'where the enemy sleeps...',
        ),
        ('Aces High - cover version', 'aces high'),
        ('Emptier Still - remastered version 2009', 'emptier still'),
        ('Join the Ranks (Bonus Track)', 'join the ranks'),
        ('Take No Prisoners - Demo/Remastered 2004', 'take no prisoners'),
        (
            'Desastre (Spanish Version - Bonus Track)',
            'desastre spanish version',
        ),
        (
            'Tomorrow Turned Into Yesterday - remixed & remastered',
            'tomorrow turned into yesterday',
        ),
        ('Phantom Antichrist - Live @ Wacken 2014', 'Unknown'),
        (
            'Fainting Spells - From Decemberunderground Sessions 2006',
            'fainting spells',
        ),
    ],
)
def test_process(name, expect):
    assert process(name, key='name') == expect

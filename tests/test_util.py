import sys

import pytest

sys.path.append('.')
from util import capwords


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

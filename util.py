import re
import string

INVALID = {
    'name': [r'\(?live( (at|@|from|in)[^)]*)?\)?'],
    'album': [
        '^unknown album',
        '^undefined',
        'greatest hits',
        r'live( (at|from|in)[^)]*)?',
        r'\(?live\)?$',
        '^(the )?(very )?best of',
        '^the very best',
        'compilation',
    ],
}
JUNK = {
    'all': {
        r'^[0-9]+\.': '',
        r'^[0-9]+ ?\- ?[^0-9]': '',
        r"[\*%|;/\n\r]": ' ',
        '[^ ]&[^ ]': ' and ',
        '&': 'and',
        '[`’]': "'",
        '…': '...',
        r'\.\.(?=[^\.])': '.. ',
        ' {2,}': ' ',
    },
    'name': [
        r'\[.*\]',
        r'\( *\)',
        r' *-.+$',
        r'[^\w \.\']',
        'bonus( track)?',
        'full dynamic range( edition ?)?',
        r'\((the )?original (version|soundtrack)\)',
        r'( *\- *)?\(?(\d+ *)?re(master|issue|mixed)(ed)?(\d+ *)?\)?',
        r'original (version|edition)',
        r'\(?demo\)?$',
    ],
    'album': [
        r'\(.*\)',
        r'\[.*\]',
        'deluxe(version|edition)',
        'special edition',
        're-?issue',
        'full dynamic range( edition ?)?',
        'deluxe( version| edition)? ?',
        r'( *\- *)?\(?(\d+ *)?re(master|issue)(ed)?(\d+ *)?\)?',
    ],
}


def is_value_invalid(value, key):
    """
    Helper function to is_invalid that checks if a single value is valid.

    The argument 'key' specifies the key to use for the global `junk` and
    `invalid` dictionaries.
    """
    return any(re.search(r, value, re.I) for r in INVALID[key])


def chunks(list0, list1, n):
    """
    Yield successive n-sized chunks from l.
    """
    list0 = list(list0)
    list1 = list(list1)
    leng = min(len(list0), len(list1))
    for i in range(0, leng, n):
        yield list0[i : i + n], list1[i : i + n]


def _capword(word):
    if not word:
        return word
    ret = word[0].upper()
    if len(word) == 1:
        return ret
    else:
        return ret + word[1:]


def capwords(value):
    """
    Capitalize words.
    """
    value = string.capwords(value)
    # Capitalize words starting with any of the following characters.
    for separator in ['(', '.', ',', '"']:
        value = separator.join(map(_capword, value.split(separator)))

    # Properly capitalize some all-caps words
    regs = ['[vx]?i+[vx]?', 'zz', 'ny', 'ufo']
    for reg in regs:
        reg = re.compile(f'^{reg}$', re.IGNORECASE)
        map_ = map(lambda i: i.upper() if reg.match(i) else i, value.split())
        value = ' '.join(map_)

    return value


def process(value, key, invalid=True, junk=True):
    """
    Remove weird characters from a string. Meant for album names, artists
    and titles.
    """
    if not value:
        return 'Unknown'
    value = value.lower()
    if invalid and is_value_invalid(value, key):
        return 'Unknown'
    junk = JUNK[key] if junk else []
    replace = JUNK['all'].copy()

    for delete in junk:
        replace[delete] = ''
    for regex, sub in replace.items():
        old_value = value
        value = re.sub(regex, sub, value, flags=re.IGNORECASE)
        if not value:
            value = old_value

    return value.strip()

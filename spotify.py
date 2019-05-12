import re
import string
import pickle
from pathlib import Path
from datetime import date

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


CACHE_DIR = Path('.cache')
replace_filename = {r'[\?\"\'<>\/\\,\-\!]': '', ':': ' ', ' {2,}': ' '}
replace_info = {
    r'^[0-9]+\.': '',
    r'^[0-9]+ ?\- ?[^0-9]': '',
    r"[\*%|;/\n\r]": ' ',
    '[^ ]&[^ ]': ' and ',
    '&': 'and',
    '[`’]': "'",
    '…': '...',
    r'\.\.(?=[^\.])': '.. ',
    ' {2,}': ' ',
}
INVALID = {
    'name': [
        r'\(live( (at|from|in)[^)]*)?\)',
        r'( *\- *)?\(?(\d+ *)?demo?(\d+ *)?\)?',
    ],
    'artist': ['various( artists)?', 'unkown artist'],
    'album': [
        '^unknown album',
        '^undefined',
        'greatest hits',
        r'\(live( (at|from|in)[^)]*)?\)',
        '^(the )?(very )?best of',
        '^the very best',
        'compilation',
    ],
}
JUNK = {
    'name': [
        'bonus( track)?',
        # r'\[.*\]', r'\( *\)',
        'full dynamic range( edition ?)?',
        r'\((the )?original (version|soundtrack)\)',
        r'( *\- *)?\(?(\d+ *)?re(master|issue|mixed)(ed)?(\d+ *)?\)?',
    ],
    # 'artist': [r'\(.*\)'],
    'album': [
        # r'\(.*\)', r'\[.*\]',
        'deluxe(version|edition)',
        'special edition',
        're-?issue',
        'full dynamic range( edition ?)?',
        r'( *\- *)?\(?(\d+ *)?re(master|issue)(ed)?(\d+ *)?\)?',
    ],
}


def is_value_invalid(value, key):
    """
    Helper function to is_invalid that checks if a single value is valid.

    The argument 'key' specifies the key to use for the global `junk` and
    `invalid` dictionaries.
    """
    if any(re.search(r, value, re.I) for r in INVALID[key]):
        return True

    replace = replace_info.copy()
    for delete in JUNK[key]:
        replace[delete] = ''
    for regex, sub in replace.items():
        value = re.sub(regex, sub, value, flags=re.IGNORECASE)
        if not value:
            return True

    return False


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

    return value


def process(value, invalid=None, junk=None):
    """
    Remove weird characters from a string. Meant for album names, artists
    and titles.
    """
    if not value:
        return 'Unknown'
    value = value.lower()
    invalid = invalid or []
    junk = junk or []
    if any(re.match(inv, value) for inv in invalid):
        return 'Unknown'
    replace = replace_info.copy()

    if junk:
        for delete in junk:
            replace[delete] = ''
    for regex, sub in replace.items():
        old_value = value
        value = re.sub(regex, sub, value, flags=re.IGNORECASE)
        if not value:
            value = old_value

    value = capwords(value)

    # Properly capitalize some all-caps words
    regs = ['[vx]?i+[vx]?', 'zz', 'ny', 'ufo']
    for reg in regs:
        reg = re.compile(f'^{reg}$', re.IGNORECASE)
        map_ = map(lambda i: i.upper() if reg.match(i) else i, value.split())
        value = ' '.join(map_)
    return value


def _set_release_date(album):
    """
    Take a spotify album object and convert its release_date string into a
    datetime.date object, taking into account the different precisions
    available.
    """
    release = album['release_date']
    if album['release_date_precision'] == 'year':
        release += '-01-01'
    elif album['release_date_precision'] == 'month':
        release += '-01'
    album['release_date'] = date(*(map(int, release.split('-'))))


class Spotify:
    def __init__(self):
        self.discography_cache = {}
        self.load_cache()
        self.sp = None

    def configure(self, client_id, client_secret):
        credentials = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        self.sp = spotipy.Spotify(client_credentials_manager=credentials)

    def save_cache(self):
        """
        Store the current organization in a cache file.
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_DIR / '.cache-spotify', 'wb') as cache_file:
            pickle.dump(self.discography_cache, cache_file)

    def load_cache(self):
        """
        Return a list of files that are cached and can be ignored.
        """
        if not (CACHE_DIR / '.cache-spotify').is_file():
            return
        with open(CACHE_DIR / '.cache-spotify', 'rb') as cache_file:
            self.discography_cache.update(pickle.load(cache_file))

    def get_discography(self, artist, song_name):
        """
        Return the list of albums and their track names.

        Invalid albums (as decided by `is_value_invalid()`) are not included.
        Song names are preprocessed using `process()`.

        The result is a dictionary indexed by album name and sorted by release
        date.
        """
        for regex, rep in replace_filename.items():
            song_name = re.sub(regex, rep, song_name, flags=re.IGNORECASE)
        query = self.sp.search(
            f'artist:{artist} track:{song_name}', type='track'
        )
        artist_id = query['tracks']['items'][0]['artists'][0]['id']
        query = self.sp.artist_albums(artist_id, album_type='album')
        artist_albums = {}
        while query:
            for album in query['items']:
                if is_value_invalid(album['name'], key='album'):
                    continue
                _set_release_date(album)
                elem = dict(id=album['id'], release_date=album['release_date'])
                name = process(album['name'], INVALID['album'], JUNK['album'])
                artist_albums[name] = elem
            query = self.sp.next(query)
        sort = sorted(
            artist_albums.items(), key=lambda x: x[1]['release_date']
        )
        artist_albums = dict(sort)

        album_ids = [album['id'] for album in artist_albums.values()]
        for albums, ids in chunks(artist_albums.values(), album_ids, 20):
            query = self.sp.albums(ids)

            for album, response in zip(albums, query['albums']):
                tracks = []
                while response:
                    if 'tracks' in response:
                        response = response['tracks']
                    tracks.extend(
                        process(t['name'], INVALID['name'], JUNK['name'])
                        for t in response['items']
                    )
                    response = self.sp.next(response)
                tracks = dict.fromkeys(tracks)
                tracks.pop('Unknown', None)
                album['tracks'] = list(tracks)
        return {
            k: v for k, v in artist_albums.items() if v.get('tracks', None)
        }

    def fetch_album(self, song):
        """
        Get the name of the album for a song from spotify.
        """
        artist, title = song.artist, song.title
        if artist not in self.discography_cache:
            try:
                discog = self.get_discography(artist, title)
            except Exception:
                discog = None
            self.discography_cache[artist] = discog

        if not self.discography_cache[artist]:
            return 'Unknown'

        for album_name, info in self.discography_cache[artist].items():
            if title.lower() in map(str.lower, info['tracks']):
                return album_name
        return 'Unknown'

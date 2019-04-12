import sys
import sqlite3
from tempfile import NamedTemporaryFile

import pytest
import lyricfetch
from lyricfetch import Song

sys.path.append('.')
import bot
from bot import start
from bot import _get_next_song
from bot import next_song
from bot import get_album_tracks


class Infinite:
    def __getattr__(self, attr):
        return Infinite()


message_buffer = []


def append_message(*args, **kwargs):
    message_buffer.append(args[0])


bot.send_message = append_message


def test_start(monkeypatch):
    with NamedTemporaryFile(mode='w+') as tmpfile:
        monkeypatch.setattr(bot, 'HELPFILE', tmpfile.name)
        tmpfile.file.write('hello world')
        tmpfile.file.flush()
        start(Infinite(), Infinite())
    assert message_buffer[-1] == 'hello world'


class FakeDB:
    def __init__(self, last_res=None):
        self._last_res = last_res

    def get_last_res(self, _):
        return self._last_res


def test_album_tracks(monkeypatch):
    """
    Test the get_album_tracks function.
    """
    song = Song('Sabaton', '1 6 4 8')
    with monkeypatch.context() as mkp:
        mkp.setattr(lyricfetch.Song, 'fetch_album_name', lambda x: None)
        assert get_album_tracks(song) == []

    tracks = get_album_tracks(song)
    tracks = '\n'.join(tracks)
    assert 'carolus rex' in tracks
    assert 'en livstid i krig' in tracks


def test_next_song_no_last(monkeypatch):
    """
    Test get the next song when there is no "last result".
    """
    monkeypatch.setattr(bot, 'DB', FakeDB(None))
    assert _get_next_song(1) == "You haven't searched for anything yet"


@pytest.mark.parametrize(
    'tracks, expect',
    [
        (None, "Could not find the album this song belongs to"),
        ([], "Could not find the album this song belongs to"),
        (['something'], "Could not find the album this song belongs to"),
        (['title'], "That was the last song on the album"),
    ],
    ids=[
        'None return',
        'Empty track list',
        'Missing last result',
        'Last song on the album',
    ],
)
def test_next_song_no_album(tracks, expect, monkeypatch):
    """
    Test the _get_next_song function when we can't find the name of the next
    song.
    """
    monkeypatch.setattr(bot, 'DB', FakeDB(('artist', 'title')))
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    assert _get_next_song(1) == expect


def test_next_song_dberror(monkeypatch):
    """
    Test get the last song when a database error is thrown.
    """
    def raise_error(*args):
        raise sqlite3.Error()

    f = FakeDB()
    f.get_last_res = raise_error
    monkeypatch.setattr(bot, 'DB', f)
    assert _get_next_song(1).startswith('There was an error while')


def test_next_song_existing(monkeypatch):
    """
    Test the _get_next_song existing when everything goes smoothly and the next
    song is found.
    """
    tracks = ['title', 'something else']
    song_next = Song('artist', 'something else', 'album')
    monkeypatch.setattr(bot, 'DB', FakeDB(('artist', 'title')))
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    monkeypatch.setattr(
        bot, 'get_lyrics', lambda s, c: (f'Searching for {s}', c)
    )

    assert _get_next_song(1) == f'Searching for {song_next}'


def test_next_song(monkeypatch):
    """
    Test the next_song function, in a similar manner to _get_next_song.
    """
    tracks = ['title', 'something else']
    song_next = Song('artist', 'something else', 'album')
    monkeypatch.setattr(bot, 'DB', FakeDB(('artist', 'title')))
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    monkeypatch.setattr(
        bot, 'get_lyrics', lambda s, c: (f'Searching for {s}', c)
    )

    update = Infinite()
    next_song(1, update)
    assert message_buffer[-1] == f'Searching for {song_next}'

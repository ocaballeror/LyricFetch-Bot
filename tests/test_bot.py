import sys
import json
import sqlite3
from tempfile import NamedTemporaryFile

import pytest
import telegram
import lyricfetch
from lyricfetch import Song
from lyricfetch.scraping import id_source

sys.path.append('.')
import bot
from bot import start
from bot import _get_next_song
from bot import next_song
from bot import get_album_tracks
from bot import other
from bot import get_song_from_string
from bot import log_result
from bot import get_lyrics
from bot import find
from bot import unknown
from bot import parse_config


class Infinite:
    def __getattr__(self, attr):
        return Infinite()


class Nothing:
    pass


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


def raise_sqlite_error(*args, **kwargs):
    raise sqlite3.Error()


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
    f = FakeDB()
    f.get_last_res = raise_sqlite_error
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


def test_other_no_lastres(monkeypatch):
    """
    Test the 'other' function when there is no last result.
    """
    monkeypatch.setattr(bot, 'DB', FakeDB(None))
    other(Infinite(), Infinite())

    expect = "You haven't searched for anything yet"
    assert message_buffer[-1] == expect


def test_other_dberror(monkeypatch):
    """
    Test the 'other' function when a database error is thrown.
    """
    f = FakeDB()
    f.get_last_res = raise_sqlite_error
    monkeypatch.setattr(bot, 'DB', f)
    other(Infinite(), Infinite())

    expect = "There was an error"
    assert message_buffer[-1].startswith(expect)


def test_other_no_sources(monkeypatch):
    """
    Test the 'other' function when there are no sources left to search.
    """
    scraping_func = lyricfetch.sources[-1].__name__
    song = Song('artist', 'title')
    fakedb = FakeDB((song.artist, song.title, scraping_func))
    monkeypatch.setattr(bot, 'DB', fakedb)

    other(Infinite(), Infinite())
    assert 'No other sources' in message_buffer[-1]


def test_other(monkeypatch):
    """
    Test the 'other' function.
    """

    def fake_get_lyrics(*args):
        return str(args), str(args)

    scraping_func = lyricfetch.sources[0].__name__
    song = Song('artist', 'title')
    fakedb = FakeDB((song.artist, song.title, scraping_func))
    monkeypatch.setattr(bot, 'DB', fakedb)
    monkeypatch.setattr(bot, 'get_lyrics', fake_get_lyrics)

    other(Infinite(), Infinite())
    msg = message_buffer[-1]
    assert repr(song) in msg
    assert scraping_func not in msg


def test_get_song_from_string():
    string = 'artist - title'
    song = Song('artist', 'title')
    assert get_song_from_string(string, None) == song
    assert get_song_from_string(song, None) == song


def test_get_song_from_string_lastres(monkeypatch):
    """
    Test get a song from string when there is no hyphen and we must get the
    last result from the database.
    """
    chat_id = 1
    monkeypatch.setattr(bot, 'DB', FakeDB(None))
    assert get_song_from_string('', chat_id) is None

    song = Song('artist', 'title')
    monkeypatch.setattr(bot, 'DB', FakeDB(('artist',)))
    assert get_song_from_string('title', chat_id) == song


def test_log_result(monkeypatch, caplog):
    buffer = []

    def fake_log_result(*args):
        buffer.append(args)

    monkeypatch.setattr(bot.DB, 'log_result', fake_log_result)
    args = (1, 'result')
    log_result(*args)
    assert buffer == [args]

    monkeypatch.setattr(bot.DB, 'log_result', raise_sqlite_error)
    log_result(*args)
    records = list(caplog.records)
    assert len(records) == 1
    assert 'sqlite3.error' in caplog.text.lower()


def test_get_lyrics_invalid_format(monkeypatch, database):
    """
    Call get_lyrics with an invalid song string.
    """
    monkeypatch.setattr(bot, 'DB', database)
    assert get_lyrics('asdf', 1) == ('Invalid format!', False)


def test_get_lyrics_notfound(monkeypatch):
    """
    Test get_lyrics when no lyrics are found.
    """

    def assert_not_found(msg, valid):
        msg, valid = get_lyrics(song, 1)
        msg = msg.lower()
        assert song.artist in msg
        assert song.title in msg
        assert 'could not be found' in msg
        assert not valid

    song = Song('artist', 'title')
    result = Nothing()
    result.source = 'hello'
    monkeypatch.setattr(bot.lyrics, 'get_lyrics', lambda a, b: result)

    msg, valid = get_lyrics(song, 1)
    assert_not_found(msg, valid)

    result.source = None
    song.lyrics = 'hello'
    msg, valid = get_lyrics(song, 1)
    assert_not_found(msg, valid)


def test_get_lyrics_error(monkeypatch, caplog):
    monkeypatch.setattr(bot, 'get_song_from_string', raise_sqlite_error)
    msg, valid = get_lyrics('', 1)
    assert msg == 'Unknown error'
    assert not valid
    assert len(caplog.records) == 1
    assert 'sqlite3.Error' in caplog.text


def test_get_lyrics_found(monkeypatch, database):
    song = Song('artist', 'title', lyrics='lyrics')
    result = Nothing()
    result.source = lyricfetch.sources[0]
    result.song = song
    source_name = id_source(result.source, full=True).lower()

    monkeypatch.setattr(bot, 'DB', database)
    monkeypatch.setattr(bot.lyrics, 'get_lyrics', lambda a, b: result)
    msg, valid = get_lyrics(song, 1)
    msg = msg.lower()
    assert valid
    assert source_name in msg
    assert song.title in msg
    assert song.artist in msg
    assert song.lyrics in msg
    assert database.get_last_res(1)


def test_find(monkeypatch):
    """
    Test the 'find' function.
    """
    call_log = []

    def log_call(*args, **kwargs):
        call_log.append((*args, *kwargs.values()))

    def fake_getlyrics(*args, **kwargs):
        log_call(*args, **kwargs)
        return 'here are your lyrics', True

    update = Nothing()
    update.message = Nothing()
    update.message.chat_id = 1
    update.message.text = 'message text'
    bot_arg = Nothing()
    bot_arg.send_chat_action = log_call
    monkeypatch.setattr(bot, 'get_lyrics', fake_getlyrics)

    find(bot_arg, update)
    assert call_log[0] == (1, telegram.ChatAction.TYPING)
    assert call_log[1] == ('message text', 1)
    assert message_buffer[-1] == 'here are your lyrics'


def test_unknown():
    """
    Test the 'unknown' function.
    """
    unknown(Infinite(), Infinite())
    assert "didn't understand that" in message_buffer[-1]


@pytest.mark.parametrize(
    'content',
    [{}, {'token': 'token'}, {'db_filename': 'filename'}],
    ids=['empty', 'no db filename', 'no token'],
)
def test_parse_config_missing_keys(content, monkeypatch):
    with NamedTemporaryFile(mode='w') as tmpfile:
        monkeypatch.setattr(bot, 'CONFFILE', tmpfile.name)
        json.dump(content, tmpfile.file)
        tmpfile.file.flush()
        with pytest.raises(KeyError):
            parse_config()


def test_parse_config(monkeypatch):
    content = {'token': 'token', 'db_filename': 'filename'}
    with NamedTemporaryFile(mode='w') as tmpfile:
        monkeypatch.setattr(bot, 'CONFFILE', tmpfile.name)
        json.dump(content, tmpfile.file)
        tmpfile.file.flush()
        data = parse_config()
    assert data == content

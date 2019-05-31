import sys
import json
import time
import sqlite3
from tempfile import NamedTemporaryFile
from threading import Thread

import pytest
import telegram
import lyricfetch
from lyricfetch import Song

sys.path.append('.')
from bot import next_song
from bot import get_album_tracks
from bot import other
from bot import get_song_from_string
from bot import get_lyrics
from bot import unknown
from bot import parse_config
from bot import send_message
from conftest import Nothing
from bot import Database


import bot as bot_module

@pytest.fixture
def bot(monkeypatch, database, sp_client):
    monkeypatch.setattr(bot_module, 'DB', database)
    monkeypatch.setattr(bot_module, 'SP', sp_client)
    yield bot_module


class FakeBot:
    def __init__(self):
        self.msg_log = []
        self.call_log = []

    def send_message(self, *args, **kwargs):
        text = kwargs['text']
        if text == 'raise error':
            raise_telegram_error()
        self.msg_log.append(text)

    def log_call(self, *args, **kwargs):
        self.call_log.append((*args, *kwargs.values()))

    def send_chat_action(self, *args, **kwargs):
        self.log_call(*args, **kwargs)


@pytest.fixture
def bot_arg():
    bot_arg = FakeBot()
    return bot_arg


@pytest.fixture
def update():
    update_arg = Nothing()
    update_arg.message = Nothing()
    update_arg.message.chat_id = 'chat_id'
    update_arg.message.text = 'message text'
    return update_arg


def test_start(monkeypatch, bot, bot_arg, update):
    with NamedTemporaryFile(mode='w+') as tmpfile:
        monkeypatch.setattr(bot, 'HELPFILE', tmpfile.name)
        tmpfile.file.write('hello world')
        tmpfile.file.flush()
        bot.start(bot_arg, update)
    assert bot_arg.msg_log[0] == 'hello world'


fake_log = Nothing(
    song=Song(
        artist='slugdge', title='putrid fairytale', album='esoteric malacology'
    ),
    source=lyricfetch.sources[0],
)

fake_res = dict(
    artist=fake_log.song.artist,
    title=fake_log.song.title,
    album=fake_log.song.album,
    source=fake_log.source.__name__,
)


def raise_sqlite_error(*args, **kwargs):
    raise sqlite3.Error()


def raise_telegram_error(*args, **kwargs):
    raise telegram.TelegramError('mock telegram error')


def test_album_tracks_lastfm(monkeypatch, bot):
    """
    Test the get_album_tracks_lastfm function.
    """
    song = Song('Sabaton', '1 6 4 8')
    with monkeypatch.context() as mkp:
        # An empty list should be returned if we can't find the album's name
        mkp.setattr(song, 'fetch_album_name', lambda: None)
        assert bot.get_album_tracks_lastfm(song) == []

    tracks = bot.get_album_tracks_lastfm(song)
    tracks = '\n'.join(tracks)
    assert 'carolus rex' in tracks
    assert 'en livstid i krig' in tracks


def test_album_tracks_lastfm_notfound(bot, monkeypatch):
    """
    Test get_album_tracks_lastfm when the album isn't found in the lastfm
    database.
    """

    def get_lastfm(*args, **kwargs):
        return []

    song = Song('Horrendous', 'The Idolater', album='Idol')
    monkeypatch.setattr(bot, 'get_lastfm', get_lastfm)
    assert bot.get_album_tracks_lastfm(song) == []


def test_album_tracks(bot, monkeypatch):
    """
    Check that bot.get_album_tracks() searches spotify first, and uses lastfm
    as a fallback.
    """
    song = Song('wintersun', 'beyond the dark sun')
    monkeypatch.setattr(bot.SP, 'get_album_tracks', lambda x: [])
    monkeypatch.setattr(bot, 'get_album_tracks_lastfm', lambda x: ['lastfm'])
    assert bot.get_album_tracks(song)[0] == 'lastfm'

    monkeypatch.setattr(bot.SP, 'get_album_tracks', lambda x: ['spotify'])
    assert get_album_tracks(song)[0] == 'spotify'


def test_next_song_no_last(bot):
    """
    Test get the next song when there is no "last result".
    """
    assert bot._get_next_song(1) == "You haven't searched for anything yet"


@pytest.mark.parametrize(
    'tracks, expect',
    [
        (None, "Could not find the album this song belongs to"),
        ([], "Could not find the album this song belongs to"),
        (['something'], "Could not find the album this song belongs to"),
        ([fake_res['title']], "That was the last song on the album"),
    ],
    ids=[
        'None return',
        'Empty track list',
        'Missing last result',
        'Last song on the album',
    ],
)
def test_next_song_no_album(monkeypatch, tracks, expect, bot):
    """
    Test the _get_next_song function when we can't find the name of the next
    song.
    """
    bot.log_result('chat_id', fake_log)
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    assert bot._get_next_song('chat_id') == expect


def test_next_song_dberror(bot):
    """
    Test get the last song when a database error is thrown.
    """
    bot.DB.get_last_res = raise_sqlite_error
    assert bot._get_next_song(1).startswith('There was an error while')


def test_next_song_existing(bot, monkeypatch):
    """
    Test the _get_next_song existing when everything goes smoothly and the next
    song is found.
    """
    tracks = [fake_res['title'], 'war squids']
    song_next = Song(fake_res['artist'], 'war squids', fake_res['album'])
    bot.log_result('chat_id', fake_log)
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    monkeypatch.setattr(bot, 'get_lyrics', lambda s, c: f'Searching for {s}')

    assert bot._get_next_song('chat_id') == f'Searching for {song_next}'


def test_next_song(monkeypatch, bot, bot_arg, update):
    """
    Test the next_song function, in a similar manner to _get_next_song.
    """
    tracks = [fake_res['title'], 'crop killer']
    song_next = Song(fake_res['artist'], 'crop killer', fake_res['album'])
    bot.log_result('chat_id', fake_log)
    monkeypatch.setattr(bot, 'get_album_tracks', lambda x: tracks)
    monkeypatch.setattr(bot, 'get_lyrics', lambda s, c: f'Searching for {s}')

    next_song(bot_arg, update)
    assert bot_arg.msg_log[0] == f'Searching for {song_next}'


def test_other_no_lastres(bot, bot_arg, update):
    """
    Test the 'other' function when there is no last result.
    """
    other(bot_arg, update)

    expect = "You haven't searched for anything yet"
    assert bot_arg.msg_log[0] == expect


def test_other_dberror(monkeypatch, bot, bot_arg, update):
    """
    Test the 'other' function when a database error is thrown.
    """
    monkeypatch.setattr(bot.DB, 'get_last_res', raise_sqlite_error)
    other(bot_arg, update)

    expect = "There was an error"
    assert bot_arg.msg_log[0].startswith(expect)


def test_other_no_sources(monkeypatch, bot, bot_arg, update):
    """
    Test the 'other' function when there are no sources left to search.
    """
    monkeypatch.setattr(fake_log, 'source', lyricfetch.sources[-1])
    bot.log_result('chat_id', fake_log)

    other(bot_arg, update)
    assert 'No other sources' in bot_arg.msg_log[0]


def test_other(monkeypatch, bot, bot_arg, update):
    """
    Test the 'other' function.
    """

    def fake_get_lyrics(*args):
        return str(args)

    bot.log_result('chat_id', fake_log)
    monkeypatch.setattr(bot, 'get_lyrics', fake_get_lyrics)

    other(bot_arg, update)
    msg = bot_arg.msg_log[0]
    assert repr(fake_log.song) in msg
    assert fake_log.source.__name__ not in msg


def test_get_song_from_string():
    string = 'carcass - mount of execution'
    song = Song('carcass', 'mount of execution')
    assert get_song_from_string(string, None) == song
    assert get_song_from_string(song, None) == song


def test_get_song_from_string_lastres(bot):
    """
    Test get a song from string when there is no hyphen and we must get the
    last result from the database.
    """
    chat_id = 'chat_id'
    assert bot.get_song_from_string('', chat_id) is None

    song = Song(fake_res['artist'], 'the spectral burrows')
    bot.log_result(chat_id, fake_log)
    assert get_song_from_string('the spectral burrows', chat_id) == song


def test_log_result(monkeypatch, bot, caplog):
    buffer = []

    def fake_log_result(*args):
        buffer.append(args)

    monkeypatch.setattr(bot.DB, 'log_result', fake_log_result)
    args = (1, 'result')
    bot.log_result(*args)
    assert buffer == [args]

    monkeypatch.setattr(bot.DB, 'log_result', raise_sqlite_error)
    bot.log_result(*args)
    records = list(caplog.records)
    assert len(records) == 1
    assert 'sqlite3.error' in caplog.text.lower()


def test_get_lyrics_invalid_format(bot):
    """
    Call get_lyrics with an invalid song string.
    """
    assert get_lyrics('asdf', 1) == 'Invalid format!'


def test_get_lyrics_notfound(monkeypatch, bot):
    """
    Test get_lyrics when no lyrics are found.
    """

    def assert_not_found(msg):
        msg = get_lyrics(song, 1)
        msg = msg.lower()
        assert song.artist in msg
        assert song.title in msg
        assert 'could not be found' in msg

    song = Song('nothing more', 'christ copyright')
    result = Nothing()
    result.source = 'hello'
    monkeypatch.setattr(bot, 'get_lyrics_threaded', lambda a, b: result)

    msg = bot.get_lyrics(song, 1)
    assert_not_found(msg)

    result.source = None
    song.lyrics = 'hello'
    msg = bot.get_lyrics(song, 1)
    assert_not_found(msg)


def test_get_lyrics_error(monkeypatch, bot, caplog):
    monkeypatch.setattr(bot, 'get_song_from_string', raise_sqlite_error)
    msg = bot.get_lyrics('', 1)
    assert msg == 'Unknown error'
    assert len(caplog.records) == 1
    assert 'sqlite3.Error' in caplog.text


def test_get_lyrics_found(monkeypatch, bot):
    song = Song('obituary', 'ten thousand ways to die', lyrics='lyrics')

    monkeypatch.setattr(bot, 'get_lyrics_threaded', lambda a, b: fake_log)
    msg = bot.get_lyrics(song, 1).lower()
    assert fake_res['source'].lower() in msg
    assert song.title in msg
    assert song.artist in msg
    assert song.lyrics in msg
    assert bot.DB.get_last_res(1)


def test_find(monkeypatch, bot, bot_arg, update):
    """
    Test the 'find' function.
    """

    def fake_getlyrics(*args, **kwargs):
        bot_arg.log_call(*args, **kwargs)
        return 'here are your lyrics'

    monkeypatch.setattr(bot, 'get_lyrics', fake_getlyrics)

    bot.find(bot_arg, update)
    assert bot_arg.call_log[0] == ('chat_id', telegram.ChatAction.TYPING)
    assert bot_arg.call_log[1] == ('message text', 'chat_id')
    assert bot_arg.msg_log[0] == 'here are your lyrics'


def test_unknown(bot_arg, update):
    """
    Test the 'unknown' function.
    """
    unknown(bot_arg, update)
    assert "didn't understand that" in bot_arg.msg_log[0]


def test_now(bot, monkeypatch, bot_arg, update):
    """
    Test the 'now' function.
    """
    print('all', bot.DB._execute('select * from sp_tokens'))
    chat_id = update.message.chat_id
    token = 'token'

    def save_token():
        time.sleep(1)
        database = Database()
        database.config(bot.DB._filename)
        database.save_sp_token(token, chat_id)

    access_token = {
        'access_token': token + '2',
        'expires_at': (time.time() + 100),
        'refresh_token': token + '_refresh',
    }
    monkeypatch.setattr(bot.SP, 'get_access_token', lambda x: access_token)

    Thread(target=save_token).start()
    monkeypatch.setattr(bot.SP, 'currently_playing', lambda x: None)
    bot.now(bot_arg, update)
    assert bot_arg.msg_log[0] == 'Please open this link to log in to Spotify'
    assert bot_arg.msg_log[1] == bot.SP.get_auth_url(chat_id)
    assert bot_arg.msg_log[2] == 'There is nothing playing!'

    song = Song('Orphaned land', 'ornaments of gold')
    lyrics = 'The light of the dark is the morning of the dawn'
    monkeypatch.setattr(bot.SP, 'currently_playing', lambda x: song)
    monkeypatch.setattr(bot, 'get_lyrics', lambda x, y: lyrics)
    bot.now(bot_arg, update)
    assert bot_arg.msg_log[3] == lyrics


@pytest.mark.parametrize(
    'content',
    [{}, {'token': 'token'}, {'db_filename': 'filename'}],
    ids=['empty', 'no db filename', 'no token'],
)
def test_parse_config_missing_keys(content, bot, monkeypatch):
    with NamedTemporaryFile(mode='w') as tmpfile:
        monkeypatch.setattr(bot, 'CONFFILE', tmpfile.name)
        json.dump(content, tmpfile.file)
        tmpfile.file.flush()
        with pytest.raises(KeyError):
            parse_config()


def test_parse_config(monkeypatch, bot):
    content = {'token': 'token', 'db_filename': 'filename'}
    with NamedTemporaryFile(mode='w') as tmpfile:
        monkeypatch.setattr(bot, 'CONFFILE', tmpfile.name)
        json.dump(content, tmpfile.file)
        tmpfile.file.flush()
        data = parse_config()
    assert data == content


def test_send_message_error(bot_arg, monkeypatch, caplog):
    msg = 'raise error'
    send_message(msg, bot_arg, 1)
    assert bot_arg.msg_log[0] == 'Unknown error'
    assert len(caplog.records) == 1
    assert 'mock telegram error' in caplog.text


def test_send_message_fitting(bot_arg):
    """
    Test sending a message that is shorter than the maximum allowed by
    telegram.
    """
    msg = 'hello world'
    send_message(msg, bot_arg, 1)
    assert bot_arg.msg_log[0] == msg


def test_send_message_not_fitting(bot_arg, monkeypatch):
    """
    Test sending a message that is longer than the maximum allowed by
    telegram.
    """
    monkeypatch.setattr(telegram.constants, 'MAX_MESSAGE_LENGTH', 5)
    msg = 'helloworld'
    send_message(msg, bot_arg, 1)
    assert bot_arg.msg_log[0] == 'hello'
    assert bot_arg.msg_log[1] == 'world'


def test_send_message_not_fitting_parragraphs(bot_arg, monkeypatch):
    """
    Test sending a message that is longer than the maximum allowed by
    telegram, and check that the returned messages are split by parragraph.
    """
    monkeypatch.setattr(telegram.constants, 'MAX_MESSAGE_LENGTH', 20)
    msg = 'hello\n\nworld, this is a message'
    send_message(msg, bot_arg, 1)
    assert bot_arg.msg_log[0] == 'hello'
    assert bot_arg.msg_log[1].strip() == 'world, this is a message'

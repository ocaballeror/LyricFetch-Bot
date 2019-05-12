import sys
import time

import pytest
import sqlite3
from lyricfetch import Song

sys.path.append('.')
from db import DB


def test_config(database):
    assert database._connection
    table_query = 'select name from sqlite_master where type="table"'
    assert database._execute(table_query) == {'name': 'log'}


def test_execute(database):
    values = ('a', 'b', 'c')
    insert = 'insert into log (chat_id, artist, title) values (?, ?, ?)'
    ret = database._execute(insert, values)
    assert ret is None

    select = """
    select chat_id, artist, title from log
    where chat_id=? and artist=? and title=?
    """
    ret = database._execute(select, values)
    assert tuple(ret.values()) == values


def test_execute_connection_closed(database):
    """
    Test that the database will try to connect again if there are any errors.
    """
    values = ('a', 'b', 'c')
    insert = 'insert into log (chat_id, artist, title) values (?, ?, ?)'
    database._execute(insert, values)

    database.close()

    select = """
    select chat_id, artist, title from log
    where chat_id=? and artist=? and title=?
    """
    ret = database._execute(select, values)
    assert tuple(ret.values()) == values


def test_execute_connection_retries(database):
    """
    Test that the database will try to connect again if there are any errors.
    """
    select = 'select * from log'
    database._retries = 0
    with pytest.raises(sqlite3.Error):
        database._execute(select)

    database._retries = 1
    database.close()
    with pytest.raises(sqlite3.Error):
        database._execute(select)


class Empty:
    pass


def test_log_result(database):
    chat_id = 'chat_id'
    song = Song('lucis absentia', 'gehenna gate')
    source = Empty()
    source.__name__ = 'source'
    result = Empty()
    result.song = song
    result.source = source

    database.log_result(chat_id, result)
    query = database._execute('select chat_id, source, artist, title from log')
    assert query == dict(
        chat_id=chat_id, source='source', artist=song.artist, title=song.title
    )

    source.__name__ = 'new source'
    database.log_result(chat_id, result)
    query = database._execute('select chat_id, source, artist, title from log')
    assert query == dict(
        chat_id=chat_id,
        source='new source',
        artist=song.artist,
        title=song.title,
    )


def test_get_last_res(database):
    chat_id = 'id'
    artist = 'testament'
    title = 'a day of reckoning'
    source = 'source'
    album = 'the new order'
    now = int(time.time())
    insert = """
    insert into log
        (chat_id, artist, title, source, album, date)
        values (?, ?, ?, ?, ?, ?)
    """

    # Insert a record and retrieve it
    database._execute(insert, (chat_id, artist, title, source, album, now))
    database._connection.commit()
    assert database.get_last_res(chat_id) == dict(
        source=source, artist=artist, title=title, album=album
    )

    # Update the chat id with a newer entry
    artist = 'new artist'
    now += 1
    database._execute(insert, (chat_id, artist, title, source, album, now))
    assert database.get_last_res(chat_id) == dict(
        source=source, artist=artist, title=title, album=album
    )

    # Updating with an older entry should return the new one again
    artist = 'old artist'
    now -= 2
    database._execute(insert, (chat_id, artist, title, source, album, now))
    assert database.get_last_res(chat_id) == dict(
        source=source, artist='new artist', title=title, album=album
    )


@pytest.mark.parametrize('param, expect', [(1, '1'), ("'hello'", "''hello''")])
def test_sanitize(database, param, expect):
    assert database.sanitize(param) == expect

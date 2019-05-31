import sys
import time

sys.path.append('.')
import bot


SAMPLE_TOKEN = dict(
    token='1234567890abcdef',
    refresh='fedcba0987654321',
    expires=int(time.time()),
)


def test_get_sp_token_db(database):
    """
    Test getting a saved token from the database.
    """
    chat_id = 'chat-id'
    assert database.get_sp_token(chat_id) is None

    database._execute(
        """
        INSERT INTO sp_tokens (token, refresh, expires, chat_id)
        VALUES (?, ?, ?, ?)
        """,
        (*SAMPLE_TOKEN.values(), chat_id),
    )

    result = database.get_sp_token(chat_id)
    assert result == SAMPLE_TOKEN


def test_save_sp_token_db(database):
    """
    Test saving and updating a token in the database.
    """
    chat_id = 'chat-id'
    token = SAMPLE_TOKEN.copy()
    token['chat_id'] = chat_id
    cur = database._connection.cursor()
    cur.execute("select * from sp_tokens")
    assert cur.fetchall() == []

    database.save_sp_token(**token)
    cur.execute("select * from sp_tokens")
    assert cur.fetchall() == [token]

    token['token'] *= 2
    database.save_sp_token(**token)
    cur.execute("select * from sp_tokens")
    # Use fetchall to verify there's still only one token in the db
    assert cur.fetchall() == [token]

    old_token = token.copy()
    token['chat_id'] *= 2
    database.save_sp_token(**token)
    cur.execute("select * from sp_tokens")
    assert cur.fetchall() == [old_token, token]


def test_get_sp_token_missing(monkeypatch):
    """
    Test the get_sp_token function in bot.py when there is nothing saved in the
    database.
    """
    chat_id = '1'
    monkeypatch.setattr(bot.DB, 'get_sp_token', lambda x: None)
    assert bot.get_sp_token(chat_id) is None


def test_get_sp_token_bot(monkeypatch, database):
    """
    Test the get_sp_token function in bot.py when there is a token stored in
    the database, and it has not expired yet.
    """
    chat_id = '1'
    token = SAMPLE_TOKEN.copy()
    token['chat_id'] = chat_id
    token['expires'] = time.time() + 1000

    monkeypatch.setattr(bot, 'DB', database)
    monkeypatch.setattr(bot.DB, 'get_sp_token', lambda x: token)
    assert bot.get_sp_token(chat_id) == token['token']


def test_get_sp_token_expired(monkeypatch, database):
    """
    Test the get_sp_token function in bot.py when the retrieved token has
    expired.
    """
    chat_id = '1'
    token = SAMPLE_TOKEN.copy()
    token['chat_id'] = chat_id
    token['expires'] = time.time() - 1

    refreshed = {
        'access_token': token['token'] + '2',
        'refresh_token': token['refresh'] + '2',
        'expires_at': (time.time() + 1),
    }
    monkeypatch.setattr(bot.SP, 'refresh_access_token', lambda x: refreshed)

    monkeypatch.setattr(bot, 'DB', database)
    with monkeypatch.context() as mkp:
        mkp.setattr(bot.DB, 'get_sp_token', lambda x: token)
        got = bot.get_sp_token(chat_id)

    expect = {
        'token': refreshed['access_token'],
        'refresh': refreshed['refresh_token'],
        'expires': refreshed['expires_at'],
    }
    assert database.get_sp_token(chat_id) == expect
    assert got == refreshed['access_token']

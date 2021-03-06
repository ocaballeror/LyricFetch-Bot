"""
Database management and utilities
"""
import time
import re
import sqlite3

from logger import logger


def row_factory(c, r):
    "Row factory to make our db connection return dictionaries."
    return dict(zip([col[0] for col in c.description], r))


class DB:
    """
    Main database class. Stores an active connection and contains a series of
    utilities to insert/query data from the database.
    """

    def __init__(self, filename='lyricfetch.db', retries=5):
        self._connection = None
        self._retries = retries
        self._filename = filename
        self._closed = True

    def config(self, filename=None):
        """
        Initial database configuration.
        """
        if filename:
            self._filename = filename
        self._connection = sqlite3.connect(self._filename)
        self._connection.row_factory = row_factory
        cursor = self._connection.cursor()
        with open('schema.sql') as schema:
            cursor.executescript(schema.read())
        self._connection.commit()
        self._closed = False

    def _execute(self, query, params=''):
        res = None
        error_msg = ''
        select = query.lstrip().partition(' ')[0].lower() == 'select'
        params = list(map(self.sanitize, params))
        logger.debug(query)
        logger.debug(params)
        for _ in range(self._retries):
            try:
                cur = self._connection.cursor()
                cur.execute(query, params)
                if select:
                    res = cur.fetchone()
                else:
                    self._connection.commit()
                break
            except sqlite3.Error as error:
                logger.exception(error)
                error_msg = str(error)
                try:
                    self._connection.close()
                except sqlite3.Error:
                    pass
                time.sleep(1)

                # Intentionally not catching exceptions here
                self._connection = sqlite3.connect(self._filename)
                self._connection.row_factory = row_factory
        else:
            raise sqlite3.Error(error_msg)

        return res

    def log_result(self, chat_id, result):
        """
        Insert a search result into the database.
        """
        title = result.song.title
        artist = result.song.artist
        album = result.song.album or 'Unknown'
        res = self._execute(
            'SELECT * FROM log WHERE chat_id=? AND artist=? AND title=?',
            [chat_id, artist, title],
        )

        if res:
            logger.debug('Updating')
            update = 'UPDATE log SET source=?, date=strftime("%s", "now")'
            values = [result.source.__name__, chat_id, artist, title]
            if res['album'] == 'Unknown':
                update += ', album=?'
                values.insert(1, album)
            update += ' WHERE chat_id=? AND artist=? AND title=?'
            self._execute(update, values)
        else:
            logger.debug('Inserting')
            self._execute(
                'INSERT INTO log (chat_id,source,artist,title,album,date) '
                'VALUES (?, ?, ?, ?, ?, strftime("%s", "now"))',
                [chat_id, result.source.__name__, artist, title, album],
            )

        self._connection.commit()

    def get_last_res(self, chat_id):
        """
        Return the last logged result of a specific chat.
        """
        res = self._execute(
            'SELECT artist,title,source,album FROM log WHERE '
            'chat_id=? AND date=(SELECT MAX(date) FROM log '
            'WHERE chat_id=?)',
            [chat_id, chat_id],
        )
        if not res:
            return res

        res = {
            k: v.replace("''", "'")
            for k, v in res.items()
            if isinstance(v, str)
        }
        return res

    def get_sp_token(self, chat_id):
        """
        Get the saved token for this chat id.

        Returns None if the chat_id is not in the database.
        """
        select = """
        SELECT token, refresh, expires FROM sp_tokens WHERE chat_id=?
        """
        res = self._execute(select, [chat_id])
        return res

    def save_sp_token(self, token, chat_id, refresh=None, expires=None):
        """
        Save the token for a chat_id.
        """
        select = "SELECT chat_id FROM sp_tokens WHERE chat_id=?"
        exists = self._execute(select, [chat_id])
        if exists:
            update = """
            UPDATE sp_tokens SET token=?, refresh=?, expires=? WHERE chat_id=?
            """
        else:
            update = """
            INSERT INTO sp_tokens (token, refresh, expires, chat_id)
            VALUES (?, ?, ?, ?)
            """
        self._execute(update, (token, refresh, expires, chat_id))

    @staticmethod
    def sanitize(string):
        """
        Remove special characters from a string to make it suitable for SQL
        queries.
        """
        if string is None:
            return None
        if not isinstance(string, str):
            string = str(string)
        newstr = re.sub("'", "''", string)

        return newstr

    def close(self):
        """
        Close the database connection.
        """
        if self._connection and not self._closed:
            self._connection.commit()
            self._connection.close()
        self._closed = True

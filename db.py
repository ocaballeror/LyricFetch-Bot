"""
Database management and utilities
"""
import time
import re
import sqlite3

from lyricfetch import logger


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
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS log(
                chat_id VARCHAR(9),
                source VARCHAR(64),
                artist VARCHAR(64),
                title VARCHAR (128),
                album VARCHAR (128) default 'unknown',
                date float,
                CONSTRAINT PK_log PRIMARY KEY (chat_id,artist,title)
            )"""
        )
        self._connection.commit()
        self._closed = False

    def _execute(self, query, params=''):
        res = None
        error_msg = ''
        select = query.lstrip().partition(' ')[0].lower() == 'select'
        params = list(map(self.sanitize, params))
        for _ in range(self._retries):
            try:
                cur = self._connection.cursor()
                cur.execute(query, params)
                if select:
                    res = cur.fetchone()
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
            'SELECT * FROM log WHERE '
            'chat_id=? AND artist=? AND title=?',
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

    @staticmethod
    def sanitize(string):
        """
        Remove special characters from a string to make it suitable for SQL
        queries.
        """
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

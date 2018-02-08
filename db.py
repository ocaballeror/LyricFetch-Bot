"""
Database management and utilities
"""
import time
import re
import psycopg2 as pg

from lyricfetch.lyrics import logger


class DB:
    """
    Main database class. Stores an active connection and contains a series of
    utilities to insert/query data from the database.
    """
    def __init__(self, retries=5):
        self._connection = None
        self._retries = retries
        self._dbname = self._dbuser = self._dbpw = self._dbhost = ''

    def config(self, dbname, dbuser, dbpassword, dbhost):
        """
        Initial database configuration.
        """
        self._dbname, self._dbuser, self._dbpw, self._dbhost =\
                dbname, dbuser, dbpassword, dbhost
        self._connection = pg.connect(database=dbname, user=dbuser,
                                      password=dbpassword, host=dbhost)
        self._execute('''\
            CREATE TABLE IF NOT EXISTS log(
                chat_id VARCHAR(9),
                source VARCHAR(64),
                artist VARCHAR(64),
                title VARCHAR (128),
                date float,
                CONSTRAINT PK_log PRIMARY KEY (chat_id,artist,title)
            )''')

    def _execute(self, query, params=''):
        res = None
        error_msg = ''
        select = query.lstrip().partition(' ')[0].lower() == "select"
        params = list(map(self.sanitize, params))
        for _ in range(self._retries):
            try:
                cur = self._connection.cursor()
                cur.execute(query, params)
                if select:
                    res = cur.fetchone()
                break
            except pg.OperationalError as error:
                logger.exception(error)
                error_msg = str(error)
                self._connection.close()
                time.sleep(1)

                # Intentionally not catching exceptions here
                self._connection = pg.connect(database=self._dbname,
                        user=self._dbuser, password=self._dbpw,
                        host=self._dbhost)
        else:
            raise pg.Error(error_msg)

        if res:
            return res
        return None


    def log_result(self, chat_id, result):
        """
        Insert a search result into the database.
        """
        title = result.song.title
        artist = result.song.artist
        res = self._execute("SELECT artist,title,source FROM log WHERE "
                            "chat_id=%s AND artist=%s AND title=%s",
                            [chat_id, artist, title])

        if res:
            logger.debug('Updating')
            self._execute("UPDATE log SET source=%s, date=extract(epoch from "
                          "now()) WHERE chat_id=%s AND artist=%s AND title=%s",
                          [result.source.__name__, chat_id, artist, title])
        else:
            logger.debug('Inserting')
            self._execute("INSERT INTO log (chat_id,source,artist,title,date) "
                          "VALUES (%s, %s, %s, %s, EXTRACT(EPOCH FROM NOW()))",
                          [chat_id, result.source.__name__, artist, title])

        self._connection.commit()

    def get_result(self, song):
        """
        Return the last search result for a specific song from the database.
        """
        res = self._execute("SELECT source FROM log WHERE artist=%s AND "
                            " title=%s", [song.artist, song.title])
        return res

    def get_last_res(self, chat_id):
        """
        Return the last logged result of a specific chat.
        """
        res = self._execute("SELECT artist,title,source FROM log WHERE "
                            "chat_id=%s AND date=(SELECT MAX(date) FROM log "
                            "WHERE chat_id=%s)", [chat_id, chat_id])

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
        if self._connection and self._connection == 0:
            self._connection.commit()
            self._connection.close()

"""
Database management and utilities
"""
import re
import psycopg2 as pg

from lyricfetch.lyrics import logger


class DB:
    """
    Main database class. Stores an active connection and contains a series of
    utilities to insert/query data from the database.
    """
    def __init__(self):
        self.connection = None

    def config(self, dbname, dbuser, dbpassword, dbhost):
        """
        Initial database configuration.
        """
        self.connection = pg.connect(database=dbname, user=dbuser,
                                     password=dbpassword, host=dbhost)
        cur = self.connection.cursor()
        cur.execute('''\
            CREATE TABLE IF NOT EXISTS log(
                chat_id VARCHAR(9),
                source VARCHAR(64),
                artist VARCHAR(64),
                title VARCHAR (128),
                date float,
                CONSTRAINT PK_log PRIMARY KEY (chat_id,artist,title)
            );''')

        self.connection.commit()

    def log_result(self, chat_id, result):
        """
        Insert a search result into the database.
        """
        chat_id = self.sanitize(chat_id)
        title = self.sanitize(result.song.title)
        artist = self.sanitize(result.song.artist)
        cur = self.connection.cursor()
        cur.execute("SELECT artist,title,source FROM log WHERE "
                    "chat_id=%s AND artist=%s AND title=%s",
                    [chat_id, artist, title])
        res = cur.fetchone()

        if res:
            logger.debug('Updating')
            cur.execute("UPDATE log SET source=%s, date=extract(epoch from "
                        "now()) WHERE chat_id=%s AND artist=%s AND title=%s",
                        [result.source.__name__, chat_id, artist, title])
        else:
            logger.debug('Inserting')
            cur.execute("INSERT INTO log (chat_id,source,artist,title,date) "
                        "VALUES (%s, %s, %s, %s, EXTRACT(EPOCH FROM NOW()))",
                        [chat_id, result.source.__name__, artist, title])

        self.connection.commit()

    def get_result(self, song):
        """
        Return the last search result for a specific song from the database.
        """
        title = self.sanitize(song.title)
        artist = self.sanitize(song.artist)

        cur = self.connection.cursor()
        cur.execute("SELECT source FROM log WHERE artist=%s AND title=%s",
                    [artist, title])
        res = cur.fetchone()
        if res:
            return res[0]
        return None

    def get_last_res(self, chat_id):
        """
        Return the last logged result of a specific chat.
        """
        chat_id = self.sanitize(chat_id)

        cur = self.connection.cursor()
        cur.execute("SELECT artist,title,source FROM log WHERE chat_id=%s AND "
                    "date=(SELECT MAX(date) FROM log WHERE chat_id=%s)",
                    [chat_id, chat_id])
        res = cur.fetchone()
        print(res)
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
        if self.connection:
            self.connection.commit()
            self.connection.close()

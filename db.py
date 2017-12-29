import psycopg2 as pg
import re
from lyricfetch.lyrics import *

class DB:
    def __init__(self, dbname, dbuser, dbpassword, dbhost):
        self.connection = None
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
        title = self.sanitize(result.song.title)
        artist = self.sanitize(result.song.artist)
        cur = self.connection.cursor()
        cur.execute(f"""SELECT artist,title,source FROM log WHERE
                chat_id='{chat_id}' and artist='{artist}'
                and title='{title}';""")
        res = cur.fetchone()

        if res:
            logger.debug('Updating')
            cur.execute(f"""UPDATE log SET
                    source='{result.source.__name__}', date=extract(epoch from now())
                    WHERE chat_id='{chat_id}' and artist='{artist}'
                    and title='{title}';""")
        else:
            logger.debug('Inserting')
            cur.execute(f"""INSERT INTO log (chat_id,source,artist,title,date)
                    values ('{chat_id}', '{result.source.__name__}',
                    '{artist}', '{title}',
                    extract(epoch from now()));""")

        self.connection.commit()

    def get_result(self, song):
        title = self.sanitize(song.title)
        artist = self.sanitize(song.artist)

        cur = self.connection.cursor()
        cur.execute(f"""SELECT source FROM log WHERE
                artist='{artist}' and title='{title}';""")
        res = cur.fetchone()
        if res:
            return res[0]
        else:
            return None

    def get_last_res(self, chat_id):
        """Return the last logged result of a specific chat"""
        cur = self.connection.cursor()
        cur.execute(f"""SELECT artist,title,source FROM log WHERE
                chat_id='{chat_id}' AND date=(SELECT MAX(date) FROM log WHERE
                chat_id='{chat_id}');""")
        res = cur.fetchone()
        print(res)
        return res

    @staticmethod
    def sanitize(string):
        newstr = re.sub("'", "''", string)

        return newstr

    def close(self):
        if self.connection:
            self.connection.commit()
            self.connection.close()

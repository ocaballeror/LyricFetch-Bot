import psycopg2 as pg
import sys
from lyricfetch.lyrics import *

class DB:
    def __init__(self, dbname, dbuser, dbpassword, dbhost):
        self.connection = None
        try:
            self.connection = pg.connect(database=dbname, user=dbuser,
                    password=dbpassword, host=dbhost)
            cur = self.connection.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS log(
        chat_id VARCHAR(9),
        source VARCHAR(64),
        artist VARCHAR(64),
        title VARCHAR (128),
        date float,
        CONSTRAINT PK_log PRIMARY KEY (chat_id,artist,title)
        );''')

            self.connection.commit()

        except pg.DatabaseError as e:
            raise e

    def close(self):
        if self.connection:
            self.connection.commit()
            self.connection.close()

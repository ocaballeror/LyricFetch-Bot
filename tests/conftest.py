import sys
import sqlite3
from tempfile import NamedTemporaryFile

import pytest

sys.path.append('.')
from db import DB


@pytest.fixture(scope='function')
def database():
    with NamedTemporaryFile() as tmpfile:
        db = DB(filename=tmpfile.name)
        db.config()
        yield db
        try:
            db.close()
        except sqlite3.Error:
            pass

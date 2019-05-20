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


class Infinite:
    """
    Dummy class that you can infinitely dot-walk.
    """

    def __getattr__(self, attr):
        return Infinite()


class Nothing:
    """
    Empty class to add arbitrary attributes to.
    """


class FakeDB:
    def __init__(self, last_res=None):
        self._last_res = last_res

    def get_last_res(self, _):
        return self._last_res

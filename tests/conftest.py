import sys
import sqlite3
import os
import json
from tempfile import NamedTemporaryFile

import pytest

sys.path.append('.')
from db import DB
from bot import CONFFILE
from spotify import Spotify


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


@pytest.fixture(scope='session')
def sp_client():
    if not os.path.isfile(CONFFILE):
        pytest.skip('No spotify config found')

    with open(CONFFILE) as f:
        config = json.load(f)

    client, secret = (
        config.get("SPOTIFY_CLIENT_ID", ''),
        config.get("SPOTIFY_CLIENT_SECRET", ''),
    )
    if not client or not secret:
        pytest.skip('Spotify keys not found in config')
    sp = Spotify()
    sp.discography_cache.clear()
    sp.configure(client, secret)
    return sp


class Nothing:
    """
    Empty class to add arbitrary attributes to.
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

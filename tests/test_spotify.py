import sys
import os
import json
import pickle
from datetime import date

import pytest

sys.path.append('.')
from bot import CONFFILE
import spotify
from spotify import _set_release_date
from spotify import Spotify


def test_set_release_date():
    expect = date(2019, 1, 1)

    album = {'release_date': '2019', 'release_date_precision': 'year'}
    _set_release_date(album)
    assert album['release_date'] == expect

    album = {'release_date': '2019-01', 'release_date_precision': 'month'}
    _set_release_date(album)
    assert album['release_date'] == expect

    album = {'release_date': '2019-01-01', 'release_date_precision': 'day'}
    _set_release_date(album)
    assert album['release_date'] == expect


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


def test_spotify_init(sp_client):
    """
    Test simple spotify object initialization and configuration.
    """
    assert sp_client.sp


def test_spotify_save_cache(sp_client, tmp_path, monkeypatch):
    """
    Test saving spotify's cache.
    """
    monkeypatch.setattr(spotify, 'CACHE_DIR', tmp_path)
    cache = {'hello': 'world'}
    sp_client.discography_cache = cache
    sp_client.save_cache()

    dst = tmp_path / '.cache-spotify'
    assert dst.is_file()
    with open(dst, 'rb') as f:
        load = pickle.load(f)
        assert load == cache


def test_spotify_load_cache(sp_client, tmp_path, monkeypatch):
    """
    Test loading spotify's cache.
    """
    monkeypatch.setattr(spotify, 'CACHE_DIR', tmp_path)
    cache = {'hello': 'world'}
    dst = tmp_path / '.cache-spotify'
    with open(dst, 'wb') as f:
        pickle.dump(cache, f)

    sp_client.load_cache()
    assert sp_client.discography_cache == cache

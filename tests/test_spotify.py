import sys
import pickle
from datetime import date

import requests
import spotipy
from lyricfetch import Song

sys.path.append('.')
import spotify

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


def test_spotify_get_discography(sp_client):
    """
    Get an artist's discography and assert that everything is in the right
    place.
    """
    discog = sp_client.get_discography('paara', 'hurmeen hauta')
    albums = list(discog.values())
    assert discog
    assert len(discog) >= 2
    for key, klass in [('id', str), ('release_date', date), ('tracks', list)]:
        assert all(isinstance(e[key], klass) for e in albums)

    dates = [e['release_date'] for e in albums]
    assert list(sorted(dates)) == dates

    assert all(e['tracks'] for e in albums)


def test_spotify_get_discography_values(sp_client):
    """
    Get an artist's discography and check that there are no live albums, and no
    remaster/remix/re-anything.
    """
    discog = sp_client.get_discography('queen', 'another one bites the dust')
    albums = list(map(str.lower, discog))
    invalid = ['live at', 'remaster', 'remix', 'deluxe', 'edition', 'version']
    for key in invalid:
        assert not any(key in al for al in albums)


def test_spotify_fetch_discography(sp_client, monkeypatch):
    log = []

    def fake_get_discography(artist, title):
        log.append((artist, title))
        return artist, title

    monkeypatch.setattr(sp_client, 'get_discography', fake_get_discography)
    song = Song('revocation', 'united in helotry')
    sp_client.fetch_discography(song)

    assert sp_client.discography_cache[song.artist] == (
        song.artist,
        song.title,
    )
    assert log == [(song.artist, song.title)]

    sp_client.fetch_discography(song)
    sp_client.fetch_discography(song)
    sp_client.fetch_discography(song)
    assert log == [(song.artist, song.title)]


def test_spotify_fetch_album_nodiscog(sp_client, monkeypatch):
    """
    Test that the fetch album method returns unknown when we can't find the
    discography for the artist.
    """
    monkeypatch.setattr(sp_client, 'fetch_discography', lambda x: {})
    song = Song('Obscura', 'diluvium')
    assert sp_client.fetch_album(song) == 'Unknown'


def test_spotify_fetch_album_notfound(sp_client, monkeypatch):
    """
    Test that the fetch album method returns unknown when we can't find the
    given track in the discography.
    """
    artist, title, album = 'trials', 'blink of an eye', 'this ruined world'
    sp_client.discography_cache = {
        artist: {album: {'tracks': ['beating the system to death']}}
    }
    monkeypatch.setattr(sp_client, 'fetch_discography', lambda x: True)
    song = Song(artist, title)
    assert sp_client.fetch_album(song) == 'Unknown'


def test_spotify_fetch_album_found(sp_client, monkeypatch):
    """
    Test that the fetch album method returns the correct album when the track
    is found in the discography.
    """
    song = Song('children of bodom', 'towards dead end', 'hatebreeder')
    sp_client.discography_cache = {
        song.artist: {song.album: {'tracks': [song.title]}}
    }
    monkeypatch.setattr(sp_client, 'fetch_discography', lambda x: True)
    assert sp_client.fetch_album(song) == song.album


def test_spotify_get_album_tracks_noalbum(sp_client, monkeypatch):
    """
    Test getting the list of album tracks when the given song already has an
    album attribute.
    """
    album = 'marrow'
    song = Song('madder mortem', 'tethered')
    monkeypatch.setattr(sp_client, 'fetch_album', lambda x: album)

    song_list = ['tethered', 'liberator']
    sp_client.discography_cache = {song.artist: {album: {'tracks': song_list}}}
    assert song_list == sp_client.get_album_tracks(song)


def test_spotify_get_album_tracks_album(sp_client, monkeypatch):
    """
    Test getting the list of album tracks when the given song already has an
    album attribute.
    """
    song = Song('arch enemy', 'carry the cross', 'doomsday machine')
    monkeypatch.setattr(sp_client, 'fetch_discography', lambda x: True)

    # No result when discography isn't found
    sp_client.discography_cache = {}
    assert [] == sp_client.get_album_tracks(song)

    # No result when the discography is empty
    sp_client.discography_cache = {'arch enemy': {}}
    assert [] == sp_client.get_album_tracks(song)

    # No result when the album is not in the discography
    sp_client.discography_cache = {
        'arch enemy': {
            'black earth': {'tracks': ['bury me an angel', 'dark insanity']}
        }
    }
    assert [] == sp_client.get_album_tracks(song)

    # Everything is in the right place and the list of tracks is returned
    song_list = ['carry the cross', 'taking back my soul']
    sp_client.discography_cache = {
        song.artist: {song.album: {'tracks': song_list}}
    }
    assert song_list == sp_client.get_album_tracks(song)


def test_spotify_get_auth_url(sp_client):
    """
    Check that the auth url is accessible and contains the chat_id.
    """
    chat_id = '12345-67890'
    url = sp_client.get_auth_url(chat_id)
    assert chat_id in url
    requests.get(url).raise_for_status()


def test_spotify_currently_playing(monkeypatch, sp_client):
    response = {
        'timestamp': 1559294488309,
        'progress_ms': 16268,
        'item': {
            'album': {
                'album_type': 'album',
                'artists': [
                    {
                        'name': 'Rise Against',
                        'type': 'artist',
                        'uri': 'spotify:artist:6Wr3hh341P84m3EI8qdn9O',
                    }
                ],
                'name': 'The Sufferer & The Witness',
            },
            'artists': [
                {
                    'name': 'Rise Against',
                    'type': 'artist',
                    'uri': 'spotify:artist:6Wr3hh341P84m3EI8qdn9O',
                }
            ],
            'duration_ms': 201026,
            'id': '2YJvYVpOF8Z9Yf8QHpOMsz',
            'name': 'Roadside',
            'popularity': 41,
            'type': 'track',
            'uri': 'spotify:track:2YJvYVpOF8Z9Yf8QHpOMsz',
        },
        'currently_playing_type': 'track',
        'actions': {'disallows': {'resuming': True}},
        'is_playing': True,
    }

    class Client(spotipy.Spotify):
        def currently_playing(self):
            return response

    monkeypatch.setattr(spotify.spotipy, 'Spotify', Client)
    expect = Song('Rise Against', 'Roadside', 'The Sufferer & The Witness')
    assert sp_client.currently_playing(token='some token') == expect

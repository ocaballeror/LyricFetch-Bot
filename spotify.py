import pickle
import logging
from pathlib import Path
from datetime import date

import spotipy
from spotipy import oauth2
from spotipy.oauth2 import SpotifyClientCredentials
from lyricfetch import Song

from util import process
from util import chunks
from util import is_value_invalid
from logger import logger


CACHE_DIR = Path('.cache')
replace_filename = {r'[\?\"\'<>\/\\,\-\!]': '', ':': ' ', ' {2,}': ' '}


def _set_release_date(album):
    """
    Take a spotify album object and convert its release_date string into a
    datetime.date object, taking into account the different precisions
    available.
    """
    release = album['release_date']
    if album['release_date_precision'] == 'year':
        release += '-01-01'
    elif album['release_date_precision'] == 'month':
        release += '-01'
    album['release_date'] = date(*(map(int, release.split('-'))))


def credentials(func):
    """
    Assert that the api is configured or raise with an error message.
    """

    def assert_credentials(self, *args, **kwargs):
        assert self.sp, 'Credentials not configured'
        return func(self, *args, **kwargs)

    return assert_credentials


class Spotify:
    def __init__(self):
        self.discography_cache = {}
        self.load_cache()
        self.sp = None

        self.scope = 'user-read-currently-playing'
        self.redirect_uri = 'http://46.101.110.129:7000/auth'
        self.sp_oauth = None

    def configure(self, client_id, client_secret):
        """
        Set up spotify API client with the specified credentials.
        """
        credentials = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        self.sp = spotipy.Spotify(client_credentials_manager=credentials)
        self.sp.cache_path = None
        self.sp_oauth = oauth2.SpotifyOAuth(
            self.sp.client_credentials_manager.client_id,
            self.sp.client_credentials_manager.client_secret,
            self.redirect_uri,
            scope=self.scope,
        )

    def get_auth_url(self, chat_id):
        """
        Get the url that the user must open to authenticate with spotify.
        """
        return self.sp_oauth.get_authorize_url(state=chat_id)

    def get_access_token(self, code):
        """
        Get an authorization token given a code from the redirect url.
        """
        return self.sp_oauth.get_access_token(code)

    def refresh_access_token(self, token):
        return self.sp_oauth.refresh_access_token(token)

    def currently_playing(self, token):
        """
        Get the song that the user to whom this token belongs to is playing
        right now.

        Returns None if they are not playing anything.
        """
        client = spotipy.Spotify(auth=token)
        try:
            song = client.currently_playing()['item']
            title = song['name']
            album = song['album']['name']
            artist = song['artists'][0]['name']
            return Song(artist, title, album)
        except (KeyError, TypeError):
            return None

    def save_cache(self):
        """
        Store the current organization in a cache file.
        """
        logger.info('writing cache')
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_DIR / '.cache-spotify', 'wb') as cache_file:
            pickle.dump(self.discography_cache, cache_file)
        logger.info('wrote cache')

    def load_cache(self):
        """
        Return a list of files that are cached and can be ignored.
        """
        logger.info('reading cache')
        if not (CACHE_DIR / '.cache-spotify').is_file():
            logger.info('cache dir does not exist. quitting')
            return
        with open(CACHE_DIR / '.cache-spotify', 'rb') as cache_file:
            logger.info('actually loading cache from file')
            self.discography_cache.update(pickle.load(cache_file))

    @credentials
    def get_discography(self, artist, song_name):
        """
        Return the list of albums and their track names.

        Invalid albums (as decided by `is_value_invalid()`) are not included.
        Song names are preprocessed using `process()`.

        The result is a dictionary indexed by album name and sorted by release
        date.
        """
        query = self.sp.search(
            f'artist:{artist} track:{song_name}', type='track'
        )
        artist_id = query['tracks']['items'][0]['artists'][0]['id']
        query = self.sp.artist_albums(artist_id, album_type='album')
        artist_albums = {}
        while query:
            for album in query['items']:
                name = process(album['name'], key='album')
                name = name.lower()
                if is_value_invalid(name, key='album'):
                    continue
                _set_release_date(album)
                elem = dict(id=album['id'], release_date=album['release_date'])
                artist_albums[name] = elem
            query = self.sp.next(query)
        sort = sorted(
            artist_albums.items(), key=lambda x: x[1]['release_date']
        )
        artist_albums = dict(sort)

        album_ids = [album['id'] for album in artist_albums.values()]
        for albums, ids in chunks(artist_albums.values(), album_ids, 20):
            query = self.sp.albums(ids)

            for album, response in zip(albums, query['albums']):
                tracks = []
                while response:
                    if 'tracks' in response:
                        response = response['tracks']
                    tracks.extend(
                        process(t['name'], key='name').lower()
                        for t in response['items']
                    )
                    response = self.sp.next(response)
                tracks = dict.fromkeys(tracks)
                tracks.pop('Unknown', None)
                album['tracks'] = list(tracks)
        return {
            k: v for k, v in artist_albums.items() if v.get('tracks', None)
        }

    @credentials
    def fetch_discography(self, song):
        """
        Get the entire discography of the artist of this song and store it in
        the discography cache.
        """
        artist, title = song.artist, song.title
        if artist in self.discography_cache:
            logger.debug('found discography in cache')
            return

        try:
            discog = self.get_discography(artist, title)
            logger.debug('got discography')
            self.discography_cache[artist] = discog
        except Exception as e:
            logger.exception(e)
            logger.debug('discography not found')

    @credentials
    def fetch_album(self, song):
        """
        Get the name of the album for a song from spotify.
        """
        artist, title = song.artist, song.title
        self.fetch_discography(song)
        if not self.discography_cache.get(artist, ''):
            return 'Unknown'

        title = process(title, key='name')
        for album_name, info in self.discography_cache[artist].items():
            if title.lower() in map(str.lower, info['tracks']):
                return album_name
        return 'Unknown'

    @credentials
    def get_album_tracks(self, song):
        """
        Get the list of tracks of the album this song belongs to.
        """
        if song.album and song.album != 'Unknown':
            song.album = process(song.album, key='album', invalid=False)
            self.fetch_discography(song)
        else:
            logger.debug('song has no embedded album. searching')
            song.album = self.fetch_album(song)
            logger.debug('got this album: %s', song.album)
        try:
            if not song.album or song.album == 'Unknown':
                raise KeyError('Album not found')
            return self.discography_cache[song.artist][song.album]['tracks']
        except KeyError:
            msg = 'Spotify could not find the list of tracks for %s'
            logging.info(msg, song)
            return []

"""
Main telegram bot module.
"""
import logging
import json
import sqlite3
import time
from functools import partial
from collections import defaultdict

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import lyricfetch as lyrics
from lyricfetch import Song
from lyricfetch import scraping
from lyricfetch.run import get_lyrics_threaded
from lyricfetch.scraping import get_lastfm
from lyricfetch.scraping import id_source

from db import DB as Database
from spotify import Spotify
from util import capwords
from logger import logger
from server import Server


HELPFILE = './help.txt'
CONFFILE = './config.json'
MSG_TEMPLATE = """\
FROM: {source}
*{artist} - {title}*

{lyrics}"""

DB = Database()
SP = Spotify()
HANDLERS = defaultdict(list)


def start(update, context):
    """
    Function to be called on /start commmand.
    """
    intro = ''
    try:
        helpfile = open(HELPFILE, 'r')
        intro = helpfile.read()
        helpfile.close()
    except Exception as error:
        logger.exception(error)

    send_message(intro, context.bot, update.message.chat_id)


def get_album_tracks_spotify(song):
    """
    Search spotify for list of tracks in the album this song belongs to.
    """
    return SP.get_album_tracks(song)


def get_album_tracks_lastfm(song):
    """
    Search lastfm for list of tracks in the album this song belongs to.
    """
    song.fetch_album_name()
    if not song.album:
        return []
    tracks = get_lastfm('album.getInfo', artist=song.artist, album=song.album)
    if not tracks:
        return []
    tracks = list(t['name'] for t in tracks['album']['tracks']['track'])
    tracks = list(map(str.lower, tracks))
    return tracks


def get_album_tracks(song):
    """
    Get the list of tracks in the album this song belongs to.
    """
    tracks = get_album_tracks_spotify(song)
    if tracks:
        logger.debug('found track list from spotify')
        return tracks
    logger.debug('no track list from spotify, searching lastfm')
    return get_album_tracks_lastfm(song)


def _get_next_song(chat_id):
    """
    Get lyrics for the next song in the album.
    """
    msg = 'OOPS'
    try:
        last_res = DB.get_last_res(chat_id)
        if not last_res:
            return "You haven't searched for anything yet"

        album = last_res['album']
        album = album if album != 'Unknown' else None
        song = Song(last_res['artist'], last_res['title'], album)
        tracks = get_album_tracks(song)
        if not tracks:
            logger.info('no track list found')
            return 'Could not find the album this song belongs to'

        title = song.title.lower()
        if title not in tracks:
            logger.info('title not found in track list')
            return 'Could not find the album this song belongs to'
        if title == tracks[-1]:
            return 'That was the last song on the album'
        new_title = tracks[tracks.index(title) + 1]
        new_song = Song(artist=song.artist, title=new_title, album=song.album)
        msg = get_lyrics(new_song, chat_id)
    except sqlite3.Error:
        msg = (
            "There was an error while looking through the conversation's "
            "history. This command is unavailable for now."
        )
    return msg


def next_song(update, context):
    """
    Get lyrics for the next song in the album.
    """
    msg = _get_next_song(update.message.chat_id)
    send_message(msg, context.bot, update.message.chat_id)


def get_sp_token(chat_id):
    """
    Get a saved Spotify user token. Refresh it if it expired.
    """
    token = DB.get_sp_token(chat_id)
    if not token:
        return None

    if token['expires'] and int(token['expires']) < time.time():
        logger.info('Refreshing access token')
        token = SP.refresh_access_token(token['refresh'])
        logger.debug(token)
        DB.save_sp_token(
            token['access_token'],
            chat_id=chat_id,
            refresh=token['refresh_token'],
            expires=token['expires_at'],
        )
        token['token'] = token['access_token']
    return token['token']


def now(update, context):
    """
    Search for the lyrics of the song that the user is playing on Spotify.
    """
    chat_id = update.message.chat_id
    send = partial(send_message, bot=context.bot, chat_id=chat_id)
    token = get_sp_token(chat_id)
    if not token:
        auth_url = SP.get_auth_url(chat_id)
        send('Please open this link to log in to Spotify')
        send(auth_url, raw=True)
        while True:
            token = DB.get_sp_token(chat_id)
            if token and token['token']:
                break
            time.sleep(1)

        token = SP.get_access_token(token['token'])
        DB.save_sp_token(
            token['access_token'],
            chat_id,
            expires=token['expires_at'],
            refresh=token['refresh_token'],
        )
        token = token['access_token']
    current = SP.currently_playing(token)
    if not current:
        send('There is nothing playing!')
    else:
        lyrics_str = get_lyrics(current, chat_id)
        send(lyrics_str)


def other(update, context):
    """
    Use a different source to find lyrics for the last searched song.
    """
    try:
        last_res = DB.get_last_res(update.message.chat_id)
        if last_res:
            song = Song(
                last_res['artist'], last_res['title'], last_res['album']
            )
            scraping_func = getattr(scraping, last_res['source'])
            sources = lyrics.exclude_sources(scraping_func, True)
            if not sources:
                msg = "No other sources left to search"
            else:
                msg = get_lyrics(song, update.message.chat_id, sources)
        else:
            msg = "You haven't searched for anything yet"
    except sqlite3.Error:
        msg = (
            "There was an error while looking through the conversation's "
            "history. This command is unavailable for now."
        )

    send_message(msg, context.bot, update.message.chat_id)


def get_song_from_string(song, chat_id):
    """
    Parse the user's input and return a song object from it.
    """
    if not song:
        return None
    if isinstance(song, Song):
        return song

    if '-' in song:
        song = Song.from_string(song)
    else:
        last_res = DB.get_last_res(chat_id)
        if not last_res:
            return None
        song = Song(artist=last_res['artist'], title=song)

    return song


def log_result(chat_id, result):
    """
    Log a search result to the database.
    """
    try:
        DB.log_result(chat_id, result)
    except sqlite3.Error as err:
        logger.exception(err)


def get_lyrics(song, chat_id, sources=None):
    """
    Get lyrics for a song. The 'song' parameter can be either an unparsed
    string directly from the user or a full Song object.
    """
    msg = ''
    try:
        song = get_song_from_string(song, chat_id)
        if not song:
            return 'Invalid format!'
        logger.info('Searching for song %s', song)

        if sources is None:
            sources = lyrics.sources
        res = get_lyrics_threaded(song, sources)

        artist = capwords(song.artist)
        title = capwords(song.title)
        if res.source is None or song.lyrics == '':
            msg = f'Lyrics for {artist} - {title} could not be found'
        else:
            msg = MSG_TEMPLATE.format(
                source=id_source(res.source, True).lower(),
                artist=artist,
                title=title,
                lyrics=song.lyrics,
            )
            log_result(chat_id, res)
    except Exception as error:
        logger.exception(error)
        msg = 'Unknown error'

    return msg


def text(update, context):
    """
    Generic text input handler.
    """
    chat_id = update.message.chat_id
    if HANDLERS[chat_id]:
        handler = HANDLERS[chat_id].pop()
        handler(update, context)
        return

    # If there is no priority handler, call the default "find"
    find(update, context)


def find(update, context):
    """
    Find lyrics for a song.
    """
    chat_id = update.message.chat_id
    bot = context.bot
    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    lyrics_str = get_lyrics(update.message.text, chat_id)
    send_message(lyrics_str, context.bot, chat_id)


def send_message(msg, bot, chat_id, raw=False):
    """
    Splits a string into MAX_LENGTH chunks and sends them as messages.
    """
    parse_mode = 'Markdown' if not raw else None
    send = partial(bot.send_message, chat_id=chat_id, parse_mode=parse_mode)
    try:
        last_section = 0
        chunksize = telegram.constants.MAX_MESSAGE_LENGTH
        for section in range(chunksize, len(msg), chunksize):
            section = msg.rfind('\n\n', last_section, section)

            # If we moved so far back that we got to the starting point, ignore
            # the 'avoid splitting' thing and just cut where you can
            if section == -1 or section <= last_section:
                section = last_section + chunksize

            send(text=msg[last_section:section])
            last_section = section

        if last_section < len(msg):
            send(text=msg[last_section : len(msg)])

    except telegram.TelegramError as error:
        logger.exception(error)
        msg = 'Unknown error'
        send(text=msg)


def unknown(update, context):
    """
    Fallback function for commands that don't match any of the known ones.
    """
    send_message(
        "Sorry, I didn't understand that command",
        context.bot,
        update.message.chat_id
    )


def parse_config():
    """
    Returns a dictionary with all the necessary data from the configuration
    file.
    """
    with open(CONFFILE) as conffile:
        data = json.load(conffile)
        required_keys = ['token', 'db_filename']
        if not all(key in data for key in required_keys):
            raise KeyError("Key '%s' not found in the config file")
        return data


def main():
    config = parse_config()
    if not config:
        return 1

    updater = Updater(config['token'], use_context=True)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('other', other))
    updater.dispatcher.add_handler(CommandHandler('next', next_song))
    updater.dispatcher.add_handler(CommandHandler('now', now))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, text))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    SP.configure(config['SPOTIFY_CLIENT_ID'], config['SPOTIFY_CLIENT_SECRET'])

    try:
        DB.config(config['db_filename'])
    except Exception as error:
        logger.critical(type(error))
        logger.critical(str(error))
        return 2

    server = Server(db_config=dict(filename=config['db_filename']))
    server.start()

    updater.bot.logger.setLevel(logging.CRITICAL)
    updater.start_polling()

    logger.info('Started')
    updater.idle()
    logger.info('Closing')
    SP.save_cache()
    server.terminate()
    try:
        DB.close()
    except sqlite3.Error:
        pass

    return 0


if __name__ == '__main__':
    exit(main())

"""
Main telegram bot module.
"""
import logging
import json
import sqlite3
from functools import partial

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import lyricfetch as lyrics
from lyricfetch import Song
from lyricfetch import scraping
from lyricfetch.scraping import get_lastfm
from lyricfetch.scraping import id_source

from db import DB as Database
from spotify import Spotify

logging.basicConfig(
    format='%(asctime)s - %(name)s - ' '%(levelname)s - %(message)s',
    level=logging.INFO,
)

HELPFILE = './help.txt'
CONFFILE = './config.json'
MSG_TEMPLATE = """\
FROM: {source}
*{artist} - {title}*

{lyrics}"""

DB = Database()
SP = Spotify()


def start(bot, update):
    """
    Function to be called on /start commmand.
    """
    intro = ''
    try:
        helpfile = open(HELPFILE, 'r')
        intro = helpfile.read()
        helpfile.close()
    except Exception as error:
        logging.exception(error)

    send_message(intro, bot, update.message.chat_id)


def fetch_album_name(song):
    """
    Find the album name for a song and set it as its 'album' attribute.
    """
    if song.album:
        return

    song.album = SP.fetch_album(song)
    if song.album:
        return

    song.fetch_album_name()


def get_album_tracks(song):
    """
    Get the list of tracks in the album this song belongs to.
    """
    fetch_album_name(song)
    if not song.album:
        return []
    tracks = get_lastfm('album.getInfo', artist=song.artist, album=song.album)
    tracks = list(t['name'] for t in tracks['album']['tracks']['track'])
    tracks = list(map(str.lower, tracks))
    return tracks


def _get_next_song(chat_id):
    """
    Get lyrics for the next song in the album.
    """
    msg = 'OOPS'
    try:
        last_res = DB.get_last_res(chat_id)
        if not last_res:
            return "You haven't searched for anything yet"
        song = Song(artist=last_res[0], title=last_res[1])
        tracks = get_album_tracks(song)
        if not tracks:
            return 'Could not find the album this song belongs to'

        title = song.title.lower()
        if title not in tracks:
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


def next_song(bot, update):
    """
    Get lyrics for the next song in the album.
    """
    msg = _get_next_song(update.message.chat_id)
    send_message(msg, bot, update.message.chat_id)


def other(bot, update):
    """
    Use a different source to find lyrics for the last searched song.
    """
    try:
        last_res = DB.get_last_res(update.message.chat_id)
        if last_res:
            song = Song(artist=last_res[0], title=last_res[1])
            scraping_func = getattr(scraping, last_res[2])
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

    send_message(msg, bot, update.message.chat_id)


def get_song_from_string(song, chat_id):
    """
    Parse the user's input and return a song object from it.
    """
    if isinstance(song, Song):
        return song

    if '-' in song:
        song = Song.from_string(song)
    else:
        last_res = DB.get_last_res(chat_id)
        if not last_res:
            return None
        song = Song(artist=last_res[0], title=song)

    return song


def log_result(chat_id, result):
    try:
        DB.log_result(chat_id, result)
    except sqlite3.Error as err:
        logging.exception(err)


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

        if sources is None:
            sources = lyrics.sources
        res = lyrics.get_lyrics(song, sources)

        if res.source is None or song.lyrics == '':
            msg = (
                f'Lyrics for {song.artist.title()} - {song.title.title()} '
                'could not be found'
            )
        else:
            msg = MSG_TEMPLATE.format(
                source=id_source(res.source, True).lower(),
                artist=song.artist.title(),
                title=song.title.title(),
                lyrics=song.lyrics,
            )
            log_result(chat_id, res)
    except Exception as error:
        logging.exception(error)
        msg = 'Unknown error'

    return msg


def find(bot, update):
    """
    Find lyrics for a song.
    """
    chat_id = update.message.chat_id
    bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)
    lyrics_str = get_lyrics(update.message.text, chat_id)
    send_message(lyrics_str, bot, chat_id)


def send_message(msg, bot, chat_id):
    """
    Splits a string into MAX_LENGTH chunks and sends them as messages.
    """
    send = partial(bot.send_message, chat_id=chat_id, parse_mode='Markdown')
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
            send(text=msg[last_section: len(msg)])

    except telegram.TelegramError as error:
        logging.exception(error)
        msg = 'Unknown error'
        send(text=msg)


def unknown(bot, update):
    """
    Fallback function for commands that don't match any of the known ones.
    """
    send_message(
        "Sorry, I didn't understand that command", bot, update.message.chat_id
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

    updater = Updater(config['token'])
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('other', other))
    updater.dispatcher.add_handler(CommandHandler('next', next_song))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, find))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    SP.configure(config['SPOTIFY_CLIENT_ID'], config['SPOTIFY_CLIENT_SECRET'])

    try:
        DB.config(config['db_filename'])
    except Exception as error:
        logging.critical(type(error))
        logging.critical(str(error))
        return 2

    updater.bot.logger.setLevel(logging.CRITICAL)
    updater.start_polling()

    print('Started')
    updater.idle()
    print('Closing')
    DB.close()

    return 0


if __name__ == '__main__':
    exit(main())

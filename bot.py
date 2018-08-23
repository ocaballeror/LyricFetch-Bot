"""
Main telegram bot module.
"""
import logging
import json
import psycopg2 as pg
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import lyricfetch as lyrics
from lyricfetch import Song

from db import DB as Database

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

HELPFILE = './help.txt'
CONFFILE = './config.json'

DB = Database()


def start(bot, update):
    """
    Function to be called on /start commmand.
    """
    intro = ""
    try:
        helpfile = open(HELPFILE, 'r')
        intro = helpfile.read()
        helpfile.close()
    except Exception as error:
        logging.exception(error)

    send_message(intro, bot, update.message.chat_id)


def other(bot, update):
    """
    Use a different source to find lyrics for the last searched song.
    """
    try:
        last_res = DB.get_last_res(update.message.chat_id)
        if last_res:
            song = Song.from_info(artist=last_res[0], title=last_res[1])
            sources = lyrics.exclude_sources(last_res[2], True)
            msg, _ = get_lyrics(song, update.message.chat_id, sources)
        else:
            msg = "You haven't searched for anything yet"
    except pg.Error:
        msg = "There was an error while looking through the conversation's "\
              "history. This command is unavailable for now."

    send_message(msg, bot, update.message.chat_id)


def get_lyrics(song, chat_id, sources=None):
    """
    Get lyrics for a song. The 'song' parameter can be either an unparsed
    string directly from the user or a full Song object.
    """
    msg = ''
    valid = False
    try:
        res = None
        if isinstance(song, str):
            song = Song.from_string(song)

        if song:
            if sources is None:
                res = lyrics.get_lyrics(song)
            else:
                res = lyrics.get_lyrics(song, sources)

        if res is None:
            msg = 'Wrong format!'
        elif res.source is None or song.lyrics == '':
            msg = f'Lyrics for {song.artist.title()} - {song.title.title()} '\
                   'could not be found'
        else:
            msg = 'FROM: %s\n\n%s' %\
                    (lyrics.id_source(res.source, True).lower(),
                     song.lyrics)
            valid = True
            try:
                DB.log_result(chat_id, res)
            except pg.Error as err:
                pass
    except Exception as error:
        logging.exception(error)
        msg = 'Unknown error'

    return msg, valid


def find(bot, update):
    """
    Find lyrics for a song.
    """
    lyrics_str, _ = get_lyrics(update.message.text, update.message.chat_id)
    send_message(lyrics_str, bot, update.message.chat_id)


def send_message(msg, bot, chat_id):
    """
    Splits a string into MAX_LENGTH chunks and sends them as messages.
    """
    try:
        last_section = 0
        chunksize = telegram.constants.MAX_MESSAGE_LENGTH
        for section in range(chunksize, len(msg), chunksize):
            section = msg.rfind('\n\n', last_section, section)

            # If we moved so far back that we got to the starting point, ignore
            # the 'avoid splitting' thing and just cut where you can
            if section == -1 or section <= last_section:
                section = last_section+chunksize

            bot.send_message(chat_id=chat_id,
                             text=msg[last_section:section])
            last_section = section

        if last_section < len(msg):
            bot.send_message(chat_id=chat_id,
                             text=msg[last_section:len(msg)])

    except telegram.TelegramError as error:
        logging.exception(error)
        if not msg:
            msg = 'Unknown error'

        bot.send_message(chat_id=chat_id, text=msg)


def unknown(bot, update):
    """
    Fallback function for commands that don't match any of the known ones.
    """
    send_message("Sorry, I didn't understand that command", bot,
                 update.message.chat_id)


def parse_config():
    """
    Returns a dictionary with all the necessary data from the configuration
    file.
    """
    try:
        with open(CONFFILE, 'r') as conffile:
            data = json.load(conffile)
            required_keys = ['token', 'dbuser', 'dbname', 'dbpassword']
            for key in required_keys:
                if key not in data:
                    logging.critical(f"Key '{key}' not found in the"
                                     "configuration file. Cannot continue")
                    return None

            # Set the database host to localhost if it's not set
            if 'dbhost' not in data:
                data['dbhost'] = 'localhost'

            return data
    except IOError:
        logging.critical('Could not read the configuration file %s', CONFFILE)
        return None


def main():
    config = parse_config()
    if not config:
        return 1

    updater = Updater(config['token'])
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('other', other))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, find))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    try:
        DB.config(config['dbname'], config['dbuser'], config['dbpassword'],
                  config['dbhost'])
    except Exception as error:
        print(type(error))
        print(error)
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

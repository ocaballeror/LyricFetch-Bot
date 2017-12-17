import logging
import lyricfetch.lyrics as lyrics
import telegram
import json

from db import DB
from lyricfetch.lyrics import Result, Song
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

HELPFILE = './help.txt'
CONFFILE = './config.json'

intro = ""
try:
    helpfile = open(HELPFILE, 'r')
    intro = helpfile.read()
    helpfile.close()
except Exception as e:
    logging.exception(e)

def start(bot, update):
    '''Function to be called on /start commmand'''
    send_message(intro, bot, update.message.chat_id)

def other(bot, update):
    last_res = db.get_last_res(update.message.chat_id)
    if last_res:
        song = Song.from_info(artist=last_res[0], title=last_res[1])
        result = Result(song, last_res[2])
        sources = lyrics.exclude_sources(last_res[2], True)
        msg, valid = get_lyrics(song, update.message.chat_id, sources)
    else:
        msg = "You haven't searched for anything yet"

    send_message(msg, bot, update.message.chat_id)

def get_lyrics(song, chat_id, sources=None):
    """Get lyrics for a song. The 'song' parameter can be either an unparsed
    string directly from the user or a full Song object"""
    msg = ''
    valid = False
    try:
        res = None
        if type(song) is str:
            song = Song.from_string(song)

        if song:
            if sources is None:
                res = lyrics.get_lyrics(song)
            else:
                res = lyrics.get_lyrics(song, sources)

        if res is None:
            msg = 'Wrong format!'
        elif res.source is None or song.lyrics == '':
            msg = f'Lyrics for {song.artist.title()} - {song.title.title()} could not be found'
        else:
            msg = 'FROM: {}\n\n{}'.format(lyrics.id_source(res.source, True).lower(), song.lyrics)
            valid = True
            db.log_result(chat_id, res)
    except Exception as e:
        print(e)
        msg = 'Unknown error'

    return msg, valid

def find(bot, update):
    lyrics, _ = get_lyrics(update.message.text, update.message.chat_id)
    send_message(lyrics, bot, update.message.chat_id)

def send_message(msg, bot, chat_id):
    try:
        last_section = 0
        chunksize=telegram.constants.MAX_MESSAGE_LENGTH
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

    except Exception as e:
        logging.exception(e)
        if not msg:
            msg = 'Unknown error'

        bot.send_message(chat_id=chat_id, text=msg)

def unknown(bot, update):
    send_message("Sorry, I didn't understand that command", bot,
            update.message.chat_id)

def parse_config():
    """Returns a dictionary with all the necessary data from the configuration
    file"""
    try:
        with open(CONFFILE, 'r') as config:
            data = json.load(config)
            required_keys = ['token', 'dbuser', 'dbname', 'dbpassword']
            for key in required_keys:
                if key not in data:
                    logging.critical(f"Key '{key}' not found in the configuration"
                            "file. Cannot continue")
                    return None

            # Set the database host to localhost if it's not set
            if 'dbhost' not in data:
                data['dbhost'] = 'localhost'

            return data
    except IOError:
        logging.critical('Could not read the configuration file '+CONFFILE)
        return None

if __name__ == '__main__':
    config = parse_config()
    if not config:
        exit(1)

    updater = Updater(config['token'])
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('other', other))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, find))
    updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    db = DB(config['dbname'], config['dbuser'], config['dbpassword'],
            config['dbhost'])
    updater.start_polling()

    print('Started')
    updater.idle()
    print('Closing')
    db.close()

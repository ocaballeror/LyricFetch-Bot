import logging
import lyricfetch.lyrics as lyrics
import telegram

from lyricfetch.lyrics import Result, Song
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

HELPFILE = './help.txt'
TOKENFILE = './token.txt'

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

token = ''
try:
    tokenfile = open(TOKENFILE, 'r')
    token = tokenfile.read()
    tokenfile.close()
except Exception:
    logger.exception(e)
    exit(1)

if token[-1] == '\n':
    token = token[0:-1]
updater = Updater(token)
updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(MessageHandler(Filters.text, find))
updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))
updater.start_polling()

print('Started')
updater.idle()

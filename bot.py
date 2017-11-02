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
    bot.send_message(chat_id=update.message.chat_id, text=intro)

def find(bot, update):
    res = None
    try:
        song = Song.from_string(update.message.text)
        res = lyrics.get_lyrics(song)

        if res is None:
            msg = 'Wrong format!'
        elif res.source is None or song.lyrics == '':
            msg = f'Lyrics for {song.artist.title()} - {song.title.title()} could not be found'
        else:
            msg = f'''FROM: {lyrics.id_source(res.source, True).lower()}

{song.lyrics}'''

        last_section = 0
        chunksize=telegram.constants.MAX_MESSAGE_LENGTH
        for section in range(chunksize, len(msg), chunksize):
            section = msg.rfind('\n\n', last_section, section)

            # If we moved so far back that we got to the starting point, ignore
            # the 'avoid splitting' thing and just cut where you can
            if section == -1 or section <= last_section:
                section = last_section+chunksize

            print(f'Section: {last_section}:{section}')
            bot.send_message(chat_id=update.message.chat_id,
                    text=msg[last_section:section])
            last_section = section

        if last_section < len(msg):
            bot.send_message(chat_id=update.message.chat_id,
                    text=msg[last_section:len(msg)])

    except Exception as e:
        logging.exception(e)
        msg = f'Lyrics for {song.artist.title()} - {song.title.title()} could not be found'
        bot.send_message(chat_id=update.message.chat_id, text=msg)

def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't"
            " understand that command")

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

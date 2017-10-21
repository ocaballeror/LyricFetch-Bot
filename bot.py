import logging
import lyrics

from lyrics import Result
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

intro = """Hi there!

I'm the lyrics bot, I can search the web and find lyrics for you.

Tell me the artist and name of the song you are looking for and I'll be right \
back with the lyrics. Just note that for now, you have to be really specific \
and use this format:

    Artist - Title

Otherwise I won't be able to find your song.

Remember I'll always be awake waiting for you to ask me something, so feel free \
to do so at any time.

Thank you for choosing me!

PS: The source code is available on github: https://github.com/ocaballeror/LyricFetch-Bot
"""

def start(bot, update):
    '''Function to be called on /start commmand'''
    bot.send_message(chat_id=update.message.chat_id, text=intro)

def find(bot, update):
    res = None
    try:
        res = lyrics.find_lyrics(update.message.text)

        if res is None:
            msg = 'Wrong format!'
        elif res.source is None or res.lyrics == '':
            msg = f'Lyrics for {res.artist.title()} - {res.title.title()} could not be found'
        else:
            msg = f'''FROM: {lyrics.id_source(res.source, True)}

    {res.lyrics}'''

        bot.send_message(chat_id=update.message.chat_id, text=msg)
    except Exception:
        msg = f'Lyrics for {res.artist.title()} - {res.title.title()} could not be found'
        bot.send_message(chat_id=update.message.chat_id, text=msg)

def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't"
            " understand that command")

updater = Updater("461228377:AAHmL7NmGiRAEwOqsBXxa02ArlxeWugc45Y")

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(MessageHandler(Filters.text, find))
updater.dispatcher.add_handler(MessageHandler(Filters.command, unknown))

updater.start_polling()
updater.idle()

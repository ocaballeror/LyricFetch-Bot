import logging
fmt = '%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s'
formatter = logging.Formatter(fmt)
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler('lyrics-bot.log', mode='a')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

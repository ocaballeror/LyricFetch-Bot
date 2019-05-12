import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - ' '%(levelname)s - %(message)s'
)
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

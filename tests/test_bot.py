import sys
from tempfile import NamedTemporaryFile

sys.path.append('.')
import bot
from bot import start


class Infinite:
    def __getattr__(self, attr):
        return Infinite()

message_buffer = []
def append_message(*args, **kwargs):
    print('hello')
    message_buffer.append(args[0])

bot.send_message = append_message


def test_start(monkeypatch):
    with NamedTemporaryFile(mode='w+') as tmpfile:
        monkeypatch.setattr(bot, 'HELPFILE', tmpfile.name)
        tmpfile.file.write('hello world')
        tmpfile.file.flush()
        start(Infinite(), Infinite())
    assert message_buffer[-1] == 'hello world'

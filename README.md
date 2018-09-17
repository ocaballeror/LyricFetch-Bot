# Lyricfetch bot
A Telegram bot to fetch lyrics from the internet.

This is the telegram interface for [LyricFetch](https://github.com/ocaballeror/LyricFetch), and it will use it as a backend to find lyrics for the requested song. Please refer to that project for implementation details on how the lyrics are fetched and all those kinds of things.

## Running
To run the bot locally, it is necessary to fill in the `config.json` file, where you must, at least, input your bot token, which you should have already received from the Botfather.

Once the configuration is set, simply run
```sh
python bot.py
```
and the bot will start listening to incoming messages.

## Usage
The telegram interface is pretty self explanatory. Send a message to the bot with the artist and title of the song you want using the obligatory `artist - title` format.

Apart from that, there are 3 special commands a user can send right now:

* /start: Show the introductory message and a few usage tips.
* /other: Repeat the last search, but try to find lyrics from a different source.
* /next: Get the next song from the album

## Contributing
As always, you can contribute to this project if you feel so inclined. Please fork this repo and submit a pull request, and I will be happy to review it.

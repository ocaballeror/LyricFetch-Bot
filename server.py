#!/usr/bin/env python3
"""
Flask server to listen for spotify authentication responses.
"""
from multiprocessing import Process
from flask import Flask, request
from db import DB


class Server(Process):
    def __init__(self, db_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = DB()
        self.db.config(**db_config)
        self.app = Flask(__name__)
        self.app.add_url_rule('/auth', 'auth', view_func=self.on_event)

    def run(self):
        super().run()
        self.app.run(host='0.0.0.0', port=7000, debug=False)

    def on_event(self):
        print(request)
        print(request.args)
        if 'code' in request.args:
            response = [
                'Logged in successfully.',
                'You can close your browser now.',
            ]
            self.db.save_sp_token(
                request.args['code'], chat_id=request.args['state']
            )
        elif 'error' in request.args:
            response = [
                "Couldn't log you in to Spotify",
                'The error was: %s' % request.args['error'],
            ]
        return '<h3>{}</h3>'.format('<br>'.join(response))

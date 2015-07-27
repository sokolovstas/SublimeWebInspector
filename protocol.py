import os
import sys
import json
import sublime

swi_folder = os.path.dirname(os.path.realpath(__file__))
if not swi_folder in sys.path:
    sys.path.append(swi_folder)

import threading
import websocket
import swi
import utils

class Protocol(object):
    """ Encapsulate websocket connection """

    def __init__(self):
        self.next_id = 0
        self.commands = {}
        self.notifications = {}
        self.last_log_object = None

    def connect(self, url, on_open=None, on_close=None):
        """ Attempt to connect to the web socket """
        print (('SWI: Connecting to ' + url))
        websocket.enableTrace(False)
        self.last_break = None
        self.last_log_object = None
        self.url = url
        self.on_open = on_open
        self.on_close = on_close
        thread = threading.Thread(target=self.thread_callback)
        thread.start()

    def thread_callback(self):
        """ Threadproc owning the socket.
            Sets up the callbacks for open, close, and message.
        """
        print ('SWI: Thread started')
        self.socket = websocket.WebSocketApp(self.url, on_message=self.message_callback, on_open=self.open_callback, on_close=self.close_callback)
        self.socket.run_forever()
        print ('SWI: Thread stopped')

    def send(self, command, callback=None, options=None):
        """ Send to web socket, with optional callback and options """
        command.id = self.next_id
        command.callback = callback
        command.options = options
        self.commands[command.id] = command
        self.next_id += 1
        if utils.get_setting('debug_mode'):
            print ('SWI: ->> ' + json.dumps(command.request, sort_keys=True, indent=4, separators=(',', ': ')))
        self.socket.send(json.dumps(command.request))

    def subscribe(self, notification, callback):
        """ Subscribe to notification with callback """
        notification.callback = callback
        self.notifications[notification.name] = notification

    def unsubscribe(self, notification):
        """ Unsubscribe to notification """
        del self.notifications[notification.name]

    def message_callback(self, ws, message):
        """ Callback on any incoming packet.
            Parse it and call matching callback.
        """
        parsed = json.loads(message)
        if utils.get_setting('debug_mode'):
            print ('SWI: <<- ' + json.dumps(parsed, sort_keys=True, indent=4, separators=(',', ': ')))
        if 'method' in parsed:
            if parsed['method'] in self.notifications:
                notification = self.notifications[parsed['method']]
                if 'params' in parsed:
                    data = notification.parser(parsed['params'])
                else:
                    data = None

                self.to_main_thread(notification.callback, (data, notification))
        else:
            if parsed['id'] in self.commands:

                command = self.commands[parsed['id']]

                if 'error' in parsed:
                    self.to_main_thread(print, ("Error from debuggee: " + parsed['error']['message'], )) # comma makes it a tuple
                else:
                    if 'result' in parsed:
                        command.data = command.parser(parsed['result'])
                    else:
                        command.data = None

                    if command.callback:
                        self.to_main_thread(command.callback, (command, )) # comma makes it a tuple

    def open_callback(self, ws):
        if self.on_open:
            self.to_main_thread(self.on_open, ())
        print ('SWI: WebSocket opened')

    def close_callback(self, ws):
        if self.on_close:
            self.to_main_thread(self.on_close, ())
        print ('SWI: WebSocket closed')

    def to_main_thread(self, f, args):
        """ Call back on the main thread
            to simplify the called code
        """
        assert(f)
        if f:   # shutdown timing races
            sublime.set_timeout(lambda: f(*args))

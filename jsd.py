import urllib2
import sublime
import sublime_plugin
import threading
import json
import websocket

buffers = {}
protocol = None
original_layout = None
debug_view = None
debug_url = None

breakpoint_icon = '../Xdebug/icons/breakpoint'
current_icon = '../Xdebug/icons/current'
current_breakpoint_icon = '../Xdebug/icons/current_breakpoint'


class Protocol(object):
    def accept(self, url, message_callback, open_callback, close_callback):
        websocket.enableTrace(False)
        self.socket = websocket.WebSocketApp(url, on_message = message_callback, on_open = open_callback, on_close = close_callback)
        self.socket.run_forever()

class JsDebugCommand(sublime_plugin.TextCommand):
    '''
    The Xdebug main quick panel menu
    '''
    def run(self, edit):
        print 'JsDebugCommand'
        mapping = {
            'js_debug_start_chrome': 'Start Chrome with remote debug port 9222',
            'js_debug_clear_console': 'Clear console',
            'js_debug_breakpoint': 'Add/Remove Breakpoint'
            
            #'xdebug_clear_all_breakpoints': 'Clear all Breakpoints',
        }

        if protocol:
            mapping['js_debug_stop'] = 'Stop debugging'
        else:
            mapping['js_debug_start'] = 'Start debugging'

        self.cmds = mapping.keys()
        self.items = mapping.values()
        self.view.window().show_quick_panel(self.items, self.callback)
    def callback_start_with_url(self, index):
        url = self.urls[index]

        window = sublime.active_window()
        window.run_command("show_panel", {"panel": "output.xdebug_inspect"})
        global original_layout
        original_layout = window.get_layout()
        global debug_view
        debug_view = window.active_view()
        window.set_layout({
             "cols": [0.0, 1.0],
             "rows": [0.0, 0.7, 1.0],
             "cells": [[0, 0, 1, 1], [0, 1, 1, 2]]
        })
        #views = window.views()

        self.view.run_command('js_debug_start', {'url': url})

    def callback(self, index):
        if index == -1:
            return

        command = self.cmds[index]

        if command == 'js_debug_start':
            response = urllib2.urlopen('http://127.0.0.1:9222/json/')
            pages = json.loads(response.read())
            mapping = {}
            for page in pages:
                if 'webSocketDebuggerUrl' in page:
                    if page['url'].find('chrome-extension://') == -1:
                        mapping[page['webSocketDebuggerUrl']] = page['url']

            self.urls = mapping.keys()
            items = mapping.values()
            self.view.window().show_quick_panel(items, self.callback_start_with_url)
            return

        if command == 'js_debug_stop':
            window = sublime.active_window()
            window.run_command('hide_panel', {"panel": 'output.xdebug_inspect'})
            window.set_layout(original_layout)

        self.view.run_command(command)

class JsDebugStartChromeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        window = sublime.active_window()
        print 'running chrome'
        window.run_command('exec', {
            "cmd": ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--remote-debugging-port=9222']
        })


class JsDebugStopCommand(sublime_plugin.TextCommand):

    '''
    Start listening for Xdebug connections
    '''
    def run(self, edit):
        global protocol
        if protocol:
            try:
                protocol.socket.close()
            except:
                print 'cant close socket'
            finally:
                protocol = None
class JsDebugClearConsoleCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        sublime.set_timeout(lambda: add_debug_info('console', 'clear'), 0)

class JsDebugBreakpointCommand(sublime_plugin.TextCommand):
    '''
    Toggle a breakpoint
    '''
    def run(self, edit):
        view = lookup_view(self.view)
        for row in view.rows(view.lines()):
            if row in view.breaks:
                view.del_breakpoint(row)
            else:
                view.add_breakpoint(row)
        view.view_breakpoints()

class JsDebugStartCommand(sublime_plugin.TextCommand):

    '''
    Start listening for Xdebug connections
    '''
    def run(self, edit, url):
        print 'run'
        self.url = url
        global protocol
        if(protocol):
            print 'try close'
            protocol.socket.close()
        else:
            print 'try open thread'
            protocol = Protocol()
            protocol_thread_stop = threading.Event()
            thread = threading.Thread(target=self.thread_callback)
            thread.start()

    def thread_callback(self):
        print 'start thread'
        protocol.accept(self.url, self.message_callback, self.open_callback, self.close_callback)
        print 'stop thread'

    def message_callback(self, ws, message):
        print 'message'
        jsonMessage = json.loads(message)

        if not 'method' in jsonMessage: return

        if jsonMessage['method'] == 'Console.messageAdded':
            message = jsonMessage['params']['message']
            if 'parameters' in message:
                message_params = message['parameters']
                params_string = []

                for element in message_params:
                    print(element)
                    if element['type'] == 'string':
                        params_string.append(element['value'])
                    if element['type'] == 'undefined':
                        params_string.append('undefined')
                    if element['type'] == 'object':
                        params_string.append(element['description'])
            else:
                params_string.append(message['text'])


            sublime.set_timeout(lambda: add_debug_info('console', ' '.join(params_string)), 0)
        else:
            print 'unset command ' + jsonMessage['method']


        #sublime.set_timeout(lambda: add_debug_info('console', jsonMessage), 0)

    def open_callback(self, ws):
        print 'open'
        protocol.socket.send(json.dumps({'id': 0, 'method': 'Console.enable'}))
        sublime.set_timeout(lambda: add_debug_info('console', 'Start Console'), 0)

    def close_callback(self, ws):
        print 'close'

class JsDebugView(object):
    '''
    The JsDebugView is sort of a normal view with some convenience methods.

    See lookup_view.
    '''
    def __init__(self, view):
        self.view = view
        self.current_line = None
        self.context_data = {}
        self.breaks = {}  # line : meta { id: bleh }

    def __getattr__(self, attr):
        if hasattr(self.view, attr):
            return getattr(self.view, attr)
        if attr.startswith('on_'):
            return self
        raise(AttributeError, "%s does not exist" % attr)

    def __call__(self, *args, **kwargs):
        pass

    def add_breakpoint(self, row):
        if not row in self.breaks:
            self.breaks[row] = {}
            if protocol and protocol.connected:
                protocol.send('breakpoint_set', t='line', f=self.uri(), n=row)
                res = protocol.read().firstChild
                self.breaks[row]['id'] = res.getAttribute('id')

    def del_breakpoint(self, row):
        if row in self.breaks:
            if protocol and protocol.connected:
                protocol.send('breakpoint_remove', d=self.breaks[row]['id'])
            del self.breaks[row]

    def view_breakpoints(self):
        self.view.add_regions('xdebug_breakpoint', self.lines(self.breaks.keys()), get_setting('breakpoint_scope'), breakpoint_icon, sublime.HIDDEN)

class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        lookup_view(view).on_pre_save()

    def on_post_save(self, view):
        if protocol:
            print 'clearBrowserCache after file save'
            protocol.socket.send(json.dumps({'id': 0, 'method': 'Network.clearBrowserCache'}))
            if view.file_name().find('.css') == -1 and view.file_name().find('.less') == -1:
                print 'reload'
                protocol.socket.send(json.dumps({'id': 1, 'method': 'Page.reload'}))
            else:
                print 'reload css'
                protocol.socket.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': '$$JSD_reloadAll()'}}))
        lookup_view(view).on_post_save()


def lookup_view(v):
    '''
    Convert a Sublime View into an XdebugView
    '''
    if isinstance(v, JsDebugView):
        return v
    if isinstance(v, sublime.View):
        id = v.buffer_id()
        if id in buffers:
            buffers[id].view = v
        else:
            buffers[id] = JsDebugView(v)
        return buffers[id]
    return None

def add_debug_info(name, data):
    '''
    Adds data to the debug output windows
    '''
    found = False
    v = None
    append = False
    window = sublime.active_window()

    if name == 'console':
        group = 1
        append = True
        fullName = "JSD Console"
    if name == 'stack':
        group = 1
        fullName = "JSD Stack"

    for v in window.views():
        if v.name() == fullName:
            found = True
            break

    if not found:
        v = window.new_file()
        v.set_scratch(True)
        v.set_read_only(False)
        v.set_name(fullName)
        v.settings().set('word_wrap', False)
        found = True

    if found:
        v.set_read_only(False)
        window.set_view_index(v, group, 0)
        edit = v.begin_edit()
        if(append):
            v.insert(edit, v.size(), data)
            v.insert(edit, v.size(), '\n')
        else:
            v.erase(edit, sublime.Region(0, v.size()))
            v.insert(edit, 0, data)
        if data == 'clear':
            v.erase(edit, sublime.Region(0, v.size()))
        v.end_edit(edit)
        v.set_read_only(False)

    window.focus_group(0)
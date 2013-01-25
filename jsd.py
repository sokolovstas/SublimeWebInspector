import random
import sublime
import sublime_plugin
import websocket
import urllib2
import threading
import json
import types
import os
import re
import wip
from wip import utils
from wip import Console
from wip import Runtime
from wip import Debugger
from wip import Network
from wip import Page
import sys

reload(sys.modules['wip.utils'])
reload(sys.modules['wip.Console'])
reload(sys.modules['wip.Runtime'])
reload(sys.modules['wip.Debugger'])
reload(sys.modules['wip.Network'])
reload(sys.modules['wip.Page'])

brk_object = {}
buffers = {}
protocol = None
original_layout = None
debug_view = None
debug_url = None
scriptId_fileName = {}
fileName_scriptId = {}

breakpoint_active_icon = '../JSD/icons/breakpoint_active'
breakpoint_inactive_icon = '../JSD/icons/breakpoint_inactive'
breakpoint_current_icon = '../JSD/icons/breakpoint_current'

# Define protocol to communicate with remote debugger by web sockets
class Protocol(object):
    def __init__(self):
        self.next_id = 0
        self.commands = {}
        self.notifications = {}
        self.last_log_object = None

    def connect(self, url, on_open=None, on_close=None):
        print 'JSD: Connecting to ' + url
        websocket.enableTrace(False)
        self.last_break = None
        self.last_log_object = None
        self.url = url
        self.on_open = on_open
        self.on_close = on_close
        thread = threading.Thread(target=self.thread_callback)
        thread.start()

    # start connect with new thread
    def thread_callback(self):
        print 'JSD: Thread started'
        self.socket = websocket.WebSocketApp(self.url, on_message=self.message_callback, on_open=self.open_callback, on_close=self.close_callback)
        self.socket.run_forever()
        print 'JSD: Thread stoped'

    # send command and increment command counter
    def send(self, command, callback=None, options=None):
        command.id = self.next_id
        command.callback = callback
        command.options = options
        self.commands[command.id] = command
        self.next_id += 1
        print 'JSD: Send -- ' + json.dumps(command.request)
        self.socket.send(json.dumps(command.request))

    # subscribe to notification with callback
    def subscribe(self, notification, callback):
        notification.callback = callback
        self.notifications[notification.name] = notification

    # unsubscribe
    def unsubscribe(self, notification):
        del self.notifications[notification.name]

    # unsubscribe
    def message_callback(self, ws, message):
        parsed = json.loads(message)
        if 'method' in parsed:
            if parsed['method'] in self.notifications:
                notification = self.notifications[parsed['method']]
                if 'params' in parsed:
                    data = notification.parser(parsed['params'])
                else:
                    data = None
                notification.callback(data, notification)
            else:
                print 'JSD: New unsubscrib notification --- ' + parsed['method']
        else:
            print parsed
            if parsed['id'] in self.commands:
                command = self.commands[parsed['id']]

                if 'error' in parsed:
                    sublime.set_timeout(lambda: sublime.error_message(parsed['error']['message']), 0)
                else:
                    if 'result' in parsed:
                        command.data = command.parser(parsed['result'])
                    else:
                        command.data = None

                    if command.callback:
                        command.callback(command)
            print 'JSD: Command response with ID ' + str(parsed['id'])

    def open_callback(self, ws):
        if self.on_open:
            self.on_open()
        print 'JSD: WebSocket opened'

    def close_callback(self, ws):
        if self.on_close:
            self.on_close()
        print 'JSD: WebSocket closed'


class JsDebugCommand(sublime_plugin.TextCommand):
    '''
    The Jsdebug main quick panel menu
    '''
    def run(self, edit):
        mapping = {}
        try:
            urllib2.urlopen('http://127.0.0.1:' + get_setting('chrome_remote_port') + '/json/')

            mapping = {
                'js_debug_clear_console': 'Clear console',
                'js_debug_breakpoint': 'Add/Remove Breakpoint',
                'js_debug_resume': 'Resume execution',

                'js_debug_clear_all_breakpoint': 'Clear all Breakpoints'
            }

            if protocol:
                mapping['js_debug_stop'] = 'Stop debugging'
            else:
                mapping['js_debug_start'] = 'Start debugging'
        except:
            mapping['js_debug_start_chrome'] = 'Start Chrome with remote debug port ' + get_setting('chrome_remote_port')

        self.cmds = mapping.keys()
        self.items = mapping.values()
        self.view.window().show_quick_panel(self.items, self.command_selected)

    def command_selected(self, index):
        if index == -1:
            return

        command = self.cmds[index]

        if command == 'js_debug_start':
            response = urllib2.urlopen('http://127.0.0.1:' + get_setting('chrome_remote_port') + '/json/')
            pages = json.loads(response.read())
            mapping = {}
            for page in pages:
                if 'webSocketDebuggerUrl' in page:
                    if page['url'].find('chrome-extension://') == -1:
                        mapping[page['webSocketDebuggerUrl']] = page['url']

            self.urls = mapping.keys()
            items = mapping.values()
            self.view.window().show_quick_panel(items, self.remote_debug_url_selected)
            return

        self.view.run_command(command)

    def remote_debug_url_selected(self, index):
        if index == -1:
            return

        url = self.urls[index]

        window = sublime.active_window()
        global original_layout
        original_layout = window.get_layout()

        #window.run_command("show_panel", {"panel": "output.console"})

        global debug_view
        debug_view = window.active_view()


        window.set_layout({
             "cols": [0.0, 1.0],
             "rows": [0.0, 0.7, 1.0],
             "cells": [[0, 0, 1, 1], [0, 1, 1, 2]]
        })
        views = window.views()
        load_breaks()
        self.view.run_command('js_debug_start', {'url': url})



class JsDebugStartChromeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        window = sublime.active_window()

        window.run_command('exec', {
            "cmd": [get_setting('chrome_path')[sublime.platform()], '--remote-debugging-port=' + get_setting('chrome_remote_port')]
        })


class JsDebugStartCommand(sublime_plugin.TextCommand):

    '''
    Start listening for Xdebug connections
    '''
    def run(self, edit, url):
        print 'Starting JSD'
        self.url = url
        global protocol
        if(protocol):
            print 'JSD: Socket closed'
            protocol.socket.close()
        else:
            print 'JSD: Creating protocol'
            protocol = Protocol()
            protocol.connect(self.url, self.connected)

    def connected(self):
        protocol.subscribe(wip.Console.messageAdded(), self.messageAdded)
        protocol.subscribe(wip.Console.messageRepeatCountUpdate(), self.messageRepeatCountUpdate)
        protocol.subscribe(wip.Console.messagesCleared(), self.messagesCleared)
        protocol.subscribe(wip.Debugger.scriptParsed(), self.scriptParsed)
        protocol.send(wip.Console.enable())
        protocol.send(wip.Debugger.enable())

    def messageAdded(self, data, notification):
        sublime.set_timeout(lambda: add_debug_info('console', str(data)), 0)

    def messageRepeatCountUpdate(self, data, notification):
        sublime.set_timeout(lambda: add_debug_info('console_repeat', data), 0)

    def messagesCleared(self, data, notification):
        sublime.set_timeout(lambda: add_debug_info('console', 'clear'), 0)

    def scriptParsed(self, data, notification):
        if data['url'] != '':
            file_name = data['url'].split('/')[-1]
            scriptId = str(data['scriptId'])
            fileName_scriptId[file_name] = scriptId
            scriptId_fileName[str(scriptId)] = file_name

            for line in get_breakpoints_by_file_name(file_name).keys():
                location = wip.Debugger.Location({'lineNumber': int(line), 'scriptId': scriptId})
                protocol.send(wip.Debugger.setBreakpoint(location), self.breakpointAdded)

    def breakpointAdded(self, command):
        breakpointId = command.data['breakpointId']
        scriptId = command.data['actualLocation'].scriptId
        lineNumber = command.data['actualLocation'].lineNumber

        try:
            breakpoint = get_breakpoints_by_scriptId(str(scriptId))[str(lineNumber)]
            breakpoint['status'] = 'enabled'
            breakpoint['breakpointId'] = str(breakpointId)
        except:
            pass

        try:
            breaks = get_breakpoints_by_scriptId(str(scriptId))[str(lineNumber)]

            lineNumber = str(lineNumber)
            lineNumberSend = str(command.params['lineNumber'])

            if lineNumberSend in breaks and lineNumber != lineNumberSend:
                breaks[lineNumber] = breaks[lineNumberSend].copy()
                del breaks[lineNumberSend]

            breaks[lineNumber]['status'] = 'enabled'
            breaks[lineNumber]['breakpointId'] = str(breakpointId)
        except:
            pass

        sublime.set_timeout(lambda: save_breaks(), 0)
        sublime.set_timeout(lambda: lookup_view(self.view).view_breakpoints(), 0)



class JsDebugClearConsoleCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        sublime.set_timeout(lambda: add_debug_info('console', 'clear'), 0)


class JsDebugBreakpointCommand(sublime_plugin.TextCommand):
    '''
    Toggle a breakpoint
    '''
    def run(self, edit):
        view = lookup_view(self.view)
        row = str(view.rows(view.lines())[0])
        init_breakpoint_for_file(view.file_name())
        breaks = get_breakpoints_by_file_path(view.file_name())
        if row in breaks:
            if protocol:
                if row in breaks:
                    protocol.send(wip.Debugger.removeBreakpoint(breaks[row]['breakpointId']))

            del_breakpoint_by_file_path(view.file_name(), row)
        else:
            if protocol:
                if full_path_to_file_name(self.view.file_name()) in fileName_scriptId:
                    location = wip.Debugger.Location({'lineNumber': int(row), 'scriptId': fileName_scriptId[full_path_to_file_name(self.view.file_name())]})
                    protocol.send(wip.Debugger.setBreakpoint(location), self.breakpointAdded, view.file_name())
            else:
                set_breakpoint_by_file_path(view.file_name(), row)

        view.view_breakpoints()

    def breakpointAdded(self, command):
        print command.data
        breakpointId = command.data['breakpointId']
        scriptId = command.data['actualLocation'].scriptId
        lineNumber = command.data['actualLocation'].lineNumber

        init_breakpoint_for_file(command.options)

        sublime.set_timeout(lambda: set_breakpoint_by_scriptId(str(scriptId), str(lineNumber), 'enabled', breakpointId), 0)
        # Scroll to position where breakpoints have resolved
        sublime.set_timeout(lambda: lookup_view(self.view).view_breakpoints(), 0)



class JsDebugStopCommand(sublime_plugin.TextCommand):

    '''
    Start listening for Xdebug connections
    '''
    def run(self, edit):
        window = sublime.active_window()

        window.focus_group(1)
        window.run_command("close")

        window.set_layout(original_layout)

        disable_all_breakpoints()

        lookup_view(self.view).view_breakpoints()

        global protocol
        if protocol:
            try:
                protocol.socket.close()
            except:
                print 'JSD: Can\'t close soket'
            finally:
                protocol = None


class JsDebugView(object):
    '''
    The JsDebugView is sort of a normal view with some convenience methods.

    See lookup_view.
    '''
    def __init__(self, view):
        self.view = view
        self.current_line = None
        self.context_data = {}

    def __getattr__(self, attr):

        if hasattr(self.view, attr):
            return getattr(self.view, attr)
        if attr.startswith('on_'):
            return self
        raise(AttributeError, "%s does not exist" % attr)

    def __call__(self, *args, **kwargs):
        pass

    # def add_breakpoint(self, row, status='disabled', bid=None):
    #     file_name = os.path.basename(os.path.realpath(self.view.file_name()))
    #     if not row in self.breaks:
    #         self.breaks[row] = {}
    #         self.breaks[row]['status'] = status
    #         self.breaks[row]['breakpointId'] = str(bid)
    #     self.view_breakpoints()
    #     save_breaks()

    # def del_breakpoint(self, row):
    #     file_name = os.path.basename(os.path.realpath(self.view.file_name()))
    #     if row in self.breaks:
    #         del self.breaks[row]
    #     self.view_breakpoints()
    #     save_breaks()

    def uri(self):
        return 'file://' + os.path.realpath(self.view.file_name())

    def lines(self, data=None):
        lines = []
        if data is None:
            regions = self.view.sel()
        else:
            if type(data) != types.ListType:
                data = [data]
            regions = []
            for item in data:
                if type(item) == types.IntType or item.isdigit():
                    regions.append(self.view.line(self.view.text_point(int(item) - 1, 0)))
                else:
                    regions.append(item)
        for region in regions:
            lines.extend(self.view.split_by_newlines(region))
        return [self.view.line(line) for line in lines]

    def rows(self, lines):
        if not type(lines) == types.ListType:
            lines = [lines]
        return [self.view.rowcol(line.begin())[0] + 1 for line in lines]

    def view_breakpoints(self):
        self.view.erase_regions('jsd_breakpoint_inactive')
        self.view.erase_regions('jsd_breakpoint_active')

        if not self.view.file_name():
            return

        breaks = get_breakpoints_by_file_path(self.view.file_name())

        if not breaks:
            return

        enabled = []
        disabled = []

        for key in breaks.keys():
            if breaks[key]['status'] == 'enabled':
                enabled.append(key)
            if breaks[key]['status'] == 'disabled':
                disabled.append(key)

        self.view.add_regions('jsd_breakpoint_active', self.lines(enabled), get_setting('breakpoint_scope'), breakpoint_active_icon, sublime.HIDDEN)
        self.view.add_regions('jsd_breakpoint_inactive', self.lines(disabled), get_setting('breakpoint_scope'), breakpoint_inactive_icon, sublime.HIDDEN)


class EventListener(sublime_plugin.EventListener):
    def on_new(self, view):
        lookup_view(view).on_new()

    def on_clone(self, view):
        lookup_view(view).on_clone()

    def on_load(self, view):
        lookup_view(view).view_breakpoints()
        lookup_view(view).on_load()

    def on_close(self, view):
        lookup_view(view).on_close()

    def on_pre_save(self, view):
        lookup_view(view).on_pre_save()

    def on_post_save(self, view):
        if protocol:
            protocol.send(Network.clearBrowserCache())
            if view.file_name().find('.css') == -1 and view.file_name().find('.less') == -1:
                protocol.send(Page.reload())
            else:
                protocol.send(Runtime.evaluate('$$JSD_reloadAll()'))
        lookup_view(view).on_post_save()

    def on_modified(self, view):
        lookup_view(view).on_modified()
        lookup_view(view).view_breakpoints()

    def on_selection_modified(self, view):
        lookup_view(view).on_selection_modified()

# [L] Components.js:832 {Object_25_5}
# [L] Components.js:832 {Object_25_6}
# [L] Components.js:832 {Object_25_7}

        selection = view.substr(view.sel()[0])
        if selection.startswith('Object'):
            parts = selection.split('_')
            if len(parts) == 3:# and protocol and protocol.last_log_object != selection:
                try:
                    objid = wip.Runtime.RemoteObjectId('')
                    print objid.loads(selection)
                    protocol.send()
                    protocol.socket.send(json.dumps({'id': 603, 'method': 'Runtime.getProperties', 'params': {'objectId': objid, 'ownProperties': True}}))
                    protocol.last_log_object = selection
                finally:
                    return

    def on_activated(self, view):
        lookup_view(view).on_activated()
        lookup_view(view).view_breakpoints()

    def on_deactivated(self, view):
        lookup_view(view).on_deactivated()

    def on_query_context(self, view, key, operator, operand, match_all):
        lookup_view(view).on_query_context(key, operator, operand, match_all)


# class EventListener(sublime_plugin.EventListener):
#     def on_load(self, view):
#         lookup_view(view).on_load()
#         lookup_view(view).on_load()

#     def on_pre_save(self, view):
#         lookup_view(view).on_pre_save()

#     def on_post_save(self, view):
#         # if protocol:
#         #     protocol.socket.send(json.dumps({'id': 303, 'method': 'Network.clearBrowserCache'}))
#         #     if view.file_name().find('.css') == -1 and view.file_name().find('.less') == -1:
#         #         print 'reload'
#         #         protocol.socket.send(json.dumps({'id': 504, 'method': 'Page.reload'}))
#         #     else:
#         #         print 'reload css'
#         #         protocol.socket.send(json.dumps({'id': 602, 'method': 'Runtime.evaluate', 'params': {'expression': '$$JSD_reloadAll()'}}))
#         lookup_view(view).on_post_save()

#     # def on_selection_modified(self, view):
#     #     selection = view.substr(view.sel()[0])
#     #     if selection.startswith('Object'):
#     #         parts = selection.split('_')
#     #         if len(parts) == 3 and protocol and protocol.last_log_object != selection:
#     #             try:
#     #                 objid = text_to_objectid(selection)
#     #                 protocol.socket.send(json.dumps({'id': 603, 'method': 'Runtime.getProperties', 'params': {'objectId': objid, 'ownProperties': True}}))
#     #                 protocol.last_log_object = selection
#     #             finally:
#     #                 return


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


def get_setting(key):
    '''
    Get Xdebug setting
    '''
    s = sublime.load_settings("jsd.sublime-settings")
    if s and s.has(key):
        return s.get(key)


def add_debug_info(name, data):
    '''
    Adds data to the debug output windows
    '''
    found = False
    v = None
    window = sublime.active_window()

    if name.startswith('console'):
        group = 1
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
        v.set_syntax_file('Packages/JSD/jsd_log.tmLanguage')
        found = True
        window.focus_view(debug_view)

    size_before = v.size()
    if found:
        v.set_read_only(False)
        window.set_view_index(v, group, 0)
        edit = v.begin_edit()
        if name == "console_repeat":
            if data > 2:
                erase_to = v.size() - len(u' \u21AA Repeat:' + str(data - 1) + '\n')
                v.erase(edit, sublime.Region(erase_to, v.size()))
            v.insert(edit, v.size(), u' \u21AA Repeat:' + str(data) + '\n')
            v.show(v.size())
        elif name == "console_stack":
            v.insert(edit, v.size(), data)
            v.insert(edit, v.size(), '\n')
            v.show(v.size())
        elif name == "console":
            v.insert(edit, v.size(), data)
            v.insert(edit, v.size(), '\n')
            v.show(v.size())
            #v.erase(edit, sublime.Region(0, v.size()))
            #v.insert(edit, 0, data)
        elif name == "console_getprop":
            selection = v.sel()[0]
            tabs_count = v.substr(v.line(selection)).count("\t")
            v.erase(edit, selection)
            v.insert(edit, selection.a, '\n')
            v.insert(edit, selection.a + 1, data)
            v.insert(edit, selection.a + 1 + len(data), '\n')
            if tabs_count - 1 >= 0:
                v.insert(edit, selection.a + 1 + len(data) + 1, '\t' * (tabs_count - 1))
            line_counter = 0
            for line in v.lines(sublime.Region(selection.a + 1, selection.a + 1 + len(data))):
                v.insert(edit, line.a + line_counter, '\t' * (tabs_count + 1))
                line_counter += tabs_count + 1
            window.run_command("indent")
            v.show(selection.begin())
        if data == 'clear':
            v.erase(edit, sublime.Region(0, v.size()))

        v.end_edit(edit)
        v.set_read_only(False)

        size_after = v.size()

        if name == "console_stack":
            v.fold(sublime.Region(size_before - 1, size_after - 1))

    window.focus_group(0)


def get_project():
    win_id = sublime.active_window().id()
    project = None
    reg_session = os.path.join(sublime.packages_path(), "..", "Settings", "Session.sublime_session")
    auto_save = os.path.join(sublime.packages_path(), "..", "Settings", "Auto Save Session.sublime_session")
    session = auto_save if os.path.exists(auto_save) else reg_session

    if not os.path.exists(session) or win_id == None:
        return project

    try:
        with open(session, 'r') as f:
            # Tabs in strings messes things up for some reason
            j = json.JSONDecoder(strict=False).decode(f.read())
            for w in j['windows']:
                if w['window_id'] == win_id:
                    if "workspace_name" in w:
                        if sublime.platform() == "windows":
                            # Account for windows specific formatting
                            project = os.path.normpath(w["workspace_name"].lstrip("/").replace("/", ":/", 1))
                        else:
                            project = w["workspace_name"]
                        break
    except:
        pass

    # Throw out empty project names
    if project == None or re.match(".*\\.sublime-project", project) == None or not os.path.exists(project):
        project = None

    return project


##############
#####################
##########################       All about breaks
#####################
##############

def load_breaks():
    breaks_file = os.path.splitext(get_project())[0] + '-breaks.json'
    global brk_object
    if not os.path.exists(breaks_file):
        with open(breaks_file, 'w') as f:
            f.write('{}')

    try:
        with open(breaks_file, 'r') as f:
            brk_object = json.loads(f.read())
    except:
        brk_object = {}


def save_breaks():
    print brk_object
    breaks_file = os.path.splitext(get_project())[0] + '-breaks.json'
    try:
        with open(breaks_file, 'w') as f:
            f.write(json.dumps(brk_object))
    except:
        pass

    #print breaks


def full_path_to_file_name(path):
    return os.path.basename(os.path.realpath(path))


def set_breakpoint_by_file_name(file_name, line, status='disabled', breakpointId=None):
    breaks = get_breakpoints_by_file_name(file_name)

    if not line in breaks:
        breaks[line] = {}
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
    else:
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
    save_breaks()


def del_breakpoint_by_file_name(file_name, line):
    breaks = get_breakpoints_by_file_name(file_name)

    if line in breaks:
        del breaks[line]
    save_breaks()


def get_breakpoints_by_file_name(file_name):
    for file_path in brk_object:
        file_name_in_breaks = full_path_to_file_name(file_path)
        if file_name_in_breaks == file_name:
            return brk_object[file_path]

    return None


def set_breakpoint_by_scriptId(scriptId, line, status='disabled', breakpointId=None):
    file_name = scriptId_fileName[str(scriptId)]
    if file_name:
        set_breakpoint_by_file_name(file_name, line, status, breakpointId)


def del_breakpoint_by_scriptId(scriptId, line):
    file_name = scriptId_fileName[str(scriptId)]
    if file_name:
        del_breakpoint_by_file_name(file_name, line)


def get_breakpoints_by_scriptId(scriptId):
    file_name = scriptId_fileName[str(scriptId)]
    if file_name:
        return get_breakpoints_by_file_name(file_name)

    return None


def set_breakpoint_by_file_path(file_path, line, status='disabled', breakpointId=None):
    set_breakpoint_by_file_name(full_path_to_file_name(file_path), line, status, breakpointId)


def del_breakpoint_by_file_path(file_path, line):
    del_breakpoint_by_file_name(full_path_to_file_name(file_path), line)


def get_breakpoints_by_file_path(file_path):
    return get_breakpoints_by_file_name(full_path_to_file_name(file_path))


def init_breakpoint_for_file(file_path):
    if not file_path in brk_object:
        brk_object[file_path] = {}


def disable_all_breakpoints():
    for file_name in brk_object:
        for line in brk_object[file_name]:
            brk_object[file_name][line]['status'] = 'disabled'
            del brk_object[file_name][line]['breakpointId']

    save_breaks()

load_breaks()

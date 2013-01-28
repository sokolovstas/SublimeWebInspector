from array import array
import hashlib
import functools
import glob
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
window = None
debug_view = None
debug_url = None
file_to_scriptId = []
project_folders = []
last_clicked = None
paused = False
current_line = None


# scriptId_fileName = {}

breakpoint_active_icon = '../SublimeWebInspector/icons/breakpoint_active'
breakpoint_inactive_icon = '../SublimeWebInspector/icons/breakpoint_inactive'
breakpoint_current_icon = '../SublimeWebInspector/icons/breakpoint_current'


####################################################################################
#   PROTOCOL
####################################################################################

# Define protocol to communicate with remote debugger by web sockets
class Protocol(object):
    def __init__(self):
        self.next_id = 0
        self.commands = {}
        self.notifications = {}
        self.last_log_object = None

    def connect(self, url, on_open=None, on_close=None):
        print 'SWI: Connecting to ' + url
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
        print 'SWI: Thread started'
        self.socket = websocket.WebSocketApp(self.url, on_message=self.message_callback, on_open=self.open_callback, on_close=self.close_callback)
        self.socket.run_forever()
        print 'SWI: Thread stoped'

    # send command and increment command counter
    def send(self, command, callback=None, options=None):
        command.id = self.next_id
        command.callback = callback
        command.options = options
        self.commands[command.id] = command
        self.next_id += 1
        print 'SWI: ->> ' + json.dumps(command.request)
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
        # print 'SWI: <<- ' + message
        # print ''
        if 'method' in parsed:
            if parsed['method'] in self.notifications:
                notification = self.notifications[parsed['method']]
                if 'params' in parsed:
                    data = notification.parser(parsed['params'])
                else:
                    data = None
                notification.callback(data, notification)
            else:
                print 'SWI: New unsubscrib notification --- ' + parsed['method']
        else:
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
            print 'SWI: Command response with ID ' + str(parsed['id'])

    def open_callback(self, ws):
        if self.on_open:
            self.on_open()
        print 'SWI: WebSocket opened'

    def close_callback(self, ws):
        if self.on_close:
            self.on_close()
        print 'SWI: WebSocket closed'


####################################################################################
#   COMMANDS
####################################################################################

class SwiDebugCommand(sublime_plugin.TextCommand):
    '''
    The SWIdebug main quick panel menu
    '''
    def run(self, editswi):
        mapping = {}
        try:
            urllib2.urlopen('http://127.0.0.1:' + get_setting('chrome_remote_port') + '/json/')

            mapping = {}
            mapping['swi_debug_clear_console'] = 'Clear console'

            if paused:
                mapping['swi_debug_resume'] = 'Resume execution'
                mapping['swi_debug_step_into'] = 'Step into'
                mapping['swi_debug_step_out'] = 'Step out'
                mapping['swi_debug_step_over'] = 'Step over'
            else:
                #mapping['swi_debug_clear_all_breakpoint'] = 'Clear all Breakpoints'
                mapping['swi_debug_breakpoint'] = 'Add/Remove Breakpoint'

            if protocol:
                mapping['swi_debug_stop'] = 'Stop debugging'
                mapping['swi_debug_reload'] = 'Reload page'
            else:
                mapping['swi_debug_start'] = 'Start debugging'
        except:
            mapping['swi_debug_start_chrome'] = 'Start Google Chrome with remote debug port ' + get_setting('chrome_remote_port')

        self.cmds = mapping.keys()
        self.items = mapping.values()
        self.view.window().show_quick_panel(self.items, self.command_selected)

    def command_selected(self, index):
        if index == -1:
            return

        command = self.cmds[index]

        if command == 'swi_debug_start':
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

        global window
        window = sublime.active_window()
        
        global original_layout
        original_layout = window.get_layout()

        global debug_view
        debug_view = window.active_view()

        window.set_layout(get_setting('console_layout'))
        views = window.views()

        load_breaks()
        self.view.run_command('swi_debug_start', {'url': url})


class SwiDebugStartChromeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        window = sublime.active_window()

        window.run_command('exec', {
            "cmd": [get_setting('chrome_path')[sublime.platform()], '--remote-debugging-port=' + get_setting('chrome_remote_port')]
        })


class SwiDebugStartCommand(sublime_plugin.TextCommand):

    def run(self, edit, url):
        file_to_scriptId = []
        window = sublime.active_window()
        global project_folders
        project_folders = window.folders()
        print 'Starting SWI'
        self.url = url
        global protocol
        if(protocol):
            print 'SWI: Socket closed'
            protocol.socket.close()
        else:
            print 'SWI: Creating protocol'
            protocol = Protocol()
            protocol.connect(self.url, self.connected)

    def connected(self):
        protocol.subscribe(wip.Console.messageAdded(), self.messageAdded)
        protocol.subscribe(wip.Console.messageRepeatCountUpdate(), self.messageRepeatCountUpdate)
        protocol.subscribe(wip.Console.messagesCleared(), self.messagesCleared)
        protocol.subscribe(wip.Debugger.scriptParsed(), self.scriptParsed)
        protocol.subscribe(wip.Debugger.paused(), self.paused)
        protocol.subscribe(wip.Debugger.resumed(), self.resumed)
        protocol.send(wip.Debugger.enable())
        protocol.send(wip.Console.enable())

    def messageAdded(self, data, notification):
        sublime.set_timeout(lambda: console_add_message(data), 0)

    def messageRepeatCountUpdate(self, data, notification):
        sublime.set_timeout(lambda: console_repeat_message(count), 0)

    def messagesCleared(self, data, notification):
        sublime.set_timeout(lambda: console_clear(), 0)

    def scriptParsed(self, data, notification):
        url = data['url']
        if url != '':
            url_parts = url.split("/")
            scriptId = str(data['scriptId'])
            file_name = ''

            del url_parts[0:3]
            while len(url_parts) > 0:
                for folder in project_folders:
                    if sublime.platform() == "windows":
                        files = glob.glob(folder + "\\" + "\\".join(url_parts))
                    else:
                        files = glob.glob(folder + "/" + "/".join(url_parts))
                        
                    if len(files) > 0 and files[0] != '':
                        file_name = files[0]
                        file_to_scriptId.append({'file': file_name, 'scriptId': str(scriptId), 'sha1': hashlib.sha1(data['url']).hexdigest()})
                del url_parts[0]

            if get_breakpoints_by_full_path(file_name):
                for line in get_breakpoints_by_full_path(file_name).keys():
                    location = wip.Debugger.Location({'lineNumber': int(line), 'scriptId': scriptId})
                    protocol.send(wip.Debugger.setBreakpoint(location), self.breakpointAdded)

    def paused(self, data, notification):
        sublime.set_timeout(lambda: window.set_layout(get_setting('stack_layout')), 0)

        sublime.set_timeout(lambda: console_show_stack(data['callFrames']), 0)

        scriptId = data['callFrames'][0].location.scriptId
        line_number = data['callFrames'][0].location.lineNumber
        file_name = find_script(str(scriptId))
        first_scope = data['callFrames'][0].scopeChain[0]
        virtual_click = {'objectId': first_scope.object.objectId, 'name': "%s:%s (%s)" % (file_name, line_number, first_scope.type)}

        sublime.set_timeout(lambda: protocol.send(wip.Runtime.getProperties(first_scope.object.objectId, True), console_add_properties, virtual_click), 30)
        sublime.set_timeout(lambda: open_script_and_focus_line(scriptId, line_number), 100)

        global paused
        paused = True

    def resumed(self, data, notification):
        sublime.set_timeout(lambda: window.focus_group(2), 0)
        sublime.set_timeout(lambda: window.run_command("close"), 0)
        sublime.set_timeout(lambda: window.set_layout(get_setting('console_layout')), 0)

        global current_line
        current_line = None

        sublime.set_timeout(lambda: lookup_view(self.view).view_breakpoints(), 50)

        global paused
        paused = False

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


class SwiDebugResumeCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        protocol.send(wip.Debugger.resume())


class SwiDebugStepIntoCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        protocol.send(wip.Debugger.stepInto())


class SwiDebugStepOutCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        protocol.send(wip.Debugger.stepOut())


class SwiDebugStepOverCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        protocol.send(wip.Debugger.stepOver())


class SwiDebugClearConsoleCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        sublime.set_timeout(lambda: console_clear(), 0)


class SwiDebugBreakpointCommand(sublime_plugin.TextCommand):
    '''
    Toggle a breakpoint
    '''
    def run(self, edit):
        view = lookup_view(self.view)
        row = str(view.rows(view.lines())[0])
        init_breakpoint_for_file(view.file_name())
        breaks = get_breakpoints_by_full_path(view.file_name())
        if row in breaks:
            if protocol:
                if row in breaks:
                    protocol.send(wip.Debugger.removeBreakpoint(breaks[row]['breakpointId']))

            del_breakpoint_by_full_path(view.file_name(), row)
        else:
            if protocol:
                scriptId = find_script(view.file_name())
                if scriptId:
                    location = wip.Debugger.Location({'lineNumber': int(row), 'scriptId': scriptId})
                    protocol.send(wip.Debugger.setBreakpoint(location), self.breakpointAdded, view.file_name())
            else:
                set_breakpoint_by_full_path(view.file_name(), row)

        view.view_breakpoints()

    def breakpointAdded(self, command):
        breakpointId = command.data['breakpointId']
        scriptId = command.data['actualLocation'].scriptId
        lineNumber = command.data['actualLocation'].lineNumber

        init_breakpoint_for_file(command.options)

        sublime.set_timeout(lambda: set_breakpoint_by_scriptId(str(scriptId), str(lineNumber), 'enabled', breakpointId), 0)
        # Scroll to position where breakpoints have resolved
        sublime.set_timeout(lambda: lookup_view(self.view).view_breakpoints(), 0)


class SwiDebugStopCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        window = sublime.active_window()

        window.focus_group(1)
        for view in window.views_in_group(1):
            window.run_command("close")

        window.focus_group(2)
        for view in window.views_in_group(2):
            window.run_command("close")

        window.set_layout(original_layout)

        disable_all_breakpoints()

        lookup_view(self.view).view_breakpoints()

        global paused
        paused = False

        global current_line
        current_line = None
        sublime.set_timeout(lambda: lookup_view(self.view).view_breakpoints(), 0)

        global protocol
        if protocol:
            try:
                protocol.socket.close()
            except:
                print 'SWI: Can\'t close soket'
            finally:
                protocol = None


class SwiDebugReloadCommand(sublime_plugin.TextCommand):
    def run(self, view):
        if(protocol):
            protocol.send(Network.clearBrowserCache())
            protocol.send(Page.reload())


####################################################################################
#   VIEW
####################################################################################

class SwiDebugView(object):
    '''
    The SWIDebugView is sort of a normal view with some convenience methods.

    See lookup_view.
    '''
    def __init__(self, view):
        self.view = view
        self.context_data = {}
        self.clicks = []
        self.prev_click_position = 0

    def __getattr__(self, attr):
        if hasattr(self.view, attr):
            return getattr(self.view, attr)
        if attr.startswith('on_'):
            return self
        raise(AttributeError, "%s does not exist" % attr)

    def __call__(self, *args, **kwargs):
        pass

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

    def insert_click(self, a, b, click_type, data):
        insert_before = 0
        new_region = sublime.Region(a, b)
        regions = self.view.get_regions('swi_log_clicks')
        for region in regions:
            if new_region.b < region.a:
                break
            insert_before += 1

        self.clicks.insert(insert_before, {'click_type': click_type, 'data': data})

        regions.append(new_region)
        self.view.add_regions('swi_log_clicks', regions, get_setting('interactive_scope'), sublime.DRAW_EMPTY_AS_OVERWRITE | sublime.DRAW_OUTLINED)

    def remove_click(self, index):
        regions = self.view.get_regions('swi_log_clicks')
        del regions[index]
        self.view.add_regions('swi_log_clicks', regions, get_setting('interactive_scope'), sublime.DRAW_EMPTY_AS_OVERWRITE | sublime.DRAW_OUTLINED)

    def view_breakpoints(self):
        self.view.erase_regions('swi_breakpoint_inactive')
        self.view.erase_regions('swi_breakpoint_active')
        self.view.erase_regions('swi_breakpoint_current')

        if not self.view.file_name():
            return

        breaks = get_breakpoints_by_full_path(self.view.file_name())

        if not breaks:
            return

        enabled = []
        disabled = []

        for key in breaks.keys():
            if breaks[key]['status'] == 'enabled' and str(current_line) != key:
                enabled.append(key)
            if breaks[key]['status'] == 'disabled' and str(current_line) != key:
                disabled.append(key)

        self.view.add_regions('swi_breakpoint_active', self.lines(enabled), get_setting('breakpoint_scope'), breakpoint_active_icon, sublime.HIDDEN)
        self.view.add_regions('swi_breakpoint_inactive', self.lines(disabled), get_setting('breakpoint_scope'), breakpoint_inactive_icon, sublime.HIDDEN)
        if current_line:
            self.view.add_regions('swi_breakpoint_current', self.lines([current_line]), get_setting('current_line_scope'), breakpoint_current_icon, sublime.DRAW_EMPTY)


def lookup_view(v):
    '''
    Convert a Sublime View into an SWIDebugView
    '''
    if isinstance(v, SwiDebugView):
        return v
    if isinstance(v, sublime.View):
        id = v.buffer_id()
        if id in buffers:
            buffers[id].view = v
        else:
            buffers[id] = SwiDebugView(v)
        return buffers[id]
    return None


####################################################################################
#   EventListener
####################################################################################

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
                protocol.send(Runtime.evaluate('$$SWI_reloadAll()'))
        lookup_view(view).on_post_save()

    def on_modified(self, view):
        lookup_view(view).on_modified()
        lookup_view(view).view_breakpoints()

    def on_selection_modified(self, view):
        lookup_view(view).on_selection_modified()

        if not view.name().startswith('SWI'):
            return

        v = lookup_view(view)
        cursor = view.sel()[0].a

        if cursor != v.prev_click_position:
            v.prev_click_position = cursor
            return

        click_counter = 0
        click_regions = view.get_regions('swi_log_clicks')
        for click in click_regions:
            if cursor > click.a and cursor < click.b:

                click = v.clicks[click_counter]

                if click['click_type'] == 'goto_file_line':
                    open_script_and_focus_line(click['data']['scriptId'], click['data']['line'])

                if click['click_type'] == 'get_params':
                    protocol.send(wip.Runtime.getProperties(click['data']['objectId'], True), console_add_properties, click['data'])
                    #v.remove_click(click_counter)

            click_counter += 1

    def on_activated(self, view):
        lookup_view(view).on_activated()
        lookup_view(view).view_breakpoints()

    def on_deactivated(self, view):
        lookup_view(view).on_deactivated()

    def on_query_context(self, view, key, operator, operand, match_all):
        lookup_view(view).on_query_context(key, operator, operand, match_all)


####################################################################################
#   Console
####################################################################################

def find_view(console_type, title=''):
    found = False
    v = None
    window = sublime.active_window()

    if console_type.startswith('console'):
        group = 1
        fullName = "SWI Console"

    if console_type == 'stack':
        group = 2
        fullName = "SWI Breakpoint stack"

    if console_type.startswith('eval'):
        group = 1
        fullName = "SWI Object evaluate"

    fullName = fullName + ' ' + title

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

    window.set_view_index(v, group, 0)

    if console_type.startswith('console'):
        v.set_syntax_file('Packages/SublimeWebInspector/swi_log.tmLanguage')

    if console_type == 'stack':
        v.set_syntax_file('Packages/SublimeWebInspector/swi_stack.tmLanguage')

    if console_type.startswith('eval'):
        v.set_syntax_file('Packages/SublimeWebInspector/swi_log.tmLanguage')

    window.focus_view(v)

    v.set_read_only(False)

    return lookup_view(v)


def console_clear():
    v = find_view('console')

    edit = v.begin_edit()

    v.erase(edit, sublime.Region(0, v.size()))

    v.end_edit(edit)
    v.show(v.size())


def console_repeat_message(count):
    v = find_view('console')

    edit = v.begin_edit()

    if count > 2:
        erase_to = v.size() - len(u' \u21AA Repeat:' + str(count - 1) + '\n')
        v.erase(edit, sublime.Region(erase_to, v.size()))
    v.insert(edit, v.size(), u' \u21AA Repeat:' + str(count) + '\n')

    v.end_edit(edit)
    v.show(v.size())


def console_add_message(message):
    v = find_view('console')

    edit = v.begin_edit()

    if message.level == 'debug':
        level = "D"
    if message.level == 'error':
        level = "E"
    if message.level == 'log':
        level = "L"
    if message.level == 'tip':
        level = "T"
    if message.level == 'warning':
        level = "W"

    v.insert(edit, v.size(), "[%s] " % (level))
    # Add file and line
    scriptId = None
    if message.url:
        scriptId = find_script(hashlib.sha1(message.url).hexdigest())
        if scriptId:
            url = message.url.split("/")[-1]
        else:
            url = message.url
    else:
        url = '---'

    if message.line:
        line = message.line
    else:
        line = 0

    insert_position = v.size()
    insert_length = v.insert(edit, insert_position, "%s:%d" % (url, line))

    if scriptId and line > 0:
        v.insert_click(insert_position, insert_position + insert_length, 'goto_file_line', {'scriptId': scriptId, 'line': str(line)})

    v.insert(edit, v.size(), " ")

    # Add text
    if len(message.parameters) > 0:
        for param in message.parameters:
            insert_position = v.size()
            insert_length = v.insert(edit, insert_position, str(param) + ' ')
            if param.type == 'object':
                v.insert_click(insert_position, insert_position + insert_length - 1, 'get_params', {'objectId': param.objectId})
    else:
        text = message.text

    v.insert(edit, v.size(), "\n")

    v.end_edit(edit)
    v.show(v.size())


def console_add_properties(command):
    sublime.set_timeout(lambda: console_print_properties(command), 0)


def console_print_properties(command):

    if 'name' in command.options:
        name = command.options['name']
    else:
        name = str(command.options['objectId'])

    if 'prev' in command.options:
        prev = command.options['prev'] + ' -> ' + name
    else:
        prev = name

    v = find_view('eval', name)

    edit = v.begin_edit()
    v.erase(edit, sublime.Region(0, v.size()))

    v.insert(edit, v.size(), prev)

    v.insert(edit, v.size(), "\n\n")

    for prop in command.data:
        v.insert(edit, v.size(), prop.name + ': ')
        insert_position = v.size()
        if(prop.value):
            insert_length = v.insert(edit, insert_position, str(prop.value) + '\n')
            if prop.value.type == 'object':
                v.insert_click(insert_position, insert_position + insert_length - 1, 'get_params', {'objectId': prop.value.objectId, 'name': prop.name, 'prev': prev})

    v.end_edit(edit)
    v.show(v.size())


def console_show_stack(callFrames):

    v = find_view('stack')

    edit = v.begin_edit()
    v.erase(edit, sublime.Region(0, v.size()))

    for callFrame in callFrames:
        line = str(callFrame.location.lineNumber)
        file_name = find_script(str(callFrame.location.scriptId))

        if file_name:
            file_name = file_name.split('/')[-1]
        else:
            file_name = '-'

        insert_position = v.size()
        insert_length = v.insert(edit, insert_position, "%s:%s" % (file_name, line))

        if file_name != '-':
            v.insert_click(insert_position, insert_position + insert_length, 'goto_file_line', {'scriptId': callFrame.location.scriptId, 'line': line})

        v.insert(edit, v.size(), " %s\n" % (callFrame.functionName))

        for scope in callFrame.scopeChain:
            v.insert(edit, v.size(), "\t")
            insert_position = v.size()
            insert_length = v.insert(edit, v.size(), "%s\n" % (scope.type))
            if scope.object.type == 'object':
                v.insert_click(insert_position, insert_position + insert_length - 1, 'get_params', {'objectId': scope.object.objectId, 'name': "%s:%s (%s)" % (file_name, line, scope.type)})

    v.end_edit(edit)
    v.show(v.size())


####################################################################################
#   All about breaks
####################################################################################


def get_project():
    if not sublime.active_window():
        return None
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


def load_breaks():
    if not get_project():
        sublime.error_message('Can\' load breaks')
        brk_object = {}
        return
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
    breaks_file = os.path.splitext(get_project())[0] + '-breaks.json'
    try:
        with open(breaks_file, 'w') as f:
            f.write(json.dumps(brk_object))
    except:
        pass

    #print breaks


def full_path_to_file_name(path):
    return os.path.basename(os.path.realpath(path))


def set_breakpoint_by_full_path(file_name, line, status='disabled', breakpointId=None):
    breaks = get_breakpoints_by_full_path(file_name)

    if not line in breaks:
        breaks[line] = {}
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
    else:
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
    save_breaks()


def del_breakpoint_by_full_path(file_name, line):
    breaks = get_breakpoints_by_full_path(file_name)

    if line in breaks:
        del breaks[line]
    save_breaks()


def get_breakpoints_by_full_path(file_name):
    if file_name in brk_object:
        return brk_object[file_name]

    return None


def set_breakpoint_by_scriptId(scriptId, line, status='disabled', breakpointId=None):
    file_name = find_script(str(scriptId))
    if file_name:
        set_breakpoint_by_full_path(file_name, line, status, breakpointId)


def del_breakpoint_by_scriptId(scriptId, line):
    file_name = find_script(str(scriptId))
    if file_name:
        del_breakpoint_by_full_path(file_name, line)


def get_breakpoints_by_scriptId(scriptId):
    file_name = find_script(str(scriptId))
    if file_name:
        return get_breakpoints_by_full_path(file_name)

    return None


def init_breakpoint_for_file(file_path):
    if not file_path in brk_object:
        brk_object[file_path] = {}


def disable_all_breakpoints():
    for file_name in brk_object:
        for line in brk_object[file_name]:
            brk_object[file_name][line]['status'] = 'disabled'
            if 'breakpointId' in brk_object[file_name][line]:
                del brk_object[file_name][line]['breakpointId']

    save_breaks()


####################################################################################
#   Utils
####################################################################################

def get_setting(key):
    s = sublime.load_settings("swi.sublime-settings")
    if s and s.has(key):
        return s.get(key)


def find_script(scriptId_or_file_or_sha1):
    for item in file_to_scriptId:
        if item['scriptId'] == scriptId_or_file_or_sha1:
            return item['file']
        if item['file'] == scriptId_or_file_or_sha1:
            return item['scriptId']
        if item['sha1'] == scriptId_or_file_or_sha1:
            return item['scriptId']

    return None


def do_when(conditional, callback, *args, **kwargs):
    if conditional():
        return callback(*args, **kwargs)
    sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)


def open_script_and_focus_line(scriptId, line_number):
    file_name = find_script(str(scriptId))
    window = sublime.active_window()
    window.focus_group(0)
    view = window.open_file(file_name, sublime.TRANSIENT)
    do_when(lambda: not view.is_loading(), lambda: view.run_command("goto_line", {"line": line_number}))


def open_script_and_show_current_breakpoint(scriptId, line_number):
    print scriptId
    print line_number
    file_name = find_script(str(scriptId))
    window.focus_group(0)
    view = window.open_file(file_name, sublime.TRANSIENT)
    do_when(lambda: not view.is_loading(), lambda: view.run_command("goto_line", {"line": line_number}))
    #do_when(lambda: not view.is_loading(), lambda: focus_line_and_highlight(view, line_number))


def focus_line_and_highlight(view, line_number):
    view.run_command("goto_line", {"line": line_number})
    global current_line
    current_line = line_number
    lookup_view(view).view_breakpoints()

sublime.set_timeout(lambda: load_breaks(), 1000)
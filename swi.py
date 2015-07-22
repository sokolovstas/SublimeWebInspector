import hashlib
import functools
import glob
import sublime
import sublime_plugin
import urllib.request, urllib.parse, urllib.error
import threading
import json
import types
import os
import re
import time
import sys
import imp

swi_folder = os.path.dirname(os.path.realpath(__file__))
if not swi_folder in sys.path:
    sys.path.append(swi_folder)

import webkit
import protocol

from webkit import utils
from webkit import Console
from webkit import Runtime
from webkit import Debugger
from webkit import Network
from webkit import Page

imp.reload(sys.modules['webkit.utils'])
imp.reload(sys.modules['webkit.Console'])
imp.reload(sys.modules['webkit.Runtime'])
imp.reload(sys.modules['webkit.Debugger'])
imp.reload(sys.modules['webkit.Network'])
imp.reload(sys.modules['webkit.Page'])

brk_object = {}
buffers = {}
channel = None
original_layout = None
window = None
file_to_scriptId = []
paused = False
current_line = None
set_script_source = False
current_call_frame = None
current_call_frame_position = None
main_thread = None

breakpoint_active_icon = 'Packages/Web Inspector/icons/breakpoint_active.png'
breakpoint_inactive_icon = 'Packages/Web Inspector/icons/breakpoint_inactive.png'
breakpoint_current_icon = 'Packages/Web Inspector/icons/breakpoint_current.png'

def plugin_loaded():
    global main_thread
    main_thread = threading.current_thread()
    close_all_our_windows()
    clear_all_views()
        
####################################################################################
#   COMMANDS
####################################################################################

class SwiDebugCommand(sublime_plugin.WindowCommand):
    """ The SWIdebug main quick panel menu 
    """
    
    def run(self):
        """ Called by Sublime to display the quick panel entries """
        mapping = {}
        try:
            if not paused and not channel:
                proxy = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy)
                urllib.request.install_opener(opener)
                urllib.request.urlopen('http://127.0.0.1:' + get_setting('chrome_remote_port') + '/json')

            mapping = {}

            if paused:
                mapping['swi_debug_pause_resume'] = 'Resume (F8)'
                mapping['swi_debug_step_into'] = 'Step in (F11)'
                mapping['swi_debug_step_out'] = 'Step out (Shift + F11)'
                mapping['swi_debug_step_over'] = 'Step over (F10)'
            elif channel:
                mapping['swi_debug_pause_resume'] = 'Pause (F8)'

            mapping['swi_debug_toggle_breakpoint'] = 'Toggle Breakpoint'

            if channel:
                mapping['swi_debug_evaluate'] = 'Evaluate selection'
                mapping['swi_debug_clear_console'] = 'Clear console'
                mapping['swi_debug_stop'] = 'Stop debugging'
                mapping['swi_debug_reload'] = 'Reload page'
                mapping['swi_show_file_mappings'] = 'Show file mappings'
                mapping['swi_debug_clear_breakpoints'] = 'Clear all Breakpoints'
            else:
                mapping['swi_debug_start'] = 'Start debugging'
        except:
            mapping['swi_debug_start_chrome'] = 'Start Google Chrome with remote debug port ' + get_setting('chrome_remote_port')

        self.cmds = list(mapping.keys())
        self.items = list(mapping.values())
        self.window.show_quick_panel(self.items, self.command_selected)

    def command_selected(self, index):
        """ Called by Sublime when a quick panel entry is selected """
        assert_main_thread()
        if index == -1:
            return

        command = self.cmds[index]

        if command == 'swi_show_file_mappings':
            # we wrap this command so we can use the correct view
            v = find_view('mapping')
            v.run_command('swi_show_file_mappings_internal')
            return

        if command == 'swi_debug_start':
            proxy = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy)
            urllib.request.install_opener(opener)
            response = urllib.request.urlopen('http://127.0.0.1:' + get_setting('chrome_remote_port') + '/json')
            pages = json.loads(response.read().decode('utf-8'))
            mapping = {}
            for page in pages:
                if 'webSocketDebuggerUrl' in page:
                    if page['url'].find('chrome-extension://') == -1:
                        mapping[page['webSocketDebuggerUrl']] = page['url']

            self.urls = list(mapping.keys())
            items = list(mapping.values())
            self.window.show_quick_panel(items, self.remote_debug_url_selected)
            return

        self.window.run_command(command)

    def remote_debug_url_selected(self, index):
        assert_main_thread()
        if index == -1:
            return

        url = self.urls[index]

        global window
        window = sublime.active_window()

        global original_layout
        original_layout = window.get_layout()

        window.set_layout(get_setting('console_layout'))

        load_breaks()
        self.window.run_command('swi_debug_start', {'url': url})


class SwiDebugStartChromeCommand(sublime_plugin.WindowCommand):
    """ Represents the start chrome command """

    def run(self):
        assert_main_thread()
        close_all_our_windows()

        window = sublime.active_window()
        key = sublime.platform()

        # sublime.arch() is x86 on x64 Windows, presumably because it's a 32 bit app
        if key == "windows" and (sublime.arch() == "x64" or sublime.executable_path().find('(x86)') >= 0):
            key += "_x64"

        url = get_setting('chrome_url')
        if url == None:
            url = ''

        self.window.run_command('exec', {
            "cmd": [os.getenv('GOOGLE_CHROME_PATH', '') + get_setting('chrome_path')[key], '--remote-debugging-port=' + get_setting('chrome_remote_port'), '--profile-directory=' + get_setting('chrome_profile'), url, '']
        })


class SwiDebugStartCommand(sublime_plugin.WindowCommand):
    """ Connect to the socket. """

    def run(self, url):
        assert_main_thread()

        close_all_our_windows()

        global debugger_enabled
        debugger_enabled = False
        global file_to_scriptId
        file_to_scriptId = []
        self.project_folders = self.window.folders()
        print ('Starting SWI')
        self.url = url
        global channel
        if(channel):
            print ('SWI: Socket closed')
            channel.socket.close()
        else:
            print ('SWI: Creating protocol')
            channel = protocol.Protocol()
            channel.connect(self.url, self.connected, self.disconnected)

        global set_script_source
        set_script_source = get_setting('set_script_source')

    def connected(self):
        """ Callback when socket connects """ 
        assert_main_thread()
        channel.subscribe(webkit.Console.messageAdded(), self.messageAdded)
        channel.subscribe(webkit.Console.messageRepeatCountUpdated(), self.messageRepeatCountUpdated)
        channel.subscribe(webkit.Console.messagesCleared(), self.messagesCleared)
        channel.subscribe(webkit.Debugger.scriptParsed(), self.scriptParsed)
        channel.subscribe(webkit.Debugger.paused(), self.paused)
        channel.subscribe(webkit.Debugger.resumed(), self.resumed)

        channel.send(webkit.Debugger.enable(), self.enabled)
        channel.send(webkit.Debugger.setPauseOnExceptions(get_setting('pause_on_exceptions')))
        channel.send(webkit.Console.enable())
        channel.send(webkit.Debugger.canSetScriptSource(), self.canSetScriptSource)

        if get_setting('user_agent') is not "":
            channel.send(webkit.Network.setUserAgentOverride(get_setting('user_agent')))

        if get_setting('reload_on_start'):
            channel.send(webkit.Network.clearBrowserCache())
            channel.send(webkit.Page.reload(), on_reload)

    def disconnected(self):
        """ Notification when socket disconnects """
        assert_main_thread()
        self.window.run_command('swi_debug_stop')

    def messageAdded(self, data, notification):
        """ Notification when console message """
        assert_main_thread()
        console_add_message(data)

    def messageRepeatCountUpdated(self, data, notification):
        """  Notification when repeated messages """
        assert_main_thread()
        console_repeat_message(data['count'])

    def messagesCleared(self, data, notification):
        """ Notification when console cleared (by navigate or on request) """
        assert_main_thread()
        clear_view('console')

    # build table of mappings from local to server
    def scriptParsed(self, data, notification):
        """ Notification when a script is parsed (loaded).
            Attempts to map it to a local file.
        """
        assert_main_thread()
        url = data['url']
        if url != '':
            url_parts = url.split("/")
            scriptId = str(data['scriptId'])
            file_name = ''
            script = get_script(data['url'])

            if script:
                if int(scriptId) > int(script['scriptId']):
                    script['scriptId'] = str(scriptId)
                file_name = script['file']
            else:
                del url_parts[0:3]
                while len(url_parts) > 0:
                    for folder in self.project_folders:
                        if sublime.platform() == "windows":
                            # eg., folder is c:\site and url is http://localhost/app.js
                            # glob for c:\site\app.js (primary) and c:\site\*\app.js (fallback only - there may be a c:\site\foo\app.js)
                            files =  glob.glob(folder + "\\" + "\\".join(url_parts)) + glob.glob(folder + "\\*\\" + "\\".join(url_parts))
                        else:
                            files = glob.glob(folder + "/" + "/".join(url_parts)) + glob.glob(folder + "/*/" + "/".join(url_parts))

                        if len(files) > 0 and files[0] != '':
                            file_name = files[0]
                            file_to_scriptId.append({'file': file_name, 'scriptId': str(scriptId), 'url': data['url']})
                            # don't try to match shorter fragments, we already found a match
                            url_parts = []
                    if len(url_parts) > 0:
                        del url_parts[0]

            if debugger_enabled:
                self.add_breakpoints_to_file(file_name)

    def paused(self, data, notification):
        """ Notification that a break was hit.
            Draw an overlay, display the callstack
            and locals, and navigate to the break.
        """
        assert_main_thread()
        
        global paused
        paused = True

        update_stack(data)

    def resumed(self, data, notification):
        """ Notification that execution resumed.
            Clear the overlay, callstack, and locals,
            and remove the highlight.
        """
        assert_main_thread()

        clear_view('stack')
        clear_view('scope')

        channel.send(webkit.Debugger.setOverlayMessage())

        global current_file
        current_file = None

        global current_line
        current_line = None

        global current_call_frame
        current_call_frame = None

        global current_call_frame_position
        current_call_frame_position = None
        
        global paused
        paused = False

        update_overlays()

    def enabled(self, command):
        """ Notification that debugging was enabled """
        assert_main_thread()
        global debugger_enabled
        debugger_enabled = True
        for file_to_script_object in file_to_scriptId:
            self.add_breakpoints_to_file(file_to_script_object['file'])

    def add_breakpoints_to_file(self, file):
        """ Apply any existing breakpoints.
            Called when debugging starts, and when a new script
            is loaded.
        """
        breakpoints = get_breakpoints_by_full_path(file)
        scriptId = find_script(file)
        if breakpoints:
            for line in list(breakpoints.keys()):
                location = webkit.Debugger.Location({'lineNumber': int(line), 'scriptId': scriptId})
                channel.send(webkit.Debugger.setBreakpoint(location), self.breakpointAdded)

    def breakpointAdded(self, command):
        """ Notification that a breakpoint was set.
            Gives us the ID and specific location.
        """
        assert_main_thread()

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
            breaks = get_breakpoints_by_scriptId(str(scriptId))
            lineNumber = str(lineNumber)
            lineNumberSend = str(command.params['location']['lineNumber'])
            if lineNumberSend in breaks and lineNumber != lineNumberSend:
                breaks[lineNumber] = breaks[lineNumberSend].copy()
                del breaks[lineNumberSend]
            breaks[lineNumber]['status'] = 'enabled'
            breaks[lineNumber]['breakpointId'] = str(breakpointId)
        except:
            pass
        save_breaks()
        update_overlays()

    def canSetScriptSource(self, command):
        """ Notification that script can be edited
            during debugging
        """
        assert_main_thread()
        global set_script_source
        set_script_source = command.data['result']

class SwiDebugPauseResumeCommand(sublime_plugin.WindowCommand):
    def run(self):
        assert_main_thread()
        if not channel:
            SwiDebugStartChromeCommand.run(self)
        elif paused:
            channel.send(webkit.Debugger.resume())
        else:
            channel.send(webkit.Debugger.pause())

class SwiDebugStepIntoCommand(sublime_plugin.WindowCommand):
    def run(self):
        if paused:
            channel.send(webkit.Debugger.stepInto())


class SwiDebugStepOutCommand(sublime_plugin.WindowCommand):
    def run(self):
        if paused:
            channel.send(webkit.Debugger.stepOut())


class SwiDebugStepOverCommand(sublime_plugin.WindowCommand):
    def run(self):
        if paused:
            channel.send(webkit.Debugger.stepOver())


class SwiDebugClearConsoleCommand(sublime_plugin.WindowCommand):
    def run(self):
        clear_view('console')


class SwiDebugEvaluateCommand(sublime_plugin.WindowCommand):
    def run(self):
        assert_main_thread()
        active_view = self.window.active_view()
        regions = active_view.sel()
        for i in range(len(regions)):
            title = active_view.substr(regions[i])
            if paused:
                if current_call_frame_position:
                    title = "%s on %s" % (active_view.substr(regions[i]), current_call_frame_position)
                channel.send(webkit.Debugger.evaluateOnCallFrame(current_call_frame, active_view.substr(regions[i])), self.evaluated, {'name': title})
            else:
                channel.send(webkit.Runtime.evaluate(active_view.substr(regions[i])), self.evaluated, {'name': title})

    def evaluated(self, command):
        if command.data.type == 'object':
            channel.send(webkit.Runtime.getProperties(command.data.objectId, True), console_add_properties, command.options)
        else:
            console_add_evaluate(command.data)

class SwiDebugClearBreakpointsCommand(sublime_plugin.WindowCommand):
    def run(self):
        # we choose to remove breakpoints only for active files, so not for unrelated sites
        # so we need to be debugging a site
        for file_to_script_object in file_to_scriptId:
            file_name = file_to_script_object['file']
            breaks = get_breakpoints_by_full_path(file_name)

            if breaks:
                for row in breaks:
                    if 'breakpointId' in breaks[row]:
                        channel.send(webkit.Debugger.removeBreakpoint(breaks[row]['breakpointId']))

                del brk_object[file_name];

        save_breaks()
        update_overlays()

class SwiDebugToggleBreakpointCommand(sublime_plugin.WindowCommand):
    def run(self):
        assert_main_thread()
        active_view = self.window.active_view()

        v = lookup_view(active_view)
        view_name = v.file_name();
        if not view_name: # eg file mapping pane
            return

        row = str(v.rows(v.lines())[0])
        init_breakpoint_for_file(view_name)
        breaks = get_breakpoints_by_full_path(view_name)
        if row in breaks:
            if channel:
                if row in breaks:
                    channel.send(webkit.Debugger.removeBreakpoint(breaks[row]['breakpointId']))

            del_breakpoint_by_full_path(view_name, row)
        else:
            if channel:
                scriptUrl = find_script_url(view_name)
                if scriptUrl:
                    channel.send(webkit.Debugger.setBreakpointByUrl(int(row), scriptUrl), self.breakpointAdded, view_name)
            else:
                set_breakpoint_by_full_path(view_name, row)

        update_overlays()

    def breakpointAdded(self, command):
        """ Notification that a breakpoint was added successfully """
        assert_main_thread()
        active_view = self.window.active_view()

        breakpointId = command.data['breakpointId']
        init_breakpoint_for_file(command.options)
        locations = command.data['locations']

        for location in locations:
            scriptId = location.scriptId
            lineNumber = location.lineNumber
            columnNumber = location.columnNumber

            set_breakpoint_by_scriptId(str(scriptId), str(lineNumber), 'enabled', breakpointId)

        update_overlays()

class SwiDebugStopCommand(sublime_plugin.WindowCommand):

    def run(self):
        active_view = self.window.active_view()

        close_all_our_windows()

        disable_all_breakpoints()

        global paused
        paused = False

        global debugger_enabled
        debugger_enabled = False

        global current_file
        current_file = None

        global current_line
        current_line = None

        update_overlays()

        global channel
        if channel:
            try:
                channel.socket.close()
            except:
                print ('SWI: Can\'t close socket')
            finally:
                channel = None


class SwiDebugReloadCommand(sublime_plugin.WindowCommand):
    def run(self):
        if(channel):
            channel.send(webkit.Network.clearBrowserCache())
            channel.send(webkit.Page.reload(), on_reload)

class SwiShowFileMappingsInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the file mapping view """
    def run(self, edit):
        
        clear_view('mapping')
        self.view.insert(edit, 0, json.dumps(file_to_scriptId, sort_keys=True, indent=4, separators=(',', ': ')))


####################################################################################
#   VIEW
####################################################################################

class SwiDebugView(object):
    """ The SWIDebugView is sort of a normal view with some convenience methods.
        See lookup_view.
    """
    def __init__(self, v):
        self.view = v
        self.context_data = {}
        self.clicks = []
        self.prev_click_position = 0

    def __getattr__(self, attr):
        if hasattr(self.view, attr):
            return getattr(self.view, attr)
        if attr.startswith('on_'):
            return self
        raise AttributeError

    def __call__(self, *args, **kwargs):
        pass

    def window(self):
        return self.view.window()

    def uri(self):
        return 'file://' + os.path.realpath(self.view.file_name())

    def lines(self, data=None):
        """ Takes a list of line numbers, regions, or else uses the selection.
            Returns regions, each covering one complete line, 
            representing the lines included in the supplied input.
        """ 
        lines = []
        if data is None:
            regions = self.view.sel()
        else:
            if type(data) != list:
                data = [data]
            regions = []
            for item in data:
                if type(item) == int or item.isdigit():
                    regions.append(self.view.line(self.view.text_point(int(item) - 1, 0)))
                else:
                    regions.append(item)

        for i in range(len(regions)):
            lines.extend(self.view.split_by_newlines(regions[i]))
        return [self.view.line(line) for line in lines]

    def rows(self, lines):
        """ Takes one or more lines and returns the 1-based (?)
            line and column of the first character in the line.
        """
        if not type(lines) == list:
            lines = [lines]
        return [self.view.rowcol(line.begin())[0] + 1 for line in lines]

    def insert_click(self, a, b, click_type, data):
        """ Creates a clickable "button" at the specified line and column.
            Records the action to be taken on click, and any parameter
            such as the object to get members from.
        """
        insert_before = 0
        new_region = sublime.Region(a, b)
        regions = self.view.get_regions('swi_log_clicks')
        for region in regions:
            if new_region.b < region.a:
                break
            insert_before += 1

        self.clicks.insert(insert_before, {'click_type': click_type, 'data': data})

        regions.append(new_region)
        self.view.add_regions('swi_log_clicks', regions, scope=get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def print_click(self, edit, position, text, click_type, data):
        """ Inserts the specified text and creates a clickable "button"
            around it.
        """
        insert_length = self.insert(edit, position, text)
        self.insert_click(position, position + insert_length, click_type, data)

    def remove_click(self, index):
        """ Removes a clickable "button" with the specified index."""
        regions = self.view.get_regions('swi_log_clicks')
        del regions[index]
        self.view.add_regions('swi_log_clicks', regions, scope=get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def clear_clicks(self):
        """ Removes all clickable regions """
        self.clicks = []

    def check_click(self):
        if not isinstance(self, SwiDebugView):
            return

        cursor = self.sel()[0].a

        click_counter = 0
        click_regions = self.get_regions('swi_log_clicks')
        for click in click_regions:
            if cursor > click.a and cursor < click.b:

                if click_counter < len(self.clicks):
                    click = self.clicks[click_counter]

                    if click['click_type'] == 'goto_file_line':
                        open_script_and_focus_line(click['data']['scriptId'], click['data']['line'])

                    if click['click_type'] == 'goto_call_frame':
                        callFrame = click['data']['callFrame']
                        change_to_call_frame(callFrame)

                    if click['click_type'] == 'get_params':
                        if channel:
                            channel.send(webkit.Runtime.getProperties(click['data']['objectId'], True), console_add_properties, click['data'])

                    if click['click_type'] == 'command':
                        self.remove_click(click_counter)
                        self.window().run_command(click['data'])

            click_counter += 1


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

def update_overlays():

    # loop over all views, identifying the files
    # we need to draw into
    for v in window.views():
        v = lookup_view(v)

        if not v.file_name():
            continue

        v.erase_regions('swi_breakpoint_inactive')
        v.erase_regions('swi_breakpoint_active')
        v.erase_regions('swi_breakpoint_current')

        breaks = get_breakpoints_by_full_path(v.file_name()) or {}

        enabled = []
        disabled = []

        for key in list(breaks.keys()):
            if breaks[key]['status'] == 'enabled':
                enabled.append(key)
            if breaks[key]['status'] == 'disabled':
                disabled.append(key)

        v.add_regions('swi_breakpoint_active', v.lines(enabled), get_setting('breakpoint_scope'), icon=breakpoint_active_icon, flags=sublime.HIDDEN)
        v.add_regions('swi_breakpoint_inactive', v.lines(disabled), get_setting('breakpoint_scope'), icon=breakpoint_inactive_icon, flags=sublime.HIDDEN)

        if current_line:
            if v.file_name() == current_file:
                if (str(current_line) in breaks and breaks[str(current_line)]['status'] == 'enabled'): # always draw current line region, but selectively draw icon
                    current_icon = breakpoint_current_icon
                else:
                    current_icon = ''

                v.add_regions('swi_breakpoint_current', v.lines([current_line]), get_setting('current_line_scope'), current_icon, flags=sublime.DRAW_EMPTY)


####################################################################################
#   EventListener
####################################################################################

class EventListener(sublime_plugin.EventListener):

    def __init__(self):
        self.timing = time.time()

    def on_new(self, v):
        lookup_view(v).on_new()

    def on_clone(self, v):
        lookup_view(v).on_clone()

    def on_load(self, v):
        update_overlays()
        lookup_view(v).on_load()

    def on_close(self, v):
        lookup_view(v).on_close()

    def on_pre_save(self, v):
        lookup_view(v).on_pre_save()

    def reload_styles(self):
        channel.send(webkit.Runtime.evaluate("var files = document.getElementsByTagName('link');var links = [];for (var a = 0, l = files.length; a < l; a++) {var elem = files[a];var rel = elem.rel;if (typeof rel != 'string' || rel.length === 0 || rel === 'stylesheet') {links.push({'elem': elem,'href': elem.getAttribute('href').split('?')[0],'last': false});}}for ( a = 0, l = links.length; a < l; a++) {var link = links[a];link.elem.setAttribute('href', (link.href + '?x=' + Math.random()));}"))

    def reload_set_script_source(self, scriptId, scriptSource):
        """ Calls update_stack because script can be edited when debugger is paused, and
            by this means potentially update the callstack.
        """
        channel.send(webkit.Debugger.setScriptSource(scriptId, scriptSource), self.update_stack)

    def reload_page(self):
        channel.send(webkit.Page.reload(), on_reload)

    def on_post_save(self, v):
        if channel and get_setting('reload_on_save'):
            channel.send(webkit.Network.clearBrowserCache())
            if v.file_name().endswith('.css') or v.file_name().endswith('.less') or v.file_name().endswith('.sass') or v.file_name().endswith('.scss'):
                sublime.set_timeout(lambda: self.reload_styles(), get_setting('reload_timeout'))
            elif v.file_name().endswith('.js'):
                scriptId = find_script(v.file_name())
                if scriptId and set_script_source:
                    scriptSource = v.substr(sublime.Region(0, v.size()))
                    self.reload_set_script_source(scriptId, scriptSource)
                else:
                    sublime.set_timeout(lambda: self.reload_page(), get_setting('reload_timeout'))
            else:
                sublime.set_timeout(lambda: self.reload_page(), get_setting('reload_timeout'))

        lookup_view(v).on_post_save()

    def on_modified(self, v):
        lookup_view(v).on_modified()
        #update_overlays()

    def on_selection_modified(self, v):
        """ We use this to discover a "button" has been clicked."""
        assert_main_thread()
        now = time.time()
        if now - self.timing > 0.1:
            lookup_view(v).check_click()
        self.timing = now

    def on_activated(self, v):
        #todo can we move to on load?
        lookup_view(v).on_activated()

    def on_deactivated(self, v):
        lookup_view(v).on_deactivated()

    def on_query_context(self, v, key, operator, operand, match_all):
        lookup_view(v).on_query_context(key, operator, operand, match_all)

    def update_stack(self, command):
        """ Called on setScriptSource """

        update_stack(command.data)


####################################################################################
#   GLOBAL HANDLERS
####################################################################################

def on_reload(command):
    global file_to_scriptId
    file_to_scriptId = []


####################################################################################
#   Console
####################################################################################

def find_view(console_type, title=''):
    found = False
    v = None
    window = sublime.active_window()

    if console_type.startswith('console'):
        group = 1
        fullName = "Javascript Console"

    if console_type == 'stack':
        group = 2
        fullName = "Javascript Callstack"

    if console_type.startswith('scope'):
        group = 1
        fullName = "Javascript Scope"

    if console_type.startswith('mapping'):
        group = 0
        fullName = "File mapping"

    window.focus_group(group)
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
        v.set_syntax_file('Packages/Web Inspector/swi_log.tmLanguage')

    if console_type == 'stack':
        v.set_syntax_file('Packages/Web Inspector/swi_stack.tmLanguage')

    if console_type.startswith('scope'):
        v.set_syntax_file('Packages/Web Inspector/swi_log.tmLanguage')

    window.focus_view(v)

    v.set_read_only(False)

    return lookup_view(v)

def clear_view(v):
    v = find_view(v)

    if not v:
        return

    v.run_command('swi_clear_view_internal')
    v.show(v.size())

    if not window:
        return

    window.focus_group(0)
    lookup_view(v).clear_clicks()

def clear_all_views():
    clear_view('console')
    clear_view('stack')
    clear_view('scope')
    clear_view('mapping')

def close_all_our_windows():
    global window

    if not window:
        window = sublime.active_window()

    window.focus_group(0)
    for v in window.views_in_group(0):
        if v.name() == 'File mapping ':
            window.run_command("close")
            break

    window.focus_group(1)
    for v in window.views_in_group(1):
        window.run_command("close")

    window.focus_group(2)
    for v in window.views_in_group(2):
        window.run_command("close")

    window.set_layout(original_layout)

def update_stack(data):

    if (not 'callFrames' in data):
        return;
    
    channel.send(webkit.Debugger.setOverlayMessage('Paused in Sublime Web Inspector'))

    window.set_layout(get_setting('stack_layout'))

    console_show_stack(data['callFrames'])

    callFrame = data['callFrames'][0];
    change_to_call_frame(callFrame)


def change_to_call_frame(callFrame):

    scriptId = callFrame.location.scriptId
    line_number = callFrame.location.lineNumber
    file_name = find_script(str(scriptId))
    first_scope = callFrame.scopeChain[0]

    if get_setting('open_stack_current_in_new_tab'):
        title = {'objectId': first_scope.object.objectId, 'name': "%s:%s (%s)" % (file_name, line_number, first_scope.type)}
    else:
        title = {'objectId': first_scope.object.objectId, 'name': "Breakpoint Local"}

    channel.send(webkit.Runtime.getProperties(first_scope.object.objectId, True), console_add_properties, title)

    global current_call_frame
    current_call_frame = callFrame.callFrameId

    global current_call_frame_position
    current_call_frame_position = "%s:%s" % (file_name, line_number)

    global current_file
    current_file = file_name

    global current_line
    current_line = line_number

    open_script_and_focus_line(scriptId, line_number)

class SwiClearViewInternalCommand(sublime_plugin.TextCommand): 
    """ Called internally on the console view """
    def run(self, edit, user_input=None):
        self.view.erase(edit, sublime.Region(0, self.view.size()))

def console_repeat_message(count):
    v = find_view('console')

    v.run_command('swi_console_repeat_message_internal', {"count":count})

    v.show(v.size())
    window.focus_group(0)

class SwiConsoleRepeatMessageInternalCommand(sublime_plugin.TextCommand): 
    """ Called internally on the console view """
    def run(self, edit, count):
        if count > 2:
            erase_to = self.view.size() - len(' \u21AA Repeat:' + str(count - 1) + '\n')
            self.view.erase(edit, sublime.Region(erase_to, self.view.size()))
        self.view.insert(edit, self.view.size(), ' \u21AA Repeat:' + str(count) + '\n')

eval_object_queue = []

def console_add_evaluate(eval_object):
    v = find_view('console')

    eval_object_queue.append(eval_object)
    v.run_command('swi_console_add_evaluate_internal')

    v.show(v.size())
    window.focus_group(0)

class SwiConsoleAddEvaluateInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):
        v = lookup_view(self.view)
        eval_object = eval_object_queue.pop(0)

        insert_position = v.size()
        v.insert(edit, insert_position, str(eval_object) + ' ')

        v.insert(edit, v.size(), "\n")

message_queue = []

def console_add_message(message):
    v = find_view('console')

    message_queue.append(message)
    v.run_command('swi_console_add_message_internal')

    v.show(v.size())
    window.focus_group(0)


class SwiConsoleAddMessageInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):
        v = lookup_view(self.view)
        message = message_queue.pop(0)

        if message.level == 'debug':
            level = "DBG"
        if message.level == 'error':
            level = "ERR"
        if message.level == 'log':
            level = "LOG"
        if message.level == 'warning':
            level = "WRN"

        v.insert(edit, v.size(), "[%s] " % (level))
        # Add file and line
        scriptId = None
        if message.url:
            scriptId = find_script(message.url)
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
            v.insert(edit, v.size(), message.text)

        v.insert(edit, v.size(), "\n")

        if level == "E" and message.stackTrace:
            stack_start = v.size()

            for callFrame in message.stackTrace:
                scriptId = find_script(callFrame.url)
                file_name = callFrame.url.split('/')[-1]

                v.insert(edit, v.size(),  '\t\u21E1 ')

                if scriptId:
                    v.print_click(edit, v.size(), "%s:%s %s" % (file_name, callFrame.lineNumber, callFrame.functionName), 'goto_file_line', {'scriptId': scriptId, 'line': str(callFrame.lineNumber)})
                else:
                    v.insert(edit, v.size(),  "%s:%s %s" % (file_name, callFrame.lineNumber, callFrame.functionName))

                v.insert(edit, v.size(), "\n")

            v.fold(sublime.Region(stack_start-1, v.size()-1))

        if message.repeatCount and message.repeatCount > 1:
            self.view.insert(edit, self.view.size(), ' \u21AA Repeat:' + str(message.repeatCount) + '\n')

properties_queue = []
def console_add_properties(command):
    assert_main_thread()

    if 'name' in command.options:
        name = command.options['name']
    else:
        name = str(command.options['objectId'])

    v = find_view('scope', name)

    properties_queue.append(command)
    v.run_command('swi_console_print_properties_internal')

    v.show(0)
    window.focus_group(0)


class SwiConsolePrintPropertiesInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):

        v = lookup_view(self.view)
        command = properties_queue.pop(0)

        if 'name' in command.options:
            name = command.options['name']
        else:
            name = str(command.options['objectId'])

        if 'prev' in command.options:
            prev = command.options['prev'] + ' -> ' + name
        else:
            prev = name

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

call_frames_queue = []
def console_show_stack(callFrames):

    v = find_view('stack')

    call_frames_queue.append(callFrames)

    v.run_command('swi_console_show_stack_internal')

    v.show(0)
    window.focus_group(0)

class SwiConsoleShowStackInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the stack view """
    def run(self, edit):
        v = lookup_view(self.view)

        callFrames = call_frames_queue.pop(0) 

        v.erase(edit, sublime.Region(0, v.size()))

        v.insert(edit, v.size(), "\n")
        v.print_click(edit, v.size(), "  Resume  ", 'command', 'swi_debug_pause_resume')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Over  ", 'command', 'swi_debug_step_over')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Into  ", 'command', 'swi_debug_step_into')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Out  ", 'command', 'swi_debug_step_out')
        v.insert(edit, v.size(), "\n\n")

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
                v.insert_click(insert_position, insert_position + insert_length, 'goto_call_frame', {'callFrame': callFrame})

            v.insert(edit, v.size(), " %s\n" % (callFrame.functionName))

            for scope in callFrame.scopeChain:
                v.insert(edit, v.size(), "\t")
                insert_position = v.size()
                insert_length = v.insert(edit, v.size(), "%s\n" % (scope.type))
                if scope.object.type == 'object':
                    v.insert_click(insert_position, insert_position + insert_length - 1, 'get_params', {'objectId': scope.object.objectId, 'name': "%s:%s (%s)" % (file_name, line, scope.type)})


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
    global brk_object
    brk_object = get_setting('breaks')


def save_breaks():
    s = sublime.load_settings("swi.sublime-settings")

    if len(brk_object) == 0:
        s.erase('breaks')
    else:
        s.set('breaks', brk_object)

    sublime.save_settings("swi.sublime-settings")

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

    if len(breaks) == 0:
        del brk_object[file_name]

    save_breaks()


def get_breakpoints_by_full_path(file_name):
    return brk_object.get(file_name, None)


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
    if not file_path:   # eg., mapping view
        return
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

def find_script_url(scriptId_or_file):
    #sha = hashlib.sha1(scriptId_or_file_or_url.encode('utf-8')).hexdigest()
    for item in file_to_scriptId:
        if item['scriptId'].lower() == scriptId_or_file.lower():
            return item['url']
        if item['file'].lower() == scriptId_or_file.lower():
            return item['url']

    return None

def find_script(scriptId_or_file_or_url):
    #sha = hashlib.sha1(scriptId_or_file_or_url.encode('utf-8')).hexdigest()
    for item in file_to_scriptId:
        if item['scriptId'].lower() == scriptId_or_file_or_url.lower():
            return item['file']
        if item['file'].lower() == scriptId_or_file_or_url.lower():
            return item['scriptId']
        if item['url'].lower() == scriptId_or_file_or_url.lower():
            return item['scriptId']

    return None

def get_script(scriptId_or_file_or_url):
    #sha = hashlib.sha1(scriptId_or_file_or_url.encode('utf-8')).hexdigest()
    for item in file_to_scriptId:
        if item['scriptId'] == scriptId_or_file_or_url:
            return item
        if item['file'] == scriptId_or_file_or_url:
            return item
        if item['url'] == scriptId_or_file_or_url:
            return item

    return None


def do_when(conditional, callback, *args, **kwargs):
    if conditional():
        return callback(*args, **kwargs)
    sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50) 


def open_script_and_focus_line(scriptId, line_number):
    file_name = find_script(str(scriptId))
    if file_name:   # race with browser
        window = sublime.active_window()
        window.focus_group(0)
        v = window.open_file(file_name)
        do_when(lambda: not v.is_loading(), lambda: open_script_and_focus_line_callback(v, line_number))

def open_script_and_focus_line_callback(v, line_number):
    v.run_command("goto_line", {"line": line_number})
    update_overlays()

def assert_main_thread():
    global main_thread
    assert threading.current_thread().ident == main_thread.ident, "not on main thread"

sublime.set_timeout(lambda: load_breaks(), 1000)

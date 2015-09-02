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
import re
import logging

swi_folder = os.path.dirname(os.path.realpath(__file__))
if not swi_folder in sys.path:
    sys.path.append(swi_folder)

import utils
import webkit
import projectsystem
import protocol
import views
import styles

from webkit import Console
from webkit import Runtime
from webkit import Debugger
from webkit import Network
from webkit import Page

from projectsystem import DocumentMapping

imp.reload(sys.modules['webkit.wkutils'])
imp.reload(sys.modules['webkit.Console'])
imp.reload(sys.modules['webkit.Runtime'])
imp.reload(sys.modules['webkit.Debugger'])
imp.reload(sys.modules['webkit.Network'])
imp.reload(sys.modules['webkit.Page'])

brk_object = {}
channel = None
original_layout = None
window = None
file_to_scriptId = []
paused = False
current_line = None
set_script_source = False
current_call_frame = None
current_call_frame_position = None
source_map_state = None

breakpoint_active_icon = 'Packages/Web Inspector/icons/breakpoint_active.png'
breakpoint_inactive_icon = 'Packages/Web Inspector/icons/breakpoint_inactive.png'
breakpoint_current_icon = 'Packages/Web Inspector/icons/breakpoint_current.png'

logger = logging.getLogger("SWI")
logger.propagate = False

def plugin_loaded():

    if not logger.handlers and utils.get_setting('debug_mode'):
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

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
        mapping = []

        if chrome_launched():
            spacer = " " * 7
            if paused:
                mapping.append(['swi_debug_step_into', 'Step in' + spacer + '    F11'])
                mapping.append(['swi_debug_step_out', 'Step out' + spacer + ' Shift+F11'])
                mapping.append(['swi_debug_step_over', 'Step over' + spacer + 'F10'])
                mapping.append(['swi_debug_pause_resume', 'Resume' + spacer + '   F8'])
            elif channel:
                mapping.append(['swi_debug_pause_resume', 'Pause' + spacer + '    F8'])

            if channel:
                mapping.append(['swi_debug_evaluate', 'Evaluate selection'])
                mapping.append(['swi_debug_clear_console', 'Clear console'])
                mapping.append(['swi_debug_stop', 'Stop debugging'])
                mapping.append(['swi_debug_reload', 'Reload page'])
            else:
                mapping.append(['swi_debug_start', 'Start debugging'])
            
            mapping.append(['swi_debug_toggle_breakpoint', 'Toggle Breakpoint'])

            if channel:
                if is_source_map_enabled:
                    mapping.append(['swi_toggle_authored_code', 'Toggle authored code'])

                mapping.append(['swi_debug_clear_breakpoints', 'Clear all Breakpoints'])
                mapping.append(['swi_dump_file_mappings', 'Dump file mappings'])
        else:
            mapping.append(['swi_debug_start_chrome', 'Start Google Chrome with remote debug port ' + utils.get_setting('chrome_remote_port')])

        self.cmds = [entry[0] for entry in mapping]
        self.items = [entry[1] for entry in mapping]
        self.window.show_quick_panel(self.items, self.command_selected)

    def command_selected(self, index):
        """ Called by Sublime when a quick panel entry is selected """
        utils.assert_main_thread()
        if index == -1:
            return

        command = self.cmds[index]

        if command == 'swi_dump_file_mappings':
            # we wrap this command so we can use the correct view
            print(command)
            v = views.find_or_create_view('mapping')
            v.run_command('swi_dump_file_mappings_internal')
            return

        self.window.run_command(command)
        
def chrome_launched():
    if channel:
        return True

    try:
        proxy = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy)
        urllib.request.install_opener(opener)
        urllib.request.urlopen('http://127.0.0.1:' + utils.get_setting('chrome_remote_port') + '/json')
        return True
    except:
        pass

    return False

class SwiDebugStartChromeCommand(sublime_plugin.WindowCommand):
    """ Represents the start chrome command """

    def run(self):
        utils.assert_main_thread()

        window = sublime.active_window()
        key = sublime.platform()

        # sublime.arch() is x86 on x64 Windows, presumably because it's a 32 bit app
        if key == "windows" and (sublime.arch() == "x64" or sublime.executable_path().find('(x86)') >= 0):
            key += "_x64"

        url = utils.get_setting('chrome_url')
        if url == None:
            url = ''

        self.window.run_command('exec', {
            "cmd": [os.getenv('GOOGLE_CHROME_PATH', '') + utils.get_setting('chrome_path')[key], '--remote-debugging-port=' + utils.get_setting('chrome_remote_port'), '--profile-directory=' + utils.get_setting('chrome_profile'), url]
        })


class SwiDebugStartCommand(sublime_plugin.WindowCommand):
    """ Connect to the socket. """

    def run(self):
        utils.assert_main_thread()
        proxy = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy)
        urllib.request.install_opener(opener)
        response = urllib.request.urlopen('http://127.0.0.1:' + utils.get_setting('chrome_remote_port') + '/json')
        pages = json.loads(response.read().decode('utf-8'))
        mapping = {}
        for page in pages:
            if 'webSocketDebuggerUrl' in page:
                url = page['url']
                if url.find('chrome-extension://') == -1:
                    mapping[page['webSocketDebuggerUrl']] = page['url']

        self.urls = list(mapping.keys())
        items = list(mapping.values())

        if len(self.urls) == 1:
            # just one URL - pick it automatically
            print('Connecting to ' + str(items[0]) + " as it's the only URL offered by the debuggee")
            self.remote_debug_url_selected(0)
        else:
            self.window.show_quick_panel(items, self.remote_debug_url_selected)

    def remote_debug_url_selected(self, index):
        utils.assert_main_thread()
        if index == -1:
            return

        url = self.urls[index]

        global window
        window = sublime.active_window()

        global original_layout
        original_layout = window.get_layout()

        window.set_layout(utils.get_setting('console_layout'))

        load_breaks()

        global debugger_enabled
        debugger_enabled = False
        global file_to_scriptId
        file_to_scriptId = []

        # Look in the folders opened in Sublime first
        self.project_folders = [s.lower() for s in self.window.folders()]

        # Then also look at the folders containing currently open files
        for v in window.views():
            file = v.file_name()
            if file and os.path.isfile(file): 
                dir = os.path.dirname(file).lower()
                # simple protection against disk root - we're going to recurse below
                if len(dir) > 3 and not dir in self.project_folders:
                    self.project_folders.append(dir)

        [logger.info('Aware of folder %s' % s) for s in self.project_folders]

        self.url = url

        global channel
        if channel:
            print ('SWI: Socket closed')
            channel.socket.close()
        else:
            channel = protocol.Protocol()
            channel.connect(self.url, self.connected, self.disconnected)

        global set_script_source
        set_script_source = utils.get_setting('set_script_source')

    def connected(self):
        """ Callback when socket connects """ 
        utils.assert_main_thread()
        channel.subscribe(webkit.Console.messageAdded(), self.messageAdded)
        channel.subscribe(webkit.Console.messageRepeatCountUpdated(), self.messageRepeatCountUpdated)
        channel.subscribe(webkit.Console.messagesCleared(), self.messagesCleared)
        channel.subscribe(webkit.Debugger.scriptParsed(), self.scriptParsed)
        channel.subscribe(webkit.Debugger.paused(), self.paused)
        channel.subscribe(webkit.Debugger.resumed(), self.resumed)
        channel.subscribe(webkit.Debugger.globalObjectCleared(), self.globalObjectCleared)

        channel.send(webkit.Debugger.enable(), self.enabled)
        channel.send(webkit.Debugger.setPauseOnExceptions(utils.get_setting('pause_on_exceptions')))
        channel.send(webkit.Console.enable())
        channel.send(webkit.Debugger.canSetScriptSource(), self.canSetScriptSource)

        #self.window.run_command('swi_styles_window')

        if utils.get_setting('user_agent') is not "":
            channel.send(webkit.Network.setUserAgentOverride(utils.get_setting('user_agent')))

        if utils.get_setting('reload_on_start'):
            channel.send(webkit.Network.clearBrowserCache())
            channel.send(webkit.Page.reload(), on_reload)

    def disconnected(self):
        """ Notification when socket disconnects """
        utils.assert_main_thread()
        self.window.run_command('swi_debug_stop')

    def messageAdded(self, data, notification):
        """ Notification when console message """
        utils.assert_main_thread()
        console_add_message(data)

    def messageRepeatCountUpdated(self, data, notification):
        """  Notification when repeated messages """
        utils.assert_main_thread()
        console_repeat_message(data['count'])

    def messagesCleared(self, data, notification):
        """ Notification when console cleared (by navigate or on request) """
        utils.assert_main_thread()
        views.clear_view('console')

    # build table of mappings from local to server
    def scriptParsed(self, data, notification):
        """ Notification when a script is parsed (loaded).
            Attempts to map it to a local file.
        """
        utils.assert_main_thread()
        url = data['url']
        if url != '':
            url_parts = url.split("/")
            url_parts = list(filter(None, url_parts)) # remove empty entries so we have eg ['http:', 'foo.com', 'bar', 'baz.biz']
            scriptId = str(data['scriptId'])
            file_name = ''
            script = get_script(data['url'])

            logger.info('====Notified of url %s====' % url)

            if script:
                if int(scriptId) > int(script['scriptId']):
                    script['scriptId'] = str(scriptId)
                file_name = script['file']

                # Create a file mapping to look for mapped source code 
                projectsystem.DocumentMapping.MappingsManager.create_mapping(file_name)
            else:
                del url_parts[0:2] # remove protocol and domain
                while len(url_parts) > 0:
                    for folder in self.project_folders:
                        if sublime.platform() == "windows":
                            # eg., folder is c:\site and url is http://localhost/app.js
                            # glob for c:\site\app.js (primary) and c:\site\*\app.js (fallback only - there may be a c:\site\foo\app.js)
                            try:
                                glob1 = folder + "\\" + "\\".join(url_parts)
                                if os.path.exists(glob1) and os.path.isfile(glob1): # literal match (url is directly relative to project folder root)
                                    files = [ glob1 ]
                                else:
                                    glob2 = folder + "\\*\\" + "\\".join(url_parts)
                                    logger.info('    Glob in %s and %s' % (glob1, glob2))
                                    files =  glob.glob(glob1) + glob.glob(glob2)
                            except:
                                pass
                        else:
                            glob1 = folder + "/" + "/".join(url_parts)
                            glob2 = folder + "/*/" + "/".join(url_parts)
                            logger.info('    Glob in %s and %s' % (glob1, glob2))
                            files = glob.glob(glob1) + glob.glob(glob2)

                        if len(files) > 0 and files[0] != '':
                            file_name = files[0]

                            if (file_name):
                                logger.info('    Matched %s' % file_name)
                                # Create a file mapping to look for mapped source code 
                                projectsystem.DocumentMapping.MappingsManager.create_mapping(file_name)

                                file_to_scriptId.append({'file': file_name, 'scriptId': str(scriptId), 'url': data['url']})

                                # don't try to match shorter fragments, we already found a match
                                url_parts = []
                                break

                    if len(url_parts) > 0:
                        del url_parts[0]

            if not file_name:
                logger.info('    Found no local match')

            if debugger_enabled and not file_name:
                self.add_breakpoints_to_file(file_name)

    def paused(self, data, notification):
        """ Notification that a break was hit.
            Draw an overlay, display the callstack
            and locals, and navigate to the break.
        """
        utils.assert_main_thread()
        
        global paused
        paused = True

        update_stack(data)

    def resumed(self, data, notification):
        """ Notification that execution resumed.
            Clear the overlay, callstack, and locals,
            and remove the highlight.
        """
        utils.assert_main_thread()

        views.clear_view('stack')
        views.clear_view('scope')
        views.clear_view('styles')

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

    def globalObjectCleared(self, data, notification):
        projectsystem.DocumentMapping.MappingsManager.delete_all_mappings()

    def enabled(self, command):
        """ Notification that debugging was enabled """
        utils.assert_main_thread()
        global debugger_enabled
        debugger_enabled = True
        for file_to_script_object in file_to_scriptId:
            self.add_breakpoints_to_file(file_to_script_object['file'])

    def add_breakpoints_to_file(self, file):
        """ Apply any existing breakpoints.
            Called when debugging starts, and when a new script
            is loaded.
        """

        if not file:
            return

        scriptId = find_script(file)
        if is_source_map_enabled():
            mapping = projectsystem.DocumentMapping.MappingsManager.get_mapping(file)
            authored_files = mapping.get_authored_files()
            for file_name in authored_files:
                 breakpoints = get_breakpoints_by_full_path(file_name)
                 if breakpoints:
                     for line in list(breakpoints.keys()):
                         column = 0
                         if 'column' in breakpoints[line] and int(breakpoints[line]['column']) >= 0:
                             column = int(breakpoints[line]['column'])

                         position = mapping.get_generated_position(file_name, int(line), column)
                         if position:
                             location = webkit.Debugger.Location({'lineNumber': position.zero_based_line(), 'columnNumber': position.zero_based_column(), 'scriptId': scriptId})
                             params = {'authoredLocation': { 'lineNumber': line, 'columnNumber': column, 'file': file_name }}
                             channel.send(webkit.Debugger.setBreakpoint(location), self.breakpointAdded, params)
        else:
            breakpoints = get_breakpoints_by_full_path(file)
            if breakpoints:
                for line in list(breakpoints.keys()):
                    column = 0
                    if 'column' in breakpoints[line] and int(breakpoints[line]['column']) >= 0:
                        column = int(breakpoints[line]['column'])
                    
                    location = webkit.Debugger.Location({'lineNumber': int(line), 'columnNumber': int(column), 'scriptId': scriptId})
                    channel.send(webkit.Debugger.setBreakpoint(location), self.breakpointAdded)

    def updateAuthoredDocument(self, command):
        save_breaks()
        update_overlays()

    def breakpointAdded(self, command):
        """ Notification that a breakpoint was set.
            Gives us the ID and specific location.
        """
        utils.assert_main_thread()

        breakpointId = command.data['breakpointId']
        scriptId = command.data['actualLocation'].scriptId
        file = find_script(str(scriptId))

        lineNumberActual = command.data['actualLocation'].lineNumber
        columnNumberActual = command.data['actualLocation'].columnNumber

        # we persist in terms of the authored file if any, so translate
        positionActual = get_authored_position_if_necessary(file, lineNumberActual, columnNumberActual)
        if positionActual:
            file = positionActual.file_name()
            lineNumberActual = str(positionActual.zero_based_line())
            columnNumberActual = str(positionActual.zero_based_column())

        # the breakpoint might have been set before debugging starts
        # in that case it might be stored under a different line number
        # to the true actual number we get back. check both.

        lineNumberSent = command.params['location']['lineNumber']
        columnNumberSent = command.params['location']['columnNumber']

        # again, prefer the authored location.
        # we could use the source maps again to get it, but those don't
        # always round trip to the original location. instead, pass them through
        if 'authoredLocation' in command.options:
            assert(file == command.options['authoredLocation']['file'])
            lineNumberSent = command.options['authoredLocation']['lineNumber']
            columnNumberSent = command.options['authoredLocation']['columnNumber']

        breakpoints = get_breakpoints_by_full_path(file)

        # delete anything persisted under the original line number and
        # move it to the correct line number
        if lineNumberSent != lineNumberActual:
            if lineNumberSent in breakpoints:
                breakpoints[lineNumberActual] = breakpoints[lineNumberSent].copy()
                del breakpoints[lineNumberSent]

        # finish updating the persisted breakpoint
        breakpoints[lineNumberActual]['status'] = 'enabled'
        breakpoints[lineNumberActual]['breakpointId'] = str(breakpointId)

        save_breaks()
        update_overlays()

    def canSetScriptSource(self, command):
        """ Notification that script can be edited
            during debugging
        """
        utils.assert_main_thread()
        global set_script_source
        set_script_source = command.data['result']

class SwiDebugPauseResumeCommand(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
        # As a convenience, we'll set up the connection
        # if there isn't one. So F5 (etc) can be hit 
        # to get started.
        if not channel:
            if not chrome_launched():
                SwiDebugStartChromeCommand.run(self)
            else:
                self.window.run_command('swi_debug_start')
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
        views.clear_view('console')


class SwiDebugEvaluateCommand(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
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

                del brk_object[file_name.lower()];

        save_breaks()
        update_overlays()

class SwiDebugToggleBreakpointCommand(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
        active_view = self.window.active_view()

        v = views.wrap_view(active_view)
        view_name = v.file_name()

        if not view_name: # eg file mapping pane
            return

        row = str(v.rows(v.lines())[0])
        init_breakpoint_for_file(view_name)
        breaks = get_breakpoints_by_full_path(view_name)
        if row in breaks:
            if channel:
                if row in breaks:
                    try:
                        channel.send(webkit.Debugger.removeBreakpoint(breaks[row]['breakpointId']))
                    except KeyError:
                        print("SWI: A key error occurred while removing the breakpoint")

            del_breakpoint_by_full_path(view_name, row)
        else:
            if channel:
                scriptUrl = ''
                if projectsystem.DocumentMapping.MappingsManager.is_authored_file(view_name):
                    mapping = projectsystem.DocumentMapping.MappingsManager.get_mapping(view_name)
                    sel = active_view.sel()[0]
                    start = active_view.rowcol(sel.begin())
        
                    position = mapping.get_generated_position(view_name, start[0], start[1])
                    scriptUrl = find_script_url(position.file_name())
                    row = str(position.zero_based_line())
                    scriptUrl = find_script_url(position.file_name())

                if not scriptUrl:
                    scriptUrl = find_script_url(view_name)

                if scriptUrl:
                    channel.send(webkit.Debugger.setBreakpointByUrl(int(row), scriptUrl), self.breakpointAdded, view_name)
            else:
                set_breakpoint_by_full_path(view_name, row)

        update_overlays()

    def breakpointAdded(self, command):
        """ Notification that a breakpoint was added successfully """
        utils.assert_main_thread()
        active_view = self.window.active_view()

        breakpointId = command.data['breakpointId']
        init_breakpoint_for_file(command.options)
        locations = command.data['locations']

        for location in locations:
            scriptId = location.scriptId
            lineNumber = location.lineNumber
            columnNumber = location.columnNumber

            file_name = find_script(str(scriptId))
            if projectsystem.DocumentMapping.MappingsManager.is_generated_file(file_name):
                position = get_authored_position_if_necessary(file_name, lineNumber, columnNumber)

                if position:
                    lineNumber = position.zero_based_line()
                    columnNumber = position.zero_based_column()
                    file_name = position.file_name()
                    init_breakpoint_for_file(file_name)

            # If this breakpoint is in TS file, then store the column number as well for future restoration
            if projectsystem.DocumentMapping.MappingsManager.is_generated_file(file_name):
                set_breakpoint_by_full_path(file_name, str(lineNumber), -1, 'enabled', breakpointId)
            else:
                set_breakpoint_by_full_path(file_name, str(lineNumber), columnNumber, 'enabled', breakpointId)

        update_overlays()

class SwiDebugStopCommand(sublime_plugin.WindowCommand):

    def run(self):
        active_view = self.window.active_view()

        close_all_our_windows()
        clear_all_views()

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
        if channel:
            channel.send(webkit.Network.clearBrowserCache())
            channel.send(webkit.Page.reload(), on_reload)

class SwiDumpFileMappingsInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the file mapping view """
    def run(self, edit):
        
        views.clear_view('mapping')

        dump = lambda obj: json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '))

        text = "File to URL mappings:\n\n"
        text += dump(file_to_scriptId) + "\n\n"
        text += "Authored to source mappings:\n\n"
        text += dump(projectsystem.DocumentMapping.MappingsManager.get_all_source_file_mappings()) + "\n\n"
        text += "Breakpoints:\n\n"
        text += dump(brk_object) + "\n\n"

        self.view.insert(edit, 0, text)


class SwiToggleAuthoredCodeCommand(sublime_plugin.TextCommand):
    """ This is a TextCommand because it specifically applies only
        to the active view
    """
    def run(self, edit):
        utils.assert_main_thread()
        view = views.wrap_view(self.view)
        view_name = view.file_name();
        if not view_name: # eg file mapping pane
            return

        file_mapping = projectsystem.DocumentMapping.MappingsManager.get_mapping(view_name)
        if file_mapping:
            is_authored_file = projectsystem.DocumentMapping.MappingsManager.is_authored_file(view_name)
 
            sel = view.sel()[0]
            start = view.rowcol(sel.begin())
            end = view.rowcol(sel.end())

            mapped_start = file_mapping.get_generated_position(view_name, start[0], start[1]) \
                                        if is_authored_file \
                                        else file_mapping.get_authored_position(start[0], start[1])

            if (start != end):
                mapped_end = file_mapping.get_generated_position(view_name, end[0], end[1]) \
                                          if is_authored_file \
                                          else file_mapping.get_authored_position(end[0], end[1])
            else:
                mapped_end = mapped_start

            window = sublime.active_window()
            window.focus_group(0)
            view = window.open_file(mapped_start.file_name())
            
            do_when(lambda: not view.is_loading(), lambda: set_selection(view,
                                                                         mapped_start.zero_based_line(),
                                                                         mapped_start.zero_based_column(),
                                                                         mapped_end.zero_based_line(),
                                                                         mapped_end.zero_based_column()))

def update_overlays():

    # loop over all views, identifying the files
    # we need to draw into
    for v in window.views():
        v = views.wrap_view(v)

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

        v.add_regions('swi_breakpoint_active', v.lines(enabled), utils.get_setting('breakpoint_scope'), icon=breakpoint_active_icon, flags=sublime.HIDDEN)
        v.add_regions('swi_breakpoint_inactive', v.lines(disabled), utils.get_setting('breakpoint_scope'), icon=breakpoint_inactive_icon, flags=sublime.HIDDEN)

        if current_line:
            if v.file_name().lower() == current_file.lower():
                if (str(current_line) in breaks and breaks[str(current_line)]['status'] == 'enabled'): # always draw current line region, but selectively draw icon
                    current_icon = breakpoint_current_icon
                else:
                    current_icon = ''

                v.add_regions('swi_breakpoint_current', v.lines([current_line]), utils.get_setting('current_line_scope'), current_icon, flags=sublime.DRAW_EMPTY)


####################################################################################
#   EventListener
####################################################################################

class EventListener(sublime_plugin.EventListener):

    def __init__(self):
        self.timing = time.time()

    def on_new(self, v):
        views.wrap_view(v).on_new()

    def on_clone(self, v):
        views.wrap_view(v).on_clone()

    def on_load(self, v):
        update_overlays()
        views.wrap_view(v).on_load()

    def on_close(self, v):
        views.wrap_view(v).on_close()

    def on_pre_save(self, v):
        views.wrap_view(v).on_pre_save()

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
        if channel and utils.get_setting('reload_on_save'):
            channel.send(webkit.Network.clearBrowserCache())
            if v.file_name().endswith('.css') or v.file_name().endswith('.less') or v.file_name().endswith('.sass') or v.file_name().endswith('.scss'):
                sublime.set_timeout(lambda: self.reload_styles(), utils.get_setting('reload_timeout'))
            elif v.file_name().endswith('.js'):
                scriptId = find_script(v.file_name())
                if scriptId and set_script_source:
                    scriptSource = v.substr(sublime.Region(0, v.size()))
                    self.reload_set_script_source(scriptId, scriptSource)
                else:
                    sublime.set_timeout(lambda: self.reload_page(), utils.get_setting('reload_timeout'))
            else:
                sublime.set_timeout(lambda: self.reload_page(), utils.get_setting('reload_timeout'))

        views.wrap_view(v).on_post_save()

    def on_modified(self, v):
        views.wrap_view(v).on_modified()
        #update_overlays()

    def on_activated(self, v):
        #todo can we move to on load?
        views.wrap_view(v).on_activated()

    def on_deactivated(self, v):
        views.wrap_view(v).on_deactivated()

    def on_query_context(self, v, key, operator, operand, match_all):
        views.wrap_view(v).on_query_context(key, operator, operand, match_all)

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

def clear_all_views():
    views.clear_view('console')
    views.clear_view('stack')
    views.clear_view('scope')
    views.clear_view('mapping')

def close_all_our_windows():
    global window

    if not window:
        window = sublime.active_window()

    window.focus_group(0)
    for v in window.views_in_group(0):
        if v.name() == 'File mapping':
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

    if not channel: # race with shutdown
        return
    
    channel.send(webkit.Debugger.setOverlayMessage('Paused in Sublime Web Inspector'))

    window.set_layout(utils.get_setting('stack_layout'))

    callFrames = data['callFrames']

    console_show_stack(callFrames)
    
    if len(callFrames) > 0: # Chrome can return none
        callFrame = callFrames[0]
        change_to_call_frame(callFrame)


def change_to_call_frame(callFrame):

    scriptId = callFrame.location.scriptId
    line_number = callFrame.location.lineNumber
    column_number = callFrame.location.columnNumber
    file_name = find_script(str(scriptId))
    first_scope = callFrame.scopeChain[0]

    position = get_authored_position_if_necessary(file_name, line_number, column_number)
    if position:
        file_name = position.file_name()
        line_number = position.zero_based_line() 
        column_number = position.zero_based_column()

    global current_call_frame
    current_call_frame = callFrame.callFrameId

    global current_call_frame_position
    display_line_number = line_number + 1
    current_call_frame_position = "%s:%s" % (file_name, display_line_number)

    global current_file
    current_file = file_name

    global current_line
    current_line = line_number

    open_script_and_focus_line_by_filename(file_name, line_number)

    params = {'objectId': first_scope.object.objectId, 'name': "%s:(%s, %s) (%s)" % (file_name, line_number, column_number, first_scope.type)}
    channel.send(webkit.Runtime.getProperties(first_scope.object.objectId, True), console_add_properties, params)


def console_repeat_message(count):
    v = views.find_or_create_view('console')

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
    v = views.find_or_create_view('console')

    eval_object_queue.append(eval_object)
    v.run_command('swi_console_add_evaluate_internal')

    v.show(v.size())
    window.focus_group(0)

class SwiConsoleAddEvaluateInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):
        v = views.wrap_view(self.view)
        eval_object = eval_object_queue.pop(0)

        v.insert(edit, v.size(), str(eval_object) + ' \n')

message_queue = []

def console_add_message(message):
    v = views.find_or_create_view('console')

    message_queue.append(message)
    v.run_command('swi_console_add_message_internal')

    v.show(v.size())
    window.focus_group(0)


class SwiConsoleAddMessageInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):
        v = views.wrap_view(self.view)
        message = message_queue.pop(0)

        if message.level == 'debug':
            level = "DBG"
        elif message.level == 'error':
            level = "ERR"
        elif message.level == 'log':
            level = "LOG"
        elif message.level == 'warning':
            level = "WRN"
        elif message.level == 'info':
            level = "INF"
        else:
            level = message.level

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

        if scriptId and line > 0:
            v.print_click(edit, v.size(),  "%s:%d" % (url, line), open_script_by_id_and_focus_line, scriptId, str(line))
        else:
            v.insert(edit, v.size(), "%s:%d" % (url, line))

        v.insert(edit, v.size(), " ")

        # Add text
        if len(message.parameters) > 0:
            for param in message.parameters:
                if param.type == 'object': #if channel here
                    v.print_click(edit, v.size(), str(param) + ' ', channel.send, webkit.Runtime.getProperties(param.objectId, True), console_add_properties, {'objectId': param.objectId})
                else:
                    v.insert(edit, v.size(), str(param) + ' ')
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
                    v.print_click(edit, v.size(), "%s:%s %s" % (file_name, callFrame.lineNumber, callFrame.functionName), open_script_by_id_and_focus_line, scriptId, str(callFrame.lineNumber))
                else:
                    v.insert(edit, v.size(),  "%s:%s %s" % (file_name, callFrame.lineNumber, callFrame.functionName))

                v.insert(edit, v.size(), "\n")

            v.fold(sublime.Region(stack_start-1, v.size()-1))

        if message.repeatCount and message.repeatCount > 1:
            self.view.insert(edit, self.view.size(), ' \u21AA Repeat:' + str(message.repeatCount) + '\n')

properties_queue = []
def console_add_properties(params):
    utils.assert_main_thread()

    v = views.find_or_create_view('scope')

    properties_queue.append(params)
    v.run_command('swi_console_print_properties_internal')

    v.show(0)
    window.focus_group(0)


class SwiConsolePrintPropertiesInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the console view """
    def run(self, edit):

        v = views.wrap_view(self.view)
        command = properties_queue.pop(0)

        if 'name' in command.options:
            name = command.options['name']
        else:
            name = ""

        if 'file' in command.options and 'line' in command.options:
            file = command.options['file']
            line = command.options['line']
            column = command.options['column'] if 'column' in command.options else "0"
        else:
            # eg., name can be
            #     c:\foo\bar\baz.js:422 (local)
            p = re.compile("^\s*(?P<file>.+)\s*:\(\s*(?P<line>\d+),\s*(?P<column>\d+)\)(?P<remainder>\s+.*)$")
            m = p.search(name)
            if m:
                file = m.group('file')
                line = int(m.group('line'))
                column = int(m.group('column'))
                name = m.group('remainder')
            else:
                file = ""
                line = 0
                column = 0

        if 'prev' in command.options:
            prev = command.options['prev'] + ' -> ' + name
        else:
            prev = name

        v.erase(edit, sublime.Region(0, v.size()))

        if file and line:
            position = get_authored_position_if_necessary(file, int(line), int(column))
            if position:
                file = position.file_name()
                line = position.zero_based_line() 
                column = position.zero_based_column()

            file = file.split('/')[-1]

            callback = lambda: open_script_and_focus_line_by_filename(file, line)
            display_line = line + 1
            v.print_click(edit, v.size(), "%s:%s" % (file, display_line), callback)

        v.insert(edit, v.size(), prev)

        v.insert(edit, v.size(), "\n\n")

        for prop in command.data:
            v.insert(edit, v.size(), prop.name + ': ')
            if (prop.value):
                if prop.value.type == 'object':
                    params = {'objectId': prop.value.objectId, 'file': file, 'line': line, 'name': prop.name, 'prev': prev}
                    v.print_click(edit, v.size(), str(prop.value) + '\n', channel.send, webkit.Runtime.getProperties(prop.value.objectId, True), console_add_properties, params)
                else:
                    v.insert(edit, v.size(), str(prop.value) + '\n')
            else:
                v.insert(edit, v.size(), '\n')

call_frames_queue = []
def console_show_stack(callFrames):

    v = views.find_or_create_view('stack')

    call_frames_queue.append(callFrames)

    v.run_command('swi_console_show_stack_internal')

    v.show(0)
    window.focus_group(0)

class SwiConsoleShowStackInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the stack view """
    def run(self, edit):
        v = views.wrap_view(self.view)

        callFrames = call_frames_queue.pop(0) 

        v.erase(edit, sublime.Region(0, v.size()))

        v.insert(edit, v.size(), "\n")
        v.print_click(edit, v.size(), "  Resume  ", self.view.window().run_command, 'swi_debug_pause_resume')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Over  ", self.view.window().run_command, 'swi_debug_step_over')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Into  ", self.view.window().run_command, 'swi_debug_step_into')
        v.insert(edit, v.size(), "  ")
        v.print_click(edit, v.size(), "  Step Out  ", self.view.window().run_command, 'swi_debug_step_out')
        v.insert(edit, v.size(), "\n\n")

        for callFrame in callFrames:
            line = callFrame.location.lineNumber
            column = callFrame.location.columnNumber
            file_name = find_script(str(callFrame.location.scriptId))

            if file_name:
                position = get_authored_position_if_necessary(file_name, line, column)
                if position:
                    file_name = position.file_name()
                    line = position.zero_based_line() 
                    column = position.zero_based_column()

                file_name = file_name.split('/')[-1]
            else:
                file_name = '-'

            display_line_number = line + 1

            if file_name != '-':
                v.print_click(edit, v.size(),  "%s:%s" % (file_name, display_line_number), change_to_call_frame, callFrame)
            else:
                v.insert(edit, v.size(), "%s:%s" % (file_name, display_line_number))

            v.insert(edit, v.size(), " %s\n" % (callFrame.functionName))

            for scope in callFrame.scopeChain:
                v.insert(edit, v.size(), "\t")
                if scope.object.type == 'object':
                    params = {'objectId': scope.object.objectId, 'name': "%s:(%s, %s) (%s)" % (file_name, line, column, scope.type)}
                    v.print_click(edit, v.size(), "%s\n" % (scope.type), channel.send, webkit.Runtime.getProperties(scope.object.objectId, True), console_add_properties, params)
                else:
                    v.insert(edit, v.size(), "%s\n" % (scope.type))


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
    brk_object = utils.get_setting('breaks')


def save_breaks():
    s = sublime.load_settings("swi.sublime-settings")

    if len(brk_object) == 0:
        s.erase('breaks')
    else:
        s.set('breaks', brk_object)

    sublime.save_settings("swi.sublime-settings")

def full_path_to_file_name(path):
    return os.path.basename(os.path.realpath(path))

def set_breakpoint_by_full_path(file_name, line, column=-1, status='disabled', breakpointId=None):
    breaks = get_breakpoints_by_full_path(file_name)

    if not line in breaks:
        breaks[line] = {}
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
        if column != -1:
            breaks[line]['column'] = str(column)
    else:
        breaks[line]['status'] = status
        breaks[line]['breakpointId'] = str(breakpointId)
        if column != -1:
            breaks[line]['column'] = str(column)

    save_breaks()


def del_breakpoint_by_full_path(file_name, line):
    breaks = get_breakpoints_by_full_path(file_name)

    if line in breaks:
        del breaks[line]

    if len(breaks) == 0:
        del brk_object[file_name.lower()]

    save_breaks()


def get_breakpoints_by_full_path(file_name):
    return brk_object.get(file_name.lower(), None)

def get_breakpoints_by_scriptId(scriptId):
    file_name = find_script(str(scriptId))
    if file_name:
        return get_breakpoints_by_full_path(file_name)

    return None


def init_breakpoint_for_file(file_path):
    file_path = file_path.lower()
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


def open_script_by_id_and_focus_line(scriptId, line_number):
    file_name = find_script(str(scriptId))
    open_script_and_focus_line_by_filename(file_name, line_number)

def open_script_and_focus_line_by_filename(file_name, line_number):
    if file_name:   # race with browser
        window = sublime.active_window()
        window.focus_group(0)
        v = window.open_file(file_name)
        do_when(lambda: not v.is_loading(), lambda: open_script_and_focus_line_callback(v, line_number))

def open_script_and_focus_line_callback(v, line_number):
    goto_line_number = line_number + 1 # goto_line is 1-based
    v.run_command("goto_line", {"line": goto_line_number}) 
    update_overlays()

def set_selection(view, start_line, start_column, end_line, end_column):
    if not view or start_line < 0 or start_column < 0 or end_line < 0 or end_column < 0:
        return

    start_point = view.text_point(start_line, start_column)
    end_point = view.text_point(end_line, end_column)

    selection = view.sel()
    selection.clear()
    selection.add(sublime.Region(start_point, end_point))


def get_authored_position_if_necessary(file_name, line_number, column_number):
    if is_source_map_enabled() and projectsystem.DocumentMapping.MappingsManager.is_generated_file(file_name):
        mapping = projectsystem.DocumentMapping.MappingsManager.get_mapping(file_name)
        if mapping.is_valid():
            return mapping.get_authored_position(line_number, column_number)

def is_source_map_enabled():
    global source_map_state
    if source_map_state == None:
        source_map_state = utils.get_setting("enable_source_maps")

    return source_map_state


sublime.set_timeout(lambda: load_breaks(), 1000)

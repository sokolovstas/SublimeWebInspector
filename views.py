import config
import utils
import sublime
import sublime_plugin

####################################################################################
#   VIEW
####################################################################################

class SwiDebugView(object):
    """ The SWIDebugView wraps a normal view, adding some convenience methods.
        See wrap_view.
        All calls to a View should be made through an SWIDebugView, 
        adding more passthroughs if necessary. This makes the code flow explicit.
    """
    def __init__(self, v):
        self.view = v
        self.callbacks = []
        self.prev_click_position = 0

    def __getattr__(self, attr):
        # a trick (with the empty __call__)
        # to implement default empty event handlers
        if attr.startswith('on_'):
            return self
        raise AttributeError

    def __call__(self, *args, **kwargs):
        pass

    def on_deactivated(self):
        if self.view.name() == "File mapping":
            self.view.close()

    def file_name(self):
        return self.view.file_name()

    def erase_regions(self, key):
        return self.view.erase_regions(key)

    def get_regions(self, key):
        return self.view.get_regions(key)

    def add_regions(self, key, regions, scope = "", icon = "", flags = 0):
        return self.view.add_regions(key, regions, scope, icon, flags)

    def run_command(self, cmd, args = None):
        return self.view.run_command(cmd, args)

    def size(self):
        return self.view.size()

    def window(self):
        return self.view.window()

    def sel(self):
        return self.view.sel()

    def insert(self, edit, pt, text):
        return self.view.insert(edit, pt, text)

    def uri(self):
        return 'file://' + os.path.realpath(self.view.file_name())

    def show(self, x, show_surrounds = True):
        return self.view.show(x, show_surrounds)

    def rowcol(self, tp):
        return self.view.rowcol(tp)

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

    def print_click(self, edit, position, text, callback, *args):
        """ Inserts the specified text and creates a clickable "button"
            around it.
        """
        assert(callback)
        insert_length = self.insert(edit, position, text)

        insert_before = 0
        new_region = sublime.Region(position, position + insert_length)
        regions = self.view.get_regions('swi_log_clicks')
        for region in regions:
            if new_region.b < region.a:
                break
            insert_before += 1

        self.callbacks.insert(insert_before, { "callback": callback, "args": args })

        regions.append(new_region)
        self.view.add_regions('swi_log_clicks', regions, scope=utils.get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def print_checkbox(self, edit, position, enabled, text, callback, *args):
        """ Inserts the specified text and creates a clickable "button"
            around it.
        """
        assert(callback)
        marker = " x " if enabled else "   "
        insert_length = self.insert(edit, position, marker)

        insert_before = 0
        new_region = sublime.Region(position, position + insert_length)
        regions = self.view.get_regions('swi_log_clicks')
        for region in regions:
            if new_region.b < region.a:
                break
            insert_before += 1

        self.callbacks.insert(insert_before, { "callback": callback, "args": args, "is_checkbox": True })

        regions.append(new_region)
        self.view.add_regions('swi_log_clicks', regions, scope=utils.get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)
        self.insert(edit, position + len(marker), " " + text)

    def remove_click(self, index):
        """ Removes a clickable "button" with the specified index."""
        regions = self.view.get_regions('swi_log_clicks')
        del regions[index]
        self.view.add_regions('swi_log_clicks', regions, scope=utils.get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def erase(self, edit, region):
        """ Removes our clickable regions 
            then erases the view
        """
        self.callbacks = [] # bug, should only erase callbacks in the region
        self.view.erase(edit, region)

    def check_click(self):
        if not isinstance(self, SwiDebugView):
            return

        cursor = self.sel()[0].a

        index = 0
        click_regions = self.get_regions('swi_log_clicks')
        for region in click_regions:
            if cursor > region.a and cursor < region.b:

                if index < len(self.callbacks):
                    callback = self.callbacks[index]
                    if "is_checkbox" in callback:
                        enabled = self.get_enabled_state(region)
                        callback["callback"](enabled, *callback["args"])
                    else: 
                        callback["callback"](*callback["args"])

            index += 1

    def get_enabled_state(self, region):
        text = self.view.substr(region)
        if text == " x ":
            return True
        return False

def find_existing_view(console_type):
    return find_or_create_view(console_type, False)

def find_or_create_view(console_type, create = True):
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

    if console_type.startswith('styles'):
        group = 1
        fullName = "Styles"

    window.focus_group(group)

    for v in window.views():
        if v.name() == fullName:
            found = True
            break

    if not found and not create:
        return None

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

    if console_type.startswith('styles'):
        v.set_syntax_file('Packages/Web Inspector/swi_styles.tmLanguage')

    window.focus_view(v)

    v.set_read_only(False)

    return wrap_view(v)

def wrap_view(v):
    """     Convert a Sublime View into an SWIDebugView
    """
    if isinstance(v, SwiDebugView):
        return v
    if isinstance(v, sublime.View):
        id = v.buffer_id()
        # Take this opportunity to replace the wrapped view,
        # if it's against the same buffer as the previously 
        # seen view
        if id in config.buffers:
            config.buffers[id].view = v
        else:
            config.buffers[id] = SwiDebugView(v)
        return config.buffers[id]
    return None

def clear_view(name):
    v = find_existing_view(name)

    if not v:
        return

    v.run_command('swi_clear_view_internal')
    v.show(v.size())

    window = sublime.active_window()
    if not window:
        return

    window.focus_group(0)

class SwiClearViewInternalCommand(sublime_plugin.TextCommand): 
    """ Called internally on a specific view """
    def run(self, edit, user_input=None):
        v = wrap_view(self.view)
        v.erase(edit, sublime.Region(0, self.view.size()))

class SwiMouseUpCommand(sublime_plugin.TextCommand):
    """ We use this to discover a "button" has been clicked.
        Previously used on_selection_modified, but it fires
        more than once per click. and there is no "mouse_up" 
        event in Sublime to filter those out.
        This event handler is hooked up to mouse1 in
        Default (xxx).sublime-mousemap - it's not via
        the standard EventListener.
    """
    def run(self, edit):
        utils.assert_main_thread()
        wrap_view(self.view).check_click()

class SwiDoubleMouseUpCommand(sublime_plugin.TextCommand):
    """ On a double click, we get one of each event, so
        run the command only once.
        Triple click does not get handled reliably, it
        may only be treated as two.
    """
    def run(self, edit):
        self.view.run_command("swi_mouse_up")

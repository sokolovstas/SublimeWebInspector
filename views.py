
import utils
import sublime
import sublime_plugin

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
        self.callbacks = []
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

    def print_click(self, edit, position, text, callback):
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

        self.callbacks.insert(insert_before, callback)

        regions.append(new_region)
        self.view.add_regions('swi_log_clicks', regions, scope=utils.get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def remove_click(self, index):
        """ Removes a clickable "button" with the specified index."""
        regions = self.view.get_regions('swi_log_clicks')
        del regions[index]
        self.view.add_regions('swi_log_clicks', regions, scope=utils.get_setting('interactive_scope'), flags=sublime.DRAW_NO_FILL)

    def clear_clicks(self):
        """ Removes all clickable regions """
        self.callbacks = []

    def check_click(self):
        if not isinstance(self, SwiDebugView):
            return

        cursor = self.sel()[0].a

        index = 0
        click_regions = self.get_regions('swi_log_clicks')
        for callback in click_regions:
            if cursor > callback.a and cursor < callback.b:

                if index < len(self.callbacks):
                    callback = self.callbacks[index]
                    callback()

            index += 1

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

    if console_type.startswith('styles'):
        group = 1
        fullName = "Styles"

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

buffers  = {}

def lookup_view(v):
    """     Convert a Sublime View into an SWIDebugView
    """
    if isinstance(v, SwiDebugView):
        return v
    if isinstance(v, sublime.View):
        id = v.buffer_id()
        # Take this opportunity to replace the wrapped view,
        # if it's against the same buffer as the previously 
        # seen view
        if id in buffers:
            buffers[id].view = v
        else:
            buffers[id] = SwiDebugView(v)
        return buffers[id]
    return None


class SwiMouseUpCommand(sublime_plugin.WindowCommand):
    """ We use this to discover a "button" has been clicked.
        Previously used on_selection_modified, but it fires
        more than once per click. and there is no "mouse_up" 
        event in Sublime to filter those out.
        This event handler is hooked up to mouse1 in
        Default (xxx).sublime-mousemap - it's not via
        the standard EventListener.
    """
    def run(self):
        utils.assert_main_thread()
        v = self.window.active_view()
        lookup_view(v).check_click()

class SwiDoubleMouseUpCommand(sublime_plugin.WindowCommand):
    """ On a double click, we get one of each event, so
        run the command only once.
        Triple click does not get handled reliably, it
        may only be treated as two.
    """
    def run(self):
        self.window.run_command("swi_mouse_up")

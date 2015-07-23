
import sublime
import sublime_plugin

import views

class SwiStylesWindowCommand(sublime_plugin.WindowCommand):
    """ Initializes the Styles pane """

    def run(self):
        v = views.find_view('styles')
        v.run_command('swi_styles_window_internal')


class SwiStylesWindowInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the correct view """

    def run(self, edit):
        self.view.insert(edit, 0, 'hello world')
import sublime
import sublime_plugin
import views
import utils
import webkit
from webkit import DOM
from webkit import CSS

import protocol
# do not import swi

def show_styles():
    v = views.find_or_create_view('styles')
    v.run_command('swi_styles_window_internal')


class SwiStylesWindowInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the correct view """

    def run(self, edit):
        v = views.wrap_view(self.view)
        v.print_click(edit, v.size(), "  Inspect Element  ", self.view.window().run_command, 'swi_styles_inspect_element')


class SwiStylesInspectElement(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
        protocol.Channel.channel.send(webkit.DOM.setInspectModeEnabled())

    #def elementSelected(self, data):

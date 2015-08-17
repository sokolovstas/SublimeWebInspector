import sublime
import sublime_plugin
import json
import views
import utils
import webkit
import stylesModel

from webkit import DOM
from webkit import CSS
from webkit import wkutils

import protocol
# do not import swi

def init_styles():
    v = views.find_or_create_view('styles')
    v.run_command('swi_styles_window_internal')
    protocol.Channel.channel.subscribe(webkit.DOM.inspectNodeRequested(), inspectNodeRequested)

    protocol.Channel.channel.send(webkit.DOM.enable())
    protocol.Channel.channel.send(webkit.CSS.enable())

def inspectNodeRequested(backendNodeId, notification):
    views.clear_view('styles')
    v = views.find_or_create_view('styles')
    v.run_command('swi_styles_window_internal')
    protocol.Channel.channel.send(webkit.DOM.pushNodesByBackendIdsToFrontend([backendNodeId]), getStyleRules)

def getStyleRules(command):
    nodeIds = command.data

    for nodeId in nodeIds:
        protocol.Channel.channel.send(webkit.CSS.getInlineStylesForNode(nodeId), updateStylesView)
        protocol.Channel.channel.send(webkit.CSS.getMatchedStylesForNode(nodeId), updateStylesView)
        # protocol.Channel.channel.send(webkit.CSS.getComputedStyleForNode(nodeId))

def updateStylesView(params):
    v = views.find_or_create_view('styles')

    if params.data["type"] == "inline":
        v.run_command('swi_styles_update_inline', {"data": params.data["content"]})
    elif params.data["type"] == "matched":
        v.run_command('swi_styles_update_matched', {"data": params.data["content"]})


class SwiStylesUpdateInlineCommand(sublime_plugin.TextCommand):
    def run(self, edit, data):
        v = views.wrap_view(self.view)
        v.insert(edit, v.size(), "\n\nInline styles: \n\n")

        cssProperties = data["cssProperties"]
        for rule in cssProperties:
            v.print_checkbox(edit, v.size(), True, rule["text"] + "\n", self.click_handler)

    def click_handler(self, enabled):
        if enabled:
            print("Checkbox enabled")
        else:
            print("Checkbox disabled")


class SwiStylesUpdateMatchedCommand(sublime_plugin.TextCommand):
    def run(self, edit, data):
        v = views.wrap_view(self.view)
        v.insert(edit, v.size(), "\n\nMatched styles: \n")

        # Display matched CSS rules
        self.parse_matched_rules(v, edit, data["matchedCSSRules"])

        v.insert(edit, v.size(), "\n\nInherited styles: \n")

        # Display inherited CSS rules
        inheritedData = data["inherited"]
        inheritedStyles = {}
        for item in inheritedData:
            matchedData = item["matchedCSSRules"]
            self.parse_matched_rules(v, edit, matchedData)

    def click_handler(self, enabled):
        if enabled:
            print("Checkbox enabled")
        else:
            print("Checkbox disabled")

    def parse_matched_rules(self, v, edit, matchedData):
        matchedCSSRules = []
        for item in matchedData:
            matchedCSSRules.append(stylesModel.RuleMatch(item))

        for matchedRule in matchedCSSRules:
            self.print_rule(v, edit, matchedRule.rule)

    def print_rule(self, v, edit, rule):
            v.insert(edit, v.size(), "\nOrigin: " + rule.origin)
            v.insert(edit, v.size(), "\nSelectors: " + rule.selectorList + "\n\n")

            for s in rule.style.cssProperties:
                v.print_checkbox(edit, v.size(), s.enabled, s.name + ": " + s.value + "\n", self.click_handler)


class SwiStylesWindowInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the correct view """

    def run(self, edit):
        v = views.wrap_view(self.view)
        v.print_click(edit, v.size(), "  Inspect Element  ", self.view.window().run_command, 'swi_styles_inspect_element')


class SwiStylesInspectElement(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
        protocol.Channel.channel.send(webkit.DOM.setInspectModeEnabled())


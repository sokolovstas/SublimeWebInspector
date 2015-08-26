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
    protocol.Channel.channel.subscribe(webkit.DOM.inlineStyleInvalidated(), inlineStyleInvalidated)

    protocol.Channel.channel.send(webkit.DOM.enable())
    protocol.Channel.channel.send(webkit.CSS.enable())

def inlineStyleInvalidated(nodeIds, notification):
    for nodeId in stylesModel.StyleUtility.current_node_ids:
        if nodeId in nodeIds:
            views.clear_view('styles')
            v = views.find_or_create_view('styles')
            v.run_command('swi_styles_window_internal')
            protocol.Channel.channel.send(webkit.CSS.getInlineStylesForNode(nodeId), displayAppliedStyles)
            protocol.Channel.channel.send(webkit.CSS.getMatchedStylesForNode(nodeId), displayAppliedStyles)

def clear_styles_view():
    views.clear_view('styles')
    v = views.find_or_create_view('styles')
    v.run_command('swi_styles_window_internal')

def inspectNodeRequested(backendNodeId, notification):
    clear_styles_view()
    protocol.Channel.channel.send(webkit.DOM.pushNodesByBackendIdsToFrontend([backendNodeId]), getStyleRules)

def getStyleRules(command):
    nodeIds = command.data
    stylesModel.StyleUtility.current_node_ids = nodeIds
    stylesModel.StyleUtility.clear_styles_cache()

    for nodeId in nodeIds:
        protocol.Channel.channel.send(webkit.CSS.getInlineStylesForNode(nodeId), displayAppliedStyles)
        protocol.Channel.channel.send(webkit.CSS.getMatchedStylesForNode(nodeId), displayAppliedStyles)

def displayAppliedStyles(command=None):
    v = views.find_or_create_view('styles')

    if command:
        if command.data["type"] == "inline":
            v.run_command('swi_styles_update_inline', {"data": command.data["content"]})
        elif command.data["type"] == "matched":
            v.run_command('swi_styles_update_matched', {"data": command.data["content"]})
    else:
        # Just refresh the view with latest styles information
        clear_styles_view()
        v.run_command('swi_styles_update_inline', {"data": {}})
        v.run_command('swi_styles_update_matched', {"data": {}})

class SwiStylesUpdateInlineCommand(sublime_plugin.TextCommand):
    def run(self, edit, data):
        if len(data) > 0:
            style = stylesModel.Style(data)
            stylesModel.StyleUtility.set_inline_rule(style)

        v = views.wrap_view(self.view)
        v.insert(edit, v.size(), "\n\nInline styles: \n\n")
        inline_rule = stylesModel.StyleUtility.get_inline_rule()
        if inline_rule:
            propertyIndex = 0
            for rule in inline_rule.cssProperties:
                v.print_checkbox(edit, v.size(), rule.is_enabled(), rule.name + ": " + rule.value + "\n", stylesModel.StyleUtility.toggle_property, { "uid": rule.uid, "propertyIndex": propertyIndex })
                propertyIndex = propertyIndex + 1


class SwiStylesUpdateMatchedCommand(sublime_plugin.TextCommand):
    def run(self, edit, data):
        if len(data) > 0:
            # Display matched CSS rules
            matchedRules = self.parse_matched_rules(data["matchedCSSRules"])
    
            # Display inherited CSS rules
            inheritedData = data["inherited"]
            inheritedRules = []
            for item in inheritedData:
                matchedData = item["matchedCSSRules"]
                rules = self.parse_matched_rules(matchedData)
                inheritedRules.extend(rules)

            stylesModel.StyleUtility.set_matched_rules(matchedRules)
            stylesModel.StyleUtility.set_inherited_rules(inheritedRules)

        v = views.wrap_view(self.view)
        self.print_section(v, edit, "Matched styles", stylesModel.StyleUtility.get_matched_rules(), 0)
        self.print_section(v, edit, "Inherited styles", stylesModel.StyleUtility.get_inherited_rules(), len(stylesModel.StyleUtility.get_matched_rules()))

    def parse_matched_rules(self, matchedData):
        matchedCSSRules = []
        for item in matchedData:
            matchedCSSRules.append(stylesModel.RuleMatch(item))
        return matchedCSSRules

    def print_section(self, v, edit, title, matchedCSSRules, startIndex):
        v.insert(edit, v.size(), "\n\n" + title + ": \n")
    
        ruleIndex = startIndex
        for matchedRule in matchedCSSRules:
            self.print_rule(v, edit, matchedRule.rule, ruleIndex)
            ruleIndex = ruleIndex + 1
    
    def print_rule(self, v, edit, rule, ruleIndex):
            v.insert(edit, v.size(), "\nOrigin: " + rule.origin)
            v.insert(edit, v.size(), "\nSelectors: " + rule.selectorList)
    
            if rule.origin == "regular":
                v.insert(edit, v.size(), "\nFile: ")
                v.print_click(edit, v.size(), rule.get_stylesheet_name(), open_styleSheet, { "name": rule.get_stylesheet_name() })
                v.insert(edit, v.size(), "\n\n")
            else:
                v.insert(edit, v.size(), "\n\n")
    
            propertyIndex = 0
            for s in rule.style.cssProperties:
                v.print_checkbox(edit, v.size(), s.is_enabled(), s.name + ": " + s.value + "\n", stylesModel.StyleUtility.toggle_property, { "ruleIndex": ruleIndex, "propertyIndex": propertyIndex})
                propertyIndex = propertyIndex + 1


class SwiStylesWindowInternalCommand(sublime_plugin.TextCommand):
    """ Called internally on the correct view """

    def run(self, edit):
        v = views.wrap_view(self.view)
        v.print_click(edit, v.size(), "  Inspect Element  ", self.view.window().run_command, 'swi_styles_inspect_element')


class SwiStylesInspectElement(sublime_plugin.WindowCommand):
    def run(self):
        utils.assert_main_thread()
        protocol.Channel.channel.send(webkit.DOM.setInspectModeEnabled())


def open_styleSheet(params):
    file_name = params["name"]
    if file_name: # race with browser
        window = sublime.active_window()
        window.focus_group(0)
        v = window.open_file(file_name)
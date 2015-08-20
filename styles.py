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
            protocol.Channel.channel.send(webkit.CSS.getInlineStylesForNode(nodeId), updateStylesView)
            protocol.Channel.channel.send(webkit.CSS.getMatchedStylesForNode(nodeId), updateStylesView)

def inspectNodeRequested(backendNodeId, notification):
    views.clear_view('styles')
    v = views.find_or_create_view('styles')
    v.run_command('swi_styles_window_internal')
    protocol.Channel.channel.send(webkit.DOM.pushNodesByBackendIdsToFrontend([backendNodeId]), getStyleRules)

def getStyleRules(command):
    nodeIds = command.data
    stylesModel.StyleUtility.current_node_ids = nodeIds

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

        # Display matched CSS rules
        matchedRules = self.parse_matched_rules(data["matchedCSSRules"])

        # Display inherited CSS rules
        inheritedData = data["inherited"]
        inheritedRules = []
        for item in inheritedData:
            matchedData = item["matchedCSSRules"]
            rules = self.parse_matched_rules(matchedData)
            inheritedRules.extend(rules)

        # Calculate all applied styles
        all_rules = []
        all_rules.extend(matchedRules)
        all_rules.extend(inheritedRules)
        stylesModel.StyleUtility.set_matched_rules(all_rules)

        self.print_section(v, edit, "Matched styles", matchedRules, 0)
        self.print_section(v, edit, "Inherited styles", inheritedRules, len(matchedRules))

    def click_handler(self, enabled, args):
        if enabled:
            print("Checkbox enabled", args["ruleIndex"], args["propertyIndex"])
        else:
            print("Checkbox disabled", args["ruleIndex"], args["propertyIndex"])

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
                v.insert(edit, v.size(), "\nFile: " + rule.get_stylesheet_name() + "\n\n")
            else:
                v.insert(edit, v.size(), "\n\n")

            propertyIndex = 0
            for s in rule.style.cssProperties:
                v.print_checkbox(edit, v.size(), s.is_enabled(), s.name + ": " + s.value + "\n", self.click_handler, { "ruleIndex": ruleIndex, "propertyIndex": propertyIndex})
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

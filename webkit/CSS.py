from .wkutils import Command, Notification, WebkitObject
from .Runtime import RemoteObject
import json
import re


def enable():
    return Command('CSS.enable', {})

def getMatchedStylesForNode(nodeId):
    return Command('CSS.getMatchedStylesForNode', { "nodeId": nodeId })

def getInlineStylesForNode(nodeId):
    return Command('CSS.getInlineStylesForNode', { "nodeId": nodeId })

def getComputedStyleForNode(nodeId):
    return Command('CSS.getComputedStyleForNode', { "nodeId": nodeId })

def styleSheetAdded():
    return Notification('CSS.styleSheetAdded')

def styleSheetAdded_parser(params):
    return params["header"]

def getInlineStylesForNode_parser(params):
    data = params["inlineStyle"]
    return data

def getMatchedStylesForNode_parser(params):
   data = {}
   data['matchedCSSRules'] = []
   for match in params['matchedCSSRules']:
       data['matchedCSSRules'].append(RuleMatch(match))

   return data


class RuleMatch:
   def __init__(self, value):
       self.rule = Rule(value['rule'])
       self.matchingSelectors= []
       # if 'children' in value:
        #    for child in value['children']:
        #        self.children.append(Node(child))


class Rule:
    def __init__(self, value):
        self.origin = value["origin"]
        self.selectorList = value["selectorList"]
        self.sourceUrl = None
        if "sourceUrl" in value:
            self.sourceUrl = value["sourceUrl"]

        if "style" in value:
            self.style = Style(value["style"])


class Style:
    def __init__(self,value):
        self.value = value
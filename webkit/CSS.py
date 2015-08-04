from .wkutils import Command, Notification, WebkitObject
from .Runtime import RemoteObject
import json
import re

def getMatchedStylesForNode(nodeid):
    return Command('CSS.getMatchedStylesForNode', { "nodeId": nodeId })

#def getMatchedStylesForNode_parser(params):
#    data = {}
#    for match in params['matchedCSSRules']:
#        data['matchedCSSRules'].append(RuleMatch(match))

#class RuleMatch:
#    def __init__(self, value):
#        self.rule = Rule(value['rule'])
#        self.matchingSelectors= []
#        if 'children' in value:
#            for child in value['children']:
#                self.children.append(Node(child))
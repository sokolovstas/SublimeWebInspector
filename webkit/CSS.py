from .wkutils import Command, Notification, WebkitObject
from .Runtime import RemoteObject
import json
import re


def enable():
    return Command('CSS.enable', {})

def setPropertyText(styleSheetId, sourceRange, text):
    params = dict({})
    params["styleSheetId"] = styleSheetId
    params["range"] = sourceRange
    params["text"] = text

    return Command('CSS.setPropertyText', params)

def getMatchedStylesForNode(nodeId):
    return Command('CSS.getMatchedStylesForNode', { "nodeId": nodeId })

def getInlineStylesForNode(nodeId):
    return Command('CSS.getInlineStylesForNode', { "nodeId": nodeId })

def getComputedStyleForNode(nodeId):
    return Command('CSS.getComputedStyleForNode', { "nodeId": nodeId })

def styleSheetAdded():
    return Notification('CSS.styleSheetAdded')

def setPropertyText_parser(params):
    return params["style"]

def getInlineStylesForNode_parser(params):
    data = {}
    data["content"] = params["inlineStyle"]
    data["type"] = "inline"
    return data

def getMatchedStylesForNode_parser(params):
    data = dict({})
    data["type"] = "matched"

    data["content"] = params
    return data

def styleSheetAdded_parser(params):
    return params["header"]

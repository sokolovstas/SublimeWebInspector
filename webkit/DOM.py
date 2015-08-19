from .wkutils import Command, Notification, WebkitObject
from .Runtime import RemoteObject
import json
import re

def enable():
    return Command('DOM.enable', {})

def getDocument():
    command = Command('DOM.getDocument')
    return command

def getDocument_parser():
    data = {}
    data['root'] = Node(result['root'])

class Node(WebkitObject):
    def __init__(self, value):
        self.set(value, 'nodeId')
        self.set(value, 'nodeName')
        #self.set(value, 'nodeValue')
        self.children= []
        if 'children' in value:
            for child in value['children']:
                self.children.append(Node(child))

def setInspectModeEnabled():
    params = {}
    params['enabled'] = True
    params["inspectUAShadowDOM"] = False

    # these are the values that Chrome inspector uses itself
    highlightConfig = {}
    highlightConfig['showInfo'] = True
    highlightConfig['showRulers'] = False
    highlightConfig['showExtensionLines'] = False
    highlightConfig['contentColor'] = json.loads("""
        {
            "contentColor": { "r": 111, "g": 168, "b": 220, "a": 0.66 },
            "paddingColor": { "r": 147, "g": 196, "b": 125, "a": 0.55 },
            "borderColor": { "r": 255, "g": 229, "b": 153, "a": 0.66 },
            "marginColor": { "r": 246, "g": 178, "b": 107, "a": 0.66 },
            "eventTargetColor": { "r": 255, "g": 196, "b": 196, "a": 0.66 },
            "shapeColor": { "r": 96, "g": 82, "b": 177, "a": 0.8 },
            "shapeMarginColor": { "r": 96, "g": 82, "b": 127, "a": 0.6 }
        }
    """)
   
    params['highlightConfig'] = highlightConfig
    command = Command('DOM.setInspectModeEnabled', params)
    return command

def inspectNodeRequested():
    return Notification('DOM.inspectNodeRequested')

def inlineStyleInvalidated():
    return Notification('DOM.inlineStyleInvalidated')

def inspectNodeRequested_parser(params):
    return params['backendNodeId']

def inlineStyleInvalidated_parser(params):
    return params['nodeIds']

def pushNodesByBackendIdsToFrontend(backendNodeIds):
    return Command('DOM.pushNodesByBackendIdsToFrontend', {"backendNodeIds": backendNodeIds })

def pushNodesByBackendIdsToFrontend_parser(params):
    return params['nodeIds'] #array

def setInspectedNode(nodeId):
    return Command('DOM.setInspectedNode', {"nodeId": nodeId})

def setChildNodes():
    return Notification('DOM.setChildNodes')

def setChildNodes_parser(params):
    data = {}
    data['parentId'] = params['parentId']
    data['nodes'] = []
    for node in params['nodes']:
        data['nodes'].append(Node(node))

    return data

def requestChildNodes(nodeId):
    return Command('DOM.requestChildNodes', { "nodeId": nodeId })




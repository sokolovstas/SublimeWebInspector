from .utils import Command, Notification, WebkitObject
from .Runtime import RemoteObject
import json
import re


def canSetScriptSource():
    command = Command('Debugger.canSetScriptSource', {})
    return command


def enable():
    command = Command('Debugger.enable', {})
    return command

def setPauseOnExceptions(state):
    command = Command('Debugger.setPauseOnExceptions', {"state": state})
    return command

def setOverlayMessage(message=None):
    if message:
        command = Command('Page.setOverlayMessage', {"message":"Paused in Sublime Web Inspector"})
    else:
        command = Command('Page.setOverlayMessage', {})
    return command


def evaluateOnCallFrame(callFrameId, expression):
    params = {}
    params['callFrameId'] = callFrameId()
    params['expression'] = expression
    command = Command('Debugger.evaluateOnCallFrame', params)
    return command


def evaluateOnCallFrame_parser(result):
    data = RemoteObject(result['result'])
    return data


def disable():
    command = Command('Debugger.disable', {})
    return command


def pause():
    command = Command('Debugger.pause', {})
    return command


def resume():
    command = Command('Debugger.resume', {})
    return command


def stepInto():
    command = Command('Debugger.stepInto', {})
    return command


def stepOut():
    command = Command('Debugger.stepOut', {})
    return command


def stepOver():
    command = Command('Debugger.stepOver', {})
    return command


def removeBreakpoint(breakpointId):
    params = {}
    params['breakpointId'] = breakpointId
    command = Command('Debugger.removeBreakpoint', params)
    return command


def setBreakpoint(location, condition=None):
    params = {}
    
    location.lineNumber = location.lineNumber-1
    params['location'] = location()

    if condition:
        params['condition'] = condition

    command = Command('Debugger.setBreakpoint', params)
    return command


def setBreakpoint_parser(result):
    data = {}
    data['breakpointId'] = BreakpointId(result['breakpointId'])
    data['actualLocation'] = Location(result['actualLocation'])
    data['actualLocation'].lineNumber = data['actualLocation'].lineNumber+1
    return data


def setScriptSource(scriptId, scriptSource):
    params = {}
    params['scriptId'] = scriptId
    params['scriptSource'] = scriptSource

    command = Command('Debugger.setScriptSource', params)
    return command


def setScriptSource_parser(result):
    data = {}
    data['callFrames'] = []
    for callFrame in result['callFrames']:
        data['callFrames'].append(CallFrame(callFrame))
    return data


def setBreakpointByUrl(lineNumber, url, urlRegex=None, columnNumber=None, condition=None):
    params = {}
    params['lineNumber'] = lineNumber-1
    params['url'] = restoreQueryString(url)

    if urlRegex:
        params['urlRegex'] = urlRegex

    if columnNumber:
        params['columnNumber'] = columnNumber
    else:
        params['columnNumber'] = 0

    if condition:
        params['condition'] = condition
    else:
        params['condition'] = ''

    command = Command('Debugger.setBreakpointByUrl', params)
    return command


def setBreakpointByUrl_parser(result):
    data = {}
    data['breakpointId'] = BreakpointId(result['breakpointId'])
    data['locations'] = []
    for location in result['locations']:
        location_found = Location(location)
        location_found.lineNumber = location_found.lineNumber + 1
        data['locations'].append(location_found)
    return data


def scriptParsed():
    notification = Notification('Debugger.scriptParsed')
    return notification


def scriptParsed_parser(params):
    url = stripQueryString(params['url'])
    return {'scriptId': ScriptId(params['scriptId']), 'url': url}


def paused():
    notification = Notification('Debugger.paused')
    return notification


def paused_parser(params):
    data = {}
    data['callFrames'] = []
    for callFrame in params['callFrames']:
        data['callFrames'].append(CallFrame(callFrame))
    data['reason'] = params['reason']
    return data

url_to_originalUrl = {}

def stripQueryString(url):
    # Some users use query strings as cache breakers
    # We don't want these in our mapping process or window titles
    # Strip on url from debuggee, restore on url to debuggee
    url_parts = url.split("/")
    url_parts[-1] = re.sub(r"\?.*$", "", url_parts[-1])
    cleanUrl = "/".join(url_parts)
    if url != cleanUrl:
        url_to_originalUrl[cleanUrl] = url
    return cleanUrl

def restoreQueryString(url):
    if url in url_to_originalUrl:
        url = url_to_originalUrl[url]
    return url

def resumed():
    notification = Notification('Debugger.resumed')
    return notification


class BreakpointId(WebkitObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class CallFrameId(WebkitObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class ScriptId(WebkitObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class Scope(WebkitObject):
    def __init__(self, value):
        self.set_class(value, 'object', RemoteObject)
        self.set(value, 'type')


class Location(WebkitObject):
    def __init__(self, value):
        self.set(value, 'columnNumber')
        self.set(value, 'lineNumber')
        self.set_class(value, 'scriptId', ScriptId)

    def __call__(self):
        obj = {}
        if self.columnNumber:
            obj['columnNumber'] = self.columnNumber
        obj['lineNumber'] = self.lineNumber
        obj['scriptId'] = self.scriptId()
        return obj


class CallFrame(WebkitObject):
    def __init__(self, value):
        self.set_class(value, 'callFrameId', CallFrameId)
        self.set(value, 'functionName')
        self.set_class(value, 'location', Location)
        self.location.lineNumber = self.location.lineNumber+1
        self.scopeChain = []
        if 'scopeChain' in value:
            for scope in value['scopeChain']:
                self.scopeChain.append(Scope(scope))

    def __str__(self):
        return "%s:%d %s" % (self.location.scriptId, self.location.lineNumber, self.functionName)

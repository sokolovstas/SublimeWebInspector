from utils import Command, Notification, WIPObject
from Runtime import RemoteObject
import json


### Console.clearMessages
def canSetScriptSource():
    command = Command('Debugger.canSetScriptSource', {})
    return command


def enable():
    command = Command('Debugger.enable', {})
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
    params['location'] = location()

    if condition:
        params['condition'] = condition

    command = Command('Debugger.setBreakpoint', params)
    return command


def setBreakpoint_parser(result):
    data = {}
    data['breakpointId'] = BreakpointId(result['breakpointId'])
    data['actualLocation'] = Location(result['actualLocation'])
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


def setBreakpointByUrl(lineNumber, url=None, urlRegex=None, columnNumber=None, condition=None):
    params = {}
    params['lineNumber'] = lineNumber
    if url:
        params['url'] = url

    if urlRegex:
        params['urlRegex'] = urlRegex

    if columnNumber:
        params['columnNumber'] = columnNumber

    if condition:
        params['condition'] = condition

    command = Command('Debugger.setBreakpointByUrl', params)
    return command


def setBreakpointByUrl_parser(result):
    data = {}
    data['breakpointId'] = BreakpointId(result['breakpointId'])
    data['locations'] = []
    for location in result['locations']:
        data['locations'].append(Location(location))
    return data


def scriptParsed():
    notification = Notification('Debugger.scriptParsed')
    return notification


def scriptParsed_parser(params):
    return {'scriptId': ScriptId(params['scriptId']), 'url': params['url']}


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


def resumed():
    notification = Notification('Debugger.resumed')
    return notification


class BreakpointId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class CallFrameId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class ScriptId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class Scope(WIPObject):
    def __init__(self, value):
        self.set_class(value, 'object', RemoteObject)
        self.set(value, 'type')


class Location(WIPObject):
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


class CallFrame(WIPObject):
    def __init__(self, value):
        self.set_class(value, 'callFrameId', CallFrameId)
        self.set(value, 'functionName')
        self.set_class(value, 'location', Location)
        self.scopeChain = []
        if 'scopeChain' in value:
            for scope in value['scopeChain']:
                self.scopeChain.append(Scope(scope))
        self.set_class(value, 'this', RemoteObject)

    def __str__(self):
        return "%s:%d %s" % (self.location.scriptId, self.location.lineNumber, self.functionName)

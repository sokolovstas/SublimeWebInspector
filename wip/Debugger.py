from utils import Command, Notification, WIPObject
from Runtime import RemoteObject


### Console.clearMessages
def canSetScriptSource():
    command = Command('Debugger.canSetScriptSource', {})
    return command


def enable():
    command = Command('Debugger.enable', {})
    return command


def disable():
    command = Command('Debugger.disable', {})
    return command

def resume():
    command = Command('Debugger.resume', {})
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
            for scope in value.scopeChain:
                self.scopeChain.append(Scope(scope))
        self.set_class(value, 'this', RemoteObject)

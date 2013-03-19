from .utils import Command, Notification, WIPObject
from .Runtime import RemoteObject
from .Network import RequestId


### Console.clearMessages
def clearMessages():
    command = Command('Console.clearMessages')
    return command


### Console.disable
def disable():
    command = Command('Console.disable')
    return command


### Console.enable
def enable():
    command = Command('Console.enable')
    return command


### Console.messageAdded
def messageAdded():
    notification = Notification('Console.messageAdded')
    return notification


def messageAdded_parser(params):
    result = ConsoleMessage(params['message'])
    return result


### Console.messageRepeatCountUpdated
def messageRepeatCountUpdated():
    notification = Notification('Console.messageRepeatCountUpdated')
    return notification


def messageRepeatCountUpdate_parser(params):
    return params['count']


### Console.messagesCleared
def messagesCleared():
    notification = Notification('Console.messagesCleared')
    return notification


class CallFrame(WIPObject):
    def __init__(self, value):
        self.set(value, 'columnNumber')
        self.set(value, 'functionName')
        self.set(value, 'lineNumber')
        self.set(value, 'url')


class ConsoleMessage(WIPObject):
    def __init__(self, value):
        self.set(value, 'level')
        self.set(value, 'line')
        self.set_class(value, 'networkRequestId', RequestId)
        self.parameters = []
        if 'parameters' in value:
            for param in value['parameters']:
                self.parameters.append(RemoteObject(param))
        self.set(value, 'repeatCount', 1)
        self.set_class(value, 'stackTrace', StackTrace)
        self.set(value, 'text')
        self.set(value, 'url')


class StackTrace(list):
    def __init__(self, value):
        for callFrame in value:
            self.append(CallFrame(callFrame))

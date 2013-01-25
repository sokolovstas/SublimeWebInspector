import json
from utils import WIPObject, Command


def evaluate(expression, objectGroup=None, returnByValue=None):
    params = {}

    params['expression'] = expression

    if(objectGroup):
        params['objectGroup'] = objectGroup

    if(returnByValue):
        params['returnByValue'] = returnByValue

    command = Command('Runtime.evaluate', params)
    return command

def getProperties(expression, objectGroup=None, returnByValue=None):
    params = {}

    params['expression'] = expression

    if(objectGroup):
        params['objectGroup'] = objectGroup

    if(returnByValue):
        params['returnByValue'] = returnByValue

    command = Command('Runtime.evaluate', params)
    return command


class RemoteObject(WIPObject):
    def __init__(self, value):
        self.set(value, 'className')
        self.set(value, 'description')
        self.set_class(value, 'objectId', RemoteObjectId)
        self.set(value, 'subtype')
        self.set(value, 'type')
        self.set(value, 'value')

    def __str__(self):
        if self.type == 'string':
            return self.value
        if self.type == 'undefined':
            return 'undefined'
        if self.type == 'number':
            return self.value
        if self.type == 'object':
            return str(self.objectId)
        if self.type == 'function':
            return self.description


class RemoteObjectId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        if self.value == '':
            return ''

        objid = json.loads(self.value)
        return "{Object_%d_%d}" % (objid['injectedScriptId'], objid['id'])

    def dumps(self):
        objid = json.loads(self.value)
        return "{Object_%d_%d}" % (objid['injectedScriptId'], objid['id'])

    def loads(self, text):
        parts = text.split('_')
        self.value = '{"injectedScriptId":%s,"id":%s}' % (parts[1], parts[2])
        return self.value


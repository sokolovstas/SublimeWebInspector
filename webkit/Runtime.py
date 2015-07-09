import json
from .utils import WIPObject, Command


def evaluate(expression, objectGroup=None, returnByValue=None):
    params = {}

    params['expression'] = expression

    if(objectGroup):
        params['objectGroup'] = objectGroup

    if(returnByValue):
        params['returnByValue'] = returnByValue

    command = Command('Runtime.evaluate', params)
    return command

def evaluate_parser(result):
    data = RemoteObject(result['result'])
    return data


def getProperties(objectId, ownProperties=False):
    params = {}

    params['objectId'] = str(objectId)
    params['ownProperties'] = ownProperties

    command = Command('Runtime.getProperties', params)
    return command


def getProperties_parser(result):
    data = []
    for propertyDescriptor in result['result']:
        data.append(PropertyDescriptor(propertyDescriptor))
    return data


class RemoteObject(WIPObject):
    def __init__(self, value):
        self.set(value, 'className')
        self.set(value, 'description')
        self.set_class(value, 'objectId', RemoteObjectId)
        self.set(value, 'subtype')
        self.set(value, 'type')
        self.set(value, 'value')

    def __str__(self):
        if self.type == 'boolean':
            return str(self.value)
        if self.type == 'string':
            return str(self.value)
        if self.type == 'undefined':
            return 'undefined'
        if self.type == 'number':
            return str(self.value)
        if self.type == 'object':
            if not self.objectId:
                return 'null'
            else:
                if self.className:
                    return self.className
                if self.description:
                    return self.description
                return '{ ... }'
        if self.type == 'function':
            return self.description.split('\n')[0]


class PropertyDescriptor(WIPObject):
    def __init__(self, _value):
        self.set(_value, 'configurable')
        self.set(_value, 'enumerable')
        #self.set_class(_value, 'get', RemoteObject)
        #self.set_class(_value, 'set', RemoteObject)
        self.set(_value, 'name')
        self.set_class(_value, 'value', RemoteObject)
        self.set(_value, 'wasThrown')
        self.set(_value, 'writable')

    def __str__(self):
        return self.name


class RemoteObjectId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

    def dumps(self):
        objid = json.loads(self.value)
        return "Object_%d_%d" % (objid['injectedScriptId'], objid['id'])

    def loads(self, text):
        parts = text.split('_')
        self.value = '{"injectedScriptId":%s,"id":%s}' % (parts[1], parts[2])
        return self.value

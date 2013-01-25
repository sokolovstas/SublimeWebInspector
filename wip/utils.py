class WIPObject(object):
    def set(self, obj, name, default=None):
        setattr(self, name, obj.get(name, default))

    def set_class(self, obj, name, classObject):
        if name in obj:
            setattr(self, name, classObject(obj[name]))
        else:
            setattr(self, name, None)

    def parse_to_class(self, obj, name, classObject):
        if name in obj:
            setattr(self, name, classObject.parse(obj[name]))
        else:
            setattr(self, name, None)


class Notification(object):
    def __init__(self, notification_name):
        self.name = notification_name
        try:
            self.parser = eval('wip.' + notification_name + '_parser', {'wip': __import__('wip')})
        except:
            self.parser = Notification.default_parser
        self.lastResponse = None
        self.callback = None

    @staticmethod
    def default_parser(params):
        print params
        return params


class Command(object):
    def __init__(self, method_name, params={}):
        self.request = {'id': 0, 'method': '', 'params': params}
        self.method = method_name
        try:
            self.parser = eval('wip.' + method_name + '_parser', {'wip': __import__('wip')})
        except:
            self.parser = Command.default_parser
        self.params = params
        self.options = None
        self.callback = None
        self.response = None
        self.error = None
        self.data = None

    def get_id(self):
        return self.request['id']

    def set_id(self, value):
        self.request['id'] = value

    def get_method(self):
        return self.request['method']

    def set_method(self, value):
        self.request['method'] = value

    id = property(get_id, set_id)
    method = property(get_method, set_method)

    @staticmethod
    def default_parser(params):
        return params

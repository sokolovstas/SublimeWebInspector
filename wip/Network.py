from utils import WIPObject, Command


def clearBrowserCache():
    command = Command('Network.clearBrowserCache', {})
    return command


class RequestId(WIPObject):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

from .utils import Command


def reload():
    command = Command('Page.reload', {})
    return command

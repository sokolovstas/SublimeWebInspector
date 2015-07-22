from .wkutils import Command


def reload():
    command = Command('Page.reload', {})
    return command

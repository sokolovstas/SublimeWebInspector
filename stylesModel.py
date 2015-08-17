import webkit

from webkit import wkutils 

class RuleMatch(wkutils.WebkitObject):
    def __init__(self, value):
       self.value = value
       self.set_class(value, 'rule', Rule)

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class Rule(wkutils.WebkitObject):
    def __init__(self, value):
        self.value = value
        self.set(value, 'origin')
        self.selectorList = value["selectorList"]["text"]

        # If origin is user-agent, styleSheedId is not set
        self.set(value, 'styleSheedId', "")
        self.set_class(value, 'style', Style)

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

class Style(wkutils.WebkitObject):
    def __init__(self, value):
        self.value = value
        self.cssProperties = [] 

        properties = value["cssProperties"]
        for prop in properties:
            self.cssProperties.append(StyleRulePair(prop))

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

class StyleRulePair(wkutils.WebkitObject):
    def __init__(self, value):
        self.value = value
        self.enabled = False

        self.set(value, 'name')
        self.set(value, 'value')

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

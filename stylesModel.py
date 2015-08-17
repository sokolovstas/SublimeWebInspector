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

class StyleUtility:
    __style_cache = {}

    @staticmethod
    def clear_cache():
        StyleUtility.__style_cache = {}

    @staticmethod
    def calculate_applied_styles(matched_rules, property_name):
        for item in matched_rules:
            # Search for property name in the selectorList
            props = [style_pair for style_pair in item.rule.style.cssProperties if property_name == style_pair.name]

            # Search the list from bottom up, because a style property encountered later in the rule
            # takes precedence over it.
            for prop in reversed(props):
                # Mark the first property encountered in the list as applied
                prop.enabled = True
                return
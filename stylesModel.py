import ntpath
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

        # If origin is user-agent, styleSheetId is not set
        self.set(value, 'styleSheetId', "")
        self.stylesheet_name = StyleUtility.get_stylesheet(self.styleSheetId)
        self.set_class(value, 'style', Style)

        # Assign uids to styles
        uid = 1
        for style_pair in self.style.cssProperties:
            style_pair.uid = self.styleSheetId + "/" + self.selectorList + "#" + str(uid)
            uid = uid + 1

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value

    def get_stylesheet_name(self):
        return ntpath.split(self.stylesheet_name)[1]


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
        self.uid = ""
        self.__enabled = None

        # If the style property is coming from a CSS file, we have its 
        # disabled property set.
        if "disabled" in value:
            self.__enabled = not value["disabled"]

        # If the style property is coming from a CSS file, we have 
        # information about its text range in the CSS file.
        self.cssRange = None
        if "range" in value:
            self.cssRange = CSSRange(value["range"])

        self.set(value, 'text', '')
        self.set(value, 'name')
        self.set(value, 'value')

    def is_enabled(self):
        if self.__enabled == None:
            self.__enabled = StyleUtility.is_winning_property(self.name, self.uid)

        return self.__enabled

    def __str__(self):
        return self.value

    def __call__(self):
        return self.value


class CSSRange(wkutils.WebkitObject):
    def __init__(self, value):
        self.value = value
        self.set(value, "endColumn")
        self.set(value, "endLine")
        self.set(value, "startColumn")
        self.set(value, "startLine")

    def __str__(self):
        self.value

    def __call__(self):
        return self.value


class StyleUtility:
    __style_cache = {}
    __matched_rules = []
    __stylesheet_map = {}
    current_node_id = None

    @staticmethod
    def add_stylesheet(style_id, url, path):
        StyleUtility.__stylesheet_map[style_id] = { "url": url, "path": path }

    def get_stylesheet(style_id):
        if style_id in StyleUtility.__stylesheet_map:
            return StyleUtility.__stylesheet_map[style_id]["path"]
        return ""

    @staticmethod
    def set_matched_rules(matched_rules):
        StyleUtility.__matched_rules = matched_rules
        StyleUtility.__style_cache = {}

    @staticmethod
    def is_winning_property(property_name, uid):
        if not property_name in StyleUtility.__style_cache:
            StyleUtility.calculate_applied_style(property_name)

        return StyleUtility.__style_cache[property_name] == uid

    @staticmethod
    def calculate_applied_style(property_name):
        for item in StyleUtility.__matched_rules:
            # Search for property name in the selectorList
            props = [style_pair for style_pair in item.rule.style.cssProperties if property_name == style_pair.name]

            # Search the list from bottom up, because a style property encountered later in the rule
            # takes precedence over the other.
            for prop in reversed(props):
                # Mark the first property encountered in the list as applied
                prop.enabled = True

                # Cache the winning property 
                StyleUtility.__style_cache[property_name] = prop.uid
                return
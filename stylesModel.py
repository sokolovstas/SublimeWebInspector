import ntpath
import webkit
import protocol
import styles

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

        # If origin is user-agent, styleSheetId is not set
        self.set(value, 'styleSheetId', "")

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
        self.sourceRange = None
        if "range" in value:
            self.sourceRange = SourceRange(value["range"])

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


class SourceRange(wkutils.WebkitObject):
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
    __stylesheet_map = {}
    __pending_property_updates_map = {}

    __all_rules = []
    __inline_rule = None
    __matched_rules = []
    __inherited_rules = []

    current_node_id = None
    inline_style_prefix = "inlineWebKitStylePrefix#"

    @staticmethod
    def get_inline_rule():
        return StyleUtility.__inline_rule
        
    @staticmethod
    def set_inline_rule(inline_rule):
        # Since inline properties are not part of any rules, 
        # we assign uids when we set it here
        StyleUtility.__inline_rule = inline_rule
        uid = 1
        if StyleUtility.__inline_rule:
            for prop in StyleUtility.__inline_rule.cssProperties:
                prop.uid =  StyleUtility.inline_style_prefix + str(uid)
                uid = uid + 1

    @staticmethod
    def get_matched_rules():
        return StyleUtility.__matched_rules

    @staticmethod
    def set_matched_rules(matched_rules):
        StyleUtility.__matched_rules = matched_rules
        StyleUtility.__all_rules.extend(matched_rules)

    @staticmethod
    def set_inherited_rules(inherited_rules):
        StyleUtility.__inherited_rules = inherited_rules
        StyleUtility.__all_rules.extend(inherited_rules)

    @staticmethod
    def get_inherited_rules():
        return StyleUtility.__inherited_rules

    @staticmethod
    def clear_styles_cache():
        StyleUtility.__style_cache = {}
        StyleUtility.__inline_rules = []
        StyleUtility.__matched_rules = []
        StyleUtility.__inherited_rules = []
        StyleUtility.__all_rules = []

    @staticmethod
    def set_property_enabled_state(style, propertyIndex, enabled):
        if propertyIndex >= len(style.cssProperties):
            return

        prop_item = style.cssProperties[propertyIndex]

        text = ""
        if (prop_item.sourceRange) and len(prop_item.text):
            text = prop_item.name + ": " + prop_item.value + ";"
            text = text if enabled else "/* " + text + " */"

        if len(text) > 0:
            # Store this in a map, to update the styles when we get a response back from the target.
            StyleUtility.__pending_property_updates_map[style.styleSheetId] = style
            protocol.Channel.channel.send(webkit.CSS.setPropertyText(style.styleSheetId, prop_item.sourceRange.value, text), StyleUtility.update_style_change)

    @staticmethod
    def update_style_change(command):
        if command.data["styleSheetId"] in StyleUtility.__pending_property_updates_map:
            style = StyleUtility.__pending_property_updates_map[command.data["styleSheetId"]]

            uid_prefix = style.cssProperties[0].uid.split("#")[0]

            # Clear all its existing properties, and update with new ones
            style.cssProperties = []
            uid = 1
            properties = command.data["cssProperties"]
            for prop in properties:
                style_prop = StyleRulePair(prop)
                style_prop.uid = uid_prefix + "#" + str(uid)
                style.cssProperties.append(style_prop)
                uid = uid + 1

            styles.displayAppliedStyles()
        else:
            assert False, "Style rule for the update notification not found"

    @staticmethod
    def add_stylesheet(style_id, url, path):
        StyleUtility.__stylesheet_map[style_id] = { "url": url, "path": path }

    def get_stylesheet(style_id):
        if style_id in StyleUtility.__stylesheet_map:
            return StyleUtility.__stylesheet_map[style_id]["path"]
        return ""

    @staticmethod
    def is_winning_property(property_name, uid):
        if not property_name in StyleUtility.__style_cache:
            StyleUtility.calculate_applied_style(property_name)

        return StyleUtility.__style_cache[property_name] == uid

    @staticmethod
    def calculate_applied_style(property_name):
        if StyleUtility.__inline_rule:
            inline_prop = [p for p in StyleUtility.__inline_rule.cssProperties if p.name == property_name]
            if len(inline_prop) > 0:
                inline_prop[0].enabled = True
                StyleUtility.__style_cache[property_name] = inline_prop[0].uid
                return

        for item in StyleUtility.__all_rules:
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

    @staticmethod
    def toggle_property(enabled, args):
        # Toggle the property state
        propertyIndex = args["propertyIndex"]
        if "uid" in args and args["uid"].index(StyleUtility.inline_style_prefix) == 0:
                StyleUtility.set_property_enabled_state(StyleUtility.__inline_rule, propertyIndex, not enabled)
        else:
            ruleIndex = args["ruleIndex"]
            if ruleIndex < len(StyleUtility.__all_rules):
                StyleUtility.set_property_enabled_state(StyleUtility.__all_rules[ruleIndex].style, propertyIndex, not enabled)

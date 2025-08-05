import re
from typing import Any


class Inflector:
    def __init__(self):
        self._rules: dict[str, dict[str, Any]] = {}
        self._initialize_locale('en')

        # Add default English rules
        self.add_plural_rule(r"([sxz])$", r"\1es", locale='en')  # box -> boxes
        self.add_plural_rule(r"([^aeiouy]|qu)y$", r"\1ies", locale='en')  # query -> queries
        self.add_plural_rule(r"$", r"s", locale='en')  # fallback

        self.add_singular_rule(r"([^aeiouy]|qu)ies$", r"\1y", locale='en')  # puppies → puppy
        self.add_singular_rule(r"(ch|sh|x|ss|z)es$", r"\1", locale='en')
        self.add_singular_rule(r"ies$", r"y", locale='en')                 # flies → fly (fallback)
        self.add_singular_rule(r"ves$", r"f", locale='en')                 # wolves → wolf (optional)
        self.add_singular_rule(r"oes$", r"o", locale='en')                 # heroes → hero (optional)
        self.add_singular_rule(r"s$", r"", locale='en')                   # cars → car

        self.add_irregular("person", "people", locale='en')
        self.add_uncountable("sheep", locale='en')
        self.add_uncountable("fish", locale='en')

    def _initialize_locale(self, locale: str):
        if locale not in self._rules:
            self._rules[locale] = {
                'plural_rules': [],
                'singular_rules': [],
                'irregular_singular_to_plural': {},
                'irregular_plural_to_singular': {},
                'uncountable_words': set()
            }

    def add_plural_rule(self, rule: str, replacement: str, locale: str = 'en'):
        self._initialize_locale(locale)
        self._rules[locale]['plural_rules'].append((re.compile(rule, re.UNICODE), replacement))

    def add_singular_rule(self, rule: str, replacement: str, locale: str = 'en'):
        self._initialize_locale(locale)
        self._rules[locale]['singular_rules'].append((re.compile(rule, re.UNICODE), replacement))

    def add_irregular(self, singular: str, plural: str, locale: str = 'en'):
        self._initialize_locale(locale)
        self._rules[locale]['irregular_singular_to_plural'][singular.lower()] = plural
        self._rules[locale]['irregular_plural_to_singular'][plural.lower()] = singular

    def add_uncountable(self, word: str, locale: str = 'en'):
        self._initialize_locale(locale)
        self._rules[locale]['uncountable_words'].add(word.lower())

    def get_plural_rules(self, locale: str = 'en') -> list[tuple[re.Pattern, str]]:
        return self._rules.get(locale, {}).get('plural_rules', [])

    def get_singular_rules(self, locale: str = 'en') -> list[tuple[re.Pattern, str]]:
        return self._rules.get(locale, {}).get('singular_rules', [])

    def remove_plural_rule(self, pattern: str, locale: str = 'en'):
        compiled = re.compile(pattern, re.UNICODE)
        self._rules[locale]['plural_rules'] = [
            r for r in self._rules[locale]['plural_rules']
            if r[0].pattern != compiled.pattern
        ]

    def remove_singular_rule(self, pattern: str, locale: str = 'en'):
        compiled = re.compile(pattern, re.UNICODE)
        self._rules[locale]['singular_rules'] = [
            r for r in self._rules[locale]['singular_rules']
            if r[0].pattern != compiled.pattern
        ]

    def _match_case(self, word: str, replacement: str) -> str:
        if word.isupper():
            return replacement.upper()
        elif word[0].isupper():
            return replacement.capitalize()
        return replacement

    def pluralize(self, word: str, locale: str = 'en') -> str:
        rules = self._rules.get(locale)
        if not rules:
            return word

        lower = word.lower()
        if lower in rules['uncountable_words']:
            return word
        if lower in rules['irregular_singular_to_plural']:
            return self._match_case(word, rules['irregular_singular_to_plural'][lower])

        for rule, replacement in rules['plural_rules']:
            if rule.search(word):
                return rule.sub(replacement, word)

        return word + "s"

    def singularize(self, word: str, locale: str = 'en') -> str:
        rules = self._rules.get(locale)
        if not rules:
            return word

        lower = word.lower()
        if lower in rules['uncountable_words']:
            return word
        if lower in rules['irregular_plural_to_singular']:
            return self._match_case(word, rules['irregular_plural_to_singular'][lower])

        for rule, replacement in rules['singular_rules']:
            if rule.search(word):
                return rule.sub(replacement, word)

        return word

    def underscore(self, word: str) -> str:
        word = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", word)
        word = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", word)
        return word.replace("-", "_").lower()

    def camelize(self, word: str, uppercase_first_letter: bool = True) -> str:
        word = word.replace("_", " ").replace("-", " ")
        word = "".join(x.capitalize() for x in word.split())
        if not uppercase_first_letter and word:
            word = word[0].lower() + word[1:]
        return word

    def tableize(self, class_name: str, locale: str = 'en') -> str:
        return self.pluralize(self.underscore(class_name), locale=locale)

    def classify(self, table_name: str, locale: str = 'en') -> str:
        return self.camelize(self.singularize(table_name, locale=locale), uppercase_first_letter=True)

    def foreign_key(self, class_name: str) -> str:
        return self.underscore(class_name) + "_id"


inflector = Inflector()

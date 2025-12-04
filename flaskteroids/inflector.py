import re
from typing import Any

Rule = tuple[re.Pattern[str], str]


class Inflector:
    """
    Basic inflector supporting pluralization, singularization,
    and naming helpers (underscore, camelize, tableize, classify, foreign_key).

    Rules are locale-specific; currently only 'en' is initialized by default.
    The English rules cover common cases but are not linguistically complete.
    """

    def __init__(self):
        self._rules: dict[str, dict[str, Any]] = {}
        self._initialize_locale("en")

        # Add default English rules
        self.add_plural_rule(r"([sxz])$", r"\1es", locale="en")  # box -> boxes
        self.add_plural_rule(
            r"([^aeiouy]|qu)y$", r"\1ies", locale="en"
        )  # query -> queries
        self.add_plural_rule(r"$", r"s", locale="en")  # fallback

        self.add_singular_rule(
            r"([^aeiouy]|qu)ies$", r"\1y", locale="en"
        )  # puppies → puppy
        self.add_singular_rule(r"(ch|sh|x|ss|z)es$", r"\1", locale="en")
        self.add_singular_rule(r"ies$", r"y", locale="en")  # flies → fly (fallback)
        self.add_singular_rule(r"ves$", r"f", locale="en")  # wolves → wolf (optional)
        self.add_singular_rule(r"oes$", r"o", locale="en")  # heroes → hero (optional)
        self.add_singular_rule(r"s$", r"", locale="en")  # cars → car

        self.add_irregular("person", "people", locale="en")
        self.add_irregular("man", "men", locale="en")
        self.add_irregular("woman", "women", locale="en")
        self.add_irregular("child", "children", locale="en")
        self.add_irregular("tooth", "teeth", locale="en")
        self.add_irregular("foot", "feet", locale="en")
        self.add_irregular("goose", "geese", locale="en")
        self.add_irregular("mouse", "mice", locale="en")
        self.add_irregular("louse", "lice", locale="en")
        self.add_irregular("ox", "oxen", locale="en")
        self.add_irregular("leaf", "leaves", locale="en")
        self.add_irregular("life", "lives", locale="en")
        self.add_irregular("knife", "knives", locale="en")
        self.add_irregular("wife", "wives", locale="en")
        self.add_irregular("self", "selves", locale="en")
        self.add_irregular("elf", "elves", locale="en")
        self.add_irregular("loaf", "loaves", locale="en")
        self.add_irregular("potato", "potatoes", locale="en")
        self.add_irregular("tomato", "tomatoes", locale="en")
        self.add_irregular("cactus", "cacti", locale="en")
        self.add_irregular("focus", "foci", locale="en")
        self.add_irregular("fungus", "fungi", locale="en")
        self.add_irregular("nucleus", "nuclei", locale="en")
        self.add_irregular("syllabus", "syllabi", locale="en")
        self.add_irregular("analysis", "analyses", locale="en")
        self.add_irregular("diagnosis", "diagnoses", locale="en")
        self.add_irregular("thesis", "theses", locale="en")
        self.add_irregular("crisis", "crises", locale="en")
        self.add_irregular("phenomenon", "phenomena", locale="en")
        self.add_irregular("criterion", "criteria", locale="en")
        self.add_irregular("datum", "data", locale="en")
        self.add_irregular("medium", "media", locale="en")
        self.add_irregular("index", "indices", locale="en")
        self.add_irregular("appendix", "appendices", locale="en")
        self.add_irregular("matrix", "matrices", locale="en")
        self.add_irregular("vertex", "vertices", locale="en")
        self.add_irregular("axis", "axes", locale="en")
        self.add_irregular("quiz", "quizzes", locale="en")
        self.add_irregular("status", "statuses", locale="en")
        self.add_irregular("alias", "aliases", locale="en")
        self.add_irregular("octopus", "octopuses", locale="en")
        self.add_irregular("virus", "viruses", locale="en")
        self.add_irregular("bus", "buses", locale="en")
        self.add_irregular("campus", "campuses", locale="en")
        self.add_irregular("move", "moves", locale="en")
        self.add_irregular("sex", "sexes", locale="en")
        self.add_irregular("shoe", "shoes", locale="en")
        self.add_irregular("zombie", "zombies", locale="en")

        self.add_uncountable("sheep", locale="en")
        self.add_uncountable("fish", locale="en")
        self.add_uncountable("deer", locale="en")
        self.add_uncountable("species", locale="en")
        self.add_uncountable("series", locale="en")
        self.add_uncountable("news", locale="en")
        self.add_uncountable("rice", locale="en")
        self.add_uncountable("money", locale="en")
        self.add_uncountable("information", locale="en")
        self.add_uncountable("equipment", locale="en")
        self.add_uncountable("moose", locale="en")
        self.add_uncountable("bison", locale="en")
        self.add_uncountable("salmon", locale="en")
        self.add_uncountable("trout", locale="en")
        self.add_uncountable("swine", locale="en")
        self.add_uncountable("aircraft", locale="en")
        self.add_uncountable("spacecraft", locale="en")
        self.add_uncountable("hovercraft", locale="en")
        self.add_uncountable("watercraft", locale="en")

    def _initialize_locale(self, locale: str):
        if locale not in self._rules:
            self._rules[locale] = {
                "plural_rules": [],
                "singular_rules": [],
                "irregular_singular_to_plural": {},
                "irregular_plural_to_singular": {},
                "uncountable_words": set(),
            }

    def add_plural_rule(self, rule: str, replacement: str, locale: str = "en"):
        """Add a regex-based pluralization rule for the given locale."""
        self._initialize_locale(locale)
        self._rules[locale]["plural_rules"].append(
            (re.compile(rule, re.UNICODE), replacement)
        )

    def add_singular_rule(self, rule: str, replacement: str, locale: str = "en"):
        """Add a regex-based singularization rule for the given locale."""
        self._initialize_locale(locale)
        self._rules[locale]["singular_rules"].append(
            (re.compile(rule, re.UNICODE), replacement)
        )

    def add_irregular(self, singular: str, plural: str, locale: str = "en"):
        """
        Add an irregular singular/plural pair.

        Both forms are stored in lowercase; original casing is restored
        via _match_case when inflecting.
        """
        self._initialize_locale(locale)
        s = singular.lower()
        p = plural.lower()
        self._rules[locale]["irregular_singular_to_plural"][s] = p
        self._rules[locale]["irregular_plural_to_singular"][p] = s

    def add_uncountable(self, word: str, locale: str = "en"):
        """Mark a word as uncountable (e.g., 'sheep', 'fish')."""
        self._initialize_locale(locale)
        self._rules[locale]["uncountable_words"].add(word.lower())

    def get_plural_rules(self, locale: str = "en") -> list[Rule]:
        """Return the list of plural rules for the given locale."""
        return self._rules.get(locale, {}).get("plural_rules", [])

    def get_singular_rules(self, locale: str = "en") -> list[Rule]:
        """Return the list of singular rules for the given locale."""
        return self._rules.get(locale, {}).get("singular_rules", [])

    def remove_plural_rule(self, pattern: str, locale: str = "en"):
        """Remove a plural rule by its pattern. No-op if locale doesn't exist."""
        rules = self._rules.get(locale)
        if not rules:
            return
        compiled = re.compile(pattern, re.UNICODE)
        rules["plural_rules"] = [
            r for r in rules["plural_rules"] if r[0].pattern != compiled.pattern
        ]

    def remove_singular_rule(self, pattern: str, locale: str = "en"):
        """Remove a singular rule by its pattern. No-op if locale doesn't exist."""
        rules = self._rules.get(locale)
        if not rules:
            return
        compiled = re.compile(pattern, re.UNICODE)
        rules["singular_rules"] = [
            r for r in rules["singular_rules"] if r[0].pattern != compiled.pattern
        ]

    def _match_case(self, word: str, replacement: str) -> str:
        """Match the case of replacement to the original word."""
        if not word:
            return replacement
        if word[0].isupper() and (len(word) == 1 or word[1:].islower()):
            return replacement.capitalize()
        if word.isupper():
            return replacement.upper()
        return replacement

    def pluralize(self, word: str, locale: str = "en") -> str:
        """
        Return the plural form of a word.

        Checks uncountables, then irregulars, then applies regex rules in order.
        """
        if not word:
            return word

        rules = self._rules.get(locale)
        if not rules:
            return word

        lower = word.lower()
        if lower in rules["uncountable_words"]:
            return word
        if lower in rules["irregular_singular_to_plural"]:
            return self._match_case(word, rules["irregular_singular_to_plural"][lower])

        for rule, replacement in rules["plural_rules"]:
            new_word, count = rule.subn(replacement, word)
            if count:
                return new_word

        return word + "s"

    def singularize(self, word: str, locale: str = "en") -> str:
        """
        Return the singular form of a word.

        Checks uncountables, then irregulars, then applies regex rules in order.
        """
        if not word:
            return word

        rules = self._rules.get(locale)
        if not rules:
            return word

        lower = word.lower()
        if lower in rules["uncountable_words"]:
            return word
        if lower in rules["irregular_plural_to_singular"]:
            return self._match_case(word, rules["irregular_plural_to_singular"][lower])

        for rule, replacement in rules["singular_rules"]:
            new_word, count = rule.subn(replacement, word)
            if count:
                return new_word

        return word

    def underscore(self, word: str) -> str:
        """Convert CamelCase to snake_case (e.g., 'HelloWorld' -> 'hello_world')."""
        word = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", word)
        word = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", word)
        return word.replace("-", "_").lower()

    def camelize(self, word: str, uppercase_first_letter: bool = True) -> str:
        """Convert snake_case to CamelCase (e.g., 'hello_world' -> 'HelloWorld')."""
        word = word.replace("_", " ").replace("-", " ")
        word = "".join(x.capitalize() for x in word.split())
        if not uppercase_first_letter and word:
            word = word[0].lower() + word[1:]
        return word

    def tableize(self, class_name: str, locale: str = "en") -> str:
        """Convert a class name to a table name (e.g., 'BlogPost' -> 'blog_posts')."""
        return self.pluralize(self.underscore(class_name), locale=locale)

    def classify(self, table_name: str, locale: str = "en") -> str:
        """Convert a table name to a class name (e.g., 'blog_posts' -> 'BlogPost')."""
        return self.camelize(
            self.singularize(table_name, locale=locale), uppercase_first_letter=True
        )

    def foreign_key(self, class_name: str) -> str:
        """Generate a foreign key name from a class name (e.g., 'BlogPost' -> 'blog_post_id')."""
        return self.underscore(class_name) + "_id"


inflector = Inflector()
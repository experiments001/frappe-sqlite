"""MarkupSafe shim for iOS — pure-Python fallback.

MarkupSafe is a C extension that doesn't have iOS wheels.
This shim provides the essential APIs that Jinja2 needs.
"""

import re
import string


class Markup(str):
    """A string that is ready to be safely inserted into an HTML or XML
    document.
    """

    __slots__ = ()

    def __new__(cls, base="", encoding=None, errors="strict"):
        if hasattr(base, "__html__"):
            return base.__html__()
        if encoding is not None:
            base = str(base, encoding, errors)
        else:
            base = str(base)
        return super().__new__(cls, base)

    def __html__(self):
        return self

    @classmethod
    def escape(cls, s):
        """Escape a string."""
        if hasattr(s, "__html__"):
            return s.__html__()
        return cls(
            str(s)
            .replace("&", "&amp;")
            .replace(">", "&gt;")
            .replace("<", "&lt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def unescape(self):
        """Unescape a string."""
        from html import unescape
        return unescape(self)

    def striptags(self):
        """Strip HTML tags."""
        return Markup(_striptags_re.sub("", self))

    @classmethod
    def format(cls, *args, **kwargs):
        """Format a string."""
        return cls(str.format(*args, **kwargs))

    def __add__(self, other):
        return self.__class__(super().__add__(other))

    def __radd__(self, other):
        return self.escape(other) + self

    def __mul__(self, num):
        if isinstance(num, int):
            return self.__class__(super().__mul__(num))
        return NotImplemented

    __rmul__ = __mul__

    def __mod__(self, arg):
        if isinstance(arg, tuple):
            arg = tuple(self.escape(x) for x in arg)
        else:
            arg = self.escape(arg)
        return self.__class__(super().__mod__(arg))

    def __repr__(self):
        return f"{self.__class__.__name__}({super().__repr__()})"

    def join(self, seq):
        return self.__class__(super().join(self.escape(x) for x in seq))

    def split(self, sep=None, maxsplit=-1):
        return [self.__class__(x) for x in super().split(sep, maxsplit)]

    def rsplit(self, sep=None, maxsplit=-1):
        return [self.__class__(x) for x in super().rsplit(sep, maxsplit)]

    def splitlines(self, keepends=False):
        return [self.__class__(x) for x in super().splitlines(keepends)]

    def strip(self, chars=None):
        return self.__class__(super().strip(chars))

    def lstrip(self, chars=None):
        return self.__class__(super().lstrip(chars))

    def rstrip(self, chars=None):
        return self.__class__(super().rstrip(chars))

    def center(self, width, fillchar=" "):
        return self.__class__(super().center(width, fillchar))

    def ljust(self, width, fillchar=" "):
        return self.__class__(super().ljust(width, fillchar))

    def rjust(self, width, fillchar=" "):
        return self.__class__(super().rjust(width, fillchar))

    def zfill(self, width):
        return self.__class__(super().zfill(width))

    def replace(self, old, new, count=-1):
        return self.__class__(super().replace(old, new, count))

    def expandtabs(self, tabsize=8):
        return self.__class__(super().expandtabs(tabsize))

    def title(self):
        return self.__class__(super().title())

    def capitalize(self):
        return self.__class__(super().capitalize())

    def swapcase(self):
        return self.__class__(super().swapcase())

    def casefold(self):
        return self.__class__(super().casefold())

    def translate(self, table):
        return self.__class__(super().translate(table))

    def upper(self):
        return self.__class__(super().upper())

    def lower(self):
        return self.__class__(super().lower())


_striptags_re = re.compile(r"(<[^>]+>)")


def escape(s):
    """Convert the characters &, <, >, ', and " in string s to HTML-safe
    sequences.
    """
    if hasattr(s, "__html__"):
        return s.__html__()
    return Markup(
        str(s)
        .replace("&", "&amp;")
        .replace(">", "&gt;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def soft_str(s):
    """Convert an object to a string if it isn't already."""
    if not isinstance(s, str):
        return str(s)
    return s


soft_unicode = soft_str

# Additional exports that Jinja2 might use
__all__ = ["Markup", "escape", "soft_str", "soft_unicode"]

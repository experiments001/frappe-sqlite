# PIL shim for iOS (Pillow unavailable)
__version__ = "0.0.0"


class Image:
    @classmethod
    def open(cls, *a, **k):
        raise NotImplementedError("Pillow not available on iOS")

    def save(self, *a, **k):
        pass

    def resize(self, *a, **k):
        return self

    def convert(self, *a, **k):
        return self

    @property
    def size(self):
        return (0, 0)

    @property
    def format(self):
        return None


class ImageFile:
    pass


class ImageOps:
    @staticmethod
    def fit(*a, **k):
        return Image()


class ExifTags:
    TAGS = {}


class UnidentifiedImageError(Exception):
    pass

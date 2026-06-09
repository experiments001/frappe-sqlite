"""pydantic_core shim for iOS — minimal fallback.

pydantic_core is a Rust extension that doesn't build for iOS.
This shim provides the minimal APIs that pydantic v2 needs.
"""


class PydanticUndefinedType:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self):
        return "PydanticUndefined"


PydanticUndefined = PydanticUndefinedType()


class SchemaValidator:
    """No-op schema validator."""
    def __init__(self, schema, config=None):
        self.schema = schema
        self.config = config or {}

    def validate_python(self, obj, strict=None, from_attributes=None, context=None):
        return obj

    def isinstance_schema(self):
        return False

    def validate_json(self, obj, strict=None, from_attributes=None, context=None):
        return obj

    def validate_strings(self, obj, strict=None, from_attributes=None, context=None):
        return obj


class ValidationError(Exception):
    """Pydantic validation error."""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []
        self.title = "ValidationError"
        self.error_count = lambda: len(self.errors)

    def json(self, indent=None):
        import json
        return json.dumps(self.errors, indent=indent)

    def errors(self):
        return self.errors


class CoreConfig:
    pass


class CoreSchema:
    pass


def __getattr__(name):
    """Return dummy objects for any unknown pydantic_core attribute."""
    if name in ("PydanticUndefined", "SchemaValidator", "ValidationError", "CoreConfig", "CoreSchema"):
        raise AttributeError(f"module 'pydantic_core' has no attribute '{name}'")
    return lambda *args, **kwargs: None

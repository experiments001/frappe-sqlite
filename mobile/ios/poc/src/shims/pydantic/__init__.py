"""pydantic shim for iOS — minimal fallback.

pydantic v2 depends on pydantic_core (Rust) which doesn't build for iOS.
This shim provides the minimal APIs that Frappe uses.
"""

import json
from typing import Any, Dict, List, Optional, Union


class BaseModel:
    """Minimal BaseModel shim."""
    model_config = {}

    def __init__(self, **data):
        for key, value in data.items():
            setattr(self, key, value)

    def __init_subclass__(cls, **kwargs):
        pass

    def model_dump(self, **kwargs):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    def model_dump_json(self, **kwargs):
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            return cls(**obj)
        return obj

    @classmethod
    def model_validate_json(cls, json_str, **kwargs):
        return cls.model_validate(json.loads(json_str))

    @classmethod
    def model_json_schema(cls, **kwargs):
        return {}

    def __repr__(self):
        return f"{self.__class__.__name__}({self.model_dump()})"


class ValidationError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []
        self.title = "ValidationError"

    def json(self, indent=None):
        return json.dumps(self.errors, indent=indent)


class HttpUrl(str):
    """URL type shim."""
    pass


class ConfigDict(dict):
    pass


def Field(default=None, **kwargs):
    """Field definition shim."""
    return default


def field_validator(*fields, mode='after', **kwargs):
    """Decorator shim that returns the function unchanged."""
    def decorator(func):
        return func
    return decorator


def model_validator(mode='after', **kwargs):
    """Decorator shim that returns the function unchanged."""
    def decorator(func):
        return func
    return decorator


def computed_field(**kwargs):
    """Decorator shim that returns the function unchanged."""
    def decorator(func):
        return property(func)
    return decorator


class RootModel:
    def __init__(self, root):
        self.root = root


def __getattr__(name):
    """Return dummy objects for any unknown pydantic attribute."""
    known = {"BaseModel", "ValidationError", "HttpUrl", "ConfigDict", "Field",
             "field_validator", "model_validator", "computed_field", "RootModel"}
    if name in known:
        raise AttributeError(f"module 'pydantic' has no attribute '{name}'")
    return lambda *args, **kwargs: None

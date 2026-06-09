"""nh3 compatibility shim for iOS (embedded Python).

nh3 is a Rust-based HTML sanitizer that doesn't build for iOS.
This shim provides a minimal safe fallback using html.escape.
"""

import html

ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def clean(
    html_string,
    tags=None,
    clean_content_tags=None,
    attributes=None,
    attribute_filter=None,
    strip_comments=False,
    link_rel=None,
    url_schemes=None,
    allow_parameterized_media=None,
    generic_attribute_prefixes=None,
    filter_style_properties=None,
):
    """Minimal fallback: escape all HTML to prevent XSS."""
    return html.escape(html_string)

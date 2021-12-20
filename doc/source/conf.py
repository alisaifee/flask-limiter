# -*- coding: utf-8 -*-
#

import sys
import os

sys.path.insert(0, os.path.abspath("../../"))
import flask_limiter

copyright = "2014, Ali-Akber Saifee"
master_doc = "index"
project = "Flask-Limiter"
version = release = flask_limiter.__version__.split("+")[0]
colors = {
    "bg0": " #fbf1c7",
    "bg1": " #ebdbb2",
    "bg2": " #d5c4a1",
    "bg3": " #bdae93",
    "bg4": " #a89984",
    "gry": " #928374",
    "fg4": " #7c6f64",
    "fg3": " #665c54",
    "fg2": " #504945",
    "fg1": " #3c3836",
    "fg0": " #282828",
    "red": " #cc241d",
    "red2": " #9d0006",
    "orange": " #d65d0e",
    "orange2": " #af3a03",
    "yellow": " #d79921",
    "yellow2": " #b57614",
    "green": " #98971a",
    "green2": " #79740e",
    "aqua": " #689d6a",
    "aqua2": " #427b58",
    "blue": " #458588",
    "blue2": " #076678",
    "purple": " #b16286",
    "purple2": " #8f3f71",
}
html_favicon = "_static/tap-icon.png"
html_static_path = ["./_static"]
html_css_files = [
    "custom.css",
    "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;700&family=Fira+Sans:ital,wght@0,100;0,400;0,800;0,900;1,800;1,900&display=swap",
]
html_theme = "alabaster"

html_theme_options = {
    "logo": "tap-logo.png",
    "github_user": "alisaifee",
    "github_repo": "flask_limiter",
    "github_button": False,
    "github_banner": True,
    "fixed_sidebar": True,
    "globaltoc_collapse": False,
    "globaltoc_maxdepth": 0,
    "description": """
    Flask-Limiter provides rate limiting features to flask routes.
    It has support for a configurable backend for storage with implementations
    for in-memory, redis, memcache & mongodb.""",
    # Style related overrides
    "anchor": "",
    "anchor_hover_bg": "",
    "anchor_hover_fg": colors["purple"],
    "body_text": colors["fg0"],
    "pre_bg": colors["fg0"],
    "code_highlight": colors["bg4"],
    "code_bg": colors["bg1"],
    "code_text": colors["fg3"],
    "footer_text": colors["fg0"],
    # "footnote_bg": "",
    # "footnote_border": "",
    "gray_1": colors["fg0"],
    "gray_2": colors["fg1"],
    "gray_3": colors["fg2"],
    "link_hover": colors["blue"],
    "link": colors["blue2"],
    "narrow_sidebar_bg": colors["fg0"],
    "narrow_sidebar_fg": colors["bg0"],
    "narrow_sidebar_link": colors["purple2"],
    "important_bg": colors["blue"],
    "important_border": colors["blue"],
    "note_bg": colors["blue"],
    "note_border": colors["blue"],
    "warn_bg": colors["orange"],
    "warn_border": colors["orange"],
    "pink_1": colors["red"],
    "pink_2": colors["red"],
    # "relbar_border": "",
    # "seealso_bg": "",
    # "seealso_border": "",
    # "sidebar_header": "",
    # "sidebar_hr": "",
    "sidebar_link": colors["purple2"],
    "sidebar_list": colors["fg3"],
    "sidebar_link_underscore": colors["purple"],
    "sidebar_search_button": colors["fg3"],
    "sidebar_text": colors["fg2"],
    "caption_font_family": "Fira Sans",
    "code_font_family": "Fira Code",
    "font_family": "Fira Sans",
    "head_font_family": "Fira Sans",
    # "caption_font_size": "",
    "code_font_size": "smaller",
    # "font_size": "",
}
panels_css_variables = {
    "tabs-color-label-active": colors["purple2"],
    "tabs-color-label-inactive": colors["purple"],
    "tabs-color-overline": colors["purple"],
    "tabs-color-underline": colors["purple2"],
    "tabs-size-label": "1rem",
}
html_sidebars = {
    "**": [
        "about.html",
        "searchbox.html",
        "localtoc.html",
        "relations.html",
        "donate.html",
    ]
}

highlight_language = "python3"
pygments_style = "gruvbox-dark"

extensions = [
    "alabaster",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinxcontrib.programoutput",
    "sphinx_autodoc_typehints",
    "sphinx_panels",
]

autodoc_default_options = {
    "members": True,
    "inherited-members": True,
    "inherit-docstrings": True,
    "member-order": "bysource",
}
add_module_names = False
autoclass_content = "both"
autosectionlabel_maxdepth = 3
autosectionlabel_prefix_document = True

extlinks = {"pypi": ("https://pypi.org/project/%s", "%s")}

intersphinx_mapping = {
    "python": ("http://docs.python.org/", None),
    "limits": ("https://limits.readthedocs.io/en/latest/", None),
    "redis-py-cluster": ("https://redis-py-cluster.readthedocs.io/en/latest/", None),
    "redis-py": ("https://redis-py.readthedocs.io/en/latest/", None),
    "pymemcache": ("https://pymemcache.readthedocs.io/en/latest/", None),
    "pymongo": ("https://pymongo.readthedocs.io/en/stable/", None),
    "flask": ("https://flask.palletsprojects.com/en/latest/", None),
    "werkzeug": ("https://werkzeug.palletsprojects.com/en/latest/", None),
    "limits": ("http://limits.readthedocs.org/en/latest/", None),
    "flaskrestful": ("http://flask-restful.readthedocs.org/en/latest/", None),
}

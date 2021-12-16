# -*- coding: utf-8 -*-
#

import sys
import os

sys.path.insert(0, os.path.abspath("../../"))
import flask_limiter

extensions = [
    "pallets_sphinx_themes",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_tabs.tabs",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = "Flask-Limiter"
copyright = "2014, Ali-Akber Saifee"

version = release = flask_limiter.__version__
exclude_patterns = []
pygments_style = "gruvbox-light"
html_theme = "flask"

htmlhelp_basename = "Flask-Ratelimitdoc"
html_logo = "_static/tap-logo.png"
html_favicon = "_static/tap-icon.png"
html_sidebars = {
    "index": [
        "sidebarintro.html",
        "localtoc.html",
        "sourcelink.html",
        "searchbox.html",
    ],
    "**": ["localtoc.html", "relations.html", "sourcelink.html", "searchbox.html"],
}

latex_documents = [
    (
        "index",
        "Flask-Limiter.tex",
        "Flask-Limiter Documentation",
        "Ali-Akber Saifee",
        "manual",
    ),
]
man_pages = [
    ("index", "flask-limiter", "Flask-Limiter Documentation", ["Ali-Akber Saifee"], 1)
]

texinfo_documents = [
    (
        "index",
        "Flask-Limiter",
        "Flask-Limiter Documentation",
        "Ali-Akber Saifee",
        "Flask-Limiter",
        "One line description of project.",
        "Miscellaneous",
    ),
]

intersphinx_mapping = {
    "python": ("http://docs.python.org/", None),
    "flask": ("https://flask.palletsprojects.com/en/latest/", None),
    "werkzeug": ("https://werkzeug.palletsprojects.com/en/latest/", None),
    "limits": ("http://limits.readthedocs.org/en/latest/", None),
    "flaskrestful": ("http://flask-restful.readthedocs.org/en/latest/", None),
}

autodoc_default_options = {"members": True, "show-inheritance": True}

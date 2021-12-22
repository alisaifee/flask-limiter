# -*- coding: utf-8 -*-
#

import sys
import os

sys.path.insert(0, os.path.abspath("../../"))
sys.path.insert(0, os.path.abspath("./"))

import flask_limiter
from theme_config import *


description = "Flask-Limiter provides rate limiting features to flask applications."
copyright = "2021, Ali-Akber Saifee"
project = "Flask-Limiter"

release = flask_limiter.__version__.split("+")[0]
version = flask_limiter.__version__

html_favicon = "_static/tap-icon.ico"
html_static_path = ["./_static"]
templates_path = ["./_templates"]
html_css_files = [
    "custom.css",
    "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;700&family=Fira+Sans:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap"
]
html_theme_options["github_repo"] = "flask-limiter"
html_theme_options["description"] = description
html_sidebars = {
    "**": [
        "about.html",
        "searchbox.html",
        "navigation.html",
        "relations.html",
        "donate.html",
    ]
}


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
    "sphinx_paramlinks",
]

autodoc_default_options = {
    "members": True,
    "inherited-members": True,
    "inherit-docstrings": True,
    "member-order": "bysource",
}
add_module_names = False

autosectionlabel_maxdepth = 3
autosectionlabel_prefix_document = True

extlinks = {
    "pypi": ("https://pypi.org/project/%s", "%s"),
    "githubsrc": ("https://github.com/alisaifee/flask-limiter/blob/master/%s", "%s"),

}

intersphinx_mapping = {
    "python": ("http://docs.python.org/", None),
    "limits": ("https://limits.readthedocs.io/en/stable/", None),
    "redis-py-cluster": ("https://redis-py-cluster.readthedocs.io/en/latest/", None),
    "redis-py": ("https://redis-py.readthedocs.io/en/latest/", None),
    "pymemcache": ("https://pymemcache.readthedocs.io/en/latest/", None),
    "pymongo": ("https://pymongo.readthedocs.io/en/stable/", None),
    "flask": ("https://flask.palletsprojects.com/en/latest/", None),
    "werkzeug": ("https://werkzeug.palletsprojects.com/en/latest/", None),
    "flaskrestful": ("http://flask-restful.readthedocs.org/en/latest/", None),
}


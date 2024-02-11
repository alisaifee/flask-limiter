#

import os
import re
import sys

sys.path.insert(0, os.path.abspath("../../"))
sys.path.insert(0, os.path.abspath("./"))

from theme_config import *

import flask_limiter

description = "Flask-Limiter adds rate limiting to flask applications."
copyright = "2023, Ali-Akber Saifee"
project = "Flask-Limiter"

ahead = 0

if ".post0.dev" in flask_limiter.__version__:
    version, ahead = flask_limiter.__version__.split(".post0.dev")
else:
    version = flask_limiter.__version__

release = version

html_title = f"{project} <small><b style='color: var(--color-brand-primary)'>{{{release}}}</b></small>"
try:
    ahead = int(ahead)

    if ahead > 0:
        html_theme_options[
            "announcement"
        ] = f"""
        This is a development version. The documentation for the latest stable version can be found <a href="/en/stable">here</a>
        """
        html_title = f"{project} <small><b style='color: var(--color-brand-primary)'>{{dev}}</b></small>"
except:
    pass

html_favicon = "_static/tap-icon.ico"
html_static_path = ["./_static"]
templates_path = ["./_templates"]
html_css_files = [
    "custom.css",
    "colors.css",
    "https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;700&family=Fira+Sans:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&family=Be+Vietnam+Pro:wght@500&display=swap",
]

html_theme_options.update({"light_logo": "tap-icon.png", "dark_logo": "tap-icon.png"})

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinxext.opengraph",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinxcontrib.programoutput",
    "sphinx_issues",
    "sphinx_inline_tabs",
    "sphinx_paramlinks",
]

autodoc_default_options = {
    "members": True,
    "inherited-members": True,
    "inherit-docstrings": True,
    "member-order": "bysource",
}
add_module_names = False
autoclass_content = "both"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
autosectionlabel_maxdepth = 3
autosectionlabel_prefix_document = True
issues_github_path = "alisaifee/flask-limiter"

ogp_image = "_static/logo-og.png"

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

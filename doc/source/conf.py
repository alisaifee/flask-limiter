# -*- coding: utf-8 -*-
#

import sys
import os

sys.path.insert(0, os.path.abspath('../../'))
sys.path.append(os.path.abspath('_themes'))
import flask_limiter

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = u'Flask-Limiter'
copyright = u'2014, Ali-Akber Saifee'

version = release = flask_limiter.__version__
exclude_patterns = []
pygments_style = 'sphinx'
html_theme_options = {
    "index_logo": "logo.png"
}
html_theme_path = ["_themes"]
html_theme = 'flask'
html_static_path = ['_static']
html_style = 'limiter.css'

htmlhelp_basename = 'Flask-Ratelimitdoc'
html_logo = 'tap-logo.png'
html_favicon = 'tap-icon.png'
html_sidebars = {
    'index': ['sidebarintro.html', 'localtoc.html', 'sourcelink.html', 'searchbox.html'],
    '**': ['localtoc.html', 'relations.html',
           'sourcelink.html', 'searchbox.html']
}

latex_documents = [
    ('index', 'Flask-Limiter.tex', u'Flask-Limiter Documentation',
     u'Ali-Akber Saifee', 'manual'),
]
man_pages = [
    ('index', 'flask-limiter', u'Flask-Limiter Documentation',
     [u'Ali-Akber Saifee'], 1)
]

texinfo_documents = [
    ('index', 'Flask-Limiter', u'Flask-Limiter Documentation',
     u'Ali-Akber Saifee', 'Flask-Limiter', 'One line description of project.',
     'Miscellaneous'),
]

intersphinx_mapping = {'python': ('http://docs.python.org/', None)
    , 'flask': ("http://flask.pocoo.org/docs/", None)
    , 'flaskrestful': ('http://flask-restful.readthedocs.org/en/latest/', None)
}

autodoc_default_flags = [
    "members"
    , "show-inheritance"
]

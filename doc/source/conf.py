# -*- coding: utf-8 -*-
#

import sys
import os
sys.path.insert(0, os.path.abspath('../../'))
sys.path.append(os.path.abspath('../_themes'))
import flask_limiter

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
source_suffix = '.rst'
source_encoding = 'utf-8-sig'
master_doc = 'index'
project = u'Flask-Limiter'
copyright = u'2014, Ali-Akber Saifee'

version = release = flask_limiter.__version__
exclude_patterns = []
pygments_style = 'sphinx'
html_theme_options = {
    "github_fork": "alisaifee/flask-limiter"
}
html_theme_path = ["../_themes"]
html_theme = 'flask_small'
html_static_path = ['_static']
htmlhelp_basename = 'Flask-Ratelimitdoc'
latex_elements = {
}
latex_documents = [
  ('index', 'Flask-Limiter.tex', u'Flask-Limiter Documentation',
   u'Ali-Akber Saifee', 'manual'),
]
man_pages = [
    ('index', 'flask-ratelimit', u'Flask-Limiter Documentation',
     [u'Ali-Akber Saifee'], 1)
]

texinfo_documents = [
  ('index', 'Flask-Limiter', u'Flask-Limiter Documentation',
   u'Ali-Akber Saifee', 'Flask-Limiter', 'One line description of project.',
   'Miscellaneous'),
]
intersphinx_mapping = {'http://docs.python.org/': None}

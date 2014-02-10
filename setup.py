"""
setup.py for Flask-Ratelimits


"""
__author__ = "Ali-Akber Saifee"
__email__ = "ali@indydevs.org"
__copyright__ = "Copyright 2014, Ali-Akber Saifee"

from setuptools import setup, find_packages
import os

this_dir = os.path.abspath(os.path.dirname(__file__))
REQUIREMENTS = filter(None, open(
	os.path.join(this_dir, 'requirements', 'main.txt')).read().splitlines())

import versioneer

versioneer.versionfile_source = "flask_ratelimits/_version.py"
versioneer.versionfile_build = "flask_ratelimits/version.py"
versioneer.tag_prefix = ""
versioneer.parentdir_prefix = "flask_ratelimits-"

setup(
	name='Flask-Ratelimits',
	author=__author__,
	author_email=__email__,
	license=open("LICENSE.txt").read(),
	url="https://flask-ratelimits.readthedocs.org/en/latest/",
	zip_safe=False,
	version=versioneer.get_version(),
	cmdclass=versioneer.get_cmdclass(),
	install_requires=REQUIREMENTS,
	classifiers=[k for k in open('CLASSIFIERS').read().split('\n') if k],
	description='Rate limiting for flask applications',
	long_description=open('README.rst').read() + open('HISTORY.rst').read(),
	packages=find_packages(),
)


# -*- coding: utf-8 -*-

from setuptools import setup
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

__license__ = "MIT, see LICENSE file"
__version__ = "0.1.0.dev1"
__contributors__ = "Martin Uhrin"

setup(
    name="apricotpy",
    version=__version__,
    description='A python event loop with persistence support',
    long_description=long_description,
    url='https://github.com/muhrin/apricotpy',
    author='Martin Uhrin',
    author_email='martin.uhrin@gmail.com',
    license=__license__,
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='event loop, asynchronous',
    # Abstract dependencies.  Concrete versions are listed in
    # requirements.txt
    # See https://caremad.io/2013/07/setup-vs-requirement/ for an explanation
    # of the difference and
    # http://blog.miguelgrinberg.com/post/the-package-dependency-blues
    # for a useful dicussion
    install_requires=[
    ],
    extras_require={
        ':python_version<"3.4"': ['enum34'],
        ':python_version<"3.2"': ['futures'],
        ':python_version<"3.0"': ['future'],
    },
    packages=['apricotpy'],
    test_suite='test'
)

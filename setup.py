#!/usr/bin/env python3
import sys
from distutils.core import setup

if sys.version_info <= (3, 2):
    sys.exit("Python 3.2 or later needed")

setup(
    name='pathlib',
    version=open('VERSION.txt').read().strip(),
    py_modules=['pathlib'],
    license='MIT License',
    description='Object-oriented filesystem paths',
    #long_description=open('README.txt').read(),
    author='Antoine Pitrou',
    author_email='solipsis@pitrou.net',
    #url='http://walkdir.readthedocs.org',
)

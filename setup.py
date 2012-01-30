#!/usr/bin/env python3
import sys
from distutils.core import setup

if sys.version_info <= (3, 2):
    sys.exit("Python 3.2 or later required")

setup(
    name='pathlib',
    version=open('VERSION.txt').read().strip(),
    py_modules=['pathlib'],
    license='MIT License',
    description='Object-oriented filesystem paths',
    #long_description=open('README.txt').read(),
    author='Antoine Pitrou',
    author_email='solipsis@pitrou.net',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Filesystems',
        ],
    download_url='https://pypi.python.org/pypi/pathlib/',
    url='http://readthedocs.org/docs/pathlib/',
)

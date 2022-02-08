# Copyright (c) 2014-2021 Matthias C. M. Troffaes
# Copyright (c) 2012-2014 Antoine Pitrou and contributors
# Distributed under the terms of the MIT License.

import io
from setuptools import setup, find_packages


def readfile(filename):
    with io.open(filename, encoding="utf-8") as stream:
        return stream.read().split("\n")


readme = readfile("README.rst")[5:]  # skip title and badges
version = readfile("VERSION")[0].strip()

setup(
    name='pathlib2',
    version=version,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    license='MIT',
    description='Object-oriented filesystem paths',
    long_description="\n".join(readme[2:]),
    author='Matthias C. M. Troffaes',
    author_email='matthias.troffaes@gmail.com',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Filesystems',
        ],
    url='https://github.com/jazzband/pathlib2',
    python_requires='>=3.6',
)

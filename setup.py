import io
from setuptools import setup
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


def readfile(filename):
    with io.open(filename, encoding="utf-8") as stream:
        return stream.read().split("\n")


readme = readfile("README.rst")[5:]  # skip title and badges
requires = readfile("requirements.txt")
version = readfile("VERSION")[0].strip()


setup(
    name='pathlib2',
    version=version,
    py_modules=['pathlib2'],
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
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: System :: Filesystems',
        ],
    download_url='https://pypi.python.org/pypi/pathlib2/',
    url='https://pathlib2.readthedocs.org/',
    install_requires=requires,
    tests_require=['pytest'],
    cmdclass = {'test': PyTest},
)

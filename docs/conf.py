# Configuration file for the Sphinx documentation builder.

project = 'pathlib2'
copyright = '2012-2014 Antoine Pitrou and contributors; 2014-2021, Matthias C. M. Troffaes and contributors'
author = 'Matthias C. M. Troffaes'

# The full version, including alpha/beta/rc tags
with open("../VERSION", "r") as version_file:
    release = version_file.read().strip()

# -- General configuration ---------------------------------------------------

extensions = []
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

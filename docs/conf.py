# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#

import os
import pathlib
import subprocess

our_dir = pathlib.Path(__file__).parent
#sys.path.insert(0, (our_dir / "src/atbu/tools").resolve().as_posix())

static_subdir = our_dir / "_static"
static_subdir.mkdir(exist_ok=True)

# Remove apidocs/* files created by sphinx-apidoc which are not needed.
# This avoids warnings without the need to insert :orhpan:.
apidocs_subdir = our_dir / "apidocs"

apidoc_to_remove = [
    "modules.rst",
    "atbu.rst",
]

for tr in apidoc_to_remove:
    tr_path = apidocs_subdir / tr
    if tr_path.exists():
        tr_path.unlink()

# Detect if we are running on read the docs
is_running_on_rtd = os.environ.get('READTHEDOCS', '').lower() == 'true'
if is_running_on_rtd:
    cmd = "sphinx-apidoc -d 4 ../src/atbu -o apidocs/ --implicit-namespaces"
    subprocess.call(cmd, shell=True)

# -- Project information -----------------------------------------------------

project = 'ATBU'
copyright = '2022, 2023, Ashley R. Thomas'
author = 'Ashley R. Thomas'

# The full version, including alpha/beta/rc tags
release = '0.036'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.autosummary',
    'myst_parser',
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'classic'
html_theme_options = {
    "codebgcolor": "#ECECEC",
    "body_min_width": "60%"
}
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_css_files = [
    'css/custom.css',
]

def ultimateReplace(app, docname, source):
    result = source[0]
    for key in app.config.ultimate_replacements:
        result = result.replace(key, app.config.ultimate_replacements[key])
    source[0] = result

ultimate_replacements = {
    "|PROJNAMELONG|" : "ATBU Backup & Persistent File Information",
    "|PROJNAME|" : "ATBU",
    "|PKGNAME|" : "atbu-pkg"
}
def setup(app):
    app.add_config_value('ultimate_replacements', {}, True)
    app.connect('source-read', ultimateReplace)

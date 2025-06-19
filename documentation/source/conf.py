# Configuration file for the Sphinx documentation builder.

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath("../../"))

# -- Project information -----------------------------------------------------

project = "YAAF"
copyright = "2024, YAAF Contributors"
author = "YAAF Contributors"
release = "1.0.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.ifconfig",
    "sphinx.ext.githubpages",
    "myst_parser",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = []

# The suffix(es) of source filenames.
source_suffix = {
    ".rst": None,
    ".md": None,
}

# The master toctree document.
master_doc = "index"

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Theme options are theme-specific and customize the look and feel of a theme
# further.
html_theme_options = {
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -- Extension configuration -------------------------------------------------

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Todo extension settings
todo_include_todos = True

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

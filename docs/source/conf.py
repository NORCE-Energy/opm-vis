"""Sphinx configuration for the opm-vis documentation."""

from __future__ import annotations

from importlib.metadata import version as _pkg_version

project = "opm-vis"
copyright = "2026, Svenn Tveit"
author = "Svenn Tveit"
release = _pkg_version("opm-vis")
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# opm-vis and its dependencies (opm, pyvista, matplotlib, click) must be
# installed in the environment building the docs: autodoc imports the real
# modules rather than mocking them.
autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_member_order = "bysource"

napoleon_numpy_docstring = True
napoleon_google_docstring = False

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
}

html_theme = "furo"
html_title = "opm-vis"

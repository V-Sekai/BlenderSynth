# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys

sys.path.insert(0, '../')

project = 'BlenderSynth'
copyright = '2023, Ollie Boyne'
author = 'Ollie Boyne'
release = '2023'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc', 'sphinx_autodoc_typehints', 'sphinx.ext.viewcode',
              'm2r2', 'sphinx.ext.napoleon']

templates_path = ['_templates']
source_dir = 'docs'
master_doc = 'index'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autodoc_mock_imports = ["bpy", "mathutils", "bpy_extras", "bmesh", "opencv-python", "cv2"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_theme_options = {
    'navigation_depth': 1,
    'collapse_navigation': True,
}

source_suffix = ['.rst', '.md']
m2r_parse_relative_links = True

# the below code provides some post-processing of function docstrings for linking to custom Typing hints

from typing import List

# get mapping from types.py without importing all of blendersynth
module_globals = {}
with open('../blendersynth/utils/types.py') as f:
    l = f.read()
    exec(l, module_globals)

sphinx_mappings = module_globals['sphinx_mappings']

def process_docstring(app, what, name, obj, options, lines: List[str]):

    new_lines = []
    # replace any instance of sphinx_mappings
    for line in lines:
        for k, v in sphinx_mappings.items():
            line = line.replace(k, v)
        new_lines.append(line)

    lines.clear()
    lines.extend(new_lines)

def setup(app):
    app.connect('autodoc-process-docstring', process_docstring)
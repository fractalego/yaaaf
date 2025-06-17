# YAAF Documentation

This directory contains the Sphinx documentation for YAAF (Yet Another Agentic Framework).

## Building the Documentation

### Prerequisites

Install the required packages:

```bash
pip install -r requirements.txt
```

### Building HTML Documentation

```bash
# Build HTML documentation
make html

# Open the documentation
open build/html/index.html
```

### Other Output Formats

```bash
# Build PDF documentation (requires LaTeX)
make latexpdf

# Build EPUB
make epub

# Build text files
make text
```

### Live Rebuild (Development)

For development, you can use sphinx-autobuild for automatic rebuilding:

```bash
pip install sphinx-autobuild
sphinx-autobuild source build/html
```

This will start a local server and automatically rebuild the documentation when files change.

## Documentation Structure

```
documentation/
├── source/
│   ├── _static/           # Static files (images, CSS, JS)
│   ├── _templates/        # Custom templates
│   ├── conf.py           # Sphinx configuration
│   ├── index.rst         # Main documentation page
│   ├── getting_started.rst
│   ├── architecture.rst
│   ├── agents.rst
│   ├── api_reference.rst
│   ├── frontend.rst
│   ├── development.rst
│   └── examples.rst
├── build/                 # Generated documentation
├── requirements.txt       # Documentation dependencies
├── Makefile              # Build commands
└── README.md             # This file
```

## Writing Documentation

### reStructuredText Format

The documentation uses reStructuredText (RST) format. Here are some common patterns:

```rst
Section Title
=============

Subsection
----------

**Bold text**
*Italic text*
``Code text``

.. code-block:: python

   def example():
       return "code example"

.. note::
   This is a note box.

.. warning::
   This is a warning box.
```

### Adding New Pages

1. Create a new `.rst` file in the `source/` directory
2. Add it to the `toctree` in `index.rst`:

```rst
.. toctree::
   :maxdepth: 2
   
   existing_page
   new_page
```

### Autodoc for Python Code

To include Python docstrings:

```rst
.. automodule:: yaaf.components.agents.base_agent
   :members:
   :undoc-members:
   :show-inheritance:
```

## Sphinx Extensions Used

- **sphinx.ext.autodoc**: Generate documentation from docstrings
- **sphinx.ext.viewcode**: Add source code links
- **sphinx.ext.napoleon**: Support for Google/NumPy style docstrings
- **myst_parser**: Markdown support alongside RST

## Themes and Styling

The documentation uses the `sphinx_rtd_theme` (Read the Docs theme) for consistent, professional appearance.

Custom styling can be added to `source/_static/custom.css`.

## Contributing to Documentation

1. Follow the existing structure and style
2. Include code examples where appropriate
3. Test that documentation builds without errors
4. Keep language clear and beginner-friendly
5. Update the documentation when adding new features

## Troubleshooting

### Common Build Errors

**Import Errors**: Make sure YAAF is properly installed and importable:
```bash
python -c "import yaaf; print('OK')"
```

**Missing Dependencies**: Install all documentation requirements:
```bash
pip install -r requirements.txt
```

**Autodoc Issues**: Ensure Python modules are in the path and properly structured.

### Clean Build

If you encounter issues, try a clean build:

```bash
make clean
make html
```

## Deployment

The documentation can be deployed to various platforms:

- **Read the Docs**: Connect your repository for automatic builds
- **GitHub Pages**: Use GitHub Actions to build and deploy
- **Static Hosting**: Upload the `build/html/` directory to any web server
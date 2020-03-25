# Pavilion Documentation

This directory holds the Pavilion documentation.

 - The docs are written in ReStructured text (with extra Sphinx bits)
 - Various versions of the docs can be generated with make
    - Example: `make html` will make the html version of the docs.
    - The docs are written with html in mind, and the links are all to '.html' pages.
    - None of these generated files should be committed to the repo (they are git ignored).
 - There are several unittests to check that the docs are generated correctly.


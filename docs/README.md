# Pavilion Documentation

This directory holds the Pavilion documentation.

 - The docs are written in ReStructured text (with extra Sphinx bits)
 - Various versions of the docs can be generated with make
    - Example: `make html` will make the html version of the docs.
    - The docs are written with html in mind, and the links are all to '.html' pages.
    - None of these generated files should be committed to the repo (they are git ignored).
 - There are several unittests to check that the docs are generated correctly.

# Testing the documentation build
Simply run `make clean` and `make html`:

```bash
make clean
make html
```

This requires Sphinx be installed on your system. 

You may find that your local build may have errors that Travis CI doesn't, or vice-versa. To fix
this:

```bash
virtualenv -p $(which python3) <wherever>/doc_build
source <wherever>/doc_build/bin/activate
pip install sphinx
cd <my_pav_repo>/docs
make clean
make html
```

Travis CI essentially follows the same steps to get Sphinx, though the Sphinx version it gets may
vary with the Python version. 

Since the unit test for doc building simply builds the documentation and greps for errors and
warnings. If you can run the build without issues, the unit test should succeed too.

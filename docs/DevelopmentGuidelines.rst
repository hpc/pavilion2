Pavilion Development Guidelines
===============================

Code contributions are welcome!  Additionally, if there are features needed for your site,
just ask. We can help you write them, or in many cases provide them directly.

Style
-----

1. Follow PEP 8 style guidelines, even the parts you don't like (80 char
   width).
2. Write docstrings using sphinx style for everything. (The yaml_config
   library is a good example.)
3. Use type annotations (please).
4. Keep modules fairly independent from each other.
5. Write regression/unit tests for new functionality and place them in
   test/tests/.  See the dev tutorials on read the docs for more info.

Publishing
----------

1. **Do NOT increment the version number.** You may want to look at
   `RELEASE.txt <_static/RELEASE.txt>`__ though.

Site Specific Code
------------------

Site specific code should go into plugins that reside in a separate
repository, and **never** the main Pavilion repository. All Pavilion
code should be targeted towards interoperability with commonly available
products such as slurm, env modules, or lmod.

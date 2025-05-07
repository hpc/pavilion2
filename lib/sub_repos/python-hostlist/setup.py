# -*- coding: utf-8 -*-

from distutils.core import setup

# Version
VERSION = "#VERSION#"
if "#" in VERSION:
    import sys
    sys.stderr.write("Bad version %s\n" % VERSION)
    sys.exit(1)


setup(name         = "python-hostlist",
      version      = VERSION,
      description  = "Python module for hostlist handling",
      long_description = "The hostlist.py module knows how to expand and collect hostlist expressions.",
      author       = "Kent Engström",
      author_email = "kent@nsc.liu.se",
      url          = "http://www.nsc.liu.se/~kent/python-hostlist/",
      license      = "GPL2+",
      classifiers  = ['Development Status :: 5 - Production/Stable',
                      'Intended Audience :: Science/Research',
                      'Intended Audience :: System Administrators',
                      'License :: OSI Approved :: GNU General Public License (GPL)',
                      'Topic :: System :: Clustering',
                      'Topic :: System :: Systems Administration',
                      'Programming Language :: Python :: 2',
                      'Programming Language :: Python :: 2.6',
                      'Programming Language :: Python :: 2.7',
                      'Programming Language :: Python :: 3',
                      ],
      py_modules   = ["hostlist"],
      scripts      = ["hostlist", "hostgrep", "pshbak", "dbuck"],
      data_files   = [("share/man/man1", ["hostlist.1",
                                          "hostgrep.1",
                                          "pshbak.1",
                                          "dbuck.1"])],
      )

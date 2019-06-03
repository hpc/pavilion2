In addition to the pavilion source (in pavilion/) this directory contains soft-links to pavilion's
dependencies. Many of these may already be installed on the system, or they may be checked out and
included in the sub_repos directory using a
`git submodule update --recursive --init` command (assuming this
copy of Pavilion is a clone of the git repo). If you don't do that, the broken
softlinks won't cause problems.

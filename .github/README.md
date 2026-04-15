# Python Versions

`py-versions.json` to determines the versions of Python under which Pavilion's unit test are run.
To add more Python versions to unit tests, simply edit the file. Within the file, Python versions
are separated into three types:

- Supported versions - These are the modern versions of Python that Pavilion supports.
- Legacy versions - These are versions of Python that are no longer fully supported by GitHub Actions
    and that may be end-of-life, but which Pavilion must still support for one reason or another.
    Unit tests run under legacy versions of Python necessarily run in containers in GitHub CI.
- Default version - For unit tests that don't need to run under multiple Python versions, this is
    the version of Python under which those unit tests run. Ideally, the default version should
    be among the supported versions.

This distinction exists solely for the purpose of GitHub Actions workflows. For each version of
Python listed in `py-versions.json`, a compatible OS must be specified. This controls the OS of
the virtual machine on which unit tests run. Typically, this is the latest version of Ubuntu with
which that version of Python is compatible.
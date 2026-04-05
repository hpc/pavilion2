# Python Versions

Edit `py-versions.json` to modify which versions of Python releases are generated for and under
which versions unit tests run.

- Supported versions - These are the primary versions of Python that Pavilion supports, and the
    versions under which the core unit tests run.
- Legacy versions - These are versions of Python that are no longer fully supported and may be end-
    of-life, but which Pavilion must still support for one reason or another. Unit tests run under
    legacy versions of Python necessarily run in containers in GitHub CI.
- Default version - For unit tests that don't need to run under multiple Python versions, this is
    the version of Python under which those unit tests run. Ideally, the default version should
    be among the supported versions.

For each version, a compatible OS must be specified. This controls the OS of the virtual machine
on which unit tests for that version of Python run. Typically, this is the latest version of
Ubuntu with which that version of Python is compatible.
Pavilion's requirements are separated into three sets:

1. `base` - requirements for Pavilion itself
2. `test` - requirements for unit tests
3. `docs` - requirements for documentation

Each of these files should contain only top-level requirements. To update requirements for a given
set, modify the corresponding *.in file.

## Generating Lockfiles

Pavilion generates lockfiles for each version of Python it supports, for the purpose of locking
down dependency versions for each release. These should not be directly modified. To generate new
lockfiles, manually trigger the `Update Pavilion dependencies` GitHub workflow, which can be found
[here](https://github.com/hpc/pavilion2/actions/workflows/update-dependencies.yml). The workflow
will automatically create a PR checking in the newly generated files.

## Adding Supported Versions of Python

To add versions of Python to the list of supported versions, open the `update-dependencies.yml`
file and edit the `update-lockfiles-modern-python` job. Add the new versions to the
`python-versions` matrix reproduced below:

```
strategy:
    fail-fast: false
    matrix:
    dep_type: [base, test, docs]
    python-version: ["3.10", "3.12"]
```

Note that older versions of Python may require you to use an older operating system than that
provided by `ubuntu-latest`, which may require the creation of separate jobs for those older
versions.
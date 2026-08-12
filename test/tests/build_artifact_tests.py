"""Tests for selective build artifact copying."""

from pavilion import unittest


class BuildArtifactsTests(unittest.PavTestCase):
    """Tests for the build.artifacts configuration option."""

    def test_listed_files_are_copied(self):
        """Files explicitly selected by build.artifacts are copied to the
        test's build directory at their paths relative to the shared build
        root.
        """
        raise NotImplementedError("Listed files are copied.")

    def test_globs_select_matching_artifacts(self):
        """Glob expressions in build.artifacts select every matching
        artifact beneath the shared build root for copying.
        """
        raise NotImplementedError("Globs select matching artifacts.")

    def test_listed_directories_are_copied_recursively(self):
        """Directories selected by build.artifacts are copied recursively,
        including their complete contents.
        """
        raise NotImplementedError(
            "Listed directories are copied recursively."
        )

    def test_listed_symlinks_are_copied_as_symlinks(self):
        """Symlinks selected by build.artifacts are copied as symlinks
        rather than being dereferenced.
        """
        raise NotImplementedError(
            "Listed symlinks are copied as symlinks."
        )

    def test_unlisted_files_are_not_copied(self):
        """When build.artifacts is specified, files that are not selected
        by any artifact expression are not copied to the test's build
        directory.
        """
        raise NotImplementedError("Unlisted files are not copied.")

    def test_unmatched_artifact_expressions_are_rejected(self):
        """Each expression in build.artifacts must select at least one
        artifact; an expression with no matches causes the build copy to
        fail.
        """
        raise NotImplementedError(
            "Unmatched artifact expressions are rejected."
        )

    def test_absolute_artifact_paths_are_rejected(self):
        """Entries in build.artifacts must be relative to the shared build
        root; absolute paths are invalid.
        """
        raise NotImplementedError(
            "Absolute artifact paths are rejected."
        )

    def test_artifact_paths_outside_build_root_are_rejected(self):
        """Entries in build.artifacts may not use path traversal to select
        artifacts outside the shared build root.
        """
        raise NotImplementedError(
            "Artifact paths outside the build root are rejected."
        )

    def test_omitting_artifacts_copies_entire_build(self):
        """When build.artifacts is omitted, Pavilion retains the existing
        behavior of copying the complete shared build.
        """
        raise NotImplementedError(
            "Omitting artifacts copies the entire build."
        )

    def test_artifacts_affect_build_hash(self):
        """The build.artifacts configuration contributes to build identity,
        so changing its value changes the build hash.
        """
        raise NotImplementedError("Artifacts affect the build hash.")

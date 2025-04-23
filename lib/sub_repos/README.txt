# Pavilion Dependencies

Pavilion's runtime dependencies go here. We include them directly because Pavilion is frequently run
on networks or systems without easy access to the internet.

Each subdirectory here is effectively a git clone of some version of the dependency, stripped down
considerably.

# Updating dependencies

1. Grab a newer version of dependency.
2. Replace the directory here with the new one.
3. Run ./clean_sub_repos.sh to remove a lot of extraneous files (tests, docs)
4. Add a lib/<mypackage> symlink to the packages library directory.

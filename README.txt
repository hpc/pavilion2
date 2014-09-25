Pavilion Development Notes 

Built and tested on Python 2.7

To Build a src distribution tar file:
  - edit the setup.py file appropriately
  - add files to include in MANIFEST.in file
  - from this directory run -> "python setup.py sdist"
  - tar file placed in "dist" directory

File Structure:
   - all source under the PAV directory
   - PLUGINS sub-dir for new commands
   - SCRIPTS sub-dir for non python tools
   - MODULES sub-dir for all custom built python src
   - SPECIAL-PKGS sub-dir for other used Python packages

Collaboration tips:

  - add new features (sub-commands) to the plugins directory or
    append a new path to the ENV variable PV_PLUGIN_DIR and place code there.
  - all remaining support code add to the modules directory or append to the
    ENV variable PV_SRC_DIR and place code there.


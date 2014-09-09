Pavilion Development Notes 

Built and tested on Python 2.7

To Build a src distribution tar file:
  - edit the setup.py file appropriately
  - add files to include in MANIFEST.in file
  - from this directory run -> "python setup.py sdist"
  - tar file placed in "dist" directory

File Structure:
 - all source under the PAV directory
   - plugins for new commands
   - scripts for non python tools
   - modules for all custom built python src
   - special-pkgs for location to place packages

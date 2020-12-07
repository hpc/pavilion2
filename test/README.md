# Pavilion Unit Tests

## Running Unit Tests
Given a reasonable (python2.7) python, you should be able to run the tests via:

```bash
./run_tests
```

This sets up an environment to find pavilion and it's dependencies, discovers the tests, and runs 
them all.

### Configuration
Some tests requires some knowledge about your environment. You'll want to create a 
`data/pav_config_dir/pavilion.yaml` file to deal with that. This file is already git ignored. 
The following config fields should be filled:
  
  - proxies - You should specify your web proxies, if any.
  - no\_proxy - You should give your internal dns roots (myorg.org) so that pavilion will know
                when not to use the proxy.

### Python Environment
It is recommended that you run your tests under a virtual env to keep up-to-date on the
latest versions of sphinx and pylint. Travis CI tests will run against the latest version
too, and this will make debugging a lot easier.

```bash
# You should create the virtual env outside of the pavilion source.
python3 -m venv <path to your venv>
source <path to your venv>/bin/activate
pip install --upgrade pip
pip install pylint sphinx
```

Then just activate your virtual environment before running tests.

 - You may want to write a script for the activation.
 - It should probably also automatically update pylint and sphinx.
   - `pip install --upgrade pylint sphinx`

### Slurm Config
If you need any special configuration for slurm, put it in a mode file in 
`data/pav_config_dir/modes/local_slurm.yaml`. The `_quick_test_cfg()` method 
(see below) will include that as the slurm defaults.

## Spack Setup
There is a script `test/utils/spack_setup`, that installs and sets up a simple spack instance for 
the spack tests running under Travis CI. Additionally, the install path for this instance is added 
to the Travis `pavilion.yaml` found at `test/data/pav_cfg_dir/pavilion.yaml.travis-ci`, under the 
config key `spack_path`.

## Adding Unit Tests
To add a unit test, simply add a new module to the `tests/` directory and utilize the `unitest` 
module. Here's an example:

```python
import unittest

class ConfigTests(unittest.TestCase):

    def test_base_config_loads(self):
        # This test will fail if the config module won't load
    
        from pavilion import config
        self.assertTrue(True) 
```

### Pavilion Configs
Each `unittest.TestCase` instance comes with a preloaded `pav_cfg` (from the 
`data/pav_config_dir/pavilion.yaml`file mentioned above) for you to
use in your tests. It's specific to your whole test class, so if you need to 
modify it you should either do so in `__init__` or use `copy.deepcopy()` to 
duplicate it first.
 
Loading a pav_cfg in the unittest environment is a bit involved, as can be 
seen in the unittest module, so it's best to use the one provided.
 
### Test data
Any data relevant to the test should go in the `data/` directory, and 
generally should be prefixed with the test module name. Test-only plugins 
should go under `data/pav_config_dir/plugins/`.

Use `self.TEST_DATA_ROOT`, a `pathlib.Path` object, to find your data files.

### Pav Tests
Creating a TestRun instance has been simplified with the `_quick_test()` method
. By default it returns an instance of a simple 'hello world' test. This test
is created using a config generated from the config returned by the 
`_quick_test_cfg()` method. You can use that config as a base, and pass it 
manually to `_quick_test` as needed.


__Note:__ If you intend to run the given test, it must be built first. Use
`test.build()` to do so.

```python
from pavilion import unittest

class ExampleTest(unittest.PavTestCase):

  def test_something(self):
    test_cfg = self._quick_test_cfg()
    test_cfg['run']['cmds'] = ['echo "Goodbye World"']
    
    test = self._quick_test(cfg=test_cfg)
    

    # Make sure to build the test before you try to run it.
    test.build()
    
    # Do stuff with the test object
```

### Plugins
If you intend to use any plugins, you must initialize the plugin system, and
reset it at the end of your test. You can do this using `setUp` and `tearDown`, 
or manually if it needs to happen more than once per test.

```python
from pavilion import unittest
from pavilion import plugins

class PluginTests(unittest.PavTestCase):
    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg) 
       
    def tearDown(self):
        plugins._reset_plugins()
```

### Other useful methods
 - `self._cmp_files()` does a full content file comparison.
 - `self._cmp_tree()` compares a whole directory structure.
 - `self.dbg_print()` should be used whenever you want to have the test print
  something for debugging purposes. It will get picked up by the extraneous
  print statement checker, and also print in an easy to identify color.

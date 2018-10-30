# Pavilion Unit Tests

## Running Unit Tests
Given a reasonable (python2.7) python, you should be able to run the tests via:

```bash
./run_tests
```

This sets up an environment to find pavilion and it's dependencies, discovers the tests, and runs 
them all.

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

### Test data
Any data relevant to the test should go in the `test_data/` directory, and should be 
prefixed with the test module name. 

Tests are assumed to run with the `${REPO_ROOT}/test/` directory as the working directory, so paths
to test data can be relative to that.

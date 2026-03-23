"""Classes to represent Pavilion test configurations."""

from pathlib import Path
from sys import exception

from pavilion.errors import TestConfigError
from pavilion.test_config.file_format import TestConfigLoader, TestSuiteLoader

class TestConfig:
    """A Pavilion configuration file (host, platform or mode)."""

    LOADER = TestConfigLoader()

    def __init__(self, name: str, type: str, path: Path, from_suite: bool = False):

        self.name = name
        self.type = type
        self.path = path
        self.from_suite = from_suite
        self._errors = []

        self._config = None

    @property
    def config(self):
        """Lazily load the test configuration."""
        
        if self._config is None: 
            try:
                with self.path.open() as file: 
                    self._config = self.LOADER.load(file)
            except (TestConfigError, TypeError) as err:
                self._errors.append(err)
                self._config = {}

        return self._config

class EmptyConfig(TestConfig):
    """An empty test config."""

    def __init__(self):

        super().__init__('__base', 'base', Path('.'), from_suite=False)
        self._config = {}
        

class SuiteConfig(TestConfig):
    """A Pavilon suite configuration file. May contain many test configs."""

    def __init__(self, name: str, path: Path):

        self.name = name
        self.path = path
        self._tests = None

    @property
    def __getitem__(self, key):
        """Lazily load tests and present as a dictionary."""

        if self._tests is None:
            

class ConfigStack:
    def __init__(self) -> None:
        self._configs = []

    def push(self, config: TestConfig):
        self._configs.append(config)

    def __getitem__(self):
        pass

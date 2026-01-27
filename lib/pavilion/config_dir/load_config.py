from pathlib import Path
from typing import Dict, Any

import yc_yaml
from yaml_config import YamlConfigLoader
from pavilion.errors import TestConfigError


def safe_load_config(cfg_type: str, path: Path, loader: YamlConfigLoader) -> Dict[str, Any]:
        """Given a path to a config, load the config, and raise an appropriate
        error if it can't be loaded"""

        try:
            with path.open() as cfg_file:
                raw_cfg = loader.load_raw(cfg_file)
        except (IOError, OSError) as err:
            raise TestConfigError("Could not open {} config '{}'"
                                  .format(cfg_type, path), prior_error=err)
        except ValueError as err:
            raise TestConfigError(
                "{} config '{}' has invalid value."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except KeyError as err:
            raise TestConfigError(
                "{} config '{}' has an invalid key."
                .format(cfg_type.capitalize(), path), prior_error=err)
        except yc_yaml.YAMLError as err:
            raise TestConfigError(
                "{} config '{}' has a YAML Error"
                .format(cfg_type.capitalize(), path), prior_error=err)
        except TypeError as err:
            raise TestConfigError(
                "Structural issue with {} config '{}'"
                .format(cfg_type, path), prior_error=err)

        return raw_cfg
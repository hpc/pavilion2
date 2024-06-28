from typing import Any

class MonadicDict:
    """Utility class for getting values from a nested dict. Each call to get is guaranteed
    to return a MonadicDict, even if the key does not exist (in the case that the key does
    not exist, the returned MonadicDict will return the default value). This behavior
    prevents having to repeatedly check whether each key exists in the underlying dictionary.
    Once the series of calls to get is finished, resolve must be called to retrieve the value
    itself."""

    def __init__(self, mdict: Any, default: Any = None):
        self.value = mdict
        self.default = default

    def get(self, key: Any) -> 'MonadicDict':
        if isinstance(self.value, dict):
            return MonadicDict(self.value.get(key, self.default))

        return self

    def resolve(self) -> Any:
        return self.value

    def __getitem__(self, key: Any) -> 'MonadicDict':
        return self.get(key)

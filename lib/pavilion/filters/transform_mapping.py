from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Mapping, Any, Hashable, Callable

from .common import identity


Transform = Callable[[Any], Any]
TransformMap = Mapping[Hashable, Transform] 

class TransformMapping(ABC):
    """Provides an interface for fetching values from an underlying dictionary
    (or dictionary-like object) and automatically applying keywise transforms
    to the fetched values."""

    def __init__(self, transforms: TransformMap, default: Transform = identity):
        self.transforms = transforms
        self.default = default

    @abstractmethod
    def get_untransformed(self, key: Hashable) -> Any:
        ...

    def __getitem__(self, key: Hashable) -> Any:
        tform = self.transforms.get(key, self.default)

        return tform(self.get_untransformed(key))


def transform(transforms: TransformMap, 
              default: Transform = identity) -> Callable:

    def f(func: Callable) -> Callable:
    
        def g(self, key: Hashable) -> Any:
            tform = transforms.get(key, default)
            
            return tform(func(self, key))

        return g

    return f

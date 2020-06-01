class FunctionPluginError(RuntimeError):
    """Error raised when there's a problem with a function plugin
    itself."""


class FunctionArgError(ValueError):
    """Error raised when a function plugin has a problem with the
    function arguments."""

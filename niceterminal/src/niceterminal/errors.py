
class TerminalClosedError(RuntimeError):
    """Raised when attempting to write to a closed terminal."""
    pass

class InterfaceError(RuntimeError):
    pass

class InterfaceNotStarted(InterfaceError):
    """Raised when attempting to write to a closed terminal."""
    pass
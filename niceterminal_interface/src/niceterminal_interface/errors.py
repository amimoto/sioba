class InterfaceError(RuntimeError):
    pass

class InterfaceNotStarted(InterfaceError):
    """Raised when attempting to write to a closed terminal."""
    pass

class InterfaceShutdown(InterfaceError):
    """Raised when attempting to read/write to a shutdown interface."""
    pass

class InterfaceInterrupt(Exception):
    """ Raised when the interface is interrupted """
    pass
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

class TerminalClosedError(RuntimeError):
    """Raised when attempting to write to a closed terminal."""
    pass

class ClientDeleted(Exception):
    """ Raised when the associated Client has been removed """
    pass
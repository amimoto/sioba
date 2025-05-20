class TerminalClosedError(RuntimeError):
    """Raised when attempting to write to a closed terminal."""
    pass

class ClientDeleted(Exception):
    """ Raised when the associated Client has been removed """
    pass
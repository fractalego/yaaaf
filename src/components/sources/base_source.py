class BaseSource:
    """
    Base class for all sources.
    """

    def __init__(self, name: str):
        self.name = name

    def get_data(self, query: str) -> str:
        """
        Get data from the source.
        """
        raise NotImplementedError("Subclasses should implement this method.")

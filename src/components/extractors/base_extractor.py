class BaseExtractor:
    """
    Base class for all extractors.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the extractor with any necessary arguments.
        """
        pass

    def extract(self, *args, **kwargs):
        """
        Extract data from the source.
        """
        raise NotImplementedError("Subclasses must implement this method.")

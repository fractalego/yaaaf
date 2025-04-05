class BaseRetriever:
    def retrieve(self, query: str):
        raise NotImplementedError()
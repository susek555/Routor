class ServiceUnavailableError(Exception):
    def __init__(self, message: str = "Service temporarily unavailable"):
        self.message = message
        super().__init__(self.message)

class GraphGenerationError(Exception):
    def __init__(self, message: str = "Graph generation failed"):
        self.message = message
        super().__init__(self.message)

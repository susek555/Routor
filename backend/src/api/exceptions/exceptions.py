class ServiceUnavailableError(Exception):
    def __init__(self, message: str = "Service temporarily unavailable"):
        self.message = message
        super().__init__(self.message)


class GraphGenerationError(Exception):
    def __init__(self, message: str = "Graph generation failed"):
        self.message = message
        super().__init__(self.message)


class NoRouteVariantsFoundError(Exception):
    def __init__(self, message: str = "No route variants found. The task might be in progress, failed, or expired."):
        self.message = message
        super().__init__(self.message)

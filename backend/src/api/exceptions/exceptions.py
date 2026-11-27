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


class UsernameAlreadyExistsError(Exception):
    def __init__(self, message: str = "Username is already taken"):
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(Exception):
    def __init__(self, message: str = "Invalid username or password"):
        self.message = message
        super().__init__(self.message)


class InvalidTokenError(Exception):
    def __init__(self, message: str = "Token is invalid or expired"):
        self.message = message
        super().__init__(self.message)

from __future__ import annotations


class ProviderError(RuntimeError):
    pass


class ProviderDependencyError(ProviderError):
    pass


class ProviderActionError(ProviderError):
    def __init__(self, operation: str, message: str) -> None:
        super().__init__(f"{operation} failed: {message}")
        self.operation = operation


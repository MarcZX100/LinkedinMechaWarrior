from __future__ import annotations


class MechaError(RuntimeError):
    """Base class for errors that the CLI reports as a clean message."""


class CredentialStoreError(MechaError):
    """The system credential store cannot be used."""


class BrowserProfileInUseError(MechaError):
    """Another browser is already using the persistent profile."""


class AuthenticationRequiredError(MechaError):
    """There is no valid LinkedIn session."""


class ChallengeError(MechaError):
    """LinkedIn asked for a security check (captcha, checkpoint, ID verification)."""


class RateLimitedError(MechaError):
    """LinkedIn rejected a request for being too frequent (HTTP 429 or 999)."""


class VoyagerError(MechaError):
    """LinkedIn's internal API returned something unexpected."""


class VoyagerHTTPError(VoyagerError):
    def __init__(self, status: int, url: str, snippet: str) -> None:
        super().__init__(f"LinkedIn API returned HTTP {status} for {url}: {snippet}")
        self.status = status
        self.url = url


class BudgetExceededError(MechaError):
    """Sending another request would exceed the configured request budget."""


class CooldownActiveError(MechaError):
    """Requests are paused after LinkedIn pushed back."""


class ComposerNotFoundError(MechaError):
    """The LinkedIn post editor could not be found or used."""


class PostValidationError(MechaError):
    """The post text is empty, too long or still has template placeholders."""


class PostGenerationError(MechaError):
    """The input cannot be turned into a useful draft."""

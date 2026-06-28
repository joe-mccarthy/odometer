"""Vehicle registration helpers."""


def normalise_registration(registration: str) -> str:
    """Uppercase and remove whitespace from a registration."""
    return "".join(registration.upper().split())


def display_registration(registration: str) -> str:
    """Return a stable display form for a stored registration."""
    return registration.upper().strip()

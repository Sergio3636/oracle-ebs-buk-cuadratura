def normalize_rut(rut: str) -> str:
    """Normalizes a Chilean RUT to '12076739-9' format (no dots, with dash).

    Handles both Buk format '12.076.739-9' and Oracle formats.
    """
    return rut.replace(".", "").strip().upper()

from fastapi import HTTPException


def not_found(entity_name: str) -> HTTPException:
    """Return a standard 404 for a missing entity."""
    return HTTPException(status_code=404, detail=f"{entity_name} not found")


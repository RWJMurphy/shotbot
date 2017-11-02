"""Exceptional things."""


class ShotbotException(Exception):
    """Base exception for Shotbot exceptions."""
    pass


class RendererException(ShotbotException):
    """Base exception for Renderer exceptions."""
    pass

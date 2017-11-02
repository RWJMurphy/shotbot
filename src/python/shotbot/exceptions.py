"""Exceptional things."""


class ShotbotException(Exception):
    """Base exception for Shotbot exceptions."""
    pass


class CommenterException(ShotbotException):
    """Base exception for Renderer exceptions."""
    pass


class RendererException(ShotbotException):
    """Base exception for Renderer exceptions."""
    pass

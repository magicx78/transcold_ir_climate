"""IR Protocol registry for generic IR Climate devices."""

from typing import Type

from .base import BaseIRProtocol
from .transcold import TranscoldProtocol

# Registry of all supported protocols
PROTOCOLS: dict[str, Type[BaseIRProtocol]] = {
    "transcold": TranscoldProtocol,
}


def get_protocol(name: str) -> BaseIRProtocol:
    """Get a protocol instance by name."""
    if name not in PROTOCOLS:
        raise ValueError(f"Unknown protocol: {name}. Supported: {list(PROTOCOLS.keys())}")
    return PROTOCOLS[name]()


def list_protocols() -> list[str]:
    """List all supported protocol names."""
    return list(PROTOCOLS.keys())


def register_protocol(name: str, protocol_class: Type[BaseIRProtocol]) -> None:
    """Register a new protocol dynamically."""
    PROTOCOLS[name] = protocol_class


BUILTIN_PROTOCOLS = ("transcold",)


def unregister_protocol(name: str) -> bool:
    """Remove a dynamically registered protocol. Built-ins are protected."""
    if name in BUILTIN_PROTOCOLS:
        return False
    return PROTOCOLS.pop(name, None) is not None

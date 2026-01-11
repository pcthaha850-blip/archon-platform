"""
Signals Module

Signal Gate integration for auditable trade signal processing.
All signals flow through this single ingress point.
"""

from archon_prime.api.signals.routes import router

__all__ = ["router"]

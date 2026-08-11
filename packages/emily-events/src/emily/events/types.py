"""Canonical event type constants."""

from __future__ import annotations


class EventTypes:
    """Stable event type names used across the platform."""

    KERNEL_BOOTSTRAP_STARTED = "kernel.bootstrap.started"
    KERNEL_BOOTSTRAP_COMPLETED = "kernel.bootstrap.completed"
    KERNEL_SHUTDOWN_STARTED = "kernel.shutdown.started"
    KERNEL_SHUTDOWN_COMPLETED = "kernel.shutdown.completed"
    KERNEL_SUBSYSTEM_STARTED = "kernel.subsystem.started"
    KERNEL_SUBSYSTEM_STOPPED = "kernel.subsystem.stopped"
    KERNEL_SUBSYSTEM_FAILED = "kernel.subsystem.failed"
    CONFIG_LOADED = "config.loaded"
    BUS_STARTED = "events.bus.started"
    BUS_STOPPED = "events.bus.stopped"

"""Typer entrypoint for Emily OS."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

from emily.config.loader import load_settings
from emily.core.version import __version__ as core_version
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem

app = typer.Typer(
    name="emily",
    help="Emily OS — AI-native desktop operating platform",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command("version")
def version() -> None:
    """Print platform and core package versions."""

    settings = load_settings()
    table = Table(title="Emily OS")
    table.add_column("Component")
    table.add_column("Version")
    table.add_row("platform", settings.app_version)
    table.add_row("emily-core", core_version)
    table.add_row("app_name", settings.app_name)
    table.add_row("environment", settings.environment)
    console.print(table)


@app.command("health")
def health(json_output: bool = typer.Option(False, "--json", help="Emit JSON")) -> None:
    """Boot the kernel briefly and report health."""

    async def _run() -> dict[str, object]:
        kernel = ExecutiveKernel()
        kernel.register(HeartbeatSubsystem())
        try:
            await kernel.start()
            return await kernel.health()
        finally:
            await kernel.stop()

    report = asyncio.run(_run())
    if json_output:
        console.print_json(json.dumps(report))
    else:
        status = "healthy" if report.get("healthy") else "unhealthy"
        console.print(f"[bold]Kernel:[/bold] {report.get('kernel_state')} ({status})")
        console.print_json(json.dumps(report))


@app.command("config")
def show_config(
    reveal_secrets: bool = typer.Option(
        False,
        "--reveal-secrets",
        help="Do not use in shared terminals",
    ),
) -> None:
    """Show non-secret configuration summary."""

    settings = load_settings()
    payload = {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "log_level": settings.log_level,
        "providers": settings.provider_summary(),
        "security": settings.security_summary(),
        "voice_enabled": settings.voice_enabled,
        "memory_enabled": settings.memory_enabled,
        "vision_enabled": settings.vision_enabled,
    }
    if reveal_secrets:
        payload["nvidia_api_key_set"] = bool(settings.nvidia_api_key.get_secret_value())
        payload["routesme_api_key_set"] = bool(settings.routesme_api_key.get_secret_value())
    console.print_json(json.dumps(payload))


@app.command("boot")
def boot(seconds: float | None = typer.Option(0.0, help="Hold running state N seconds")) -> None:
    """Bootstrap the executive kernel (smoke path)."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        kernel.register(HeartbeatSubsystem())
        await kernel.start()
        console.print("[green]Kernel running[/green]")
        if seconds and seconds > 0:
            await asyncio.sleep(seconds)
        await kernel.stop()
        console.print("[green]Kernel stopped cleanly[/green]")

    asyncio.run(_run())


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""Typer entrypoint for Emily OS."""

from __future__ import annotations

import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

from emily.agents.models import AgentTaskRequest
from emily.agents.subsystem import AgentsSubsystem
from emily.agents.team import AgentTeam
from emily.browser.subsystem import BrowserSubsystem
from emily.config.loader import load_settings
from emily.core.types.agent import AgentKind
from emily.core.types.memory import MemoryKind
from emily.core.types.tool import ToolPermissionLevel
from emily.core.version import __version__ as core_version
from emily.desktop.subsystem import DesktopSubsystem
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.kernel.orchestrator import DeepOrchestrationEngine
from emily.memory.models import MemoryQuery, MemoryWrite, WorldObservation
from emily.memory.subsystem import MemorySubsystem
from emily.missions.models import MissionSpec
from emily.missions.subsystem import MissionsSubsystem
from emily.providers.subsystem import ProvidersSubsystem
from emily.tools.models import CapabilityToken, ToolSource
from emily.tools.subsystem import ToolsSubsystem
from emily.voice.session.wake_word import resolve_wake_question
from emily.security.subsystem import SecuritySubsystem
from emily.vision.subsystem import VisionSubsystem
from emily.voice.personality import check_impress_context
from emily.voice.subsystem import VoiceSubsystem

app = typer.Typer(
    name="emily",
    help="Emily OS — AI-native desktop operating platform",
    no_args_is_help=True,
    add_completion=False,
)
missions_app = typer.Typer(help="Mission runtime commands")
agents_app = typer.Typer(help="Agent runtime commands")
memory_app = typer.Typer(help="Memory runtime commands")
world_app = typer.Typer(help="World model commands")
tools_app = typer.Typer(help="Tool runtime commands")
mcp_app = typer.Typer(help="MCP catalog commands")
desktop_app = typer.Typer(help="Desktop runtime commands")
browser_app = typer.Typer(help="Browser runtime commands")
voice_app = typer.Typer(help="Voice runtime commands")
vision_app = typer.Typer(help="Vision runtime commands")
security_app = typer.Typer(help="Security & Vault commands")
app.add_typer(missions_app, name="mission")
app.add_typer(agents_app, name="agent")
app.add_typer(memory_app, name="memory")
app.add_typer(world_app, name="world")
app.add_typer(tools_app, name="tool")
app.add_typer(mcp_app, name="mcp")
app.add_typer(desktop_app, name="desktop")
app.add_typer(browser_app, name="browser")
app.add_typer(voice_app, name="voice")
app.add_typer(vision_app, name="vision")
app.add_typer(security_app, name="security")
console = Console()


def _register_default_subsystems(kernel: ExecutiveKernel) -> None:
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(SecuritySubsystem())
    kernel.register(MemorySubsystem())
    kernel.register(ToolsSubsystem())
    kernel.register(DesktopSubsystem())
    kernel.register(BrowserSubsystem())
    kernel.register(VoiceSubsystem())
    kernel.register(VisionSubsystem())
    kernel.register(MissionsSubsystem())
    kernel.register(AgentsSubsystem())


def _register_voice_wake_subsystems(kernel: ExecutiveKernel) -> None:
    """Minimal kernel for wake-only CLI — skips browser, desktop, memory, agents."""
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(VoiceSubsystem())


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
        _register_default_subsystems(kernel)
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
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "provider_failover_enabled": settings.provider_failover_enabled,
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
        _register_default_subsystems(kernel)
        await kernel.start()
        console.print("[green]Kernel running[/green]")
        if seconds and seconds > 0:
            await asyncio.sleep(seconds)
        await kernel.stop()
        console.print("[green]Kernel stopped cleanly[/green]")

    asyncio.run(_run())


@app.command("providers")
def providers_cmd(json_output: bool = typer.Option(False, "--json", help="Emit JSON")) -> None:
    """Probe configured LLM providers and print health."""

    async def _run() -> dict[str, object]:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.provider_router is not None
            reports = await ctx.provider_router.health_reports()
            return {
                "primary": ctx.settings.primary_provider,
                "backup": ctx.settings.backup_provider,
                "failover_enabled": ctx.settings.provider_failover_enabled,
                "providers": [r.model_dump(mode="json") for r in reports],
                "analytics": ctx.provider_analytics.summary() if ctx.provider_analytics else {},
            }
        finally:
            await kernel.stop()

    payload = asyncio.run(_run())
    if json_output:
        console.print_json(json.dumps(payload))
        return

    table = Table(title="Provider Health")
    table.add_column("Name")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Latency ms")
    provider_rows = payload.get("providers", [])
    if not isinstance(provider_rows, list):
        provider_rows = []
    for report in provider_rows:
        if not isinstance(report, dict):
            continue
        latency = report.get("latency_ms")
        table.add_row(
            str(report.get("name", "")),
            str(report.get("model", "")),
            str(report.get("status", "")),
            f"{float(latency):.1f}" if isinstance(latency, (int, float)) else "-",
        )
    console.print(table)


@security_app.command("set-secret")
def security_set_secret(
    key: str = typer.Argument(..., help="Secret key name"),
    value: str = typer.Argument(..., help="Secret key value"),
) -> None:
    """Store an encrypted secret in Emily Secrets Vault."""
    sec = SecuritySubsystem()
    sec.vault.set_secret(key, value)
    console.print(f"[green]Secret '{key}' encrypted and saved in Secrets Vault.[/green]")


@security_app.command("get-secret")
def security_get_secret(
    key: str = typer.Argument(..., help="Secret key name"),
) -> None:
    """Decrypt and display a secret value."""
    sec = SecuritySubsystem()
    val = sec.vault.get_secret(key)
    if val is not None:
        console.print(f"[bold]{key}:[/bold] {val}")
    else:
        console.print(f"[red]Secret '{key}' not found in Secrets Vault.[/red]")


@security_app.command("audit")
def security_audit() -> None:
    """Verify cryptographic hash integrity of the audit log."""
    sec = SecuritySubsystem()
    ok = sec.audit.verify_integrity()
    if ok:
        console.print("[green]Audit Log Integrity: VERIFIED (0 tamperings detected)[/green]")
    else:
        console.print("[bold red]Audit Log Integrity: COMPROMISED / INVALID HASH[/bold red]")


@app.command("workbench")
@app.command("server")
@app.command("ui")
def ui_cmd(
    port: int = typer.Option(8000, help="Port for Emily OS Web Workbench"),
    open_browser: bool = typer.Option(False, "--open/--no-open", help="Open browser automatically"),
    host: str = typer.Option("127.0.0.1", help="Bind address (loopback by default)"),
) -> None:
    """Launch Emily OS Web Workbench & API server."""
    import uvicorn
    import webbrowser
    from pathlib import Path
    from fastapi.responses import HTMLResponse
    from emily_cli.server import create_emily_app

    kernel = ExecutiveKernel()
    _register_default_subsystems(kernel)
    web_app = create_emily_app(kernel)

    ui_file = (Path("apps/emily-ui/dist/index.html") if Path("apps/emily-ui/dist/index.html").exists() else Path("apps/emily-ui/index.html")).resolve()

    @web_app.get("/", response_class=HTMLResponse)
    async def serve_ui() -> str:
        if ui_file.exists():
            return ui_file.read_text(encoding="utf-8")
        return "<h1>Emily OS Web Workbench</h1>"

    console.print(f"[bold green]Emily OS Workbench running at http://localhost:{port}[/bold green]")
    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run(web_app, host=host, port=port, log_level="info")


@app.command("impress")
def impress_cmd() -> None:
    """Trigger Emily's signature Bengali impress response."""
    reply = check_impress_context("impress me")
    if reply:
        console.print(f"[bold magenta]{reply}[/bold magenta]")


@app.command("orchestrate")
@app.command("deep-demo")
def orchestrate_cmd(
    goal: str = typer.Option("Execute full-spectrum enterprise security audit & trading transaction", help="Workflow goal"),
) -> None:
    """Run full 8-phase cross-subsystem orchestration transaction live."""
    async def _run() -> None:
        import time
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        ctx = await kernel.start()
        try:
            console.print("[bold cyan]Running Emily OS Master Multi-Subsystem Orchestration...[/bold cyan]")
            orchestrator = DeepOrchestrationEngine(ctx, kernel=kernel)
            result = await orchestrator.execute_master_workflow(goal=goal, enable_voice=False)
            table = Table(title="Emily OS Master Orchestration Results", show_header=True)
            table.add_column("Phase", style="cyan")
            table.add_column("Subsystem / Task", style="bold white")
            table.add_column("Status", style="green")
            table.add_column("Latency ms", style="magenta")

            for p in result["phases"]:
                table.add_row(
                    str(p["phase"]),
                    p["name"],
                    p["status"].upper(),
                    f"{p['latency_ms']:.2f}",
                )
            console.print(table)
            console.print(f"[bold green]Master Workflow Complete in {result['total_latency_ms']:.2f} ms[/bold green]")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@app.command("benchmark")
def benchmark_cmd() -> None:
    """Run Emily OS subsystem latency and throughput benchmarks."""
    async def _run() -> None:
        import time
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        ctx = await kernel.start()
        try:
            console.print("[bold yellow]Benchmarking Emily OS Core Subsystems...[/bold yellow]")
            t_mem0 = time.perf_counter()
            if ctx.memory_runtime:
                await ctx.memory_runtime.remember("benchmark test content", kind=MemoryKind.WORKING)
            mem_lat = (time.perf_counter() - t_mem0) * 1000

            t_sec0 = time.perf_counter()
            sec_sub = kernel.get_subsystem("security")
            if sec_sub and hasattr(sec_sub, "vault"):
                sec_sub.vault.set_secret("bench_key", "bench_val")
            sec_lat = (time.perf_counter() - t_sec0) * 1000

            table = Table(title="Subsystem Micro-Benchmarks", show_header=True)
            table.add_column("Subsystem", style="cyan")
            table.add_column("Operation", style="bold white")
            table.add_column("Latency ms", style="magenta")

            table.add_row("emily-memory", "Remember Working Memory", f"{mem_lat:.3f}")
            table.add_row("emily-security", "Encrypt Secrets Vault", f"{sec_lat:.3f}")
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@vision_app.command("screenshot")
def vision_screenshot() -> None:
    """Capture current desktop screen and analyze OCR and UI elements."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            vision_sub = kernel.get_subsystem("vision")
            if vision_sub and hasattr(vision_sub, "runtime"):
                frame = vision_sub.runtime.capture_and_ground()
                console.print_json(json.dumps(frame.to_dict()))
            else:
                console.print("[red]Vision subsystem unavailable[/red]")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@app.command("chat")
def chat(
    prompt: str = typer.Argument(..., help="User prompt"),
    provider: str | None = typer.Option(None, help="Force provider: nvidia|routesme"),
    system: str = typer.Option("You are Emily OS.", help="System prompt"),
) -> None:
    """Send a one-shot chat completion through the provider router."""

    # Check for impress context easter egg
    impress_reply = check_impress_context(prompt)
    if impress_reply:
        console.print(f"[bold magenta]{impress_reply}[/bold magenta]")
        return

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.provider_router is not None
            result = await ctx.provider_router.achat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                provider=provider,
            )
            console.print(result.content)
            console.print(
                f"[dim]provider={result.provider} model={result.model} "
                f"latency_ms={result.latency_ms:.1f} "
                f"tokens={result.usage.total_tokens} "
                f"est_cost_usd={result.estimated_cost_usd}[/dim]"
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("create")
def mission_create(goal: str = typer.Argument(..., help="Mission goal")) -> None:
    """Create a draft mission."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.create(MissionSpec(goal=goal))
            console.print_json(json.dumps(mission.model_dump(mode="json")))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("start")
def mission_start(mission_id: str = typer.Argument(..., help="Mission id")) -> None:
    """Plan and execute a mission to completion (or pause/cancel)."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.start(mission_id)
            console.print(
                f"[bold]{mission.status.value}[/bold] {mission.mission_id} — {mission.goal}"
            )
            if mission.verification:
                console.print(f"verification: {mission.verification}")
            if mission.reflection:
                console.print(f"reflection: {mission.reflection}")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("list")
def mission_list() -> None:
    """List archived missions."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            rows = await ctx.mission_runtime.list()
            table = Table(title="Missions")
            table.add_column("ID")
            table.add_column("Status")
            table.add_column("Goal")
            for mission in rows:
                table.add_row(mission.mission_id, mission.status.value, mission.goal[:60])
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("get")
def mission_get(mission_id: str) -> None:
    """Show one mission document."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.get(mission_id)
            console.print_json(json.dumps(mission.model_dump(mode="json")))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("pause")
def mission_pause(mission_id: str) -> None:
    """Request pause for a mission."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.pause(mission_id)
            console.print(f"paused {mission.mission_id}")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("resume")
def mission_resume(mission_id: str) -> None:
    """Resume a paused mission from its stored checkpoint."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.resume(mission_id)
            console.print(f"{mission.status.value} {mission.mission_id}")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("cancel")
def mission_cancel(mission_id: str) -> None:
    """Cancel a mission."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            mission = await ctx.mission_runtime.cancel(mission_id)
            console.print(f"cancelled {mission.mission_id}")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@missions_app.command("run")
def mission_run(goal: str = typer.Argument(..., help="Goal to create and run")) -> None:
    """Create and immediately start a mission."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.mission_runtime is not None
            created = await ctx.mission_runtime.create(MissionSpec(goal=goal))
            mission = await ctx.mission_runtime.start(created.mission_id)
            console.print(
                f"[bold]{mission.status.value}[/bold] {mission.mission_id}\n{mission.goal}"
            )
            if mission.reflection:
                console.print(mission.reflection)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("roles")
def agent_roles() -> None:
    """List registered agent roles."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            table = Table(title="Agent Roles")
            table.add_column("Kind")
            table.add_column("Title")
            table.add_column("Retries")
            table.add_column("Capabilities")
            for role in ctx.agent_supervisor.registry.list_roles():
                table.add_row(
                    role.kind.value,
                    role.title,
                    str(role.default_max_retries),
                    ", ".join(role.capabilities),
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("list")
def agent_list(
    all_agents: bool = typer.Option(False, "--all", help="Include terminated"),
) -> None:
    """List live agents."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            rows = ctx.agent_supervisor.list_agents(include_terminated=all_agents)
            table = Table(title="Agents")
            table.add_column("ID")
            table.add_column("Kind")
            table.add_column("Status")
            table.add_column("Runs")
            for agent in rows:
                table.add_row(
                    agent.agent_id,
                    agent.kind.value,
                    agent.status.value,
                    str(agent.run_count),
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("run")
def agent_run(
    title: str = typer.Argument(..., help="Task title"),
    kind: str | None = typer.Option(None, help="Agent kind override"),
    description: str = typer.Option("", help="Task description"),
) -> None:
    """Spawn an agent, run a verified task, then terminate."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            agent_kind = AgentKind(kind) if kind else None
            result = await ctx.agent_supervisor.run_task(
                AgentTaskRequest(
                    title=title,
                    description=description,
                    kind=agent_kind,
                )
            )
            console.print(result.output)
            console.print(
                f"[dim]success={result.success} kind={result.kind.value} "
                f"attempts={result.attempts} latency_ms={result.latency_ms} "
                f"verification={result.verification}[/dim]"
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("pipeline")
def agent_pipeline(
    goal: str = typer.Argument(..., help="Dotted multi-step goal"),
) -> None:
    """Run a multi-agent pipeline inferred from a dotted goal."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            team = ctx.get_extra("agent_team") or AgentTeam(ctx.agent_supervisor)
            result = await team.run_goal_pipeline(goal)
            for index, step in enumerate(result.steps):
                console.print(
                    f"[bold]{index + 1}.[/bold] {step.kind.value} "
                    f"success={step.success} attempts={step.attempts}"
                )
            console.print(result.final_output)
            console.print(
                f"[dim]pipeline_success={result.success} steps={len(result.steps)} "
                f"error={result.error}[/dim]"
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("stats")
def agent_stats() -> None:
    """Show agent analytics after a short self-check run."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            await ctx.agent_supervisor.run_task(
                AgentTaskRequest(title="Warmup stats probe", description="noop")
            )
            summary = ctx.agent_supervisor.analytics.summary()
            pool = ctx.agent_supervisor.pool.snapshot()
            console.print_json(json.dumps({"analytics": summary, "pool": pool}))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@agents_app.command("history")
def agent_history(
    limit: int = typer.Option(20, help="Max records"),
) -> None:
    """List recent agent run history."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.agent_supervisor is not None
            store = ctx.agent_supervisor.history
            if store is None:
                console.print("[yellow]Agent history disabled[/yellow]")
                return
            rows = await store.list_runs(limit=limit)
            table = Table(title="Agent History")
            table.add_column("Run")
            table.add_column("Kind")
            table.add_column("OK")
            table.add_column("Attempts")
            table.add_column("Title")
            for row in rows:
                table.add_row(
                    row.run_id,
                    row.kind.value,
                    "yes" if row.success else "no",
                    str(row.attempts),
                    row.title,
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@memory_app.command("kinds")
def memory_kinds() -> None:
    """List memory kinds."""
    table = Table(title="Memory Kinds")
    table.add_column("Kind")
    for kind in MemoryKind:
        table.add_row(kind.value)
    console.print(table)


@memory_app.command("put")
def memory_put(
    content: str = typer.Argument(..., help="Memory content"),
    kind: str = typer.Option("working", help="Memory kind"),
    title: str = typer.Option("", help="Optional title"),
    importance: float = typer.Option(0.5, help="Importance 0..1"),
) -> None:
    """Write a memory record."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            record = await ctx.memory_runtime.put(
                MemoryWrite(
                    kind=MemoryKind(kind),
                    content=content,
                    title=title,
                    importance=importance,
                )
            )
            console.print(f"{record.memory_id} [{record.kind.value}] {record.content}")
        finally:
            await kernel.stop()

    asyncio.run(_run())


@memory_app.command("get")
def memory_get(memory_id: str = typer.Argument(..., help="Memory id")) -> None:
    """Fetch a memory by id."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            record = await ctx.memory_runtime.get(memory_id)
            console.print_json(data=record.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@memory_app.command("search")
def memory_search(
    text: str = typer.Argument(..., help="Query text"),
    kind: str | None = typer.Option(None, help="Optional kind filter"),
    limit: int = typer.Option(8, help="Max hits"),
) -> None:
    """Retrieve ranked memories."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            kinds = [MemoryKind(kind)] if kind else []
            hits = await ctx.memory_runtime.search(
                MemoryQuery(text=text, kinds=kinds, limit=limit)
            )
            table = Table(title="Memory Hits")
            table.add_column("Score")
            table.add_column("Kind")
            table.add_column("ID")
            table.add_column("Preview")
            for hit in hits:
                preview = hit.record.content[:80].replace("\n", " ")
                table.add_row(
                    f"{hit.score:.3f}",
                    hit.record.kind.value,
                    hit.record.memory_id,
                    preview,
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@memory_app.command("stats")
def memory_stats() -> None:
    """Show memory and world stats."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            console.print_json(data=await ctx.memory_runtime.stats())
        finally:
            await kernel.stop()

    asyncio.run(_run())


@memory_app.command("consolidate")
def memory_consolidate() -> None:
    """Promote ephemeral memories into durable stores."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            result = await ctx.memory_runtime.consolidate()
            console.print_json(data=result.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@world_app.command("show")
def world_show() -> None:
    """Show world-model snapshot summary."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            snap = ctx.memory_runtime.world_snapshot()
            console.print_json(data=snap.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@world_app.command("observe")
def world_observe(
    text: str = typer.Argument(..., help="Observation text"),
    entities: str = typer.Option("", help="Comma-separated entity names"),
) -> None:
    """Ingest an observation into the world model."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            entity_list = [e.strip() for e in entities.split(",") if e.strip()]
            snap = await ctx.memory_runtime.observe(
                WorldObservation(
                    text=text,
                    entities=entity_list,
                    source="cli",
                )
            )
            console.print(
                f"entities={snap.metadata.get('entity_count')} "
                f"relations={snap.metadata.get('relation_count')} "
                f"facts={snap.metadata.get('fact_count')}"
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@world_app.command("entities")
def world_entities() -> None:
    """List known world entities."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.memory_runtime is not None
            rows = ctx.memory_runtime.world.list_entities()
            table = Table(title="World Entities")
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Confidence")
            for ent in rows:
                table.add_row(
                    ent.entity_id,
                    ent.name,
                    ent.entity_type,
                    f"{ent.confidence:.2f}",
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@tools_app.command("list")
def tool_list(
    source: str | None = typer.Option(None, help="Filter: builtin|mcp|plugin"),
) -> None:
    """List registered tools."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            src = ToolSource(source) if source else None
            rows = ctx.tool_runtime.list_tools(source=src)
            table = Table(title="Tools")
            table.add_column("Name")
            table.add_column("Source")
            table.add_column("Permissions")
            table.add_column("Description")
            for tool in rows:
                table.add_row(
                    tool.name,
                    tool.source.value,
                    ",".join(p.value for p in tool.permissions),
                    tool.description[:60],
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@tools_app.command("info")
def tool_info(name: str = typer.Argument(..., help="Tool name")) -> None:
    """Show tool metadata."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            tool = ctx.tool_runtime.registry.get(name)
            console.print_json(data=tool.spec.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@tools_app.command("invoke")
def tool_invoke(
    name: str = typer.Argument(..., help="Tool name"),
    args_json: str = typer.Option("{}", "--args", help="JSON arguments object"),
    grant: str = typer.Option("", help="Comma-separated capability grants"),
) -> None:
    """Invoke a tool with optional capability token."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            arguments = json.loads(args_json)
            capabilities = None
            if grant.strip():
                levels = [
                    ToolPermissionLevel(part.strip())
                    for part in grant.split(",")
                    if part.strip()
                ]
                capabilities = CapabilityToken(granted=levels, label="cli")
            result = await ctx.tool_runtime.invoke(
                name,
                arguments,
                capabilities=capabilities,
                caller="cli",
            )
            console.print_json(data=result.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@tools_app.command("permissions")
def tool_permissions() -> None:
    """Show policy-allowed permission levels."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            console.print_json(data=ctx.tool_runtime.stats())
        finally:
            await kernel.stop()

    asyncio.run(_run())


@mcp_app.command("list")
def mcp_list() -> None:
    """List MCP servers from the catalog."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            table = Table(title="MCP Servers")
            table.add_column("Name")
            table.add_column("Transport")
            table.add_column("Enabled")
            table.add_column("Tools")
            for server in ctx.tool_runtime.discovery.catalog.servers:
                table.add_row(
                    server.name,
                    server.transport,
                    "yes" if server.enabled else "no",
                    str(len(server.tools)),
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@mcp_app.command("reload")
def mcp_reload() -> None:
    """Hot-reload MCP catalog into the tool registry."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            result = await ctx.tool_runtime.reload_mcp_async()
            console.print_json(data=result)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@mcp_app.command("show")
def mcp_show() -> None:
    """Show the loaded MCP catalog JSON."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.tool_runtime is not None
            console.print_json(data=ctx.tool_runtime.discovery.catalog.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("status")
def desktop_status() -> None:
    """Show desktop runtime backend and policy status."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            snap = await ctx.desktop_runtime.snapshot()
            console.print_json(
                data={
                    "stats": ctx.desktop_runtime.stats(),
                    "snapshot": snap.model_dump(mode="json"),
                }
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("windows")
def desktop_windows() -> None:
    """List desktop windows."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            windows = await ctx.desktop_runtime.list_windows()
            table = Table(title="Windows")
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("Process")
            table.add_column("Focused")
            for window in windows:
                table.add_row(
                    window.window_id,
                    window.title,
                    window.process_name,
                    "yes" if window.focused else "no",
                )
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("focus")
def desktop_focus(
    title: str | None = typer.Option(None, help="Title substring"),
    window_id: str | None = typer.Option(None, help="Window id"),
) -> None:
    """Focus a window by id or title."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            window = await ctx.desktop_runtime.focus_window(window_id, title=title)
            console.print_json(data=window.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("clipboard")
def desktop_clipboard(
    set_text: str | None = typer.Option(None, "--set", help="Set clipboard text"),
) -> None:
    """Get or set clipboard text."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            if set_text is not None:
                content = await ctx.desktop_runtime.clipboard_set(set_text)
            else:
                content = await ctx.desktop_runtime.clipboard_get()
            console.print_json(data=content.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("type")
def desktop_type(text: str = typer.Argument(..., help="Text to type/record")) -> None:
    """Type or record text input."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            event = await ctx.desktop_runtime.type_text(text)
            console.print_json(data=event.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("powershell")
def desktop_powershell(
    command: str = typer.Argument(..., help="PowerShell command"),
    dry_run: bool = typer.Option(False, help="Validate without executing"),
    timeout: float = typer.Option(15.0, help="Timeout seconds"),
) -> None:
    """Run a policy-gated PowerShell command."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            result = await ctx.desktop_runtime.powershell(
                command,
                timeout_seconds=timeout,
                dry_run=dry_run,
            )
            console.print_json(data=result.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@desktop_app.command("registry")
def desktop_registry(
    path: str = typer.Argument(..., help="Registry path"),
    name: str = typer.Argument(..., help="Value name"),
    set_value: str | None = typer.Option(None, "--set", help="Write value"),
) -> None:
    """Get or set an allowlisted registry value."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.desktop_runtime is not None
            if set_value is not None:
                value = await ctx.desktop_runtime.registry_set(path, name, set_value)
            else:
                value = await ctx.desktop_runtime.registry_get(path, name)
            console.print_json(data=value.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("status")
def browser_status() -> None:
    """Show browser runtime status."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            snap = await ctx.browser_runtime.status()
            console.print_json(
                data={"stats": ctx.browser_runtime.stats(), "snapshot": snap.model_dump(mode="json")}
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("open")
def browser_open(profile: str | None = typer.Option(None, help="Profile name")) -> None:
    """Open Chromium with a persistent profile."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            console.print_json(data=await ctx.browser_runtime.open(profile=profile))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("goto")
def browser_goto(url: str = typer.Argument(..., help="URL to open")) -> None:
    """Navigate the active tab."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            tab = await ctx.browser_runtime.goto(url)
            console.print_json(data=tab.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("snapshot")
def browser_snapshot() -> None:
    """Capture DOM/accessibility grounding."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            grounding = await ctx.browser_runtime.snapshot()
            console.print_json(data=grounding.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("click")
def browser_click(
    selector: str | None = typer.Option(None, help="CSS selector"),
    role: str | None = typer.Option(None, help="ARIA role"),
    name: str | None = typer.Option(None, help="Accessible name"),
    ref: str | None = typer.Option(None, help="Grounding ref from snapshot"),
) -> None:
    """Click an element."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            result = await ctx.browser_runtime.click(
                selector=selector, role=role, name=name, ref=ref
            )
            console.print_json(data=result)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("type")
def browser_type(
    text: str = typer.Argument(..., help="Text to type"),
    selector: str | None = typer.Option(None, help="CSS selector"),
    role: str | None = typer.Option(None, help="ARIA role"),
    name: str | None = typer.Option(None, help="Accessible name"),
    clear: bool = typer.Option(False, help="Clear before typing"),
) -> None:
    """Type into an element."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            result = await ctx.browser_runtime.type_text(
                text, selector=selector, role=role, name=name, clear=clear
            )
            console.print_json(data=result)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("tabs")
def browser_tabs() -> None:
    """List open tabs."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            tabs = await ctx.browser_runtime.tabs()
            table = Table(title="Browser Tabs")
            table.add_column("ID")
            table.add_column("Title")
            table.add_column("URL")
            table.add_column("Active")
            for tab in tabs:
                table.add_row(tab.tab_id, tab.title, tab.url, "yes" if tab.active else "no")
            console.print(table)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("eval")
def browser_eval(expression: str = typer.Argument(..., help="JS expression")) -> None:
    """Evaluate JavaScript in the page."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            result = await ctx.browser_runtime.evaluate(expression)
            console.print_json(data={"result": result})
        finally:
            await kernel.stop()

    asyncio.run(_run())


@browser_app.command("close")
def browser_close() -> None:
    """Close the browser context."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.browser_runtime is not None
            await ctx.browser_runtime.close()
            console.print_json(data={"closed": True})
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("status")
def voice_status() -> None:
    """Show voice runtime status."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            if ctx.voice_runtime is None:
                console.print_json(data={"enabled": False, "message": "voice subsystem disabled"})
                return
            snap = await ctx.voice_runtime.status()
            console.print_json(
                data={
                    "stats": ctx.voice_runtime.stats(),
                    "status": snap.model_dump(mode="json"),
                }
            )
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("speak")
def voice_speak(
    text: str = typer.Argument(..., help="Text to speak"),
    play: bool = typer.Option(False, help="Play audio through speakers"),
) -> None:
    """Synthesize speech via Speech Director + TTS router."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            plan = await ctx.voice_runtime.speak(text, play=play)
            console.print_json(data=plan.model_dump(mode="json"))
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("listen")
def voice_listen(
    duration: float = typer.Option(3.0, help="Capture duration seconds"),
) -> None:
    """Capture microphone audio and transcribe (requires ASR + audio extras)."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            transcript = await ctx.voice_runtime.listen_once(duration_s=duration)
            console.print_json(data={"transcript": transcript})
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("barge-in")
def voice_barge_in() -> None:
    """Interrupt current speech playback/generation."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            console.print_json(data=await ctx.voice_runtime.barge_in())
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("models")
def voice_models(
    name: str | None = typer.Option(None, help="Filter by model name"),
    download: bool = typer.Option(False, help="Explicitly download (requires network)"),
    verify: bool = typer.Option(False, help="Verify model install/import"),
) -> None:
    """Show local voice model status; optional explicit download/verify."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            if download:
                result = ctx.voice_runtime.models.download(
                    name or "kokoro",
                    allow_download=True,
                )
                console.print_json(data={"download": result.model_dump(mode="json")})
            if verify:
                target = name or "kokoro"
                console.print_json(data={"verify": ctx.voice_runtime.models.verify(target).model_dump(mode="json")})
            console.print_json(data={"models": ctx.voice_runtime.model_status(name)})
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("converse")
def voice_converse(
    text: str | None = typer.Option(None, help="Skip mic; process this transcript"),
    play: bool = typer.Option(False, help="Play TTS through speakers"),
    duration: float = typer.Option(3.0, help="Mic listen duration if no --text"),
) -> None:
    """One conversational turn (listen or --text → LLM → Speech Director → TTS)."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            engine = ctx.voice_runtime.engine
            assert engine is not None
            if text:
                result = await engine.process_transcript(text, play=play)
            else:
                result = await ctx.voice_runtime.converse_turn(duration_s=duration, play=play)
            console.print_json(data=result)
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("metrics")
def voice_metrics() -> None:
    """Print voice latency metrics snapshot."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            console.print_json(data=ctx.voice_runtime.metrics_snapshot())
        finally:
            await kernel.stop()

    asyncio.run(_run())


@voice_app.command("wake")
def voice_wake(
    play: bool = typer.Option(True, help="Play TTS responses"),
    once: bool = typer.Option(False, help="Wait for one wake hit then exit"),
) -> None:
    """
    Continuous wake-word loop.

    ASR phrase mode (default): fixed mic chunks + faster-whisper matches EMILY_WAKE_WORD.
    Optional: set EMILY_VOICE_WAKE_WORD_MODEL to an openWakeWord ONNX model path.
    """

    def _prepare_wake_settings():
        settings = load_settings()
        settings.voice_enabled = True
        settings.voice_wake_word_enabled = True
        if (settings.wake_word or "").strip().lower() == "emily":
            settings.wake_word = "Hey Emily"
        return settings

    async def _run() -> None:
        settings = _prepare_wake_settings()
        kernel = ExecutiveKernel(settings=settings)
        _register_voice_wake_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            runtime = ctx.voice_runtime

            def _status(message: str) -> None:
                console.print(f"[cyan]{message}[/cyan]")

            listener = runtime.wake_listener(on_status=_status)
            if not listener.enabled():
                raise BackendUnavailableError(
                    "wake word unavailable — install emily-voice[asr,audio] and enable microphone access"
                )

            _status("Warming up voice models...")
            await runtime.ensure_warm()

            if once:
                hit = await listener.wait_once()
                console.print_json(
                    data={
                        "detected": True,
                        "phrase": hit.phrase,
                        "backend": hit.backend.value,
                        "score": hit.score,
                    }
                )
                if runtime.engine is not None:
                    followup = await resolve_wake_question(
                        runtime.engine.asr,
                        hit,
                        on_status=_status,
                    )
                    if followup.strip():
                        _status(f"Using question from wake utterance: {followup!r}")
                        result = await runtime.engine.process_transcript(
                            followup,
                            play=play,
                            on_status=_status,
                        )
                    else:
                        _status(
                            "Wake detected. Ask your question now (you have ~10 seconds)."
                        )
                        result = await runtime.engine.converse_turn(
                            play=play,
                            on_status=_status,
                        )
                    console.print_json(data=result)
                return
            console.print(
                f"Wake-word loop active (phrase={listener.phrase!r}, "
                f"backend={listener.backend().value}). Ctrl+C to stop."
            )
            await runtime.run_wake_loop(converse=True, play=play, on_status=_status)
        finally:
            await kernel.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("Wake loop stopped.")


@voice_app.command("serve")
def voice_serve(
    port: int = typer.Option(8765, help="HTTP port for voice status UI"),
    seconds: float = typer.Option(0.0, help="Hold N seconds (0 = until Ctrl+C)"),
) -> None:
    """Expose GET /voice/status for desktop UI (Tauri/React polls this endpoint)."""

    async def _run() -> None:
        kernel = ExecutiveKernel()
        _register_default_subsystems(kernel)
        try:
            ctx = await kernel.start()
            assert ctx.voice_runtime is not None
            server = ctx.voice_runtime.start_ui_server(port=port)
            console.print(f"Voice UI status: http://127.0.0.1:{server.port}/voice/status")
            if seconds and seconds > 0:
                await asyncio.sleep(seconds)
            else:
                while True:
                    await asyncio.sleep(3600)
        finally:
            await kernel.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("Voice UI server stopped.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

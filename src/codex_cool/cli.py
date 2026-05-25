from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from codex_cool.config import ProxyConfig, ProviderConfig, load_config, save_config

console = Console()


@click.group()
@click.option("--config", "-c", type=click.Path(), default=None, help="Config file path")
@click.pass_context
def main(ctx, config):
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = Path(config) if config else None


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", "-p", default=8766, type=int, help="Port to bind")
@click.option("--log-level", default="INFO", help="Log level")
@click.pass_context
def serve(ctx, host, port, log_level):
    config = load_config(ctx.obj.get("config_path"))
    config.host = host or config.host
    config.port = port or config.port
    config.log_level = log_level or config.log_level

    import uvicorn

    from codex_cool.main import create_app

    app = create_app(config)
    console.print(f"[bold green]Codex-Cool Proxy[/bold green] starting on {config.host}:{config.port}")
    console.print(f"Providers: {', '.join(p.name for p in config.providers if p.enabled)}")
    console.print(f"Endpoints:")
    console.print(f"  OpenAI Responses:  http://{config.host}:{config.port}/v1/responses")
    console.print(f"  Chat Completions:  http://{config.host}:{config.port}/v1/chat/completions")
    console.print(f"  Anthropic Messages: http://{config.host}:{config.port}/v1/messages")

    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level.lower())


@main.command()
@click.pass_context
def providers(ctx):
    config = load_config(ctx.obj.get("config_path"))
    if not config.providers:
        console.print("[yellow]No providers configured[/yellow]")
        return

    table = Table(title="Configured Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Base URL", style="green")
    table.add_column("Format", style="magenta")
    table.add_column("Enabled", style="yellow")
    table.add_column("Priority", style="white")

    for p in config.providers:
        table.add_row(p.name, p.base_url, p.api_format, str(p.enabled), str(p.priority))

    console.print(table)


@main.command()
@click.argument("name")
@click.argument("base_url")
@click.option("--api-key", "-k", default="", help="API key (or env:VAR_NAME)")
@click.option("--format", "-f", "api_format", type=click.Choice(["responses", "chat", "anthropic"]), default="chat", help="API format")
@click.option("--model", "-m", multiple=True, help="Model mapping (alias=real)")
@click.option("--priority", "-p", default=0, type=int, help="Priority (higher = preferred)")
@click.option("--disabled", is_flag=True, help="Add as disabled")
@click.pass_context
def add(ctx, name, base_url, api_key, api_format, model, priority, disabled):
    config = load_config(ctx.obj.get("config_path"))

    for p in config.providers:
        if p.name == name:
            console.print(f"[red]Provider '{name}' already exists[/red]")
            return

    models = {}
    for m in model:
        if "=" in m:
            alias, real = m.split("=", 1)
            models[alias] = real

    provider = ProviderConfig(
        name=name,
        base_url=base_url,
        api_key=api_key,
        api_format=api_format,
        models=models,
        priority=priority,
        enabled=not disabled,
    )
    config.providers.append(provider)

    if not config.default_provider:
        config.default_provider = name

    save_config(config, ctx.obj.get("config_path"))
    console.print(f"[green]Provider '{name}' added successfully[/green]")


@main.command()
@click.argument("name")
@click.pass_context
def remove(ctx, name):
    config = load_config(ctx.obj.get("config_path"))
    original_len = len(config.providers)
    config.providers = [p for p in config.providers if p.name != name]

    if len(config.providers) == original_len:
        console.print(f"[red]Provider '{name}' not found[/red]")
        return

    if config.default_provider == name:
        config.default_provider = config.providers[0].name if config.providers else ""

    save_config(config, ctx.obj.get("config_path"))
    console.print(f"[green]Provider '{name}' removed[/green]")


@main.command()
@click.argument("name")
@click.pass_context
def default(ctx, name):
    config = load_config(ctx.obj.get("config_path"))
    found = any(p.name == name for p in config.providers)
    if not found:
        console.print(f"[red]Provider '{name}' not found[/red]")
        return
    config.default_provider = name
    save_config(config, ctx.obj.get("config_path"))
    console.print(f"[green]Default provider set to '{name}'[/green]")


@main.command()
@click.pass_context
def show_config(ctx):
    config = load_config(ctx.obj.get("config_path"))
    console.print(yaml.dump(config.model_dump(exclude_none=True), default_flow_style=False, allow_unicode=True))


@main.command()
@click.pass_context
def init(ctx):
    config_path = ctx.obj.get("config_path") or Path.home() / ".codex-cool" / "config.yaml"
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        return

    config = ProxyConfig(
        providers=[
            ProviderConfig(
                name="openai",
                base_url="https://api.openai.com/v1",
                api_key="env:OPENAI_API_KEY",
                api_format="chat",
                priority=10,
            ),
        ],
        default_provider="openai",
    )
    save_config(config, config_path)
    console.print(f"[green]Config initialized at {config_path}[/green]")


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind for management UI")
@click.option("--port", "-p", default=18080, type=int, help="Port for management UI")
@click.pass_context
def desktop(ctx, host, port):
    from codex_cool.desktop import run_desktop

    run_desktop(host=host, port=port)


if __name__ == "__main__":
    main()

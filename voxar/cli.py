"""Command line. Thin: parse arguments, call the facade, print results, map errors to exit codes."""

import argparse
import os
import platform
import sys
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import voxar
from voxar.api import Voxar
from voxar.config import Config
from voxar.domain import AudioChunk, EngineUnavailableError, TranscriptEvent, VoxarError
from voxar.llm import PROVIDERS, ChatClient, Message, client_from_config
from voxar.mic import mic_chunks
from voxar.models import CATALOG, Fetcher, ModelSpec, ModelStore
from voxar.net import fetcher_for as https_fetcher_for
from voxar.registry import Registry
from voxar.voice import Player, VoiceIO, play_audio

EXIT_OK = 0
EXIT_ERROR = 2

FetcherFactory = Callable[[ModelSpec], Fetcher]
MicSource = Callable[[], Iterable[AudioChunk]]
ServeMcp = Callable[[Voxar, Sequence[Path], Callable[[], dict[str, list[str]]], bool], None]
ServeHttp = Callable[[Voxar, Callable[[], dict[str, list[str]]], str, int, bool, bool], None]
LlmFactory = Callable[..., ChatClient]
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class _Context:
    """Everything a command needs, injected so tests never touch the network or a microphone."""

    config: Config
    registry: Registry
    fetcher_for: FetcherFactory
    mic: MicSource
    serve_mcp: ServeMcp
    serve_http: ServeHttp
    llm: LlmFactory
    play: Player
    env: Mapping[str, str]
    out: TextIO


def _serve_mcp(
    app: Voxar,
    allowed: Sequence[Path],
    engines: Callable[[], dict[str, list[str]]],
    voice: bool,
) -> None:
    try:
        from voxar.mcp_server import build_server

        devices = VoiceIO(play=play_audio, listen_chunks=mic_chunks) if voice else None
        server = build_server(app, allowed, engines, devices)
    except ImportError as exc:
        raise EngineUnavailableError(
            "the MCP server needs an optional dependency: pip install 'voxar[mcp]'"
        ) from exc
    server.run()  # stdio: stdout belongs to the protocol, so nothing may be printed here


def _warm_in_background(app: Voxar) -> threading.Thread:
    """Load the engines while the server starts listening; failures only print a note."""

    def run() -> None:
        try:
            app.warm_up()
        except Exception as exc:  # noqa: BLE001 - an optimization must never crash the server
            print(f"warm-up skipped: {exc}", file=sys.stderr)

    thread = threading.Thread(target=run, name="voxar-warm-up", daemon=True)
    thread.start()
    return thread


def _serve_http(
    app: Voxar,
    engines: Callable[[], dict[str, list[str]]],
    host: str,
    port: int,
    allow_remote: bool,
    warm: bool,
) -> None:
    try:
        import uvicorn

        from voxar.server import ANY_HOST, LOOPBACK_NAMES, create_app
    except ImportError as exc:
        raise EngineUnavailableError(
            "the HTTP server needs optional dependencies: pip install 'voxar[server]'"
        ) from exc
    allowed = frozenset({ANY_HOST}) if allow_remote else LOOPBACK_NAMES
    if warm:
        _warm_in_background(app)
    uvicorn.run(create_app(app, engines, allowed_hosts=allowed), host=host, port=port)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voxar", description="On-device speech.")
    parser.add_argument("--version", action="version", version=f"voxar {voxar.__version__}")
    commands = parser.add_subparsers(dest="command")

    transcribe = commands.add_parser("transcribe", help="transcribe a 16 kHz mono WAV file")
    transcribe.add_argument("file", help="path to a 16 kHz mono 16-bit WAV file")

    commands.add_parser("listen", help="transcribe the microphone live (Ctrl-C to stop)")

    say = commands.add_parser("say", help="synthesize speech to a WAV file")
    say.add_argument(
        "text", help="text to speak (Latin-script words are dropped by the Arabic voice)"
    )
    say.add_argument("-o", "--output", help="write a WAV file here (default: play on the speakers)")
    say.add_argument("--voice", help="voice name; engine-specific (default: the engine's default)")

    models = commands.add_parser("models", help="manage models")
    model_commands = models.add_subparsers(dest="models_command", required=True)
    model_commands.add_parser("list", help="list known models")
    pull = model_commands.add_parser("pull", help="download and verify a model")
    pull.add_argument("name")
    pull.add_argument(
        "--accept-license", action="store_true", help="confirm you reviewed the model's license"
    )
    verify = model_commands.add_parser("verify", help="check an installed model's checksums")
    verify.add_argument("name")

    serve = commands.add_parser("mcp", help="run the MCP server on stdio (for agents)")
    serve.add_argument(
        "--allow-dir",
        action="append",
        metavar="DIR",
        help="directory the agent may read/write audio in (repeatable; default: current directory)",
    )
    serve.add_argument(
        "--voice",
        action="store_true",
        help="also let the agent speak (announce, ask) and listen (listen, ask) through this "
        "machine's speakers and microphone",
    )

    http = commands.add_parser("serve", help="run the local HTTP/WebSocket server")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=8765)
    http.add_argument(
        "--no-warm",
        action="store_true",
        help="load engines on first use instead of at start-up (saves memory until needed)",
    )
    http.add_argument(
        "--allow-remote",
        action="store_true",
        help="allow binding a non-loopback address (the server has NO authentication)",
    )

    llm = commands.add_parser("llm", help="talk to a language model (HUMAIN Node, OpenRouter, ...)")
    llm_commands = llm.add_subparsers(dest="llm_command", required=True)
    llm_commands.add_parser("providers", help="list providers and whether their API key is set")
    llm_models = llm_commands.add_parser("models", help="list the models a provider offers you")
    ask = llm_commands.add_parser("ask", help="send one message and print the reply")
    ask.add_argument("text", help="what to say to the model")
    ask.add_argument("--system", help="system prompt (default: none)")
    ask.add_argument("--max-tokens", type=int, default=400, help="longest reply (default: 400)")
    ask.add_argument("--no-stream", action="store_true", help="print the reply when it is complete")
    for sub in (llm_models, ask):
        sub.add_argument(
            "--provider", choices=sorted(PROVIDERS), help="default: VOXAR_LLM_PROVIDER"
        )
        sub.add_argument("--base-url", help="override the provider's URL (https, or localhost)")
    ask.add_argument("--model", help="model id; default: VOXAR_LLM_MODEL or the provider's default")

    commands.add_parser("doctor", help="show environment and available engines")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    registry: Registry | None = None,
    fetcher_for: FetcherFactory | None = None,
    mic: MicSource | None = None,
    serve_mcp: ServeMcp | None = None,
    serve_http: ServeHttp | None = None,
    llm: LlmFactory | None = None,
    play: Player | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(file=err)
        print("error: a command is required", file=err)
        return EXIT_ERROR
    try:
        environment = env if env is not None else os.environ
        context = _Context(
            config=Config.from_env(environment),
            registry=registry or Registry(),
            fetcher_for=fetcher_for or https_fetcher_for,
            mic=mic or mic_chunks,
            serve_mcp=serve_mcp or _serve_mcp,
            serve_http=serve_http or _serve_http,
            llm=llm or client_from_config,
            play=play or play_audio,
            env=environment,
            out=out,
        )
        _run(args, context)
    except (VoxarError, ValueError) as exc:
        print(f"error: {exc}", file=err)
        return EXIT_ERROR
    return EXIT_OK


def _run(args: argparse.Namespace, ctx: _Context) -> None:
    if args.command == "transcribe":
        print(Voxar.from_config(ctx.config, ctx.registry).transcribe(args.file), file=ctx.out)
    elif args.command == "listen":
        _listen(ctx)
    elif args.command == "say":
        voxar_app = Voxar.from_config(ctx.config, ctx.registry)
        if args.output:
            voxar_app.speak_to_file(args.text, args.output, voice=args.voice)
        else:
            ctx.play(voxar_app.speak(args.text, voice=args.voice))
    elif args.command == "mcp":
        allowed = [Path(d) for d in args.allow_dir] if args.allow_dir else [Path.cwd()]
        app = Voxar.from_config(ctx.config, ctx.registry)
        ctx.serve_mcp(app, allowed, ctx.registry.available, args.voice)
    elif args.command == "serve":
        _serve(args, ctx)
    elif args.command == "models":
        _models(args, ctx)
    elif args.command == "llm":
        _llm(args, ctx)
    elif args.command == "doctor":
        _doctor(ctx)


def _serve(args: argparse.Namespace, ctx: _Context) -> None:
    if args.host not in LOOPBACK_HOSTS and not args.allow_remote:
        raise ValueError(
            f"refusing to listen on {args.host}: the server has no authentication. "
            "Use 127.0.0.1, or pass --allow-remote if you understand the risk"
        )
    app = Voxar.from_config(ctx.config, ctx.registry)
    print(
        f"voxar on http://{args.host}:{args.port}  (open it in a browser; Ctrl-C to stop)",
        file=sys.stderr,
    )
    ctx.serve_http(
        app, ctx.registry.available, args.host, args.port, args.allow_remote, not args.no_warm
    )


def _listen(ctx: _Context) -> None:
    app = Voxar.from_config(ctx.config, ctx.registry)
    live = ctx.out.isatty()
    try:
        for event in app.stream(ctx.mic()):
            _show(event, ctx.out, live=live)
    except KeyboardInterrupt:
        pass


def _show(event: TranscriptEvent, out: TextIO, *, live: bool) -> None:
    if event.is_final:
        prefix = "\r\x1b[K" if live else ""
        print(f"{prefix}{event.text}", file=out, flush=True)
    elif live:
        out.write(f"\r\x1b[K{event.text}")
        out.flush()


def _llm(args: argparse.Namespace, ctx: _Context) -> None:
    if args.llm_command == "providers":
        for provider in PROVIDERS.values():
            key = provider.key_env
            status = (
                "no key needed"
                if key is None or provider.local
                else (f"{key} ({'set' if ctx.env.get(key) else 'not set'})")
            )
            where = "on this machine" if provider.local else "remote"
            print(f"{provider.name:<11} {where:<16} {status}", file=ctx.out)
        return
    client = ctx.llm(
        ctx.config,
        ctx.env,
        provider=args.provider,
        model=getattr(args, "model", None),
        base_url=args.base_url,
        need_model=args.llm_command == "ask",
    )
    if args.llm_command == "models":
        for name in client.models():
            print(name, file=ctx.out)
        return
    turns = [Message("user", args.text)]
    options = {"system": args.system, "max_tokens": args.max_tokens}
    if args.no_stream:
        print(client.reply(turns, **options), file=ctx.out)
        return
    for piece in client.stream(turns, **options):
        ctx.out.write(piece)
        ctx.out.flush()
    ctx.out.write("\n")


def _models(args: argparse.Namespace, ctx: _Context) -> None:
    if args.models_command == "list":
        _list_models(ctx.out)
        return
    spec = _known_model(args.name)
    store = ModelStore(ctx.config.cache_dir, offline=ctx.config.offline)
    if args.models_command == "verify":
        store.verify(spec)
        print(f"{spec.id}: ok", file=ctx.out)
    else:
        _pull(spec, store, ctx, accept_license=args.accept_license)


def _list_models(out: TextIO) -> None:
    if not CATALOG:
        print("No models registered yet.", file=out)
    for known in CATALOG.values():
        print(f"{known.id}  {known.revision}  {known.license}", file=out)


def _known_model(name: str) -> ModelSpec:
    spec = CATALOG.get(name)
    if spec is None:
        raise ValueError(f"unknown model {name!r}; run: voxar models list")
    return spec


def _pull(spec: ModelSpec, store: ModelStore, ctx: _Context, *, accept_license: bool) -> None:
    if store.is_installed(spec):
        store.verify(spec)
        print(f"{spec.id}: already installed and verified", file=ctx.out)
        return
    target = store.install(spec, ctx.fetcher_for(spec), accept_license=accept_license)
    print(f"{spec.id}: installed and verified at {target}", file=ctx.out)


def _doctor(ctx: _Context) -> None:
    engines = ctx.registry.available()
    config = ctx.config
    print(f"voxar: {voxar.__version__}", file=ctx.out)
    print(f"python: {platform.python_version()} ({platform.system()})", file=ctx.out)
    print(f"cache dir: {config.cache_dir} (exists: {config.cache_dir.exists()})", file=ctx.out)
    print(f"offline: {config.offline}", file=ctx.out)
    print(f"recognizers: {', '.join(engines['recognizers']) or 'none'}", file=ctx.out)
    print(f"synthesizers: {', '.join(engines['synthesizers']) or 'none'}", file=ctx.out)

"""Langfuse tracing (TRD section 1/3: "traces every agent step — prompt,
tokens, latency, cost"). `@observe` wraps each pipeline node and each
LLM/embedding call site.

Graceful degradation: if LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set (the
default in a fresh env), `observe` is a plain passthrough decorator — no
network calls, no warnings, no behavior change. Tracing is additive
observability, never a dependency the pipeline can fail on.
"""

from typing import Callable, TypeVar

from app.core.config import settings

F = TypeVar("F", bound=Callable)

_ENABLED = bool(settings.langfuse_public_key and settings.langfuse_secret_key)

if _ENABLED:
    from langfuse import Langfuse
    from langfuse import observe as _observe

    langfuse_client: "Langfuse | None" = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    observe = _observe
else:
    langfuse_client = None

    def observe(*decorator_args, **decorator_kwargs) -> Callable[[F], F] | F:
        # Support both @observe and @observe(name=..., as_type=...) usage
        # without Langfuse configured — just return the function untouched.
        if decorator_args and callable(decorator_args[0]) and not decorator_kwargs:
            return decorator_args[0]

        def _wrap(func: F) -> F:
            return func

        return _wrap

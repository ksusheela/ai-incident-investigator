"""Filesystem MCP server — exposes stored incident artifacts as MCP tools.

This is the "server" side of Model Context Protocol integration: this
project choosing to expose its own data to external MCP clients (Claude
Desktop, another agent, an MCP inspector) over the standard protocol,
rather than a bespoke REST shape. The mirror image —
`infrastructure/mcp/client/` — would be this app *consuming* someone
else's MCP tools from within an agent; that side remains unbuilt (still
empty) since nothing in this pipeline needs an external tool yet.

Every tool here is a thin, validating wrapper around
`IncidentArtifactStore` — no business logic lives in this module, only
the translation between MCP's tool-call shape and the store's plain
Python methods (including moving the store's blocking file I/O off the
event loop via `anyio.to_thread`, since this server runs in the same
process as the rest of the API).
"""

import dataclasses
from collections.abc import Callable
from functools import partial

import anyio
from mcp.server import MCPServer

from app.infrastructure.filesystem.artifact_store import (
    ExportedFileNotFoundError,
    IncidentArtifactStore,
    IncidentNotFoundError,
)

_STORE_LOOKUP_ERRORS = (IncidentNotFoundError, ExportedFileNotFoundError, ValueError)


async def _call_store[T](
    func: Callable[..., T], *args: object, error_prefix: str, **kwargs: object
) -> T:
    """Run a blocking `IncidentArtifactStore` method off the event loop,
    translating its lookup/validation errors into one consistent `ValueError`
    shape -- the MCP SDK surfaces any `ValueError` a tool raises as a
    protocol-level tool error a client can detect and handle programmatically.
    """
    try:
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))
    except _STORE_LOOKUP_ERRORS as exc:
        raise ValueError(f"{error_prefix}: {exc}") from exc


SERVER_NAME = "ai-incident-investigator-filesystem"
SERVER_VERSION = "1.0.0"
SERVER_INSTRUCTIONS = (
    "Tools for reading and managing AI Incident Investigator's stored incident "
    "artifacts: uploaded logs, generated reports, and incident metadata. Every "
    "tool operates on the local filesystem; incidents are only created by "
    "running an investigation that actually detects a problem."
)


def create_mcp_server(store: IncidentArtifactStore) -> MCPServer:
    """Build an MCPServer exposing `store` via five tools.

    A fresh server is built per store rather than shared globally, so
    tests can point it at an isolated temp-directory store the same way
    the LLM-backed agent graph is built fresh per `LLMProvider`.
    """
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.tool()
    async def read_uploaded_log(incident_id: str) -> str:
        """Return the raw log text that was submitted for `incident_id`."""
        return await _call_store(
            store.read_uploaded_log,
            incident_id,
            error_prefix=f"Cannot read log for incident {incident_id!r}",
        )

    @server.tool()
    async def save_report(incident_id: str, markdown: str) -> str:
        """Save (or overwrite) the Markdown incident report for `incident_id`."""
        await _call_store(
            store.save_report,
            incident_id,
            markdown,
            error_prefix=f"Cannot save report for incident {incident_id!r}",
        )
        return f"Saved report for incident {incident_id}."

    @server.tool()
    async def list_incidents(limit: int = 50) -> list[dict[str, str]]:
        """List stored incidents, most recently created first."""
        records = await anyio.to_thread.run_sync(partial(store.list_incidents, limit=limit))
        return [dataclasses.asdict(record) for record in records]

    @server.tool()
    async def list_exported_files(incident_id: str | None = None) -> list[dict[str, str | int]]:
        """List exported files, optionally filtered to a single incident."""
        files = await _call_store(
            store.list_exported_files,
            incident_id=incident_id,
            error_prefix=f"Cannot list files for incident {incident_id!r}",
        )
        return [dataclasses.asdict(file) for file in files]

    @server.tool()
    async def delete_exported_file(incident_id: str, filename: str) -> str:
        """Delete a single exported file from an incident's directory."""
        await _call_store(
            store.delete_exported_file,
            incident_id,
            filename,
            error_prefix=f"Cannot delete {filename!r} for incident {incident_id!r}",
        )
        return f"Deleted {filename} from incident {incident_id}."

    return server

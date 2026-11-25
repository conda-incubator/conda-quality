# SPDX-License-Identifier: BSD-3-Clause
"""Serve a local channel over HTTPS with a certificate no client trusts.

The certificate is generated per use with the OpenSSL CLI, so no private key
lives in the repository. Any client that verifies certificates must reject the
server, so a command can only succeed against it once verification is disabled.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import shutil
import ssl
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.runner import CliRunner
from conda_e2e.utils import IS_WINDOWS

if TYPE_CHECKING:
    from collections.abc import Iterator

    from conda_e2e.channel import Package


@dataclass(frozen=True, slots=True)
class SelfSignedChannel:
    """A loopback HTTPS channel and the one package it serves."""

    url: str
    package: Package


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve channel files quietly, bounding each connection's request I/O."""

    timeout = 10

    def log_message(self, _format: str, *_args: object) -> None:
        """Suppress per-request access logs."""


def _openssl_executable() -> str:
    """Return the OpenSSL CLI that ships with the test environment."""
    found = shutil.which("openssl")
    if found is not None:
        return found
    if IS_WINDOWS:
        bundled = Path(sys.prefix) / "Library" / "bin" / "openssl.exe"
        if bundled.is_file():
            return str(bundled)
    raise FileNotFoundError("openssl is required to generate the loopback certificate")


def _generate_self_signed_certificate(directory: Path) -> tuple[Path, Path]:
    """Generate a throwaway server certificate for the loopback channel.

    The certificate and key are created under ``directory`` for one use only.
    They are not credentials: the unencrypted key is readable only by the test
    user, so never trust the certificate and never point a real network client
    at it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    cert_file = directory / "cert.pem"
    key_file = directory / "key.pem"
    request = (
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        # Unencrypted because the key is a throwaway test credential.
        "-nodes",
        "-keyout",
        str(key_file),
        "-out",
        str(cert_file),
        "-days",
        "1",
        "-subj",
        "/CN=127.0.0.1",
    )
    CliRunner(executable=_openssl_executable()).run(*request).assert_ok()
    key_file.chmod(0o600)
    return cert_file, key_file


@contextlib.contextmanager
def serve_self_signed_channel(channel_dir: Path, certificate_dir: Path) -> Iterator[str]:
    """Serve ``channel_dir`` over HTTPS on a loopback port and yield its base URL."""
    cert_file, key_file = _generate_self_signed_certificate(certificate_dir)
    handler = functools.partial(_QuietHandler, directory=str(channel_dir))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

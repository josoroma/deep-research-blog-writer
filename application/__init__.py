"""Shared application use cases for the CLI and the HTTP worker.

Modules here own admission and execution policy. They must not import FastAPI
request/response types, psycopg, or any HTTP client; concrete adapters live in
``api/``, ``workers/`` and ``services/``.
"""

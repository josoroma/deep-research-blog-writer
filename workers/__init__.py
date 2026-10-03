"""Background scheduling for research jobs. Claims durable work and executes it.

Import from ``workers.research_worker`` directly. Re-exporting it here made
``python -m workers.research_worker`` warn that the module ran after import.
"""

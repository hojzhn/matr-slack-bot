"""UI layer — **dumb** view builders.

Each module here turns plain data into Block Kit view dicts and nothing else:
no config loading, no Slack client, no I/O, no business logic, no validation.
Builders are pure functions (same input → same output), so they're trivial to
unit-test. The cogs resolve all data first (config, conversions, schema) and
hand it in; these functions just render.
"""

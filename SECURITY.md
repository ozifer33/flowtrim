# Security

FlowTrim is designed to reduce context safely, not to collect private evidence.

## Do Not Submit

- Secret values, tokens, credentials, or environment-file contents.
- Private command output, customer data, production traces, raw diffs, or source
  bodies.
- Private repository names, commit messages, or local machine paths.

## Reporting Privacy Issues

Open an issue with a minimal public-safe reproduction. Describe the command,
profile, and expected gate behavior, but do not paste private output. If a report
contains sensitive data, keep it local and describe the failing field or gate.

## Supported Proof Posture

The benchmark suite should remain read-only for public corpus checks. Optional
tools such as Headroom or RTK must stay direct, ephemeral, and non-invasive:
no proxy, wrap mode, MCP registration, memory, learning, telemetry, or persistent
configuration changes inside FlowTrim tests.

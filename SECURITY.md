# Security

Generation is offline and reads only paths explicitly supplied by the user.
The output is a new Python unittest; inputs are never overwritten. It contains
masked fixture values, not a replacement map. No shell commands or raw code are
interpolated from inputs: fixtures are encoded as JSON inside Python literals.

Masking has limited coverage and can miss secrets or personal information.
Review output before sharing or committing it. Extra masking strings belong in
a local values file, not command-line arguments. Keep that file private.

Generated tests send JSON to explicitly configured loopback receiver endpoints;
use test state because requests may cause side effects. No authorization headers,
production signing secrets, remote opt-in or automatic fixture uploads exist.

Do not post exploit details or credentials publicly. If no private reporting
channel is available, ask the maintainer to establish one without disclosing
the vulnerability itself. No external security audit or response SLA is claimed.

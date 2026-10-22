# Webhook Regression Kit

**Turn local webhook fixtures into a reviewable Python regression test.**

Provide events, a Delivery Probe scenario and the receiver state you expect.
The kit masks selected sensitive fields and text patterns and emits a unittest
that uses [Delivery Probe](https://github.com/sesenface-tech/delivery-probe).
The generated test catches incorrect final state even if all deliveries return
HTTP 200. No AI key, network access or runtime dependencies are needed to
GENERATE tests. Running the generated test requires Delivery Probe 0.1.x.

## Generate

From this checkout with Python 3.10+:

```sh
python -m webhook_regression_kit \
  --events examples/events.json \
  --expected examples/expected.json \
  --scenario duplicate \
  --output test_generated.py
```

Use `python3` or `py` if appropriate for your system. The output must be a new
`.py` file; existing paths and symlink destinations are never overwritten.
The tool creates the file with mode 0600 on POSIX. Generation performs no HTTP
requests and leaves source files unchanged. CLI errors do not echo file content.

The input is an array of 1..100 JSON event objects with unique printable ASCII
`id` fields; each event is at most 64 KiB, each input file at most 1 MiB. The
entire object becomes the webhook JSON body. Expected state is a non-empty JSON
object: choose an invariant that reflects actual business effects, not merely
HTTP acceptance. The tool does not infer correct state from a failing system.

## Review and run

Read the generated `CASE` and confirm that masking has not changed the behavior
you intend to test. Use isolated test data. Set receiver addresses at RUN time;
they are never embedded in the generated file.

```sh
# With delivery-probe installed, or its checkout on PYTHONPATH:
WEBHOOK_TARGET=http://127.0.0.1:8080/webhook \
WEBHOOK_STATE_URL=http://127.0.0.1:8080/state \
python test_generated.py
```

PowerShell:

```powershell
$env:WEBHOOK_TARGET = 'http://127.0.0.1:8080/webhook'
$env:WEBHOOK_STATE_URL = 'http://127.0.0.1:8080/state'
python test_generated.py
```

Missing receiver variables FAIL the test rather than silently skipping it.
Only loopback endpoints are supported by generated tests. Provider signatures,
authentication headers and byte-for-byte capture are not implemented.

Scenarios: `normal`, `duplicate` (repeat first event), `delayed` (pause before
second event), `reorder` (reverse order). `--delay` and `--wait` accept 0..5s.
Each test performs one final-state observation after an optional wait; it does
not certify concurrent, durable or eventual-consistency behavior. Use a fresh
receiver state for every independent test.

## Masking scope

Known JSON keys include password, token, API key, authorization, cookie, email,
phone, address, location and vehicle identifiers. Text patterns cover URLs,
emails, bearer tokens, selected API-key formats, JWT-like strings and complete
PEM private-key blocks. Repeated values receive stable placeholders within one
generation. The in-memory replacement map is never written to disk.

For extra known values, use `--redact-values-file local-values.json`, containing
a JSON array of non-empty strings. Do not put live secrets in command-line
arguments or commit that file. Summary output contains counts only.

**Masking is best effort, not complete anonymization or a security audit.**
Unknown formats, data embedded in unusual keys, incomplete key blocks and free
text personal data may remain. Review before sharing. Masking can change types,
signatures and equality behavior; these are test fixtures, not production replay
payloads. A generated test's correctness depends on the supplied expected state.

## Test the kit

Clone Delivery Probe alongside this repository, then from this repository:

```sh
PYTHONPATH=.:../delivery-probe python -m unittest discover -s tests -v
```

PowerShell: `$env:PYTHONPATH = ".;../delivery-probe"`, then run the unittest
command. Tests execute generated files against actual isolated loopback HTTP
receivers, including deliberately broken negative controls. Synthetic fixtures
and self-integration are not evidence of third-party adoption.

## Related work and maintenance

[webhook-replay](https://pypi.org/project/webhook-replay/) and
[HookRadar](https://github.com/aniketmishra-0/Hookradar) already support capture
and replay workflows. This project focuses on deterministic Python test-file
generation and explicit receiver-state expectations. No uniqueness claim and
no external adoption is claimed. Maintained by Serkan Esen; MIT licensed.

See CONTRIBUTING.md and SECURITY.md. The generator and generated fixtures are
intended for local, authorized development environments.

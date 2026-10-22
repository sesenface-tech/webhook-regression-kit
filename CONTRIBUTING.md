# Contributing

Use synthetic fixtures only. Run the documented tests with Delivery Probe on
PYTHONPATH. Regression tests should demonstrate a failure before a fix and pass
after the fix. Add tests for new masking formats, preserving stable replacements
and documenting behavior changes. Do not promise complete secret removal.

Keep generation deterministic and offline. Do not add AI services, automatic
uploads, provider authentication or external messaging without discussing scope.
Avoid real customer payloads in issues, examples and pull requests.

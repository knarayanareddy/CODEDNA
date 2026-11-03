# CodeDNA remediation plan

All work below is proposed, not performed. Preserve current thresholds and tests; obtain owner approval before changing distribution, privacy or daemon access policies.

## Dependency map and phases

| Phase | Entry | Tasks and exit |
|---|---|---|
| Baseline | Pinned revision available | CD-T1 reproduces packaging and manifest behavior |
| Correctness | CD-T1 | CD-T2 removes CD-1 and demonstrates real IPC |
| Security and supply chain | CD-T1 | CD-T3 documents threat model and checks local boundary |
| Automation | CD-T2, CD-T3 | CD-T4 gates broken behavior and packaging |
| Release and acceptance | CD-T4 and owner decisions | CD-T5 verifies supported platforms, restore and rollback |

### CD-T1 — Establish reproducible baseline (CD-1, CD-2)
Prerequisites: isolated checkout, supported Python and Rust toolchains; observed paths `rust-scanner/Cargo.toml`, `pyproject.toml`, `.github/workflows/ci.yml`.
1. Record toolchain versions and inspect declared packaging for the scanner binary.
2. In a disposable environment, attempt manifest parsing/build and record the actual failure before changing it.
3. Run existing Python tests independently and compare results with CI's compile-only gate.
Deliverable: redacted baseline with commands, outcomes and versioned artifacts. Verification: a second maintainer reproduces the failure at the same SHA.
- [ ] Duplicate-key failure and test baseline recorded separately.
- [ ] No claimed pass is inferred from historical CI.

### CD-T2 — Repair scanner and exercise actual integration (CD-1)
Prerequisite: CD-T1; observed `rust-scanner/Cargo.toml`, `rust-scanner/src/main.rs`, `src/codedna/daemon/scanner_client.py`.
1. Remove the duplicate key without changing crate identity.
2. Build and package the scanner on each supported target and verify the installed executable is discoverable.
3. Drive a real JSON request from the daemon through the subprocess, including malformed and oversized requests, and assert degraded/error responses.
Deliverable: valid crate and end-to-end IPC regression tests. Verification: deliberately corrupt the protocol or hide the executable and confirm the tests fail for the expected reason.
- [ ] Scanner builds from clean source and is present in the install artifact.
- [ ] IPC success, error and degraded paths have independent assertions.

### CD-T3 — Local trust boundary and data protection (CD-3, CD-4)
Prerequisite: CD-T1 and owner threat-model decision; observed `src/codedna/daemon/middleware.py`, daemon routes and `requirements.txt`.
1. Trace bind address, Host/Origin checks, each route's authorization, caller paths that can reach loopback, permissive-versus-strict header behavior, subprocess arguments and stored fingerprint lifecycle.
2. Implement a locally appropriate authorization and origin policy if needed; do not treat the static client header as a credential or as verified client identity unless unknown values are actually rejected.
3. Lock and verify dependencies, constrain file access and document encryption, retention, secret rotation and local backup permissions.
Deliverable: threat model and tests for untrusted origin, missing header, spoofed or unregistered `X-CodeDNA-Client` values, path traversal, oversized input and unauthorized local access. Verification: perform attacks against a running isolated daemon, including spoofed and unregistered header values from intended and non-intended caller paths, and verify rejection or explicitly documented permissive behavior without leaking source.
- [ ] Real request tests demonstrate the intended access policy, including missing, spoofed and unregistered header cases.
- [ ] Data ownership, retention and dependency update process are documented.

### CD-T4 — Meaningful automation (CD-2)
Prerequisites: CD-T2 and CD-T3; observed workflow and `tests/`.
1. Add clean Python test and Rust build/test jobs with pinned toolchains and dependency resolution.
2. Test an installed artifact and VS Code-to-daemon integration, including a missing-scanner case and the chosen client-header policy.
3. Gate each job independently and publish actionable failure diagnostics without source or credentials.
Deliverable: CI that covers actual behavior rather than syntax alone. Verification: intentionally break a scanner response and authorization condition separately; each relevant job must fail.
- [ ] Tests fail on deliberate mutations and pass after restoration.
- [ ] CI checks the built distribution, not just the source tree.

### CD-T5 — Recovery, UX and independent acceptance (preventive)
Prerequisite: CD-T4, approved support matrix; observed CLI and extension manifests.
1. Exercise CLI and extension on supported platforms, including keyboard navigation and understandable scanner-offline messages.
2. Back up a synthetic database, restore it in isolation, and test upgrade and rollback compatibility.
3. Independently review results, signing/provenance, and performance claims with representative repositories.
Deliverable: release checklist and observed restore/rollback record. Verification: compare restored fingerprints and inspect a signed artifact on a clean system.
- [ ] Recovery and UX observations recorded per platform.
- [ ] An independent reviewer accepts evidence; no authorship guarantee is implied.

## Release and production acceptance

- [ ] Owner approves daemon exposure, credential and retention policy, release signing, and supported platforms.
- [ ] Reproducible signed artifact, security tests, UX and restore evidence are attached to the release.
- [ ] Roll back by reinstalling the last verified artifact and restoring a compatible backup; rehearse migration downgrade before release. Stop the daemon during restore and verify data integrity before reopening access.

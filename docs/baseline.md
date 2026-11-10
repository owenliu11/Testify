# Baseline and milestone status

- SkyWatch target: `413a8237fdcf9afeaa9e495f9e6e96c720bcf18f`.
- AgentForge target from the build guide: `0e41dcc`; the local checkout was at `84b1c95` when inspected. No AgentForge tests are configured yet.
- SkyWatch requires Docker, a TimescaleDB container, Redis, a synthetic provider, and the API. The test uses ports 18000 and 18080 and no real provider credentials.
- The starter integration scenario has passed locally. M1 still requires a successful fresh-clone CI run with saved evidence; CI configuration alone does not establish that gate.
- Licensing for TestForge and redistribution of the target repositories has not yet been decided. No license is implied by this document.

# Security Policy

## Supported version

Security fixes are applied to the latest public beta release.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is available for
this repository. If it is not enabled, open a minimal issue asking the
maintainer for a private contact channel. Do not include tokens, private Codex
content, local paths, proof-of-concept exploits, or other sensitive details in
a public issue.

Please include the affected version, the feature involved, the expected
security boundary, and whether the issue can be reproduced with the default
configuration. Allow a reasonable remediation window before public
disclosure.

## Security model

- The control service listens only on the local loopback interface.
- State-changing API requests require a locally generated random token.
- Cross-origin and non-JSON state-changing requests are rejected.
- Codex status events omit prompt text, response content, and workspace paths.
- Session and request identifiers are anonymized before entering bridge state.
- Keyboard shortcut capture is explicitly entered, visibly indicated, and
  automatically cancelled on completion or timeout.

Mapping a controller button to a global keyboard shortcut grants that physical
button the same effect as pressing the shortcut on the keyboard. Review custom
mappings before enabling them.

Release authenticity and signing incidents are handled according to the
[code signing policy](CODE_SIGNING_POLICY.md). Data handling and local storage
are documented in the [privacy policy](PRIVACY.md).

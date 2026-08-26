# Code signing policy

Last updated: 2026-08-27

## Status and attribution

Release 0.2.4 and earlier are unsigned public beta builds. A release must not be
described as signed until its downloadable files have passed the verification
steps in this policy.

Free code signing provided by [SignPath.io](https://signpath.io/), certificate
by [SignPath Foundation](https://signpath.org/).

## Team roles

- **Committer and reviewer:** [Jhen-da](https://github.com/Jhen-da) maintains
  the source code, build scripts, packaging, and release workflow. Contributions
  from people without commit access require maintainer review before merge.
- **Approver:** [Jhen-da](https://github.com/Jhen-da) manually evaluates each
  release signing request. Signing approval is never automated.

All people with repository or SignPath access must enable multi-factor
authentication. Credentials, one-time codes, API tokens, and private keys must
not be committed, shared in issues, or included in release artifacts.

## What may be signed

Only release artifacts produced from this repository by the protected GitHub
Actions release workflow may be submitted:

- `DualSenseCodex.exe`, built from the tagged source with PyInstaller.
- `DualSense-Codex-Setup-<version>.exe`, built from the already signed portable
  application with Inno Setup.

The release may contain unmodified redistributable files from open-source
dependencies or Windows system libraries. They are not represented as binaries
authored or signed by this project. The optional virtual touchpad source keeps
its separate upstream notices and is not part of the default signed package.

## Build and approval controls

1. The version tag must exactly match `VERSION`.
2. A GitHub-hosted Windows runner builds the portable application from the
   checked-out tag.
3. GitHub stores the unsigned artifact before the SignPath request is created.
4. SignPath signs only the executable selected by the portable artifact
   configuration after a manual approval.
5. The installer is then built from the signed portable files and submitted as
   a separate signing request that also requires manual approval.
6. The workflow verifies the Authenticode signature and trusted timestamp on
   both executables. Any missing, invalid, or unexpected file stops publication.
7. SHA-256 checksums are generated only after signing, and GitHub publishes the
   verified artifacts from the same workflow run.

Local builds, manually uploaded executables, workflow runs missing SignPath
configuration, and unsigned artifacts must not be published as signed releases.

## File metadata

Signed files identify the product as **Codex Controller for DualSense** and use
the version from the repository's `VERSION` file. SignPath artifact
configurations must enforce the expected product name and version metadata.

## Privacy

See the project [privacy policy](PRIVACY.md). This program will not transfer any
information to other networked systems unless specifically requested by the
user or the person installing or operating it.

## Incident response

If a signing credential, repository account, workflow, or published artifact
may be compromised, the maintainer will stop signing, remove affected downloads
when necessary, investigate the source and build history, notify SignPath, and
request certificate revocation when appropriate. A corrected release receives
a new version and a new signing approval; signed files are never silently
replaced under an existing version.

The repository's CODEOWNERS file designates changes to this policy, the release
workflow, and packaging scripts for explicit maintainer review. Repository
branch protection should require that review whenever the hosting plan and team
structure allow it.

# Releasing Flaskteroids

Releases are maintainer-driven: choose a version bump, review a release PR,
then publish a draft GitHub release. No Conventional Commit format is required.
Only stable `X.Y.Z` releases are supported by these workflows.

## One-time setup

### Release PR token

Create a fine-grained GitHub personal access token with access only to this
repository and these repository permissions:

- **Contents: Read and write** (push the release branch).
- **Pull requests: Read and write** (check for existing release PRs and open one).

Store it as the repository Actions secret **`RELEASE_PR_TOKEN`**. The token owner
must have write access to the repository. Approve the token for the organization
if required, and renew it before it expires.

A GitHub App installation token with equivalent permissions can be used instead
if you provide a fresh token to the preparation workflow. The built-in
`GITHUB_TOKEN` is deliberately not used for opening the PR: its events do not
normally trigger other workflows, so the release PR would miss automatic CI.

### PyPI Trusted Publishing

On GitHub, create an environment named **`pypi`**. Optionally configure required
reviewers for an additional approval immediately before uploading.

On PyPI, open the existing `flaskteroids` project's **Publishing** settings and
add a GitHub trusted publisher with:

| Setting | Value |
| --- | --- |
| Owner | `nullco` |
| Repository | `flaskteroids` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Use the actual owner/repository if this project moves. No PyPI API token or
password is needed in GitHub secrets. The publishing job obtains a short-lived
credential using OpenID Connect.

Configure branch protection for `main` to require the existing test checks before
merging a release PR. These workflows do not bypass branch protection.

## For each release

1. Maintain user-facing notes under **`## Unreleased`** in `CHANGELOG.md` as you
   merge changes. Include breaking changes and migration instructions where
   relevant. The preparation action refuses an empty or comments-only section.
   The initial Unreleased section summarizes recent framework changes; review
   it against the last published version before your first automated release.
2. Open **Actions → Prepare Release → Run workflow** and choose:
   - **patch**: `0.1.6` → `0.1.7`
   - **minor**: `0.1.6` → `0.2.0`
   - **major**: `0.1.6` → `1.0.0`

   The action always prepares from the repository's default branch. It updates
   `pyproject.toml`, refreshes `uv.lock` and the README badge URL, moves Unreleased
   notes into a dated release section, and opens a PR from a `release/` branch.
   The badge URL gets a release-specific query parameter to reduce stale image
   caching on GitHub and PyPI; it still reports the latest version from PyPI.
   It refuses to open another release PR while one is pending.
3. Review the version and changelog, wait for CI, then merge the PR. The
   **Create Draft Release** action creates a draft for `vX.Y.Z` targeting the
   exact merged commit, with the changelog notes. Squash merges are supported;
   subsequent commits on `main` are not included in this release.
4. Review the draft under **Releases**, then click **Publish release**.
   This is the decision to publish to PyPI. Keep the prerelease checkbox off.
5. Watch **Publish** complete. It runs the Python test matrix, checks the
   tag/version/lockfile/changelog, builds and validates the source distribution
   and wheel, then installs the wheel into a fresh environment. The smoke test
   generates an app and scaffold, applies migrations, and requests the scaffold
   page. Only then are the same built artifacts uploaded to PyPI.

The `Unreleased` section remains ready for the next changes. Regular merges do
not publish anything. You may edit a draft's announcement before publishing it;
edit the release PR if the packaged changelog itself needs changes.

## Failures and retries

- Preparation failures do not publish anything. Correct the notes or token
  configuration, then run the action again.
- A merge without a draft usually means **Create Draft Release** failed. Fix the
  reported problem and rerun it. If the version's tag already exists, the action
  refuses to reuse it; inspect the existing tag and release rather than moving
  a published tag.
- A published GitHub release does not guarantee the PyPI upload succeeded.
  Check **Publish**, including any pending `pypi` environment approval. If tests,
  packaging, or credentials fail before upload, resolve the problem and rerun
  the workflow. Workflow fixes require a new release if they are absent from
  the tagged commit.
- PyPI versions are immutable. Never overwrite or move a published version's
  tag. Fix a bad release with a new patch version; yank the bad version on PyPI
  if needed. If an upload partially succeeded, inspect PyPI before retrying:
  uploading files that already exist will be rejected.

## Local checks

The bookkeeping helper uses only Python's standard library. To exercise it on a
clean local branch after adding Unreleased notes:

```sh
python scripts/release.py prepare patch
uv lock
python scripts/release.py validate-tag "v$(python scripts/release.py version)"
python scripts/release.py notes
uv build
uvx twine check --strict dist/*
```

These commands modify the local version and changelog but do not commit, tag,
open a PR, or publish. GitHub Actions is the normal release entry point.

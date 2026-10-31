# Versioning

The documentation site is versioned with [mike](https://github.com/jimporter/mike),
so readers can switch between the docs for each release. The version selector in
the header is provided by mike; it reads the `extra.version` block in
`mkdocs.yml`.

## How the site is published

Publishing runs in CI, not from a workstation. The workflow
`.github/workflows/docs.yml` builds the site and calls mike on two triggers:

- a push to `main` publishes the `dev` version;
- a version tag such as `v0.2.0` publishes that version and moves the `latest`
  alias to it.

Both jobs write to the `gh-pages` branch. Nothing is pushed from a local build.

## Commands for a maintainer

These commands are for a maintainer working on a release. Run them only when you
intend to publish.

```bash
# Preview the current working tree without publishing anything
uv run --group docs mkdocs serve

# Build the current tree into the local site/ directory
uv run --group docs mkdocs build --strict

# Publish a new version and point the latest alias at it
uv run --group docs mike deploy --push --update-aliases 0.2.0 latest

# Make latest the version a first-time reader lands on
uv run --group docs mike set-default --push latest

# List the versions that are published
uv run --group docs mike list

# Serve a published version locally
uv run --group docs mike serve
```

## Version names

- `latest` is an alias, not a directory. It always points at the newest release.
- Release versions are the project version without the leading `v`, for example
  `0.2.0`.
- `dev` tracks `main` between releases. It is not the default.

## What a version contains

Every version is a complete build of `docs/` at that commit. Pages under
`docs/internal/` are excluded by `mkdocs.yml`, so engineering notes never appear
in a published version.

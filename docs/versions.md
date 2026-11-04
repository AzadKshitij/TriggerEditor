# Publishing the site

The public site has two parts, served from one GitHub Pages deployment:

| Path | Source | Built by |
|---|---|---|
| `/` | `homepage/` | nothing; plain HTML, CSS and JavaScript |
| `/docs/` | `docs/` | [Zensical](https://zensical.org/), configured in `zensical.toml` |

The two are separate on purpose. The landing page can change its look without
touching the guide, and a page in `docs/` can assume the reader already decided
to install the app.

## There is one live version

The site is not versioned. Whatever is on `main` is what readers get. The alpha
has no users who need to pin docs to an older release, and a version selector
would double the surface to keep correct for every page.

Confirmed bug reports name the app version they came from, so an issue tells you
which docs applied when it was filed.

## How publishing works

Publishing runs in CI, not from a workstation. `.github/workflows/docs.yml`
runs on every push to `main` and on manual dispatch:

1. it installs the `docs` dependency group;
2. it builds `docs/` into `site/docs` with Zensical;
3. it copies `homepage/` over the root of `site/` and adds `.nojekyll`;
4. it force-pushes `site/` to the `gh-pages` branch.

The force-push means `gh-pages` is a build artifact, not a branch to commit to.
Nothing is pushed from a local build.

## Commands for a maintainer

```bash
# Preview the documentation with live reload
uv run --group docs zensical serve

# Build exactly what CI builds, into site/docs
uv run --group docs zensical build --clean

# Preview the landing page on its own
python -m http.server 8000 --directory homepage
```

To check the assembled site the way it will be served, build the docs, copy the
homepage over the root, and serve `site/`:

```bash
uv run --group docs zensical build --clean
cp -R homepage/. site/
python -m http.server 8000 --directory site
```

## What gets published

Everything in `homepage/` and everything in `docs/` except the paths listed under
`exclude_docs` in `zensical.toml`. `docs/internal/` holds engineering notes,
plans and historical reports. It stays in the repository and never appears on
the site.

Check a change before pushing: `zensical build` prints broken links and missing
pages as warnings.

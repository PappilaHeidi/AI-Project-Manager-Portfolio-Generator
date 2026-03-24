# docs/

This folder contains all project documentation for the AI Project Manager & Portfolio Generator, written in Markdown and built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

Navigation is managed automatically by [mkdocs-awesome-nav](https://lukasgeiter.github.io/mkdocs-awesome-nav/) using `.nav.yml` files in each folder.

## Structure

```
docs/
├── projektiraportti/       # Project report documents
│   ├── .nav.yml            # Navigation order for this section
│   ├── 00-ohjeet.md
│   ├── 01-projektisuunnitelma.md
│   ├── 02-vaatimukset.md
│   ├── 03-data-aineisto.md
│   ├── 04-arkkitehtuuri.md
│   ├── 05-menetelmät.md
│   ├── 06-tulokset.md
│   ├── 07-pohdinta.md
│   └── 08-liitteet.md
├── images/                 # Images used in documentation
├── .nav.yml                # Top-level navigation order
├── index.md                # Documentation front page
├── paivakirja.md           # Development journal
└── yhteenveto.md           # Project summary
```

## Viewing the Documentation Locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
# Go to the docs directory
cd docs

# Serve with live reload (opens browser automatically)
uvx --with mkdocs-material --with mkdocs-awesome-nav mkdocs serve --livereload --open --strict
```

The local development server runs at `http://127.0.0.1:8000` by default.

## Deployment

Documentation is automatically built and deployed to GitLab Pages via `.gitlab-ci.yml` on every commit to the main branch. No manual deployment is needed.
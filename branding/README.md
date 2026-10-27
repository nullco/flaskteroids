# Flaskteroids brand assets

The official Flaskteroids logo is a silver-gray flask containing luminous green
potion, with green bubbles and sparkles. No slogan is part of the logo.

Open [preview.html](preview.html) for the asset gallery.

This directory is the canonical logo kit for repository maintainers, not part
of the framework user guide. `docs/assets/brand/` contains only the four image
files used by the documentation site. After updating those originals, refresh
the site copies from the repository root:

```sh
cp branding/icon-small.svg branding/favicon.png \
  branding/logo-horizontal-dark.svg branding/logo-horizontal-light.svg \
  docs/assets/brand/
```

The default welcome page and mailer preview browser share a small set of SVGs as
framework package resources, so generated applications display the logo without
static-file configuration or network access. Refresh those copies after a logo change:

```sh
cp branding/logo-horizontal-dark.svg branding/logo-horizontal-light.svg \
  branding/favicon.svg flaskteroids/controllers/templates/brand/
```

## Choose an asset

| Use | SVG | PNG |
| --- | --- | --- |
| Horizontal logo, dark background | [SVG](logo-horizontal-dark.svg) | [PNG](logo-horizontal-dark.png) |
| Horizontal logo, light background | [SVG](logo-horizontal-light.svg) | [PNG](logo-horizontal-light.png) |
| Stacked logo, dark background | [SVG](logo-stacked-dark.svg) | [PNG](logo-stacked-dark.png) |
| Stacked logo, light background | [SVG](logo-stacked-light.svg) | [PNG](logo-stacked-light.png) |
| Wordmark, dark background | [SVG](wordmark-dark.svg) | [PNG](wordmark-dark.png) |
| Wordmark, light background | [SVG](wordmark-light.svg) | [PNG](wordmark-light.png) |
| Full icon, dark background | [SVG](icon.svg) | [512px PNG](icon.png) |
| Full icon, light background | [SVG](icon-light.svg) | [512px PNG](icon-light.png) |
| Small icon, headers | [SVG](icon-small.svg) | [64px PNG](icon-small.png) |
| Single-color dark ink | [SVG](icon-mono-black.svg) | [PNG](icon-mono-black.png) |
| Single-color white ink | [SVG](icon-mono-white.svg) | [PNG](icon-mono-white.png) |
| Social/share image | [SVG](social-card.svg) | [1200 × 630 PNG](social-card.png) |
| Favicon | [SVG](favicon.svg) | [48px PNG](favicon.png), [32px PNG](favicon-32.png) |
| Touch icon | — | [180px PNG](apple-touch-icon.png) |

`dark` and `light` describe the **intended background**, not the ink color.
The monochrome variants are explicitly named `black` and `white`.
All logos have transparent backgrounds except the social card, favicon, and
touch icon, which use charcoal. All PNGs use the same artwork as their SVGs.

## Usage

- Prefer SVG for websites and scalable artwork; use PNG when SVG is unsupported.
- Use the horizontal logo by default, the stacked version when space is taller,
  and the icon when the framework name is already visible.
- Use the simplified icon at 64px and below. It removes blur, sparkles, and
  fine details for legibility.
- Keep at least one flask-neck width of clear space around the artwork.
- Preserve proportions, colors, and the green full stop. Do not add slogans to
  the logo, stretch it, or use the glowing version as a single-color stencil.
- Use the darker silver treatment and dark wordmark on light backgrounds.
  Use the white wordmark and brighter silver treatment on dark backgrounds.

## Palette and typography

- Potion: `#EDFF9D` → `#B1FF53` → `#49CF87`
- Bubbles and sparkles: `#C9FF80`
- Silver glass: `#F0F1F3` → `#B8BBC2` → `#737780`
- Charcoal presentation background: `#100F1B`

The wordmark is based on Lato Black with tight spacing. Its lettering is
converted to vector paths: no installed fonts, external resources, or embedded
font files are required. SVGs retain accessible titles and descriptions.

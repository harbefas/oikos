# oikos hub — UI

Two surfaces, one design system:

| Entry | Route | Surface |
|---|---|---|
| `index.html` → `src/phone/` | `/` | Console Hub, phone, touch |
| `tv.html` → `src/tv/` | `/home` | Home Screen, TV kiosk, d-pad |

Built with Svelte + Vite to static files. `console-hub.py` serves `dist/`; it
holds no HTML of its own.

## Develop

Do not deploy to see a change. Run the dev server against the real hub:

```sh
pnpm install
OIKOS_DEV_API=http://homelab:8100 pnpm dev
```

Vite proxies `/api`, `/jf`, `/jfbd`, `/acover`, `/cover`, `/img`, `/wallpaper`
and `/steamhero` to that host, so the UI runs locally with live data.

## Design system

Colour, type, spacing, radius, shadow, motion durations and easings come from
`src/lib/mate-tokens.css`, which is **generated** — never edit it. Values live
in `mateCreations/ui/tokens/*.json`; the rules live in `mateCreations/DESIGN.md`
and must be read before writing UI. Refresh the vendored copy with:

```sh
./scripts/sync-tokens.sh
```

It is vendored rather than installed because `mateCreations` is a local-only
repo — a CI runner cloning oikos cannot resolve `@matecreations/ui`, and this
repo has to stay buildable by anyone.

`src/lib/tokens.css` holds only what is genuinely oikos-specific: the ambient
scrim and the geometry of the 10-foot shelf.

### Motion

The TV surface is the first consumer of `DESIGN.md` §6a — the reading-distance
rule. Motion and depth are allowed there because at three metres a 1px border
cannot say which card has focus. That is a justification, not a blanket
exemption: the phone stays on chrome rules (120ms, colour only, nothing moves).

Anything added here must still answer §6a's test — *is this saying something a
1px line could not?* If not, cut it.

## Build and deploy

```sh
pnpm build          # -> dist/
```

CI builds on push to `master` and publishes a tarball on a `ui-v*` tag. The
homelab downloads it; Node never gets installed there.

```sh
git tag ui-v1 && git push --tags
```

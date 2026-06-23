# helix-ide

A self-contained **Helix IDE rice**: Helix + zellij + kitty wired into a single
IDE layout, with two things you don't usually get for free:

- 🎨 **Live theme sync with an animated fade.** Change the Helix theme
  (`:theme <name>`) and the *whole* IDE — editor pane, pane frames, the bottom
  terminal and the kitty window/gap — smoothly fades to the new colours.
- 🟣 **Discord Rich Presence** for Helix (optional), without recompiling Helix.

It's a single layout: Helix on top (~70%), a persistent terminal below (~30%),
launched with one command — `hx`. Quitting Helix (`:q`) tears the whole session
down and drops you back to your normal shell.

```
┌──────────────────────────────────────┐
│  Helix              (editor pane)     │
│  src/main.rs                          │
│                                       │
├──────────────────────────────────────┤
│  $ cargo test       (terminal pane)   │
└──────────────────────────────────────┘
   ↑ everything recolours together when you :theme
```

## How the theme sync works

Helix has no hook that fires on `:theme`, so the colour change is detected the
only place it's observable — the colours Helix actually paints. A transparent
PTY wrapper (`hx_presence.py`) already runs Helix inside a virtual terminal
(`pyte`); `theme_sync.py` samples the dominant background/foreground of the
editor area and, when it changes, animates every surface to match:

| Surface | Driven by | Mechanism |
|---|---|---|
| Editor pane + frame | `theme_sync.py` (editor pane) | `zellij action set-pane-color` |
| kitty window / inter-pane gap | `theme_sync.py` | `kitty @ set-colors` over a socket |
| Bottom terminal pane | `theme_watch.py` (that pane) | shared `theme-state` file + `set-pane-color` |

Everything is best-effort: if a zellij/kitty call fails, the editor is never
disturbed.

## Requirements

- [Helix](https://helix-editor.com) (binary `hx` or `helix`)
- [zellij](https://zellij.dev) ≥ 0.44 (needs `action set-pane-color`)
- [kitty](https://sw.kovidgoyal.net/kitty/) (theme-sync target; remote control)
- [fish](https://fishshell.com) (the `hx` launcher is a fish function)
- Python 3 (for the wrapper; the installer makes a venv with `pyte`)
- A Nerd Font (default config uses *JetBrains Mono Nerd Font*)
- *Optional:* [starship](https://starship.rs) for the IDE prompt

## Install

```sh
git clone https://github.com/AlexZ671/helix-ide.git
cd helix-ide
./install.sh
```

The installer copies configs into `~/.config`, sets up the Python venv under
`~/.local/share/hx-presence`, and **backs up anything it overwrites** to
`<file>.bak-<timestamp>`. Then:

1. **Restart kitty** (so `allow_remote_control` / `listen_on` take effect — the
   gap won't recolour until you do).
2. Run `hx`.
3. Try `:theme onedark`, `:theme dark_plus`, `:theme catppuccin_mocha`, … and
   watch it fade.

## Discord presence (optional, off by default)

Presence is disabled until you set a `client_id` in
`~/.local/share/hx-presence/config.json`:

- **Vesktop / arRPC users:** any id works and icons load from URLs. The generic
  arRPC id `1045800378228281345` gives instant "now editing …" presence.
- **Branded as "Helix":** register an app at
  <https://discord.com/developers/applications> and paste its *Application ID*.
- Debug with `HX_PRESENCE_DEBUG=1` (writes `presence.log`).

## Layout / keys

- `Alt + ↑ / ↓` — move between editor and terminal panes
- `Alt + ← / →` — move between panes horizontally
- `Alt + +/-` — resize the focused pane
- `:q` in Helix — quit the whole IDE session

## Customising

- **Colours:** ships with the warm `beans` palette. Swap `config/helix/themes`,
  `config/zellij/config.kdl` (frame colours) and `config/kitty/theme.conf`, or
  point kitty's `include` at a generator (pywal / matugen / quickshell).
- **Animation speed:** `STEPS` and `DURATION` at the top of
  `hx-presence/theme_sync.py`.
- **Split ratio:** the `size="70%"` / `size="30%"` in
  `config/zellij/layouts/hx-ide.kdl`.

## Uninstall

Restore the `*.bak-<timestamp>` files the installer made, and remove
`~/.config/fish/functions/hx.fish` (so `hx` becomes the plain editor again) and
`~/.local/share/hx-presence`.

## License

[MIT](LICENSE) © AlexZ671

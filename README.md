# iterm-layout

Save and restore your iTerm2 windows: tabs, split panes, the folder each pane was in, and the Claude Code session running in it.

A crashed terminal, a reboot or one wrong `pkill` can close a dozen carefully arranged windows. `iterm-layout restore` brings them back as they were.

```
$ iterm-layout list
 1) 2026-11-06 20:17:53  5 windows, 12 panes, 5 claude sessions
   window 1: 1 pane(s) 1  api*
   window 3: 2 pane(s) V(1,1)  web, api*
```

## Install

```sh
brew install mpilukov/tap/iterm-layout
```

Or copy the single `iterm-layout` file anywhere on your `PATH`. It is one Python 3 script with no dependencies beyond the standard library.

Requirements: macOS, iTerm2, `python3` (ships with the Xcode Command Line Tools). The first run asks for permission to control iTerm2 (System Settings → Privacy & Security → Automation).

## Commands

| Command | What it does |
|---|---|
| `iterm-layout save` | Take a snapshot now (skipped when nothing changed since the last one) |
| `iterm-layout list [N]` | Show the last N snapshots (10 by default) |
| `iterm-layout show [N]` | Print what `restore N` would open, without opening anything |
| `iterm-layout restore [N]` | Recreate snapshot N from `list`; asks which one when N is omitted |
| `iterm-layout name N NAME` | Give snapshot N a name (`name N ""` removes it); alias `rename` |
| `iterm-layout delete N` | Delete snapshot N; asks first, `--yes` skips the question |
| `iterm-layout auto` | Snapshot at most once a minute and only inside iTerm2, for hooks |
| `iterm-layout --version` | Print the version |

N is a number from `list` or a snapshot name, so `iterm-layout restore work` works once a snapshot is named `work` (with several of the same name, the newest wins).

Snapshots are JSON files in `~/.config/iterm-layout/snapshots`. The last 200 unnamed snapshots are kept; named ones are never cleaned up, so name the layouts you want to keep.

## How it works

`save` asks iTerm2 (via AppleScript) for every window, tab and pane, then finds the working folder of each pane's shell. AppleScript does not expose pane geometry, so the split tree (side by side vs stacked, nested) is inferred from each pane's columns and rows and the window's aspect ratio.

`restore` opens new windows with the same bounds, splits them the same way and types `cd <folder>` into each pane.

## Claude Code

If a pane was running [Claude Code](https://claude.com/claude-code), the snapshot records its session id (from `~/.claude/sessions`) and the flags it was started with. `restore` then runs `cd <folder> && claude <flags> --resume <session id>` in that pane, so the conversation picks up where it was.

- A session that is already open in another pane is not started twice.
- Without the `claude` command on `PATH`, those panes reopen as a plain `cd <folder>`.

To snapshot automatically, call `iterm-layout auto` from Claude Code hooks (for example `SessionStart` and `Stop`, as async command hooks); it does nothing outside iTerm2 and at most once a minute.

## Use it from menuki

[menuki](https://github.com/MPilukov/menuki) ships a ready menu for it:

```sh
menuki examples iterm-layout
```

## License

MIT

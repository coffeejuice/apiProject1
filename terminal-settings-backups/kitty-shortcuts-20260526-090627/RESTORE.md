# Kitty Shortcut Backup

Source: /home/alextub/.config/kitty
Created: 20260526-090627

Included:
- .config/kitty/kitty.conf: active Kitty configuration with custom keyboard maps.
- .config/kitty/kitty-startup.session: startup session file.
- .config/kitty/kitty_search/: helper kitten referenced by the kitty_mod+/ shortcut, excluding its .git metadata.
- meta/active-map-lines.txt: all active `map` lines from kitty.conf.
- meta/relevant-shortcuts.txt: lines matching Ctrl+C, Ctrl+V, Ctrl+X, Alt+S, and kitty_mod+/ searches.

Restore on another PC:
1. Install Kitty.
2. Extract this archive.
3. Copy the extracted .config/kitty/ contents into ~/.config/kitty/.
4. Restart Kitty, or reload config from Kitty if desired.

Current active custom shortcuts found in kitty.conf include:
- map kitty_mod+/ launch --allow-remote-control kitty +kitten kitty_search/search.py @active-kitty-window-id
- map ctrl+c copy_to_clipboard
- map ctrl+shift+c send_key ctrl+c
- map ctrl+v paste_from_clipboard
- map ctrl+shift+v send_key ctrl+v
- map ctrl+x copy_or_noop
- map ctrl+shift+x send_key ctrl+x

I did not find an active `map alt+s ...` line in the current Kitty config; only a commented example for ctrl+alt+s appears in the default documentation comments.

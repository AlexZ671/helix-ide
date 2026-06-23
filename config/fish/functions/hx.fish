function hx --description 'Helix: IDE-режим в zellij (Discord presence сохраняется)'
    # Снаружи zellij и в интерактиве → открыть IDE-раскладку (Helix + терминал снизу).
    # Сам Helix запустится внутри панели уже через hx-presence (см. hx-ide.kdl).
    if status is-interactive; and test -z "$ZELLIJ"
        # Фон всего окна kitty → чёрный (#111111) на время IDE, чтобы зазор между
        # панелями не светился тёплым фоном quickshell.
        printf '\e]11;#111111\a'
        env HX_ARGS="$argv" zellij --layout hx-ide
        # Вернуть тёплую палитру quickshell после выхода из IDE.
        set -l seq ~/.local/state/quickshell/user/generated/terminal/sequences.txt
        if test -f $seq
            cat $seq
        else
            printf '\e]111\a'
        end
        return
    end

    # Иначе (уже внутри zellij, либо неинтерактивно) → Helix напрямую с Discord Rich Presence.
    set -l dir "$HOME/.local/share/hx-presence"
    # Найти настоящий бинарник Helix (минуя эту же функцию hx):
    # /usr/local/bin/hx → helix в PATH → бинарь hx в PATH (type -fp пропускает функции).
    set -l real /usr/local/bin/hx
    test -x "$real"; or set real (command -v helix)
    test -x "$real"; or set real (type -fp hx 2>/dev/null)[1]
    if test -x "$dir/venv/bin/python"
        "$dir/venv/bin/python" "$dir/hx_presence.py" "$real" $argv
    else
        "$real" $argv
    end
end

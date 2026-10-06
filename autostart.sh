#!/bin/sh
set -eu
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
case "${1:-enable}" in
    enable)
        if [ ! -f /usr/share/applications/monitorbar.desktop ]; then
            echo 'Installez d’abord MonitorBar avec ./install.sh.' >&2
            exit 1
        fi
        mkdir -p "$config_dir"
        cp /usr/share/applications/monitorbar.desktop "$config_dir/monitorbar.desktop"
        echo 'MonitorBar démarrera à la prochaine ouverture de session.'
        ;;
    disable)
        rm -f -- "$config_dir/monitorbar.desktop"
        echo 'Démarrage automatique désactivé.'
        ;;
    *) echo 'Utilisation : ./autostart.sh enable|disable' >&2; exit 2 ;;
esac

#!/bin/sh
# Installs the supplied package and resolves dependencies through Ubuntu's APT.
set -eu
if [ "$(uname -s)" != Linux ]; then
    echo 'Cet installateur est destiné à Ubuntu.' >&2
    exit 1
fi
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
package="$PWD/dist/monitorbar_1.0.0_all.deb"
if [ ! -f "$package" ]; then
    /usr/bin/python3 build_release.py
fi
sudo apt install "$package"
printf '\nInstallation terminée. Ouvrez MonitorBar dans Applications ou tapez monitorbar.\n'

#!/bin/sh
# Run ON the Kindle (over SSH) after copying device/ to /mnt/us/dash/: installs the upstart job
# so the dashboard starts at boot. Re-runnable. `sh install.sh remove` undoes it and brings the
# stock UI back.
set -e
if [ "$1" = "remove" ]; then
    mntroot rw; rm -f /etc/upstart/dash.conf; mntroot ro
    stop dash 2>/dev/null || true; start framework 2>/dev/null || true
    echo "dashboard removed; stock UI restarted"; exit 0
fi
mntroot rw
cp /mnt/us/dash/dash.conf /etc/upstart/dash.conf
mntroot ro
chmod +x /mnt/us/dash/dash.sh /mnt/us/dash/touch.sh /mnt/us/dash/button.sh
initctl reload-configuration 2>/dev/null || true
echo "installed /etc/upstart/dash.conf — 'start dash' now, or reboot"

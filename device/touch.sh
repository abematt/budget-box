#!/bin/sh
# Touch reader for the dashboard: turns swipes and taps on the Paperwhite's touchscreen into
# page changes. Started by dash.sh. Reads raw input_event structs (16 bytes on this 32-bit ARM:
# 8 bytes timestamp, u16 type, u16 code, s32 value) from the goodix touchscreen with hexdump,
# follows one finger from first contact to lift, and writes "next" or "prev" to $BASE/gesture,
# then breaks dash.sh's long poll so it redraws at once.
#   any tap or swipe -> next page (the pages cycle)
# ROTATE (from config) maps device axes to what the viewer sees: the panel is portrait
# 1072x1448; rotate=90 draws the image rotated counter-clockwise, so the viewer's x runs along
# the panel's y, decreasing.
BASE=/mnt/us/dash
. "$BASE/config"
DEV=$(grep -l goodix /sys/class/input/event*/device/name 2>/dev/null | head -1 | sed 's#/sys/class/input/\(event[0-9]*\)/.*#/dev/input/\1#')
DEV=${DEV:-/dev/input/event2}
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') touch: $*" >> "$BASE/dash.log"; }
log "reading $DEV (rotate ${ROTATE:-0})"

# hexdump buffers its output (4 KB), so a tap's few events would sit unseen until a long
# swipe pushed them through. Instead: keep the device open on fd 3, let dd return whatever
# the kernel has queued (one read, up to 4 KB), and hexdump that batch; a fresh hexdump per
# batch means its output reaches awk the moment the batch ends.
exec 3<"$DEV"
while dd bs=4096 count=1 <&3 2>/dev/null | hexdump -v -e '8/2 "%u " "\n"'; do :; done \
    | awk -v rot="${ROTATE:-0}" -v out="$BASE/gesture" -v W=1072 -v H=1448 -v debug="${TOUCH_DEBUG:-0}" -f "$BASE/touch.awk"
log "device read ended; touch reader stopping"

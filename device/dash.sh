#!/bin/sh
# budget-box display loop for the jailbroken Paperwhite 4. Installed at /mnt/us/dash/dash.sh,
# started at boot by /etc/upstart/dash.conf (see device/dash.conf), config in /mnt/us/dash/config.
#
# Sleep: button.sh handles the power button (sleep behind sleep.png, wake and redraw).
#
# Pages: /views lists them (shared budget, each person's own budget); a swipe or a tap
# (touch.sh) steps through them and breaks the long poll so the new page draws at once.
#
# Event-driven: fetch /screen.png (which carries X-Data-Version), paint it with eips, then
# hold a long-poll request on /wait?v=<version> that the server answers the moment the
# budget data changes, or after its heartbeat timeout. On failure, keep the last good image on screen with an
# "offline since" line, back off, and retry.
BASE=/mnt/us/dash
. "$BASE/config"                     # SERVER, TOKEN, ROTATE, HEARTBEAT, FULL_EVERY
LOG="$BASE/dash.log"
CUR="$BASE/dash.png"; NEW="$BASE/dash.new.png"; HDR="$BASE/headers.txt"
export TZ="${TZ:-CET-1CEST,M3.5.0,M10.5.0/3}"   # Europe/Madrid, for the log and the offline stamp
SERVER="${SERVER%/}"
URL="$SERVER/screen.png"; WAIT_URL="$SERVER/wait"; VIEWS_URL="$SERVER/views"
GESTURE="$BASE/gesture"
ASLEEP="$BASE/asleep"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; tail -c 200000 "$LOG" > "$LOG.t" 2>/dev/null && mv "$LOG.t" "$LOG"; }

battery() { cat /sys/class/power_supply/*/capacity 2>/dev/null | head -1; }
lan_ip()  { ifconfig wlan0 2>/dev/null | sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p' | head -1; }

wifi_up() {
    [ -n "$(lan_ip)" ] && return 0
    lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null
    i=0; while [ $i -lt 30 ]; do [ -n "$(lan_ip)" ] && return 0; sleep 2; i=$((i+1)); done
    return 1
}

take_over_screen() {
    # Our image, nothing else: no reader UI, no screensaver, no suspend while on power.
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null
    if initctl status framework 2>/dev/null | grep -q running; then
        stop framework >/dev/null 2>&1; log "stopped framework"
    fi
    # the status bar (clock, wifi, battery) is drawn by these two, not by the framework
    for svc in statusbar pillow; do
        initctl status $svc 2>/dev/null | grep -q running && stop $svc >/dev/null 2>&1 && log "stopped $svc"
    done
    eips -c >/dev/null 2>&1
}

# e-ink: a partial update only nudges the pixels that changed, so earlier screens ghost
# through; a full update (-f) flashes and drives every pixel, which clears them. Full when the
# whole screen changes (page turn, wake) and every FULL_EVERY redraws; partial otherwise.
draw()      { eips -g "$1" >/dev/null 2>&1; }
draw_full() { eips -f -g "$1" >/dev/null 2>&1; }
# eips text: row 0..~39 for the PW4 at the default console font; the bottom row is ours.
offline_line() { eips 2 39 "  offline since $1  (last image above)  " >/dev/null 2>&1; }

# the pages we cycle through (one name per line from the server; "budget" if unreachable)
VIEWS="budget"; VI=0
load_views() {
    v=$(curl -sf --max-time 20 -H "Authorization: Bearer $TOKEN" "$VIEWS_URL" | tr -d '\r' | grep .)
    [ -n "$v" ] && VIEWS="$v"
}
view_count() { echo "$VIEWS" | wc -l | tr -d ' '; }
view_name()  { echo "$VIEWS" | sed -n "$((VI + 1))p"; }
# a swipe/tap recorded by touch.sh: step the page index; 0 if there was one
take_gesture() {
    [ -f "$GESTURE" ] || return 1
    g=$(cat "$GESTURE"); rm -f "$GESTURE"
    n=$(view_count); [ "$n" -gt 1 ] || return 1
    case "$g" in
        next) VI=$(( (VI + 1) % n )) ;;
        prev) VI=$(( (VI + n - 1) % n )) ;;
        *) return 1 ;;
    esac
    log "$g → page $((VI + 1))/$n $(view_name)"
    return 0
}

# fetch -> 0 and sets VERSION from the response header; non-zero on any failure
fetch() {
    curl -sf --max-time 40 -o "$NEW" -D "$HDR" \
         -H "Authorization: Bearer $TOKEN" -H "X-Kindle-Ip: $(lan_ip)" -H "X-Kindle-Battery: $(battery)" \
         "$URL?w=1072&h=1448&rotate=${ROTATE:-0}&view=$(view_name)" && [ -s "$NEW" ] || return 1
    VERSION=$(tr -d '\r' < "$HDR" | sed -n 's/^[Xx]-[Dd]ata-[Vv]ersion: *//p' | tail -1)
    return 0
}

# block until the server reports a change (or its heartbeat); 0 = answered, 1 = connection failed
wait_change() {
    curl -sf --max-time $(( ${HEARTBEAT:-900} + 60 )) -H "Authorization: Bearer $TOKEN" \
         "$WAIT_URL?v=${VERSION:-0}&timeout=${HEARTBEAT:-900}" -o "$BASE/wait.json" || return 1
    grep -q '"changed": *true' "$BASE/wait.json" && log "change → redraw"
    return 0
}

take_over_screen
[ -f "$CUR" ] && draw "$CUR"
rm -f "$GESTURE"
pkill -f "$BASE/touch.sh" 2>/dev/null; pkill -f "$BASE/button.sh" 2>/dev/null
pkill -x hexdump 2>/dev/null; pkill -x dd 2>/dev/null
[ -x "$BASE/touch.sh" ] && { sh "$BASE/touch.sh" & }
[ -x "$BASE/button.sh" ] && { sh "$BASE/button.sh" & }
# asleep (button.sh): wait it out, then redraw from scratch; 0 if we slept
napped() {
    [ -f "$ASLEEP" ] || return 1
    while [ -f "$ASLEEP" ]; do sleep 1; done
    rm -f "$GESTURE"                            # taps made while asleep don't count
    # straight away: the last page we had, with "Updating…" over its "as of" line, until Wi-Fi
    # is back and the fresh image replaces it. The banner is placed for ROTATE=90 (landscape).
    if [ -f "$CUR" ]; then
        draw_full "$CUR"
        [ "${ROTATE:-0}" = 90 ] && [ -f "$BASE/updating.png" ] && eips -g "$BASE/updating.png" -x 992 -y 0 >/dev/null 2>&1
    fi
    backoff=15; return 0
}
wifi_up && load_views
n=0; since=""; backoff=15; VERSION=""; paged=0
while :; do
    if wifi_up && fetch; then
        mv "$NEW" "$CUR"; since=""; backoff=15
        n=$((n+1))
        # full update on a page turn and every FULL_EVERY redraws; otherwise a quiet partial one
        if [ $((n % ${FULL_EVERY:-6})) -eq 0 ] || [ $paged = 1 ]; then draw_full "$CUR"; else draw "$CUR"; fi
        paged=0
        wait_change && continue
        # the long poll ended early: a page turn or going to sleep breaks it on purpose,
        # anything else is a failure
        # (after a nap the last page was already drawn full, so the fresh one can be partial)
        if take_gesture; then paged=1; elif napped; then :; else sleep "$backoff"; fi
    else
        napped || { take_gesture && paged=1; }
        rm -f "$NEW"
        [ -z "$since" ] && since="$(date '+%H:%M')" && log "fetch failed; offline since $since"
        [ -f "$CUR" ] && draw "$CUR"
        offline_line "$since"
        sleep "$backoff"; [ "$backoff" -lt 300 ] && backoff=$((backoff * 2))
    fi
done

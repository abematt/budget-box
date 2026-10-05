#!/bin/sh
# Power-button watcher for the dashboard: a press shows the "Budget Box" screen and suspends
# the Kindle; the next press wakes it and the dashboard redraws. Started by dash.sh.
#
# Detecting the press: on this Paperwhite the button never shows up as an input event, and
# powerd ignores it while the stock UI is stopped. It does reach the kernel as an interrupt
# from the bd71827 power chip ("bd71827 2 ... bd71827-power" in /proc/interrupts), so we watch
# that counter. Plugging or unplugging the charger bumps the same counter; those are told
# apart by bd71827_ac/online changing at the same time.
#
# Sleeping: a real suspend (echo $SLEEP_STATE > /sys/power/state), Wi-Fi off first. The power chip is a
# wake source, and so is the SoC's RTC: a safety alarm every SAFETY seconds wakes the Kindle, and
# if the button wasn't what woke it (alarm, charger) it goes straight back to sleep. If a
# suspend ever fails outright we stay awake rather than spin.
# While asleep, $BASE/asleep exists; dash.sh pauses on it and redraws when it disappears.
BASE=/mnt/us/dash
. "$BASE/config"
ASLEEP="$BASE/asleep"
# Sleep state for /sys/power/state. "mem" (deep) saves the most, but on the PW4 a short press
# doesn't wake it: the power chip swallows the first press, so it takes two presses or a long
# hold. "standby" keeps interrupt handling alive and wakes on one press; "freeze" is lighter still.
STATE=${SLEEP_STATE:-standby}
RTC=/sys/class/rtc/rtc1
AC=/sys/class/power_supply/bd71827_ac/online
SAFETY=21600                                   # 6 h
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') button: $*" >> "$BASE/dash.log"; }
count() { awk '$3 == "bd71827" && $4 == "2" && $NF == "bd71827-power" { print $2 }' /proc/interrupts; }
alarms() { awk '/rtc alarm/ { print $2 }' /proc/interrupts; }
ac() { cat "$AC" 2>/dev/null; }
nap() { if [ -n "$US" ]; then usleep 300000; else sleep 1; fi; }
US=$(which usleep 2>/dev/null)

disarm() { echo 0 > "$RTC/wakealarm" 2>/dev/null; }
arm()    { disarm; echo $(( $(cat "$RTC/since_epoch") + SAFETY )) > "$RTC/wakealarm" 2>/dev/null; }

go_to_sleep() {
    touch "$ASLEEP"
    pkill -x curl 2>/dev/null                  # dash.sh's long poll / fetch: it pauses on $ASLEEP
    eips -f -g "$BASE/sleep.png" >/dev/null 2>&1   # full update: no ghost of the dashboard
    lipc-set-prop com.lab126.cmd wirelessEnable 0 2>/dev/null
    log "sleep ($STATE)"
    sleep 2
    while :; do
        b0=$(count); a0=$(alarms); c0=$(ac)
        arm; sync
        if ! echo "$STATE" > /sys/power/state 2>/dev/null; then
            log "suspend failed; staying awake"; break
        fi
        sleep 1
        b1=$(count); a1=$(alarms); c1=$(ac)
        if [ "$c1" != "$c0" ]; then log "charger $( [ "$c1" = 1 ] && echo plugged in || echo unplugged ) while asleep; back to sleep"; continue; fi
        if [ "$a1" != "$a0" ] && [ "$b1" = "$b0" ]; then log "safety alarm; back to sleep"; continue; fi
        break                                  # the button (or something we can't tell): wake
    done
    disarm
    lipc-set-prop com.lab126.cmd wirelessEnable 1 2>/dev/null
    # anything left open across the suspend is a dead TCP connection that could hang dash.sh
    # for up to --max-time (16 min); kill it so the loop sees $ASLEEP gone at once
    pkill -x curl 2>/dev/null
    rm -f "$ASLEEP"
    log "wake"
}

rm -f "$ASLEEP"; disarm
last=$(count); lastac=$(ac)
[ -n "$last" ] || { log "power-key interrupt not found; button watcher stopping"; exit 1; }
log "watching the power-key interrupt (count $last)"
while :; do
    nap
    c=$(count)
    [ "$c" = "$last" ] && continue
    sleep 1; last=$(count)                     # let the bounce settle, then re-baseline
    now_ac=$(ac)
    if [ "$now_ac" != "$lastac" ]; then
        lastac=$now_ac; log "charger $( [ "$now_ac" = 1 ] && echo plugged in || echo unplugged ); ignored"
        continue
    fi
    go_to_sleep
    sleep 1; last=$(count); lastac=$(ac)       # swallow the press that woke us
done

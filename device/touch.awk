# Gesture decoder for touch.sh (busybox awk). Input: one input_event per line as eight
# unsigned 16-bit words (hexdump -e '8/2 "%u " "\n"'): $5 type, $6 code, $7/$8 value lo/hi.
# Variables: rot (0/90/270), out (gesture file), W/H (portrait panel size).
function hms(t,   u) { u = (t + 7200) % 86400; return sprintf("%02d:%02d:%02d", int(u / 3600), int(u % 3600 / 60), u % 60) }  # Madrid, roughly
function s32(lo, hi) { return hi >= 32768 ? lo + hi * 65536 - 4294967296 : lo + hi * 65536 }
function viewer_x(x, y) { if (rot == 90) return H - y; if (rot == 270) return y; return x }
function viewer_y(x, y) { if (rot == 90) return x; if (rot == 270) return W - x; return y }
function viewer_w()     { return rot == 90 || rot == 270 ? H : W }
function emit(g,   cmd) {
    if ((getline junk < "/mnt/us/dash/asleep") >= 0) { close("/mnt/us/dash/asleep"); return }  # asleep: ignore
    printf "%s\n", g > out; close(out)
    # break dash.sh's long poll so the new page draws now (. not ?: the pattern is a regex)
    cmd = "pkill -f \"/wait.v=\" >/dev/null 2>&1"; system(cmd)
}
function lift() {
    # any touch, tap or swipe, steps to the next page (pages cycle, so one gesture is enough)
    if (debug) print hms($1 + $2 * 65536) " touch: lift have=" have " events=" nev " from " x0 "," y0 " to " x "," y " [" trace "]" >> dbg
    if (have) emit("next")
    down = 0; have = 0; nev = 0; trace = ""
}
BEGIN { dbg = "/mnt/us/dash/dash.log" }
{
    type = $5; code = $6; val = s32($7, $8)
    if (debug && type != 0) { nev++; if (nev <= 30) trace = trace " " type ":" code "=" val }
    if (type == 3 && code == 53) { x = val; if (!have) { x0 = x; hx = 1 } }
    if (type == 3 && code == 54) { y = val; if (!have) { y0 = y; hy = 1 } }
    if (!have && hx && hy) { have = 1; down = 1; hx = hy = 0 }
    if ((type == 3 && code == 57 && val == -1) || (type == 1 && code == 330 && val == 0)) lift()
}

#!/bin/sh
# The spinning coin on waking.png: cycles loading/NN.png in place while $BASE/loading.flag
# exists, using a fast two-level e-ink waveform so only the sprite updates and nothing flashes.
# Started by dash.sh on wake; it removes the flag when fresh data is drawn (or gives up).
# The frames and their framebuffer position (loading/pos) come from make_images.py.
BASE=/mnt/us/dash
FLAG="$BASE/loading.flag"
DIR="$BASE/loading"
read X Y < "$DIR/pos" || exit 0
# Fast waveform if this eips knows it, else a plain partial update (slower, still no flash).
WAVE=""
for w in a2 du; do
    if eips -g "$DIR/00.png" -x "$X" -y "$Y" -w "$w" >/dev/null 2>&1; then WAVE="-w $w"; break; fi
done
i=0; n=$(ls "$DIR"/*.png | wc -l); limit=$(( $(date +%s) + 120 ))
while [ -f "$FLAG" ] && [ "$(date +%s)" -lt "$limit" ]; do
    eips -g "$DIR/$(printf %02d $i).png" -x "$X" -y "$Y" $WAVE >/dev/null 2>&1
    i=$(( (i + 1) % n ))
    usleep 120000 2>/dev/null || sleep 1
done

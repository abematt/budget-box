#!/bin/sh
# The spinning coin on waking.png: cycles loading/NN.png in place while $BASE/loading.flag
# exists, using a fast two-level e-ink waveform so only the sprite updates and nothing flashes.
# Started by dash.sh on wake; it removes the flag when fresh data is drawn (or gives up).
# The frames and their framebuffer position (loading/pos) come from make_images.py.
BASE=/mnt/us/dash
FLAG="$BASE/loading.flag"
DIR="$BASE/loading"
read X Y < "$DIR/pos" || exit 0
# A2: the fastest two-level waveform (wave_mode 6 on the PW4). eips accepts any -w name without
# complaint, so there's nothing to probe; a gray-capable mode would be slower and flicker more.
WAVE="-w a2"
i=0; n=$(ls "$DIR"/*.png | wc -l); limit=$(( $(date +%s) + 120 ))
while [ -f "$FLAG" ] && [ "$(date +%s)" -lt "$limit" ]; do
    eips -g "$DIR/$(printf %02d $i).png" -x "$X" -y "$Y" $WAVE >/dev/null 2>&1
    i=$(( (i + 1) % n ))
    usleep 120000 2>/dev/null || sleep 1
done

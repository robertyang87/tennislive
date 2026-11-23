#!/bin/bash
# Re-render salt (c02160, c02400) and fuel (c03840) after layoutText-safe HUD fix.
# Does NOT touch McRae/proof segments. Assumes scene.js rebuilt and 8780 up.
set -u
EP=/workspace/tennislive/tools/vibetennis/episodes/vibetennis-banana-2026
cd "$EP"
LOG=$EP/log/render_overlap3.log
exec >>"$LOG" 2>&1
echo "==== render_overlap3 start $(date '+%F %T %Z') ===="
# backups already in /tmp/ep14_seg_bak_overlap2
for a in 02160 02400 03840 05280 05520 05760; do
  rm -f /tmp/ep14_seg/c$a.mp4 /tmp/ep14_seg/c$a.mp4.anchors.json
done
export NODE_PATH=/workspace/nodetools/node_modules
export STALL=${STALL:-600} MAXT=${MAXT:-5400} TRIES=${TRIES:-3}
export VT_PRESET=${VT_PRESET:-veryfast} VT_CRF=${VT_CRF:-14} VT_LANG=${VT_LANG:-zh} PORT=${PORT:-8780}
cd r3d
one(){ a=$1; b=$2; f=$(printf "seg/c%05d.mp4" $a)
  for try in $(seq 1 $TRIES); do
    [ -f "$f.anchors.json" ] && return 0; rm -f "$f"
    setsid env VT_LANG=$VT_LANG VT_PRESET=$VT_PRESET VT_CRF=$VT_CRF NODE_PATH=$NODE_PATH \
      node ../../../engine/cap.js $a $b $f 1920 1080 $PORT >> seg/r_$a.log 2>&1 & pid=$!
    last=0; lastchg=$(date +%s); start=$lastchg
    while kill -0 $pid 2>/dev/null; do sleep 20; now=$(date +%s)
      sz=$(stat -c %s "$f" 2>/dev/null || echo 0); [ "$sz" != "$last" ] && { last=$sz; lastchg=$now; }
      if [ $((now-lastchg)) -gt $STALL ] || [ $((now-start)) -gt $MAXT ]; then
        echo "段 $a 第 $try 次卡住（$((now-lastchg)) s 无进展），杀进程组 $pid 重试"
        kill -TERM -- -$pid 2>/dev/null; sleep 5; kill -KILL -- -$pid 2>/dev/null; break
      fi
    done; wait $pid 2>/dev/null
    [ -f "$f.anchors.json" ] && { echo "段 $a 完成（第 $try 次）"; return 0; }
    echo "段 $a 第 $try 次失败"; tail -20 seg/r_$a.log 2>/dev/null
  done; echo "段 $a 放弃"; return 1; }
export -f one
export STALL MAXT TRIES VT_PRESET VT_CRF VT_LANG NODE_PATH PORT
xargs -P ${K:-4} -L 1 bash -c 'one "$0" "$1"' < /tmp/ep14_overlap3_jobs.txt
ok=0
while read a b; do [ -f $(printf "seg/c%05d.mp4.anchors.json" $a) ] && ok=$((ok+1)); done < /tmp/ep14_overlap3_jobs.txt
echo "重叠段3 $ok / 6 完成 $(date '+%F %T %Z')"
[ "$ok" = 6 ]

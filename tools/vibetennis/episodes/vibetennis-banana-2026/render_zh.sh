#!/bin/bash
# 中文段看门狗渲染（沿用 EP13 en_patch/render_en2.sh）：每段独立进程组；
# 输出 STALL 秒不增长（默认 600）或单段超过 MAXT（默认 5400）就杀掉重试，最多 TRIES 次。
# 可续渲：.anchors.json 在就跳过。
cd "$(dirname "$0")"; E=$(pwd); K=${K:-4}; export NODE_PATH=/workspace/nodetools/node_modules
export STALL=${STALL:-600} MAXT=${MAXT:-5400} TRIES=${TRIES:-3}
export VT_PRESET=${VT_PRESET:-veryfast} VT_CRF=${VT_CRF:-14} VT_LANG=${VT_LANG:-zh}
PORT=${PORT:-8780}
bash ../../engine/serve.sh "$E" "$PORT" || exit 1
cd r3d; mkdir -p seg
one(){ a=$1; b=$2; f=$(printf "seg/c%05d.mp4" $a)
  for try in $(seq 1 $TRIES); do
    [ -f "$f.anchors.json" ] && return 0; rm -f "$f"
    setsid env VT_LANG=${VT_LANG:-zh} VT_PRESET=${VT_PRESET:-veryfast} VT_CRF=${VT_CRF:-14} NODE_PATH=/workspace/nodetools/node_modules \
      node ../../../engine/cap.js $a $b $f 1920 1080 ${PORT:-8780} >> seg/r_$a.log 2>&1 & pid=$!
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
export PORT STALL MAXT TRIES VT_PRESET VT_CRF VT_LANG NODE_PATH
xargs -P $K -L 1 bash -c 'one $0 $1' < ../jobs.txt
n=$(wc -l < ../jobs.txt); ok=0
while read a b; do [ -f $(printf "seg/c%05d.mp4.anchors.json" $a) ] && ok=$((ok+1)); done < ../jobs.txt
echo "中文段 $ok / $n 完成"
[ $ok = $n ]

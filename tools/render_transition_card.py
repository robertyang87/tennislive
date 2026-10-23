#!/usr/bin/env python3
"""Render any column's content-directed transition through the shared component."""
import argparse
import json
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parent)]
from tennislive.video.transition_cards import render_clip, export_hyperframes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text',required=True)
    parser.add_argument('--kicker',default='')
    parser.add_argument('--content',type=Path,help='已核实的转场信息关系 JSON')
    parser.add_argument('--seconds',type=float,required=True,help='完整配音窗口')
    parser.add_argument('--fps',default='25')
    parser.add_argument('--band',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--hyperframes',type=Path,help='同时导出同一场景的离线 HyperFrames 工程')
    args=parser.parse_args()
    if args.out.suffix.lower()!='.mp4':parser.error('--out 必须为 .mp4')
    content=json.loads(args.content.read_text()) if args.content else None
    render_clip(args.text,args.out,seconds=args.seconds,kicker=args.kicker,content=content,
                fps=args.fps,size=(1080,960) if args.band else (1080,1440))
    if args.hyperframes:
        export_hyperframes(args.text,args.hyperframes,seconds=args.seconds,kicker=args.kicker,content=content,fps=args.fps,size=(1080,960) if args.band else (1080,1440))
    print(args.out)


if __name__=='__main__':main()

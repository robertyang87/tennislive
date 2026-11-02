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
    parser.add_argument('--text')
    parser.add_argument('--kicker',default='')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--content',type=Path,help='已核实的转场信息关系 JSON')
    group.add_argument('--scene',type=Path,help='自由组合的故事组件 JSON 同一原生入口')
    parser.add_argument('--seconds',type=float,required=True,help='完整配音窗口')
    parser.add_argument('--fps',default='25')
    parser.add_argument('--band',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--hyperframes',type=Path,help='同时导出同一场景的离线 HyperFrames 工程')
    args=parser.parse_args()
    if args.out.suffix.lower()!='.mp4':parser.error('--out 必须为 .mp4')
    if not args.text and not args.scene:parser.error('需要 --text 或 --scene')
    content=({'scene':json.loads(args.scene.read_text())} if args.scene
             else json.loads(args.content.read_text()) if args.content else None)
    if args.hyperframes and content and 'scene' in content:
        parser.error('组合组件目前使用原生MP4导出 HyperFrames桥接尚未验收')
    title=args.text or '故事转场'
    render_clip(title,args.out,seconds=args.seconds,kicker=args.kicker,content=content,
                fps=args.fps,size=(1080,960) if args.band else (1080,1440))
    if args.hyperframes:
        export_hyperframes(title,args.hyperframes,seconds=args.seconds,kicker=args.kicker,content=content,fps=args.fps,size=(1080,960) if args.band else (1080,1440))
    print(args.out)


if __name__=='__main__':main()

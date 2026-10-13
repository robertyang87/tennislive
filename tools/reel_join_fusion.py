"""Keep the native audio/video clock, and join full-size video at its final encode.

The tiny H.264 clock is an intermediate only. Its PTS, AAC join, and the existing
mixer's video-copy/shortest contract are unchanged. It is never published.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess


@dataclass(frozen=True)
class FusionPlan:
    video_graph: str
    audio_graph: str
    parts: int

    def clock_graph(self) -> str:
        video = self.video_graph
        for index in range(self.parts):
            video = video.replace(f'[{index}:v]', f'[fusion_clock_{index}]')
        scales = ';'.join(f'[{index}:v]scale=2:2[fusion_clock_{index}]'
                          for index in range(self.parts))
        return scales + ';' + video + ';' + self.audio_graph

    def final_graph(self, native_final: str) -> str:
        """Replace only native source labels; mixed audio follows the parts."""
        count = native_final.count('[0:v]')
        if not count or not native_final.endswith('[out]'):
            raise ValueError('Native final graph has no supported joined-video output')
        if '[fusion_' in native_final:
            raise ValueError('Native final graph collides with fusion labels')
        labels = [f'[fusion_canvas_{index}]' for index in range(count)]
        cursor = iter(labels)

        def input_label(match):
            index = int(match.group(1))
            if index == 0:
                return next(cursor)
            if index == 1:
                raise ValueError('Native final graph consumes the mixed-audio video track')
            return f'[{index + self.parts - 1}:v]'

        graph = re.sub(r'\[(\d+):v\]', input_label, native_final)
        bridge = 'format=yuv420p:color_ranges=tv'
        bridge += f',split={count}' if count > 1 else ',null'
        # Use a real format/range conversion at the removed encoder boundary.
        # Relabeling full-range pixels with setparams changes the image.
        return (self.video_graph.replace('[vout]', '[fusion_joined]')
                + ';[fusion_joined]' + bridge + ''.join(labels) + ';' + graph)


def plan(native_graph: str, parts: int) -> tuple[FusionPlan | None, str]:
    """Preselect legacy for unrecognized native graphs before any join encode."""
    if not isinstance(parts, int) or parts < 1:
        return None, 'invalid part count'
    if parts == 1:
        if native_graph != '[0:v]null[vout];[0:a]anull[aout]':
            return None, 'unrecognized one-part dissolve graph'
        return FusionPlan('[0:v]null[vout]', '[0:a]anull[aout]', parts), ''
    chains = native_graph.split(';')
    videos, audios = [], []
    for chain in chains:
        if 'xfade=' in chain:
            if not re.fullmatch(
                    r'\[(?:0:v|vx\d+)\]\[\d+:v\]xfade=transition=fade:'
                    r'duration=[0-9.]+:offset=[0-9.]+\[(?:vout|vx\d+)\]', chain):
                return None, 'unrecognized video dissolve operation'
            videos.append(chain)
        elif re.fullmatch(r'\[\d+:a\]apad=whole_len=\d+,atrim=end_sample=\d+\[ap\d+\]', chain):
            audios.append(chain)
        elif re.fullmatch(r'\[(?:ap0|ax\d+)\]\[ap\d+\]acrossfade=d=[0-9.]+:'
                          r'c1=tri:c2=tri\[(?:aout|ax\d+)\]', chain):
            audios.append(chain)
        else:
            return None, 'unrecognized native dissolve operation'
    if (len(videos) != parts - 1 or len(audios) != 2 * parts - 1
            or not videos[-1].endswith('[vout]') or not audios[-1].endswith('[aout]')
            or set(re.findall(r'\[(\d+):v\]', ';'.join(videos))) != set(map(str, range(parts)))
            or set(re.findall(r'\[(\d+):a\]', ';'.join(audios))) != set(map(str, range(parts)))):
        return None, 'native dissolve topology does not match the parts'
    return FusionPlan(';'.join(videos), ';'.join(audios), parts), ''


def video_clock(path: Path) -> tuple[Fraction, tuple[tuple[Fraction, Fraction], ...]]:
    """Read real packet PTS without decoding a second full-size movie.

    DTS order differs with medium's B frames. PTS order is the displayed clock.
    Payload hashes and dimensions intentionally differ for the 2x2 clock.
    """
    proc = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
        '-show_entries', 'stream=time_base,r_frame_rate:packet=pts,duration',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    if proc.stderr.strip():
        raise ValueError('Video clock probe reported an error')
    data = json.loads(proc.stdout)
    stream, = data['streams']
    base = Fraction(stream['time_base'])
    rate = Fraction(stream['r_frame_rate'])
    packets = tuple(sorted((int(row['pts']) * base, int(row['duration']) * base)
                           for row in data['packets']))
    if not packets or any(duration <= 0 for _, duration in packets):
        raise ValueError('Missing or invalid video clock packets')
    if any(packets[i][0] >= packets[i + 1][0] for i in range(len(packets) - 1)):
        raise ValueError('Video clock has repeated presentation timestamps')
    return rate, packets


def require_matching_frame_clock(clock: Path, final: Path) -> None:
    if video_clock(clock) != video_clock(final):
        raise ValueError('Fused final video differs from the native joined frame clock')

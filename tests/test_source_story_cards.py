import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tennislive.video import explainer as E


def test_native_evidence_insert_keeps_its_picture_sound_and_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(E, 'VIDEO_W', 108)
    slides = []
    audios = []
    for name, color, frequency in [('first', 'red', 220), ('second', 'blue', 880)]:
        slide = tmp_path / f'{name}.png'
        Image.new('RGB', (108, 144), color).save(slide)
        slides.append(slide)
        audio = tmp_path / f'{name}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'sine=frequency={frequency}:sample_rate=24000:duration=1',
                        str(audio)], check=True)
        audios.append(audio)
    insert = tmp_path / 'native.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'color=green:s=108x144:r=30:d=1', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=24000:duration=1',
                    '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(insert)], check=True)
    film = E.assemble_explainer_video(slides, audios, tmp_path/'film.mp4',
                                     inserts={1: insert}, canvas_h=144,
                                     full_bleed=True, lead_silence=0, tail_silence=0)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
                       '-show_streams', '-of', 'json', str(film)]))['streams']
    assert abs(float(probe[0]['duration']) - 3) < .1
    assert abs(float(probe[0]['duration']) - float(probe[1]['duration'])) < .1
    for at, expected, frequency in [(.4, 0, 220), (1.4, 1, 440), (2.4, 2, 880)]:
        rgb = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(at),
            '-i', str(film), '-frames:v', '1', '-vf', 'scale=1:1',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        assert np.argmax(list(rgb)) == expected
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(at),
            '-t', '0.2', '-i', str(film), '-vn', '-ar', '16000',
            '-f', 'f32le', '-'])
        signal = np.frombuffer(raw, dtype=np.float32)
        peak = np.fft.rfftfreq(len(signal), 1/16000)[np.argmax(abs(np.fft.rfft(signal)))]
        assert abs(peak - frequency) < 10


def test_source_layout_never_substitutes_a_missing_original():
    segment = E.ExplainerSegment('cause', 'case', 'Title', 'Speech',
                                 visual={'layout': 'case', 'photo': 'missing-proof.jpg',
                                         'source': 'Actual source'})
    with pytest.raises(FileNotFoundError):
        E._slide_html(1, segment)

"""SLAM signature, board disappearance, and measured variable width."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from rna_scoreboard import board_edge
from atp_scoreboard import stabilize
from reel_facts import broadcast_profile


def board(width=462):
    a = np.full((110, 777, 3), (80, 155, 65), dtype=np.uint8)
    a[:, :88] = (87, 247, 202)
    a[:, 88:width] = (4, 27, 74)
    a[[0, 54, 109], :width] = 240
    a[:, width-2:width] = 240
    return a


def test_actual_edges_and_variable_width():
    assert board_edge(board()) == 462
    assert board_edge(board(520), cap=462) == 520


def test_absence_and_lookalike_background():
    assert board_edge(np.full((110, 777, 3), (4, 27, 74), dtype=np.uint8)) is None
    assert board_edge(np.full((110, 777, 3), (87, 247, 202), dtype=np.uint8)) is None
    assert board_edge(np.full((110, 777, 3), (80, 155, 65), dtype=np.uint8)) is None
    assert stabilize([(462, None), (None, None), (462, None)])[1] == (None, None)


def test_profile_uses_event_signature():
    assert broadcast_profile("纳达尔学院 十周年") == "rna-slam"


def test_probe_uses_same_profile_and_preserves_absence():
    import probe_board as pb
    assert pb.CALIBRATED['rna-slam'] == ((183, 890, 645, 1000),)
    assert pb.band_width('rna-slam', (183, 890, 645, 1000), 1920) == 777
    scans = pb.scan_frames([board(), np.full_like(board(), (80, 155, 65))],
                          [(('rna-slam',), (183, 890, 645, 1000))], 1920, (183, 890))
    result = scans[0]['profiles']['rna-slam']
    assert result['present'] == 1
    assert result['runs'] == [[1, 645, 645], [1, None, None]]


def test_white_border_stops_navy_background_bleeding():
    a = board()
    a[:, 462:] = (4, 27, 74)
    assert board_edge(a) == 462
    a[:, 460:462] = (4, 27, 74)
    assert board_edge(a) is None

"""Regression: official 23/40 first-serve points is 58%, not float-rounded 57%."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import render_stat_card as sc

def test_official_stat_percentages_round_half_up():
    a={"won":23,"total":40}
    b={"won":5,"total":8}
    av,af,bv,bf,lead=sc._stat_row("pct",a,b,"won","total")
    assert (av,af,bv,bf)==("58%","23/40","63%","5/8")
    assert lead=="b"

def test_zero_denominator_remains_zero():
    assert sc._stat_row("pct",{"w":0,"n":0},{"w":1,"n":3},"w","n")[:4]==("0%","0/0","33%","1/3")

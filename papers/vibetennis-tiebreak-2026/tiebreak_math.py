"""EP12 抢七轮发：片中三个算出来的数（python3 tiebreak_math.py 复现）。

模型：每分独立，发球方赢这一分的概率 p 固定（两人一样强时都等于 p）。这是 Brams & Ismail 2018 第 5 节同一个模型。
  ① 抢七（先到 7 分且净胜 2 分）：一人一分（ABAB）和 1-2-2-2（ABBA）两种顺序，先发的人赢的概率
  ② 去掉净胜两分、先到 7 分就赢：两种顺序都一样偏向先发的人（最多 13 分，先发的人发 7 个）
  ③ 前 12 分里两人各发几个；每到双数分两人发过的球数；12 分里换几次发球
"""
from functools import lru_cache

def server(order, k):  # k：第几分（从 0 起）
    if order == "ABAB": return "AB"[k % 2]
    if order == "ABBA": return "A" if ((k + 1) // 2) % 2 == 0 else "B"   # 甲｜乙乙｜甲甲｜乙乙……
    if order == "TM":   return "AB"[bin(k).count("1") % 2]                 # Thue–Morse

def p_first(order, pa, pb, win_by_two=True, target=7):
    @lru_cache(None)
    def f(a, b):
        if win_by_two:
            if a >= target and a - b >= 2: return 1.0
            if b >= target and b - a >= 2: return 0.0
            if a == b and a > target + 40: return 0.5
        else:
            if a == target: return 1.0
            if b == target: return 0.0
        p = pa if server(order, a + b) == "A" else 1 - pb
        return p * f(a + 1, b) + (1 - p) * f(a, b + 1)
    return f(0, 0)

if __name__ == "__main__":
    for o in ("ABAB", "ABBA", "TM"): print(o, "".join(server(o, k) for k in range(16)))
    p = 0.65
    for o in ("ABAB", "ABBA"):
        print(f"① {o} 抢七 先发者胜率 p={p}: {p_first(o, p, p):.4f}")
        print(f"② {o} 先到7分无净胜 先发者胜率: {p_first(o, p, p, win_by_two=False):.4f}")
    for o in ("ABAB", "ABBA"):
        s = [server(o, k) for k in range(12)]
        diff, d = [], 0
        for c in s: d += 1 if c == "A" else -1; diff.append(d)
        print(f"③ {o} 前12分 甲发{s.count('A')} 乙发{s.count('B')}；累计差 {diff}；换发球 {sum(s[i] != s[i+1] for i in range(11))} 次")
    for pa, pb in ((0.7, 0.6), (0.6, 0.65)):   # 两人不一样强：两种顺序仍然完全相同
        print("不等强", pa, pb, [round(p_first(o, pa, pb), 6) for o in ("ABAB", "ABBA")])

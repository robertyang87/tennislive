#!/usr/bin/env python3
"""封面帧和画面裁切的**认人 ＋ 睁眼**：这张脸是不是那个人、眼睛是不是睁着。

## 来路（账号所有者 2026-09-27 在多选题里选的「两个都加」：O2 认人 ＋ O3 睁眼）

原来那道本地封面闸（`audit_interview_cover.py`，OpenCV Haar）只证明「照片里有一张
够大、够正、够清楚的脸，Haar 数得出两只眼」——**不认人，也分不出眼睛是睁着还是
垂着**。它放行、推出去之后才被人眼拦下的：

| 事件 | 放行的是什么 | 提交 |
|---|---|---|
| tien-cobolli 封面 97.0 | 镜头切到了**阿加西**，闸不查是谁（推送之后） | 9ae8918f |
| federer 入选致辞 | 家属席，不是本人（推送之后） | 13a2734c |
| sabalenka | 审到的脸是教练席 | 3f7d68d1 |
| asian-games / hsieh-chan / osaka-iverson / comeback | 选错人、脸落进裁切 | c701f271 76c42ef5 2566185d 2e336f49 a15954fd |
| bu-jodar 发布会 264.4 | Haar 数到 2 只眼、脸高 0.267——**他低着头、眼睛朝下** | 47eed1de |
| ruud-cerundolo 发布会 245.0 | 低头闭眼（推送之后） | 9ae8918f / 063d2de7 |

`identify_player_frame.py` 早就证明过人脸向量分得清（2026-08-07 26/26），它的
docstring 把「接不接进流程」留给了账号所有者——**这一次他批了**。

## 为什么不 `pip install insightface`——量出来的

2026-09-27 在一次性 venv 里实装了一遍 `insightface`（2.0，PyPI 现版本）：

    pip install onnxruntime           2.7 s   （rembg[cpu] 本来就带它）
    pip install insightface          11.6 s   外加 scipy / scikit-image / onnx …，venv 524 MB
    ⚠️ 它的依赖写的是 `opencv-python`（**不是 headless**），装上来的是 **5.0.0.93**

最后一行是否决项：`cv2` 被换成 5.x，**`cv2.CascadeClassifier` 没了**——而
`audit_interview_cover.py` 的 Haar 闸就靠它。`pyproject` 那句「opencv 钉在 `<5`，
5.x 里 CascadeClassifier 没了，红得和没装一模一样」这次是被一个依赖**顺手**
踩上的。所以这里只用 **insightface 的模型文件**（buffalo_s 里的三个 onnx），
推理走 `onnxruntime`，前后处理（SCRFD 解码、ArcFace 对齐、106 点裁切）照抄
insightface 的实现写在本文件里——**一个新依赖族（onnxruntime ＋ 这三份权重）**。
和 insightface 包本身的输出逐数对过：见 `tests/test_face_checks.py` 的注释。

## 用的是哪三个模型（buffalo_s，v0.7 release）

| 文件 | 干什么 | 大小 |
|---|---|---|
| `det_500m.onnx` | SCRFD 人脸框 ＋ 5 点 | 2.5 MB |
| `w600k_mbf.onnx` | ArcFace 512 维向量（`identify_player_frame` 用的同一个） | 13.6 MB |
| `2d106det.onnx` | 106 点轮廓——眼睑上下沿，算睁眼程度 | 5.0 MB |

buffalo_s 包里还有一个 143 MB 的 `1k3d68.onnx`，**用不上、不解压、不进缓存**。

## 判据

- **认人**：拿这张脸和官方头像（`assets/players/headshots/`，已发 spec 认过的那张）
  比余弦相似度。和「应该是的那个人」够像 → `match`；和每一个候选都不像 → `mismatch`；
  中间地带、脸太小、没头像 → `unknown`（**不硬判**，照 `identify_player_frame`
  「拿不准就说拿不准」那条）。门槛是拿仓库里真实的头像和封面量出来的，见
  `MATCH_SIM` / `MISMATCH_SIM` 的注释
- **睁眼**：106 点里眼睑上下沿的平均开口 ÷ 眼角距离（眼睛纵横比）。阈值见
  `EYE_CLOSED_EAR` / `EYE_OPEN_EAR`
- **模型加载不了就大声降级**：返回 `status: unavailable` ＋ 原因，调用方把它写进
  产物（`render.json` / 封面凭证）并打 ⚠️——**不许悄悄当成通过**，也不拖垮出片
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 模型

#: 模型包与版本。**缓存键跟着这个字符串走**（工作流 `actions/cache` 的 key 读它），
#: 换权重就改这里，缓存自然失效。
MODEL_PACK = "buffalo_s"
MODEL_RELEASE = "v0.7"
MODEL_VERSION = f"{MODEL_PACK}-{MODEL_RELEASE}"
MODEL_URL = ("https://github.com/deepinsight/insightface/releases/download/"
             f"{MODEL_RELEASE}/{MODEL_PACK}.zip")
#: 只要这三个；sha256 钉死——下错一个字节就当没下（下错的权重算出来的数照样像数）。
MODEL_FILES = {
    "det_500m.onnx": "5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a",
    "w600k_mbf.onnx": "9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f",
    "2d106det.onnx": "f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf",
}
#: 工作流 `actions/cache` 的键：**按内容定址**——版本号 ＋ 三个权重 sha256 的摘要。
#: 换权重（哪怕版本号忘了改）键就跟着变，旧目录不会被当成新的命中。工作流里写的是
#: 字面值，`test_人脸模型缓存键跟着模型版本走` 逼着它和这里逐字一致。
#: ⚠️ 键按内容算还不够：`fetch` 下到一半失败会留下半截目录，所以存缓存那一步
#: **只在 fetch 成功之后跑**（`actions/cache/save` 挂在 fetch 的 `ok` 输出上），
#: 半截目录永远不会被钉进一个不可变的键里。
CACHE_KEY = "face-models-{}-{}".format(
    MODEL_VERSION,
    hashlib.sha256("".join(f"{n}:{d}\n" for n, d in sorted(MODEL_FILES.items()))
                   .encode()).hexdigest()[:12])

# ---------------------------------------------------------------- 判据

#: 认人：和「应该是的那个人」的官方头像余弦相似度 ≥ 这个数 → match。
#:
#: 两组数都是 2026-09-27 量的，不是拍的：
#:
#: - **不同的人**（`python tools/face_checks.py calibrate`）：仓库 171 张能读的官方
#:   头像两两比（去掉大小写两份的同一张，14529 对），99.9 分位 0.308、99 分位 0.227、
#:   97 分位 0.182；最像的是塞伦多洛兄弟 0.45、佩古拉／凯斯 0.36、大小威 0.35
#: - **同一个人**（仓库历史里 85 张真发过／渲过的封面和封面帧，对照本场 spec 里
#:   认过的头像）：0.217~0.925，中位 0.46；16 张低于 0.34——打开看了最低的 5 张，
#:   全是侧脸／怒吼／运动模糊——判 unknown（只报不拦），**没有一张落到 `MISMATCH_SIM` 以下**
#:
#: 0.34 让「不同的人被认成是他」压在万分之四（14529 对里 6 对）；代价是一部分真的是他的侧脸
#: 说「拿不准」——照 `identify_player_frame` 那条：宁可承认模糊，不输出赌的答案。
MATCH_SIM = 0.34
#: 和**每一个**候选都低于这个数 → mismatch（这张脸不是这场球里的任何一个人）。
#: 阿加西那帧对勒纳·钱是 −0.004；同一个人 85 张里最低 0.217（中岛布兰登的侧脸）。
#: 不同的人 93.6% 落在 0.15 以下（拦得住）；同一个人 0 张落在它以下。0.15 留了
#: 0.067 的余量——**这一档是硬拦**，误拦一张对的封面比漏掉一张错的贵（错的还有
#: 人眼和后面的闸），所以门槛往「宁可放过」那边靠。
MISMATCH_SIM = 0.15

#: 睁眼：眼睑平均开口 ÷ 眼角距离（EAR）。
#: 量出来的（同一批 104 张量得到眼睛的脸）：鲁德发布会 245.0（低头垂眼、推送后被换掉）
#: 0.097；郑钦文低头那张官方图 0.147；其余睁眼的 0.16~0.65。
EYE_CLOSED_EAR = 0.12
#: 0.12~0.16 是「半睁／往下看」，判 downcast，和闭眼一样不许上封面——bu-jodar 264.4
#: 那种「Haar 数得到两只眼、人其实低着头眼睛朝下」要拦的就是这一档（那一帧的
#: poster 没进仓库，没量到它的数；郑钦文低头那张 0.147 落在这一档）。
#: ⚠️ **不是 0.18**：第一版写 0.18，同一批里阿尔卡拉斯**大笑眯眼**那张（0.171）和
#: 胡佳咬牙那张（0.164）被判成垂眼——情绪外露正是封面要的（「情绪对不对题」那条），
#: 拿睁眼闸把笑脸拦掉是误伤。
EYE_OPEN_EAR = 0.16

#: 脸太小就不判（ArcFace 输入 112×112，106 点输入 192×192——比这小一大截的脸，
#: 放大上去的是马赛克，算出来的数不代表人）。单位：原图像素，取框高。
MIN_ID_FACE_PX = 56
MIN_EYE_FACE_PX = 72

DET_SIZE = 640
DET_THRESH = 0.5
NMS_THRESH = 0.4

# 106 点里两只眼：眼角一对，上下眼睑各三点一一对应（上 i ↔ 下 i）。
# 序号是拿参考实现在鲁德正脸上逐点画出来认的，不是凭记忆（草图见
# tests/test_face_checks.py 的注释）。
_EYES = (
    {"corners": (35, 39), "upper": (41, 40, 42), "lower": (36, 33, 37)},
    {"corners": (89, 93), "upper": (95, 94, 96), "lower": (90, 87, 91)},
)

# ArcFace 对齐模板（insightface.utils.face_align.arcface_dst，112×112）
_ARCFACE_DST = (
    (38.2946, 51.6963), (73.5318, 51.5014), (56.0252, 71.7366),
    (41.5493, 92.3655), (70.7299, 92.2041),
)


class ModelUnavailable(RuntimeError):
    """模型加载不了：没装 onnxruntime / 权重不在 / 下载被关 / 校验不过。

    调用方**必须**把它记进产物并出声，不许吞成通过。"""


def model_dir() -> Path:
    """权重落在哪儿。工作流的 `actions/cache` 缓存的就是这个目录。"""
    env = os.environ.get("TENNISLIVE_FACE_MODELS", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "tennislive" / "face-models" / MODEL_VERSION


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def models_ready(directory: Path | None = None) -> list[str]:
    """缺哪几个（空列表＝齐了且校验通过）。"""
    directory = directory or model_dir()
    bad = []
    for name, digest in MODEL_FILES.items():
        path = directory / name
        if not path.is_file() or _sha256(path) != digest:
            bad.append(name)
    return bad


def onnxruntime_importable() -> bool:
    """装没装 onnxruntime（不 import，只找模块）。"""
    import importlib.util  # noqa: PLC0415

    return importlib.util.find_spec("onnxruntime") is not None


def fetch_models(directory: Path | None = None, *, url: str = MODEL_URL) -> Path:
    """把三个 onnx 下好、校验好。已经齐了就一个字节都不下。

    `TENNISLIVE_FACE_MODEL_FETCH=0` 时不许联网（单元测试 autouse 这么设），
    缺了就是 `ModelUnavailable`——和 `TENNISLIVE_HEADSHOT_FETCH` 同一个形状。
    """
    directory = directory or model_dir()
    missing = models_ready(directory)
    if not missing:
        return directory
    if not onnxruntime_importable():
        # **先问推理引擎在不在，再下 127 MB。** 没装 onnxruntime 时下好的权重也
        # 一个字节都用不上——那一趟下载纯属白等（评审 2026-09-27 nit 6）
        raise ModelUnavailable(
            "没装 onnxruntime——装 extra：pip install -e \".[faces]\"（没下模型：装不上引擎，"
            "下了也用不了）")
    if os.environ.get("TENNISLIVE_FACE_MODEL_FETCH", "1") == "0":
        raise ModelUnavailable(
            f"人脸模型不在 {directory}（缺 {', '.join(missing)}），"
            "而 TENNISLIVE_FACE_MODEL_FETCH=0 不许现下。"
            "先跑一次 `python tools/face_checks.py fetch`")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:   # noqa: S310
            blob = resp.read()
    except Exception as exc:                                     # noqa: BLE001
        raise ModelUnavailable(f"人脸模型下载失败：{type(exc).__name__}: {exc}") from exc
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise ModelUnavailable(f"人脸模型包不是 zip（{len(blob)} 字节）") from exc
    names = {Path(n).name: n for n in archive.namelist()}
    for name, digest in MODEL_FILES.items():
        if name not in names:
            raise ModelUnavailable(f"模型包 {url} 里没有 {name}")
        data = archive.read(names[name])
        got = hashlib.sha256(data).hexdigest()
        if got != digest:
            raise ModelUnavailable(f"{name} 校验不过：{got[:12]}… ≠ {digest[:12]}…")
        # 先写临时文件再改名：下到一半断掉不会留一个「在，但是半截」的权重
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
            tmp.write(data)
        os.replace(tmp.name, directory / name)
    return directory


# ---------------------------------------------------------------- 推理

@dataclass
class Face:
    """一张脸。坐标都是**传进来那张图**的像素。"""

    bbox: tuple[float, float, float, float]
    score: float
    kps: object                      # (5, 2) float32
    embedding: object | None = None  # (512,) 归一化
    landmarks: object | None = None  # (106, 2)
    extra: dict = field(default_factory=dict)

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return float((self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1]))

    def box(self) -> list[int]:
        return [int(round(v)) for v in self.bbox]


class FaceModel:
    """三个 onnx 各一个 session。**进程里只建一次**（`load()` 缓存）。"""

    def __init__(self, directory: Path):
        try:
            import onnxruntime as ort  # noqa: PLC0415
        except ImportError as exc:
            raise ModelUnavailable(
                "没装 onnxruntime——装 extra：pip install -e \".[faces]\"") from exc
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # **两个线程就够**：一帧 0.1~0.3 秒，瓶颈不在这儿；而分段那道查验和 x264
        # 同时跑（见 `reel_face_gate.start_segment_checks`），线程开满只会去抢编码的核。
        opts.intra_op_num_threads = max(1, int(os.environ.get("TENNISLIVE_FACE_THREADS", "2")))
        opts.inter_op_num_threads = 1
        providers = ["CPUExecutionProvider"]

        def _session(name: str):
            return ort.InferenceSession(str(directory / name), sess_options=opts,
                                        providers=providers)

        try:
            self.det = _session("det_500m.onnx")
            self.rec = _session("w600k_mbf.onnx")
            self.lmk = _session("2d106det.onnx")
        except Exception as exc:                                  # noqa: BLE001
            raise ModelUnavailable(f"onnx 加载失败：{type(exc).__name__}: {exc}") from exc
        self.det_in = self.det.get_inputs()[0].name
        self.rec_in = self.rec.get_inputs()[0].name
        self.lmk_in = self.lmk.get_inputs()[0].name
        self._centers: dict = {}

    # -- 检测：SCRFD（insightface.model_zoo.scrfd.SCRFD.detect 的照抄）
    def detect(self, img, *, thresh: float = DET_THRESH) -> list[Face]:
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        h, w = img.shape[:2]
        if h / w > 1.0:
            new_h, new_w = DET_SIZE, int(DET_SIZE / (h / w))
        else:
            new_w, new_h = DET_SIZE, int(DET_SIZE * (h / w))
        scale = new_h / h
        canvas = np.zeros((DET_SIZE, DET_SIZE, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = cv2.resize(img, (new_w, new_h))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128.0, (DET_SIZE, DET_SIZE),
                                     (127.5, 127.5, 127.5), swapRB=True)
        outs = self.det.run(None, {self.det_in: blob})
        scores_l, boxes_l, kps_l = [], [], []
        for idx, stride in enumerate((8, 16, 32)):
            scores = outs[idx]
            boxes = outs[idx + 3] * stride
            kps = outs[idx + 6] * stride
            gh = gw = DET_SIZE // stride
            key = (gh, gw, stride)
            centers = self._centers.get(key)
            if centers is None:
                centers = np.stack(np.mgrid[:gh, :gw][::-1], axis=-1).astype(np.float32)
                centers = (centers * stride).reshape(-1, 2)
                centers = np.stack([centers] * 2, axis=1).reshape(-1, 2)
                self._centers[key] = centers
            pos = np.where(scores >= thresh)[0]
            x1 = centers[:, 0] - boxes[:, 0]
            y1 = centers[:, 1] - boxes[:, 1]
            x2 = centers[:, 0] + boxes[:, 2]
            y2 = centers[:, 1] + boxes[:, 3]
            bb = np.stack([x1, y1, x2, y2], axis=-1)
            pts = np.stack([centers[:, i % 2] + kps[:, i] for i in range(10)],
                           axis=-1).reshape(-1, 5, 2)
            scores_l.append(scores[pos])
            boxes_l.append(bb[pos])
            kps_l.append(pts[pos])
        scores = np.vstack(scores_l).ravel()
        if scores.size == 0:
            return []
        order = scores.argsort()[::-1]
        boxes = np.vstack(boxes_l)[order] / scale
        kpss = np.vstack(kps_l)[order] / scale
        scores = scores[order]
        keep = _nms(np.hstack([boxes, scores[:, None]]), NMS_THRESH)
        return [Face(bbox=tuple(float(v) for v in boxes[i]), score=float(scores[i]),
                     kps=kpss[i]) for i in keep]

    # -- 认人：ArcFace（face_align.norm_crop ＋ ArcFaceONNX.get_feat）
    def embed(self, img, face: Face):
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        if face.embedding is not None:
            return face.embedding
        m = _umeyama(np.asarray(face.kps, dtype=np.float64),
                     np.asarray(_ARCFACE_DST, dtype=np.float64))[:2]
        aligned = cv2.warpAffine(img, m, (112, 112), borderValue=0.0)
        blob = cv2.dnn.blobFromImage(aligned, 1.0 / 127.5, (112, 112),
                                     (127.5, 127.5, 127.5), swapRB=True)
        vec = self.rec.run(None, {self.rec_in: blob})[0][0]
        face.embedding = vec / float(np.linalg.norm(vec))
        return face.embedding

    # -- 106 点（insightface.model_zoo.landmark.Landmark.get，旋转 0）
    def landmarks(self, img, face: Face):
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        if face.landmarks is not None:
            return face.landmarks
        x1, y1, x2, y2 = face.bbox
        size = 192
        s = size / (max(x2 - x1, y2 - y1) * 1.5)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        m = np.array([[s, 0, size / 2 - cx * s], [0, s, size / 2 - cy * s]],
                     dtype=np.float64)
        crop = cv2.warpAffine(img, m, (size, size), borderValue=0.0)
        # 2d106det 的图里自带减均值／乘系数（首两个节点 _minusscalar0/_mulscalar0），
        # insightface 据此把 mean/std 定成 0/1——这里照抄，不再归一化一遍
        blob = cv2.dnn.blobFromImage(crop, 1.0, (size, size), (0.0, 0.0, 0.0),
                                     swapRB=True)
        pred = self.lmk.run(None, {self.lmk_in: blob})[0][0].reshape(-1, 2)
        pred = (pred + 1.0) * (size // 2)
        inv = cv2.invertAffineTransform(m)
        face.landmarks = pred @ inv[:, :2].T + inv[:, 2]
        return face.landmarks


def _nms(dets, thresh: float) -> list[int]:
    import numpy as np  # noqa: PLC0415

    x1, y1, x2, y2, scores = (dets[:, i] for i in range(5))
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


def _umeyama(src, dst):
    """相似变换最小二乘（skimage.transform.SimilarityTransform.estimate 的算法）。"""
    import numpy as np  # noqa: PLC0415

    num, dim = src.shape
    src_mean, dst_mean = src.mean(axis=0), dst.mean(axis=0)
    src_d, dst_d = src - src_mean, dst - dst_mean
    a = dst_d.T @ src_d / num
    d = np.ones((dim,))
    if np.linalg.det(a) < 0:
        d[dim - 1] = -1
    t = np.eye(dim + 1)
    u, s, v = np.linalg.svd(a)
    rank = np.linalg.matrix_rank(a)
    if rank == dim - 1 and np.linalg.det(u) * np.linalg.det(v) <= 0:
        keep = d[dim - 1]
        d[dim - 1] = -1
        t[:dim, :dim] = u @ np.diag(d) @ v
        d[dim - 1] = keep
    else:
        t[:dim, :dim] = u @ np.diag(d) @ v
    scale = 1.0 / src_d.var(axis=0).sum() * (s @ d)
    t[:dim, dim] = dst_mean - scale * (t[:dim, :dim] @ src_mean.T)
    t[:dim, :dim] *= scale
    return t


_MODEL: FaceModel | None = None
_MODEL_ERROR: str | None = None


_LOAD_LOCK = threading.Lock()


def load(*, fetch: bool = False) -> FaceModel:
    """进程内单例。失败一次就记住原因，后面同样抛（别每一帧重试一次下载）。

    上锁：render 里分段那道在后台线程、封面那道在主线程，两边可能同时第一次叫它。

    ⚠️ **默认不联网**（`fetch=False`）。出片链路（封面闸、分段认人、采访封面闸）里
    权重由工作流「备好人脸模型」那一步先下好、缓存住；那一步没备上，这里就该
    **当场报 unavailable**，而不是在 job 中途再去 GitHub Release 拉 127 MB 的包
    （评审 2026-09-27 nit 6：原来默认 `fetch=True`，缺权重时每条出片链路都会
    现下一遍，还排在「onnxruntime 装没装」之前）。只有人手跑的命令行
    （`face_checks.py check/scan/...`、`identify_player_frame.py`）才显式 `fetch=True`。"""
    global _MODEL, _MODEL_ERROR
    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL
        if _MODEL_ERROR is not None:
            raise ModelUnavailable(_MODEL_ERROR)
        try:
            directory = fetch_models() if fetch else model_dir()
            missing = models_ready(directory)
            if missing:
                raise ModelUnavailable(f"人脸模型不全：缺 {', '.join(missing)}（{directory}）")
            _MODEL = FaceModel(directory)
        except ModelUnavailable as exc:
            _MODEL_ERROR = str(exc)
            raise
        return _MODEL


def status() -> dict:
    """给产物用的一行状态：`{"status": "ok"|"unavailable", ...}`。"""
    try:
        load()
    except ModelUnavailable as exc:
        return {"status": "unavailable", "model": MODEL_VERSION, "error": str(exc)}
    return {"status": "ok", "model": MODEL_VERSION}


def _reset_for_tests() -> None:
    global _MODEL, _MODEL_ERROR
    _MODEL, _MODEL_ERROR = None, None


# ---------------------------------------------------------------- 读图

def read_bgr(image) -> object:
    """路径 / PIL / BGR ndarray → BGR ndarray。

    PNG 头像是调色板＋透明底（ATP 那批 300×300 全是 `P` 模式）：先铺白底再转，
    直接 `cv2.imread` 会把透明区读成黑，脸的边缘被当成一圈黑框。
    """
    import numpy as np  # noqa: PLC0415

    if hasattr(image, "shape"):
        return image
    from PIL import Image, ImageOps  # noqa: PLC0415

    pil = image if hasattr(image, "convert") else Image.open(Path(image))
    pil = ImageOps.exif_transpose(pil)
    if pil.mode in ("P", "LA", "RGBA") or "transparency" in pil.info:
        rgba = pil.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        pil = Image.alpha_composite(bg, rgba)
    rgb = np.asarray(pil.convert("RGB"))
    return np.ascontiguousarray(rgb[:, :, ::-1])


def _pad(img, frac: float):
    """四周各补 `frac` 倍边长的白边。官方头像是**满画幅大头**——SCRFD 在 640 输入
    上对占满整幅的脸是检不出来的（atp-T0HA / atp-C0E9 原样一张都检不出，补边之后都出）。"""
    import cv2  # noqa: PLC0415

    h, w = img.shape[:2]
    py, px = int(h * frac), int(w * frac)
    return cv2.copyMakeBorder(img, py, py, px, px, cv2.BORDER_CONSTANT,
                              value=(255, 255, 255))


def largest_face(model: FaceModel, img) -> Face | None:
    faces = model.detect(img)
    return max(faces, key=lambda f: f.area) if faces else None


# ---------------------------------------------------------------- 头像

_HEADSHOT_CACHE: dict[str, object] = {}


_INDEX: dict[str, str] | None = None


def headshot_path(name: str) -> Path | None:
    """中文名 → 官方头像。**从已发 spec 推，不维护名单**（`headshot_index`，
    同一张脸只挂一个名那条判据保证反查唯一）。"""
    global _INDEX
    if _INDEX is None:
        sys.path.insert(0, str(ROOT / "tools"))
        from headshot_index import index_from_specs  # noqa: PLC0415

        _INDEX = index_from_specs()
    hit = _INDEX.get(str(name).strip())
    if hit and (ROOT / hit).is_file():
        return ROOT / hit
    return None


def headshot_embedding(model: FaceModel, path: Path):
    """一张官方头像的向量（补白边再检，取最大那张脸）。检不出脸 → None。"""
    key = f"{Path(path).resolve()}:{Path(path).stat().st_mtime_ns}"
    if key in _HEADSHOT_CACHE:
        return _HEADSHOT_CACHE[key]
    try:
        img = read_bgr(path)
    except Exception:                                             # noqa: BLE001
        # 坏图（`wta-322451.png` 至今 PIL 都读不开）当「没有头像」——调用方会把
        # 它记成 unknown 并说出是哪个名字缺，不会因此判 mismatch
        _HEADSHOT_CACHE[key] = None
        return None
    face = None
    for frac in (0.0, 0.5, 1.0):
        probe = _pad(img, frac) if frac else img
        face = largest_face(model, probe)
        if face is not None:
            emb = model.embed(probe, face)
            break
    else:
        emb = None
    _HEADSHOT_CACHE[key] = emb
    return emb


def resolve_expected(expected: Mapping[str, object] | Sequence[str] | str
                     ) -> dict[str, Path | None]:
    """`["鲁德"]` / `"鲁德/兹维列夫"` / `{"鲁德": "assets/…png"}` → 名字 → 头像路径。"""
    if isinstance(expected, str):
        expected = [p for p in expected.replace("／", "/").split("/") if p.strip()]
    if isinstance(expected, Mapping):
        out = {}
        for name, path in expected.items():
            p = Path(str(path)) if path else None
            if p is not None and not p.is_absolute():
                p = ROOT / p
            out[str(name)] = p if p is not None and p.is_file() else headshot_path(name)
        return out
    return {str(n).strip(): headshot_path(n) for n in expected if str(n).strip()}


# ---------------------------------------------------------------- 两个判定
#
# **判定只从数算，不从字符串算。** 凭证落盘之后，`check_interview_landed` 和
# `auto_push_interview_gate` 会拿存下来的数**重判一遍**（`problems_of`）——手改一个
# `"verdict": "match"` 骗不过去，因为重判看的是 `similarity` / `ear` 这几个数。
# 下面两个纯函数是全文件唯一的判据，`identify` / `eyes_open` / `problems_of` 都调它们。

def identity_verdict(sims: Mapping[str, float], missing: Sequence[str],
                     face_px: float, target: Sequence[str] | None = None
                     ) -> tuple[str, str | None, str]:
    """(verdict, name, reason)。

    `target`：候选里**封面要的是哪一个（几个）**。给了它，`match` 就只认它——
    另外那几个人只用来判「这张脸是谁」（是对手 → `mismatch`）和「拿不准」，
    **永远不许让一张对手的脸算通过**。

    来路（评审 2026-09-27 BLOCKING）：赛场之上的封面要认的候选是 `cover.matchup`
    里的两个人，原来「像两人之一就算 match」——`medvedev-royer` 那帧梅德韦杰夫
    的脸，把 `cover.subject` 改成鲁瓦耶照样 `match`、`problems=[]`。80 条抽帧封面
    里 74 条在 `cover.subject` 写着封面上是谁，这道闸却一次都没看它。
    """
    if face_px <= 0:
        return "unknown", None, "没检出人脸"
    if face_px < MIN_ID_FACE_PX:
        return "unknown", None, f"脸高 {face_px:.0f}px < {MIN_ID_FACE_PX}px，认不了"
    if not sims:
        return "unknown", None, f"没有可比的官方头像：{'、'.join(missing) or '（未给人名）'}"
    best = max(sims, key=sims.get)
    want = [str(n) for n in (target or []) if str(n)]
    if want:
        return _targeted_verdict(sims, missing, want, best)
    if sims[best] >= MATCH_SIM:
        return "match", best, f"像 {best}（{sims[best]:.2f} ≥ {MATCH_SIM}）"
    if not missing and all(v < MISMATCH_SIM for v in sims.values()):
        detail = "、".join(f"{k} {v:.2f}" for k, v in sims.items())
        who = (f"不是{next(iter(sims))}" if len(sims) == 1
               else f"不是{'／'.join(sims)}里的任何一个")
        return "mismatch", None, f"{who}（和官方头像的相似度 {detail}，< {MISMATCH_SIM}）"
    why = f"最像 {best} 也只有 {sims[best]:.2f}，介于 {MISMATCH_SIM}~{MATCH_SIM}"
    if missing:
        why += f"；{'、'.join(missing)} 没有官方头像，不敢判「不是他」"
    return "unknown", best, why


def _targeted_verdict(sims: Mapping[str, float], missing: Sequence[str],
                      want: Sequence[str], best: str) -> tuple[str, str | None, str]:
    """`identity_verdict` 给了 `target` 的那一支。四种结论，按顺序：

    1. 封面主角像到 `MATCH_SIM` 以上、而且没有别人比他更像 → `match`
    2. 别人（对手／搭档）像到 `MATCH_SIM` 以上、封面主角没到 → `mismatch`：
       **这张脸是另一个人**——`MATCH_SIM` 让「不同的人被认成是他」压在万分之四
    3. 封面主角有头像、相似度低于 `MISMATCH_SIM` → `mismatch`：同一个人 85 张真封面
       里最低 0.217，**0 张落在 0.15 以下**，和别人像不像无关
    4. 其余（主角没头像、落在中间地带、两个人都像）→ `unknown`，只报不拦
    """
    who = "／".join(want)
    tsims = {n: sims[n] for n in want if n in sims}
    tmissing = [n for n in want if n not in sims]
    tbest = max(tsims, key=tsims.get) if tsims else None
    if tbest is not None and tsims[tbest] >= MATCH_SIM:
        if best not in want and sims[best] > tsims[tbest]:
            return "unknown", tbest, (
                f"像 {tbest}（{tsims[tbest]:.2f}）也像 {best}（{sims[best]:.2f}，更像），"
                "两个人分不清——不硬判")
        return "match", tbest, f"像 {tbest}（{tsims[tbest]:.2f} ≥ {MATCH_SIM}）"
    if best not in want and sims[best] >= MATCH_SIM:
        mine = (f"，和{who}只有 {tsims[tbest]:.2f}" if tbest is not None
                else f"，{who}没有官方头像")
        return "mismatch", best, (f"这张脸是{best}（{sims[best]:.2f} ≥ {MATCH_SIM}）"
                                  f"{mine}——封面要的是{who}")
    if tsims and not tmissing and all(v < MISMATCH_SIM for v in tsims.values()):
        detail = "、".join(f"{k} {v:.2f}" for k, v in tsims.items())
        return "mismatch", None, (f"不是封面主角{who}（和官方头像的相似度 {detail}，"
                                  f"< {MISMATCH_SIM}）")
    if tbest is None:
        why = f"封面主角{who}没有官方头像，认不了"
        if missing:
            why += f"（缺头像：{'、'.join(sorted(set(missing)))}）"
        return "unknown", None, why
    return "unknown", tbest, (f"和封面主角{tbest}只有 {tsims[tbest]:.2f}，"
                              f"介于 {MISMATCH_SIM}~{MATCH_SIM}")


def eyes_verdict(ear: float | None, face_px: float) -> tuple[str, str]:
    """(verdict, reason)。"""
    if face_px <= 0:
        return "unknown", "没检出人脸"
    if face_px < MIN_EYE_FACE_PX:
        return "unknown", f"脸高 {face_px:.0f}px < {MIN_EYE_FACE_PX}px，眼睛量不准"
    if ear is None:
        return "unknown", "没量到眼睛"
    if ear < EYE_CLOSED_EAR:
        return "closed", f"眼睛纵横比 {ear:.2f} < {EYE_CLOSED_EAR}"
    if ear < EYE_OPEN_EAR:
        return "downcast", (f"眼睛纵横比 {ear:.2f}，介于 {EYE_CLOSED_EAR}~{EYE_OPEN_EAR}"
                            "（半睁／往下看）")
    return "open", f"眼睛纵横比 {ear:.2f} ≥ {EYE_OPEN_EAR}"


def identify(image, expected_players, *, face: Face | None = None,
             model: FaceModel | None = None, target: Sequence[str] | None = None) -> dict:
    """这张图里最大的那张脸，是不是 `expected_players` 里的人。

    返回 `{"verdict": "match"|"mismatch"|"unknown", "name", "similarity", "missing", ...}`。
    **只有两种硬结论**：像到 `MATCH_SIM` 以上＝match；和每一个候选都不到
    `MISMATCH_SIM`＝mismatch（**有人没头像就不判 mismatch**）。其余一律 unknown。

    给了 `target`（必须是 `expected_players` 里的名字）：只有**它**能 match，
    别的候选只拿来认「这张脸是谁」——见 `_targeted_verdict`。
    """
    model = model or load()
    img = read_bgr(image)
    face = face or largest_face(model, img)
    refs = resolve_expected(expected_players)
    face_px = round(face.height, 1) if face else 0.0
    missing = sorted(n for n, p in refs.items() if p is None)
    sims: dict[str, float] = {}
    if face is not None and face.height >= MIN_ID_FACE_PX:
        emb = model.embed(img, face)
        for name, path in refs.items():
            if path is None:
                continue
            ref = headshot_embedding(model, path)
            if ref is None:
                missing.append(name)
                continue
            sims[name] = round(float((emb * ref).sum()), 4)
    want = sorted(str(n) for n in (target or []) if str(n) in refs)
    if target and not want:
        raise ValueError(f"target {list(target)} 不在候选 {sorted(refs)} 里")
    verdict, name, reason = identity_verdict(sims, missing, face_px, want or None)
    out = {"verdict": verdict, "name": name, "similarity": sims,
           "missing": sorted(set(missing)), "expected": sorted(refs),
           "face": face.box() if face else None, "face_px": face_px,
           "reason": reason,
           "thresholds": {"match": MATCH_SIM, "mismatch": MISMATCH_SIM,
                          "min_face_px": MIN_ID_FACE_PX}}
    if want:
        # 落盘：`problems_of` 重判时要知道「只认谁」，不然重判会退回「两人之一」
        out["target"] = want
    return out


def eyes_open(image, face: Face | None = None, *, model: FaceModel | None = None) -> dict:
    """这张脸眼睛睁着吗：`{"verdict": "open"|"closed"|"downcast"|"unknown", "ear", ...}`。"""
    import numpy as np  # noqa: PLC0415

    model = model or load()
    img = read_bgr(image)
    face = face or largest_face(model, img)
    face_px = round(face.height, 1) if face else 0.0
    ear, each = None, None
    if face is not None and face.height >= MIN_EYE_FACE_PX:
        pts = model.landmarks(img, face)
        each = []
        for eye in _EYES:
            a, b = (pts[i] for i in eye["corners"])
            width = float(np.linalg.norm(a - b))
            gap = np.mean([np.linalg.norm(pts[u] - pts[lo])
                           for u, lo in zip(eye["upper"], eye["lower"])])
            each.append(round(float(gap / width) if width > 1e-6 else 0.0, 4))
        ear = round(float(np.mean(each)), 4)
    verdict, reason = eyes_verdict(ear, face_px)
    return {"verdict": verdict, "ear": ear, "ear_each": each,
            "face": face.box() if face else None, "face_px": face_px, "reason": reason,
            "thresholds": {"closed": EYE_CLOSED_EAR, "open": EYE_OPEN_EAR,
                           "min_face_px": MIN_EYE_FACE_PX}}


def problems_of(block: object) -> tuple[list[str], list[str]]:
    """一份存下来的 `check_frame` 结果 → (硬问题, 提示)。**从数重判，不信字符串。**

    - `status: unavailable` → 没有硬问题，但一定有一条提示（大声降级，不是通过）
    - 缺块 / 形状不对 → 当成没查（调用方决定这算不算问题，见 `audit_interview_cover`）
    """
    if not isinstance(block, dict):
        return [], ["没有人脸模型证据"]
    if block.get("status") != "ok":
        return [], [f"人脸模型不可用，认人和睁眼都没查：{block.get('error') or '原因没记'}"]
    problems, warnings = [], []
    ident = block.get("identity") or {}
    sims = {str(k): float(v) for k, v in (ident.get("similarity") or {}).items()}
    verdict, _name, reason = identity_verdict(
        sims, list(ident.get("missing") or []), float(ident.get("face_px") or 0.0),
        [str(n) for n in ident.get("target") or []] or None)
    if verdict == "mismatch":
        problems.append(f"这张脸不是本人：{reason}")
    elif verdict == "unknown":
        warnings.append(f"认人拿不准：{reason}")
    eyes = block.get("eyes") or {}
    ear = eyes.get("ear")
    everdict, ereason = eyes_verdict(None if ear is None else float(ear),
                                     float(eyes.get("face_px") or 0.0))
    if everdict in ("closed", "downcast"):
        label = "闭眼" if everdict == "closed" else "垂眼／半睁"
        problems.append(f"这张脸{label}：{ereason}")
    elif everdict == "unknown":
        warnings.append(f"睁眼量不了：{ereason}")
    return problems, warnings


def restrict_identity(ident: Mapping, names: Sequence[str],
                      target: Sequence[str] | None = None) -> dict:
    """同一张脸对一批候选的 `identify` 结果 → **只拿 `names` 这几个人去认**的那一份。

    相似度是逐人各算各的（同一张脸的向量 · 各自头像的向量），所以只留 `names` 的相似度、
    缺头像名单，再按 `target` 重判一次，和 `identify(image, names, target=target)`
    **逐字段一样**——`check_frame(rivals=…)` 靠它让「多比了几个人」不改动终审那一份。"""
    keep = [str(n) for n in names]
    sims = {n: v for n, v in (ident.get("similarity") or {}).items() if n in keep}
    missing = sorted({str(n) for n in ident.get("missing") or [] if n in keep})
    want = sorted(str(n) for n in (target or []) if str(n) in keep)
    verdict, name, reason = identity_verdict(sims, missing, float(ident.get("face_px") or 0.0),
                                             want or None)
    out = {**{k: v for k, v in ident.items() if k != "target"},
           "verdict": verdict, "name": name, "similarity": sims, "missing": missing,
           "expected": sorted(keep), "reason": reason}
    if want:
        out["target"] = want
    return out


def check_frame(image, expected_players, *, model: FaceModel | None = None,
                target: Sequence[str] | None = None,
                rivals: Sequence[str] = (), all_faces: bool = False) -> dict:
    """封面帧一次查两件事（同一张脸）。给 `audit_interview_cover` 和
    `reel_face_gate` 共用——**两条线一个出口，别写两份**。

    返回 `{"status": "ok"|"unavailable", "identity": {...}, "eyes": {...},
    "problems": [...], "warnings": [...]}`；`problems` 只放**硬结论**
    （mismatch / closed / downcast），unknown 进 `warnings`。

    `rivals`：同场、同框可能出现的**别人**（对手、搭档、文案里点了名的冠军……）。给了就
    多出一块 `rivals`：同一张脸拿 `expected_players ＋ rivals` 一起认、`target` 只认
    `expected_players`——「更像别人」的脸在那一块里是 unknown／mismatch。`identity`、
    `problems`、`warnings` **和不给 rivals 时逐字段一样**（`restrict_identity`）：终审
    那一份不因为多比了几个人而变，要更严一档的调用方（赛后开麦封面的机器换帧）自己读
    `rivals` 那一块。只支持按名字给的候选（str／名单），显式头像路径的 Mapping 不混用。

    `all_faces`：多给两块——`faces`（检出的每一张脸的框，大的在前，O4 拿它认两人同框）和 `pose`
    （最大那张脸正不正、清不清楚，`face_pose`，O4 排序用）。
    """
    try:
        model = model or load()
    except ModelUnavailable as exc:
        block = {"status": "unavailable", "model": MODEL_VERSION, "error": str(exc)}
        problems, warnings = problems_of(block)
        return {**block, "problems": problems, "warnings": warnings}
    img = read_bgr(image)
    detected = model.detect(img)
    face = max(detected, key=lambda f: f.area) if detected else None
    refs = resolve_expected(expected_players)
    others = [str(r) for r in rivals if str(r).strip() and str(r) not in refs]
    if others:
        full = identify(img, {**refs, **resolve_expected(others)}, face=face, model=model,
                        target=list(target or refs))
        ident = restrict_identity(full, list(refs), target)
    else:
        full, ident = None, identify(img, expected_players, face=face, model=model,
                                     target=target)
    block = {"status": "ok", "model": MODEL_VERSION, "identity": ident,
             "eyes": eyes_open(img, face, model=model)}
    if all_faces:
        # 检出的每一张脸（大的在前）：O4 按它认「两人同框」（`cover_upgrade.second_face`）。
        # 只在要的时候给——别的调用方把这一块整个落进凭证，平白多一串坐标
        block["faces"] = [f.box() for f in sorted(detected, key=lambda f: -f.area)]
        block["pose"] = face_pose(img, face)
    if full is not None:
        block["rivals"] = full
    problems, warnings = problems_of(block)
    return {**block, "problems": problems, "warnings": warnings}


#: 「偏正面」：两眼间距 ÷ 脸框宽 ≥ 这个数。2026-09-28 杭州／新加坡／瓜达拉哈拉 20 张官方原图量的：
#: 正脸 0.38~0.46（Medvedev-022 0.41、Safiullin-022 0.42、捧杯 vc-5 0.38），四分之三侧 0.25~0.33
#: （Medvedev-014 0.25），侧脸 < 0.23（Medvedev-019 0.17、-024 0.22、握手照 0.18）
FRONTAL_EYE_SPAN = 0.30
#: 「脸是清楚的」：脸框缩到 112×112 灰度后的拉普拉斯方差 ≥ 这个数。同一批量的：清楚的 460~3141，
#: 动感模糊的 Medvedev-019 193、背景里的小脸 230~255、横幅上的误检 63。**只拿来排序**（`cover_upgrade.taste_key`），
#: 不是闸——不同镜头的方差不可比（`rank_frame_sharpness` 那条），所以门槛放得很低，只分「糊透了」
SHARP_FACE_LAPLACIAN = 300.0


def face_pose(img, face: Face | None) -> dict | None:
    """最大那张脸的「正不正」「清不清楚」：`eye_span`（两眼间距 ÷ 脸框宽，5 点里的两只眼）和
    `sharp`（脸框缩到 112×112 灰度的拉普拉斯方差）。账号所有者的口味：正脸或偏正面 ＞ 侧脸（2026-09-26）、
    封面要清楚（2026-08-16）——O4 挑图时排序用（`cover_upgrade.taste_key`）。"""
    if face is None:
        return None
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    kps = np.asarray(face.kps, dtype=np.float64)
    x1, y1, x2, y2 = (int(round(v)) for v in face.bbox)
    width = max(x2 - x1, 1)
    eye_span = float(abs(kps[1][0] - kps[0][0]) / width)
    h, w = img.shape[:2]
    crop = img[max(y1, 0):min(y2, h), max(x1, 0):min(x2, w)]
    sharp = None
    if crop.size:
        gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (112, 112),
                          interpolation=cv2.INTER_AREA)
        sharp = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
    return {"eye_span": round(eye_span, 3), "sharp": sharp,
            "frontal": eye_span >= FRONTAL_EYE_SPAN,
            "clear": sharp is not None and sharp >= SHARP_FACE_LAPLACIAN}


def rank_frames(frames: Iterable[tuple[str, object]], expected_players, *,
                model: FaceModel | None = None,
                target: Sequence[str] | None = None) -> list[dict]:
    """一批候选帧里**哪几张能过**：同一个人（match）＋ 睁眼，按相似度、睁眼程度排。

    这是「拦下来之后换哪一帧」那一步——`python tools/face_checks.py scan` 走这里，
    `reel_face_gate` 拦住封面帧时也拿它在 `frame_at` 前后扫一圈，把能过的秒数
    印进报错里，不用人再去 2 秒一格的缩略图墙上猜。

    给了 `target` 就只有它的脸算「能过」——**拦下一张对手的脸之后，推荐的换帧
    不许又是对手**（评审 2026-09-27 BLOCKING 的同一个洞）。排序用的相似度也是
    认出来的那个人的，不是所有候选里最大的那个。
    """
    model = model or load()
    rows = []
    for label, frame in frames:
        res = check_frame(frame, expected_players, model=model, target=target)
        ident = res["identity"]
        sims = ident["similarity"]
        ok = (not res["problems"] and ident["verdict"] == "match"
              and res["eyes"]["verdict"] == "open")
        sim = (sims.get(ident["name"]) if ident["name"] in sims
               else max(sims.values(), default=None))
        rows.append({"frame": label, "ok": ok, "similarity": sim,
                     "name": ident["name"], "ear": res["eyes"]["ear"],
                     "face_px": ident["face_px"], "problems": res["problems"]})
    rows.sort(key=lambda r: (not r["ok"], -(r["similarity"] or -1), -(r["ear"] or 0)))
    return rows


# ---------------------------------------------------------------- 画面裁切

#: 裁切那道只报不拦，但报出来的要站得住：认出的「另一个人」得比旁白点名的那个
#: 像出这么多。0.15 是 `identify_player_frame` 的「拿不准」线——那边 26/26 的
#: 验证里两张边缘案例的余量是 0.05~0.06，这里要求高出一截才开口。
CROP_MARGIN = 0.15


def crop_findings(frames: Iterable[tuple[str, object]], named: str,
                  others: Sequence[str], *, model: FaceModel | None = None
                  ) -> tuple[list[str], dict]:
    """一段画面（若干张已裁成 3:4 窗口的帧）里，旁白点名的是 `named`，
    画面里认得出的脸却是 `others` 里的人 → 一条发现。

    **只报不拦**：转播宽景里球员的脸常常只有二三十像素（`MIN_ID_FACE_PX` 以下
    一律 unknown），这一道的精度没有像封面那样拿真样本量过。返回
    (发现, 计数)，计数里把「看了几帧、几帧有够大的脸、几帧认得出」都记下——
    **只在出事时出声的检查证明不了它看过**。
    """
    model = model or load()
    out: list[str] = []
    tally = {"frames": 0, "faces": 0, "named_seen": 0, "other_seen": 0}
    for label, frame in frames:
        tally["frames"] += 1
        ident = identify(frame, [named, *others], model=model)
        if ident["face_px"] >= MIN_ID_FACE_PX:
            tally["faces"] += 1
        sims = ident["similarity"]
        if ident["verdict"] != "match":
            continue
        if ident["name"] == named:
            tally["named_seen"] += 1
            continue
        lead = sims[ident["name"]] - sims.get(named, -1.0)
        if lead >= CROP_MARGIN:
            tally["other_seen"] += 1
            out.append(f"{label}：旁白讲{named}，3:4 画面里最大的那张脸是"
                       f"{ident['name']}（{ident['name']} {sims[ident['name']]:.2f} ／ "
                       f"{named} {sims.get(named, float('nan')):.2f}）")
    return out, tally


# ---------------------------------------------------------------- 命令行

def _bench(images: list[Path]) -> dict:
    t0 = time.perf_counter()
    _reset_for_tests()
    model = load(fetch=True)
    t_load = time.perf_counter() - t0
    rows = []
    for path in images:
        img = read_bgr(path)
        t1 = time.perf_counter()
        face = largest_face(model, img)
        t2 = time.perf_counter()
        if face is not None:
            model.embed(img, face)
        t3 = time.perf_counter()
        if face is not None:
            model.landmarks(img, face)
        t4 = time.perf_counter()
        rows.append({"image": str(path), "size": list(img.shape[:2]),
                     "detect_ms": round((t2 - t1) * 1000, 1),
                     "embed_ms": round((t3 - t2) * 1000, 1),
                     "landmarks_ms": round((t4 - t3) * 1000, 1)})
    return {"load_s": round(t_load, 3), "frames": rows}


def _calibrate() -> dict:
    """仓库里全部官方头像两两比——**不同的人**能像到多少（MATCH/MISMATCH 门槛的来路）。"""
    import numpy as np  # noqa: PLC0415

    model = load()
    paths = sorted(p for p in (ROOT / "assets" / "players" / "headshots").iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    embs, used, failed = [], [], []
    for p in paths:
        try:
            e = headshot_embedding(model, p)
        except Exception as exc:                                  # noqa: BLE001
            failed.append(f"{p.name}: {type(exc).__name__}")
            continue
        if e is None:
            failed.append(f"{p.name}: 没检出脸")
            continue
        embs.append(e)
        used.append(p.name)
    m = np.stack(embs)
    sims = m @ m.T
    iu = np.triu_indices(len(used), 1)
    # 同一个人存了两份（`atp-N0AE.png` / `atp-n0ae.png` 大小写两份，逐字节相同）
    # 不算「不同的人」——不排掉的话 max 恒为 1.0，这张表就什么都说明不了
    same = np.array([used[a].lower() == used[b].lower() or sims[a, b] > 0.95
                     for a, b in zip(*iu)])
    vals = sims[iu][~same]
    pairs = [(used[a], used[b]) for (a, b), s in zip(zip(*iu), same) if not s]
    top = np.argsort(vals)[::-1][:8]
    return {"headshots": len(used), "failed": failed, "pairs": int(vals.size),
            "dropped_same_person_duplicates": int(same.sum()),
            "max": round(float(vals.max()), 4),
            "p999": round(float(np.quantile(vals, 0.999)), 4),
            "p99": round(float(np.quantile(vals, 0.99)), 4),
            "p97": round(float(np.quantile(vals, 0.97)), 4),
            "share_below_mismatch": round(float((vals < MISMATCH_SIM).mean()), 4),
            "share_at_or_above_match": round(float((vals >= MATCH_SIM).mean()), 5),
            "top_pairs": [(*pairs[k], round(float(vals[k]), 4)) for k in top]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="下好并校验三个 onnx（工作流在缓存没命中时跑）")
    sub.add_parser("version", help="印模型版本")
    sub.add_parser("cache-key", help="印工作流 actions/cache 该用的键（按权重内容定址）")
    c = sub.add_parser("check", help="查一张图：是不是这个人、眼睛睁没睁")
    c.add_argument("image")
    c.add_argument("--expect", action="append", default=[],
                   help="应该是谁（中文名，可重复；双打写两次）")
    c.add_argument("--subject", action="append", default=[],
                   help="--expect 里封面要的是哪一个（给了就只认他，另一个只用来认对手）")
    s = sub.add_parser("scan", help="一批候选帧里哪几张能过（同一个人＋睁眼），按好坏排")
    s.add_argument("images", nargs="+")
    s.add_argument("--expect", action="append", default=[], required=True)
    s.add_argument("--subject", action="append", default=[])
    b = sub.add_parser("bench", help="量加载和每帧推理的耗时")
    b.add_argument("images", nargs="+")
    sub.add_parser("calibrate", help="官方头像两两比，看「不同的人」能像到多少")
    args = ap.parse_args(argv)

    if args.cmd == "version":
        print(MODEL_VERSION)
        return 0
    if args.cmd == "cache-key":
        print(CACHE_KEY)
        return 0
    if args.cmd == "fetch":
        t0 = time.perf_counter()
        before = models_ready()
        try:
            directory = fetch_models()
        except ModelUnavailable as exc:
            # 非零退出：工作流「备好人脸模型」据此**不写** ok=true，缓存就不会存下半截目录
            print(f"[人脸模型] 没备好：{exc}", file=sys.stderr)
            return 1
        print(f"[人脸模型] {MODEL_VERSION} → {directory}"
              f"（{'已在缓存里' if not before else '现下 ' + ', '.join(before)}，"
              f"{time.perf_counter() - t0:.1f}s）")
        return 0
    # 人手跑的命令行：缺权重就现下（出片链路里的 `load()` 默认不联网，见它的注释）
    try:
        load(fetch=True)
    except ModelUnavailable as exc:
        print(f"[人脸模型] 不可用：{exc}", file=sys.stderr)
        return 2
    if args.cmd == "check":
        res = check_frame(Path(args.image), args.expect, target=args.subject or None)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 1 if res.get("problems") else 0
    if args.cmd == "scan":
        rows = rank_frames([(p, Path(p)) for p in args.images], args.expect,
                           target=args.subject or None)
        for r in rows:
            mark = "✅" if r["ok"] else "  "
            print(f"{mark} {r['frame']}  像 {r['name'] or '?'} {r['similarity']}  "
                  f"眼 {r['ear']}  脸 {r['face_px']}px  {'；'.join(r['problems'])}")
        print(f"{sum(r['ok'] for r in rows)}/{len(rows)} 张能过")
        return 0 if any(r["ok"] for r in rows) else 1
    if args.cmd == "bench":
        print(json.dumps(_bench([Path(p) for p in args.images]), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "calibrate":
        print(json.dumps(_calibrate(), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

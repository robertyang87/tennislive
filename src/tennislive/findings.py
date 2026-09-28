"""全库测试里「只报、不判红」的 warning 类型——必须定义在这个包里，不能定义在 tools/ 里。

pytest-xdist 的 worker 把 warning 发回主控进程时，主控要按 ``type(w).__module__``
重新 import 这个类才能反序列化；主控的 ``sys.path`` 里没有 ``tools/``
（``tests/conftest.py`` 只在个别 fixture 里临时加）。类原来定义在
``tools/build_interview_request.py``：worker 一发这条 warning，主控就
``ModuleNotFoundError: No module named 'build_interview_request'`` → INTERNALERROR，
整场测试会话崩掉、CI 红（PR #1138，run 36421724798；main 上 4 份未核的自动草稿就会触发）。
本地加 ``-p no:warnings`` 跑不出来——warning 不走序列化那条路。

判据 ``tests/test_warning_classes.py``：tools/ 下不许再定义 Warning 子类。
"""


class UnverifiedAutoSpecFinding(UserWarning):
    """全库测试里自动 spec 的发现：只报、不判 main 红（pytest 的 warnings 汇总里看得见）。"""

import os,sys,ssl
from pathlib import Path
ROOT=Path('/workspace/tennislive')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
import edge_tts,edge_tts.communicate as ec
ec._SSL_CTX=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
Original=edge_tts.Communicate
class ProxyCommunicate(Original):
 def __init__(self,*a,**kw):
  kw.setdefault('proxy',os.environ.get('HTTPS_PROXY'))
  super().__init__(*a,**kw)
edge_tts.Communicate=ProxyCommunicate
import measure_polyphone as mp
mp._ca_done=True
mp.CACHE=ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation/audio'
if __name__=='__main__':
 p,m=mp.synth('赛场之上，郑钦文晋级中网八强。','zh-CN-YunjianNeural','+6%')
 print({'audio':str(p),'bytes':p.stat().st_size,'marks':m})

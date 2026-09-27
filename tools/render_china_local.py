"""Local runtime adapter: use system proxy CA for the existing story renderer."""
import os,sys,ssl,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
# CI installs CJK system fonts; this local image does not. Install a static
# instance of the repository font under the family used by the existing ASS.
font_target=Path.home()/'.local/share/fonts/tennis-china-open/NotoSansCJKSC-Bold.ttf'
if not font_target.exists():
 from fontTools.ttLib import TTFont
 from fontTools.varLib.instancer import instantiateVariableFont
 font=TTFont(Path(__file__).resolve().parents[1]/'assets/fonts/NotoSansSC-Bold-sub.ttf')
 if 'fvar' in font:font=instantiateVariableFont(font,{'wght':700},inplace=False)
 names={1:'Noto Sans CJK SC',2:'Bold',4:'Noto Sans CJK SC Bold',6:'NotoSansCJKSC-Bold',16:'Noto Sans CJK SC',17:'Bold'}
 for n in font['name'].names:
  if n.nameID in names:n.string=names[n.nameID].encode(n.getEncoding())
 font_target.parent.mkdir(parents=True,exist_ok=True);font.save(font_target)
 subprocess.run(['fc-cache','-f'],check=True)
import edge_tts,edge_tts.communicate as ec
ec._SSL_CTX=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
Original=edge_tts.Communicate
class ProxyCommunicate(Original):
 def __init__(self,*a,**kw):
  kw.setdefault('proxy',os.environ.get('HTTPS_PROXY'))
  super().__init__(*a,**kw)
edge_tts.Communicate=ProxyCommunicate
import build_match_reel
if __name__=='__main__':raise SystemExit(build_match_reel.main())

"""Temporary: fetch chosen trophy photo originals."""
import json, os, sys, requests
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
CUA = {"User-Agent": "tennislive-research/1.0 (https://github.com/robertyang87/tennislive) python-requests"}
U = {
 "rg_7194.jpg": "https://images.prismic.io/fft-rg-commun-news/aELkHbh8WN-LVvsJ_20150607_RG_CD_7194StanWawrinkamen%27ssinglesfinal2015.jpg",
 "us_P5S_8397.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120479_20160911_P5S_8397.jpg",
 "us_DSC21088.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120454_20160911_DSC21088.jpg",
 "us_DSC21075.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120447_20160911_DSC21075.jpg",
 "us_DSC21049.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120442_20160911_DSC21049.jpg",
 "us_DSC21076.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120448_20160911_DSC21076.jpg",
 "us_DSC21052.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120443_20160911_DSC21052.jpg",
 "us_P5S_8402.jpg": "https://photo-assets.usopen.org/images/pics/large/f_USTA120480_20160911_P5S_8402.jpg",
 "ao15_16104151589.jpg": "https://upload.wikimedia.org/wikipedia/commons/f/f1/Australian_Open_2015_%2816104151589%29.jpg",
 "ao15_16104428927.jpg": "https://upload.wikimedia.org/wikipedia/commons/a/ac/Australian_Open_2015_%2816104428927%29.jpg",
 "ao15_16102933790.jpg": "https://upload.wikimedia.org/wikipedia/commons/8/8d/Australian_Open_2015_%2816102933790%29.jpg",
 "ao15_brookes.jpg": "https://upload.wikimedia.org/wikipedia/commons/b/b0/Stan_Wawrinka_Norman_Brookes_Challenge_Cup.jpg",
}
for n, u in U.items():
    r = requests.get(u, headers=CUA if "wikimedia" in u else H, timeout=60)
    print(n, r.status_code, len(r.content))
    if r.ok: open(f"{OUT}/{n}", "wb").write(r.content)

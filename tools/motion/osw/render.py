import subprocess,sys
from playwright.sync_api import sync_playwright
name,dur=sys.argv[1],float(sys.argv[2]);FPS=50;N=int(FPS*dur)
ff=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-i","-","-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-shortest",
 "-vf","pad=2560:1440:740:0:color=0x05080f,fps=25","-c:v","libx264","-pix_fmt","yuv420p","-crf","14","-preset","medium","-c:a","aac","-movflags","+faststart",f"out/{name.replace('@','_')}.mp4"],stdin=subprocess.PIPE)
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"]);pg=b.new_page(viewport={"width":1080,"height":1440})
    pg.goto(f"file:///workspace/osw/{name.split('@')[0]}.html"+(("?m="+name.split("@")[1]) if "@" in name else ""));pg.evaluate("document.fonts.ready.then(()=>1)")
    for i in range(N):
        pg.evaluate(f"renderAt({i/FPS},{FPS})");ff.stdin.write(pg.screenshot(type="png"))
    pg.screenshot(path=f"out/{name.replace('@','_')}-final.png");b.close()
ff.stdin.close();ff.wait()

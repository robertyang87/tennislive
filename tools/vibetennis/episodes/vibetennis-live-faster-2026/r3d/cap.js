const puppeteer=require('puppeteer-core'); const {spawn}=require('child_process'); const fs=require('fs');
const [,,f0,f1,out,w,h]=process.argv; const FPS=30;
(async()=>{
 const b=await puppeteer.launch({executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',headless:'new',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist',`--window-size=${w||1920},${h||1080}`]});
 const p=await b.newPage(); await p.setViewport({width:+(w||1920),height:+(h||1080)});
 p.on('console',m=>{ if(m.type()==='error') console.error('PAGE',m.text()); }); p.on('pageerror',e=>console.error('PAGEERR',e.message));
 await p.goto(`http://127.0.0.1:8765/index.html?w=${w||1920}&h=${h||1080}`); await p.waitForFunction('window.READY===true',{timeout:60000});
 const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-','-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p',out]);
 const anchors=[]; const t0=Date.now();
 for(let f=+f0;f<+f1;f++){
   const r=await p.evaluate(t=>{ const a=window.renderAt(t); return [a, document.querySelector('canvas').toDataURL('image/jpeg',0.93)]; }, f/FPS);
   anchors.push([f,JSON.parse(r[0])]);
   const buf=Buffer.from(r[1].split(',')[1],'base64'); if(!ff.stdin.write(buf)) await new Promise(res=>ff.stdin.once('drain',res));
   if((f-f0)%60===0) console.log('frame',f,((Date.now()-t0)/(f-f0+1)).toFixed(0),'ms/f');
 }
 ff.stdin.end(); await new Promise(r=>ff.on('close',r)); fs.writeFileSync(out+'.anchors.json',JSON.stringify(anchors)); await b.close();
})();

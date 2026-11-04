const {chromium}=require('playwright');
(async()=>{ const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}); const p=await b.newPage();
 const [bb,ll]=process.argv.slice(2); let u='http://127.0.0.1:8771/dev_measure.html?'; if(bb) u+='b='+encodeURIComponent(bb)+'&'; if(ll) u+='l='+encodeURIComponent(ll);
 p.on('pageerror',e=>console.error('ERR',e.message)); await p.goto(u); await p.waitForFunction('window.READY===true',{timeout:120000});
 console.log(JSON.stringify(await p.evaluate(()=>window.M))); if(process.env.PROF) console.error((await p.evaluate(()=>window.PROF)).map(r=>r.join(" ")).join("\n")); await b.close(); })();

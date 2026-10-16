const g=i=>document.getElementById(i),cl=x=>Math.max(0,Math.min(1,x));
const expo=p=>p>=1?1:1-Math.pow(2,-10*p),q4=p=>1-Math.pow(1-p,4),io=p=>p<.5?2*p*p:1-Math.pow(-2*p+2,2)/2;
const spring=u=>u<=0?0:1-Math.exp(-8*u)*Math.cos(12*u);
const bounce=u=>u<=0?1:1+0.05*Math.exp(-6*u)*Math.cos(14*u);
function enter(el,t0,dur,dy,blur){const p=expo(cl((window._t-t0)/dur));el.style.opacity=p;
 el.style.transform='translateY('+(dy*(1-p))+'px)';el.style.filter=p>=.999?'none':'blur('+(blur*(1-p)).toFixed(2)+'px)';return p}
function bgAt(t,D){const dp=io(cl(t/D));g('stage').style.transform='scale('+(1+0.03*dp)+')';
 g('bloom1').style.transform='translate('+(60*Math.sin(t*0.5))+'px,'+(30*dp)+'px)';g('bloom2').style.transform='translate('+(80*dp)+'px,0)'}
const BG='<div id="bg" class="abs"></div><div id="bloom1" class="abs"></div><div id="bloom2" class="abs"></div>';

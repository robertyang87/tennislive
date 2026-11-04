import json,sys
T=json.load(open(sys.argv[1]))['ratio_to_stature']; M=json.loads(open(sys.argv[2]).read())
tgt={'acromialheight':T['acromialheight'],'trochanterionheight':T['trochanterionheight'],'kneeheightmidpatella':T['kneeheightmidpatella'],
 'biacromial_joints':T['biacromialbreadth']-0.038,'upperarm':T['acromionradialelength'],'forearm':T['radialestylionlength'],
 'chestbreadth':T['chestbreadth'],'chestdepth':T['chestdepth'],'waistbreadth':T['waistbreadth'],'waistdepth':T['waistdepth'],'hipbreadth':T['hipbreadth'],'buttockdepth':T['buttockdepth'],
 'headbreadth':T['headbreadth'],'headlength':T['headlength']}
for k,v in tgt.items(): print(f'{k:22s} model {M[k]:.3f}  target {v:.3f}  ratio {v/M[k]:.2f}')
import math
for k,c in [('thigh_d','thighcircumference'),('calf_d','calfcircumference'),('upperarm_d','bicepscircumferenceflexed'),('forearm_d','forearmcircumferenceflexed')]:
    if k in M: t=T[c]/math.pi; print(f'{k:22s} model {M[k]:.3f}  target {t:.3f}  ratio {t/M[k]:.2f}  (围度/π)')

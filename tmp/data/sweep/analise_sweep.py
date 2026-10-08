import struct,statistics as st,collections,sys,os
Z="/tmp/claude-1000/-home-leonardo-projects-renode-stm32f103-fidelity/28f2f499-b63b-4998-a02b-658081cab4a3/scratchpad/raw_zip/raw/"
D="/home/leonardo/projects/renode-stm32f103-fidelity/data/sweep/"
def rd(f):
    p=f if os.path.exists(f) else (D+f+".bin" if os.path.exists(D+f+".bin") else Z+f+".bin")
    b=open(p,'rb').read(); return struct.unpack('<%dI'%(len(b)//4),b)
def c1(f):
    a=rd(f); return [st.mean(a[i::7])/1000 for i in range(7)]
def c2(f):
    a=rd(f); cyc=a[0::2]; cnt=a[1::2]; d=[(cyc[i+1]-cyc[i])&0xffffffff for i in range(len(cyc)-1)]
    return dict(mean=round(st.mean(d),2),sd=round(st.pstdev(d),2),mode=collections.Counter(d).most_common(2),cnt=collections.Counter(cnt).most_common(2))
def c3(f):
    a=rd(f); p=[(a[i],a[i+1]>>16,a[i+1]&0x1ff) for i in range(0,len(a),2)]
    ids=collections.Counter(x[1] for x in p); tie=[x for x in p if x[1]==7]
    first=collections.Counter(tie[i][2] for i in range(0,len(tie)-1,2)); iv=collections.Counter(tie[i+1][0]-tie[i][0] for i in range(0,len(tie)-1,2))
    m5=[x[0] for x in p if x[1]==5]; m6=[x[0] for x in p if x[1]==6]
    b1=[x[0] for x in p if x[1]==1]; b1d=[b1[i+1]-b1[i] for i in range(len(b1)-1)]
    return dict(n=len(p),ids=dict(sorted(ids.items())),tie_first={'TIM2' if k==44 else 'TIM3':v for k,v in first.items()},tie_iv=iv.most_common(2),
                prim=m5[1]-m5[0] if len(m5)>1 else None, basep=m6[1]-m6[0] if len(m6)>1 else None, base_T3=collections.Counter(b1d).most_common(2))
def c4(f):
    a=rd(f); ts=a[:1024]; d=[(ts[i+1]-ts[i])&0xffffffff for i in range(1023)]
    return dict(mean=round(st.mean(d),2),med=st.median(d),sd=round(st.pstdev(d),2),mn=min(d),mx=max(d),tail=a[1024:1032])

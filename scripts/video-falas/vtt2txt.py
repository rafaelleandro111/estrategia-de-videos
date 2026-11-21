import re,sys,glob,os
# Converte VTT automatico do YouTube em blocos de ~20s com tempo inicial
for f in sorted(glob.glob(os.path.join(sys.argv[1],'*.pt-orig.vtt'))):
    vid=os.path.basename(f).split('.')[0]
    words=[]
    cur=None
    for line in open(f,encoding='utf-8'):
        m=re.match(r'(\d+):(\d+):([\d.]+) -->',line)
        if m:
            cur=int(m[1])*3600+int(m[2])*60+float(m[3]);continue
        if '<c>' in line or re.search(r'<\d\d:',line):
            # linha com timestamps por palavra
            parts=re.split(r'<(\d\d:\d\d:\d\d\.\d+)>',line)
            t=cur
            for i,p in enumerate(parts):
                if i%2==1:
                    h,mi,s=p.split(':');t=int(h)*3600+int(mi)*60+float(s)
                else:
                    for w in re.sub(r'</?c[^>]*>','',p).split():
                        words.append((t,w))
    out=[];blk=[];t0=None
    for t,w in words:
        if t0 is None:t0=t
        blk.append(w)
        if t-t0>20:
            out.append(f"[{int(t0//60)}:{int(t0%60):02d}] "+' '.join(blk));blk=[];t0=None
    if blk:out.append(f"[{int(t0//60)}:{int(t0%60):02d}] "+' '.join(blk))
    open(os.path.join(sys.argv[1],vid+'.txt'),'w',encoding='utf-8').write('\n'.join(out))
    print(vid,len(words))

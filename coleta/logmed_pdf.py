import subprocess, sys, csv, glob, os, io
import numpy as np
from PIL import Image
p=int(sys.argv[1])
subprocess.run(['pdftoppm','-f',str(p),'-l',str(p),'-r','400','-gray','-png','logmed.pdf','o'],check=True)
f=sorted(glob.glob('o-*.png'))[0]
im=Image.open(f).convert('L').rotate(-90,expand=True,fillcolor=255); os.remove(f)
a=np.array(im); dark=a<128
H,W=a.shape
rows=np.where(dark.mean(1)>0.4)[0]; cols=np.where(dark.mean(0)>0.4)[0]
a2=a.copy()
for r in rows: a2[max(0,r-4):r+5,:]=255
for c in cols: a2[:,max(0,c-4):c+5]=255
Image.fromarray(a2).save(f'c{p}.png')
# column boundaries: group vertical line x's
xs=[]; 
for c in cols:
    if not xs or c-xs[-1][-1]>9: xs.append([c])
    else: xs[-1].append(c)
xs=[int(np.mean(g)) for g in xs]
ys=[]
for r in rows:
    if not ys or r-ys[-1][-1]>9: ys.append([r])
    else: ys[-1].append(r)
ys=[int(np.mean(g)) for g in ys]
tsv=subprocess.run(['tesseract',f'c{p}.png','-','--psm','6','tsv'],capture_output=True,text=True).stdout
words=[w for w in csv.DictReader(io.StringIO(tsv),delimiter='\t',quoting=csv.QUOTE_NONE) if (w.get('text') or '').strip()]
# assign each word to cell (row band between ys, col between xs)
import bisect
cells={}
for w in words:
    x=int(w['left'])+int(w['width'])//2; y=int(w['top'])+int(w['height'])//2
    ri=bisect.bisect(ys,y); ci=bisect.bisect(xs,x)
    cells.setdefault((ri,ci),[]).append((y,x,w['text']))
out=[]
for ri in sorted({k[0] for k in cells}):
    row=[]
    for ci in range(1,len(xs)):
        ws=sorted(cells.get((ri,ci),[]),key=lambda t:(t[0]//28,t[1]))
        row.append(' '.join(t[2] for t in ws))
    import re as _re
    if row and (row[0].strip() in ('PR','PI','PE','RJ','RS') or any(_re.search(r'\d{5}-?\d{3}', c) for c in row)):
        if 0 < ri < len(ys) and len(xs) > 3:
            cell = Image.fromarray(a2[ys[ri-1]+6:ys[ri]-4, xs[2]+6:xs[3]-4])
            cell = cell.resize((cell.width*2, cell.height*2))
            cell.save('cell.png')
            t = subprocess.run(['tesseract','cell.png','-','--psm','6'],capture_output=True,text=True).stdout
            row[2] = ' | '.join(x.strip() for x in t.splitlines() if x.strip())
        out.append(row)
w=csv.writer(sys.stdout)
for r in out: w.writerow([p]+r)

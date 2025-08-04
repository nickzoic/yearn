from PIL import Image
import numpy as np

with open("dat/WORLD.MAP", "rb") as fh:
    world = fh.read(65536)

SCALE = 12

def tile(x, y):
    if 0 <= x <= 255 and 0 <= y <= 255:
        b = world[(y//32)*8192+(x//32)*1024+(y%32)*32+(x%32)]
        if b == 0x17: return 3
        if b == 9: return 8
        if b < 9: return b
        return 4
    return 0

def neighbours(x, y):
    return [
        tile(xx, yy)
        for xx in (x-1,x,x+1)
        for yy in (y-1,y,y+1)
    ]

def median(nn):
    nn = sorted(nn)
    if len(nn) % 2 == 0:
        return (nn[len(nn)//2-1] + nn[len(nn)//2]) / 2
    else:
        return (nn[len(nn)//2])

def interpolate(x,y,z0,z1,z2,z3):
    # bilinear interpolation
    w0 = (1-x)*(1-y)
    w1 = (1-x)*y
    w2 = x*(1-y)
    w3 = x*y
    return z0 * w0 + z1 * w1 + z2 * w2 + z3 * w3

def sliding(aa, size):
    aaa = np.pad(aa,size)
    for pos, _ in np.ndenumerate(aa):
        window = tuple(
            slice(p,p+2*size+1) 
            for p in pos
        )
        yield pos, aaa[window]
        
import matplotlib.pyplot as plt
import numpy

scale = 12

w = numpy.zeros((256*scale,256*scale))
for x in range(0,256):
    for y in range(0,256):
        w[y*scale:(y+1)*scale,x*scale:(x+1)*scale] = tile(x, y)

ww = numpy.zeros((256*scale,256*scale))
for pos, dat in sliding(w, scale//2):
    ww[pos] = median(dat.ravel())

aa = numpy.zeros((256*scale, 256*scale))

for x in range(1, 256*scale-1):
    for y in range(1, 256*scale-1):
        if ww[y, x] == 1:
            aa[y, x] = 80
        elif ww[y, x] == 2:
            aa[y, x] = 90
        elif ww[y,x] == 3:
            aa[y, x] = 100
        elif 4 <= ww[y, x] <= 6 and any(n <= 3 for n in ww[y-1:y+2, x-1:x+2].ravel()):
            aa[y, x] = 110

for i in range(100):
    ab = aa.copy()
    for pos, dat in sliding(aa, 1):
        if dat[1,1] == 0 and 4 <= ww[pos] <= 6:
            m = max(dat.ravel())
            if m > 0:
                print(i, m)
                ab[pos] = m + ww[pos] - 3
    aa = ab

plt.imshow(aa)
plt.show()

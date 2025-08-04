from PIL import Image
import numpy as np
import cProfile

with open("dat/WORLD.MAP", "rb") as fh:
    world = fh.read(65536)

def tile(x, y):
    if 0 <= x <= 255 and 0 <= y <= 255:
        b = world[(y//32)*8192+(x//32)*1024+(y%32)*32+(x%32)]
        if b == 0x17: return 3
        if b == 9: return 8
        if b < 9: return b
        return 4
    return 0

scale = 12
width = 256 * scale

w = bytearray()
for y in range(256):
    for _ in range(scale):
        for x in range(256):
            t = tile(x, y)
            w.extend([t] * scale)

span = scale // 2 + 1

def smooth(w):
    ww = w.copy()
    for x in range(span, width-span-1):
        for y in range(span, width-span-1):
            tt = [
                t
                for yy in range(y-span, y+span+1)
                for t in w[yy*width+x-span:yy*width+x+span+1]
            ]
            if all(t == tt[0] for t in tt[1:]):
                continue
            tt.sort()
            ww[y*width+x] = tt[len(tt)//2]
    
    return [
        ww[y*width:(y+1)*width]
        for y in range(width)
    ]

#cProfile.run("smooth(w)")

www = smooth(w)

import matplotlib.pyplot as plt
plt.imshow(www)
plt.show()

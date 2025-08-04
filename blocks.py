from collections import defaultdict
import glob

with open("dat/WORLD.MAP", "rb") as fh:
    world = fh.read(256*256)

count = defaultdict(int)
for block in world:
    count[block] += 1

print("WORLD:")

for k, v in sorted(count.items()):
    print("%02X %s" % (k, v))

count = defaultdict(int)

for filename in glob.glob("dat/*.ULT"):
    with open(filename, "rb") as fh:
        world = fh.read(32*32)
        for block in world:
            count[block] += 1

print("\nTOWNS:")

for k, v in sorted(count.items()):
    print("%02X %s" % (k, v))



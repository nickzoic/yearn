import sqlite3
import zstd
import random

# https://wiki.minetest.org/Games/Minetest_Game/Nodes

block_map = {
        "default:water_source": 0,
        "default:river_water_source": 1,
        "default:sand": 2,
        "default:dirt": 3,
        "default:dry_dirt": 4,
        "default:stone": 5,
        "default:stone_with_iron": 6,
        "default:stone_with_coal": 7,
        "default:lava": 8,
}

valid_blocks = set(block_map.values())

print(valid_blocks)

def u16(n):
    yield n >> 8 & 0xFF
    yield n & 0xFF

def u32(n):
    yield n >> 24 & 0xFF
    yield n >> 16 & 0xFF
    yield n >> 8 & 0xFF
    yield n & 0xFF

# see https://github.com/luanti-org/luanti/blob/master/doc/world_format.md#mapsqlite-1
# for database format details

def block_to_data(block):
    # block is a binary array of node IDs in ZYX order.
    assert type(block) is bytes
    assert len(block) == 4096

    # headers

    yield 14 # flags: generated, lighting expired, day_night_differs, NOT is_underground
    yield from u16(0) # lighting needs recomputing in all directions
    yield from u32(0xffffffff) # timestamp

    # block mapping: only bother including blocks present in
    # this sector.

    present_blocks = set(block)
    present_block_map = [ (k, v) for k, v in block_map.items() if v in present_blocks ]

    yield 0    # mapping version
    yield from u16(len(present_block_map)) # length of block map
    for k, v in present_block_map:
        yield from u16(v)
        yield from u16(len(k))
        yield from bytes(k, 'ascii')
    yield 2 # content_width
    yield 2 # params_width

    for b in block:
        yield from u16(b) # param0

    for b in block:
        yield 0           # param1

    for b in block:
        yield 0           # param2

    yield from u32(0)

    yield 10
    yield from u16(0)  # no timers


def block_to_binary(block):

    yield 29
    yield from zstd.compress(bytes(block_to_data(block)))


db = sqlite3.connect('/home/nick/.minetest/worlds/x/map.sqlite')

def write_block(x, y, z, block):
    pos = x * 4096 * 4096 + y + z * 4096
    data = bytes(block_to_binary(block))
    db.execute("insert or replace into blocks (pos, data) values (?, ?)", (pos, data))

with open('WORLD.MAP', 'rb') as fh:
    world = fh.read(65536)

#print(world)

for x1 in range(0,8):
    for y1 in range(0,8):
        for x2 in range(0,32):
            for y2 in range(0,32):
                x = x1*32+x2
                y = y1*32+y2
                n = world[y1*8192+x1*1024+y2*32+x2]
                print("%d %d %d %d => %d %d => %d" % (x1, y1, x2, y2, x, y, n))
                if n in valid_blocks:
                    write_block(x, y, 0, bytes([n]) * 4096)
        db.commit()

db.close()




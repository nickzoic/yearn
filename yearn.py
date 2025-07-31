import sqlite3
import zstd
import random
from collections import defaultdict

# The read format (Ultima IV) and write format (minetest) are so different that
# the easiest way to convert between them is an intermediate format. We could
# come up with a way to do this on-the-fly but RAM is cheap so let's store it
# all in bytes buffers, one byte per voxel.

# Axis conventions are from minetest:
#  X: West -> East
#  Y: Down -> Up
#  Z: South -> North
# https://docs.luanti.org/for-players/coordinates/
#
# All three axes are limited to ±30,000 or so:
# https://docs.luanti.org/for-players/world-boundaries/
#
# Minetest maps are broken into 16x16x16 "chunks" so we'll store them
# that way in memory as well.
# "The locations of each block in the chunk is given by ((z%16)*16*16 + (y%16)*16 + (x%16))"
# https://github.com/luanti-org/luanti/blob/master/doc/world_format.md#node-data
#
# The overhead of storing 1,000,000 or so chunks in separate buffers isn't much
# so let's do that. Unused chunks default to all zeros, which we can map to "air".

CHUNK = 16
CHUNK3 = CHUNK * CHUNK * CHUNK

World = defaultdict(lambda: bytearray(CHUNK3))

def set_block(x, y, z, b):
    chunk = World[(x//CHUNK,y//CHUNK,z//CHUNK)]
    chunk[(z%CHUNK)*CHUNK*CHUNK + (y%CHUNK)*CHUNK + (x%CHUNK)] = b

# Minetest uses "itemstrings" to describe its various blocks, we don't 
# want to store these so we keep a table translating them to byte values.

# available block types in the base game are listed at:
#     https://wiki.minetest.org/Games/Minetest_Game/Nodes
# for full representation of villages etc we might need
# to make some custom "letter blocks", etc.

block_map = {
        "air": 0,
        "default:stone": 1,
        "default:sand": 2,
        "default:dirt": 3,
}

# Add new block types as they get seen.

def get_block_byte(itemstring):
    return block_map.setdefault(itemstring, len(block_map))

# This maps the Ultima IV tile types to little stacks of Minetest
# blocks.

blocks_for_tile = {
        0: [ 'default:sand', 'default:water_source', 'default:water_source' ],
        1: [ 'default:sand', 'default:sand', 'default:water_source' ],
        2: [ 'default:sand', 'default:sand', 'default:sand_with_kelp' ],
        3: [ 'default:stone', 'default:dirt', 'default:dirt', 'default:junglegrass' ],
        4: [ 'default:stone', 'default:dirt', 'default:dirt_with_grass' ],
        5: [ 'default:stone', 'default:dirt', 'default:dirt_with_rainforest_litter' ],
        6: [ 'default:stone', 'default:dirt', 'default:dirt', 'default:dirt_with_coniferous_litter' ],
        7: [ 'default:stone', 'default:stone', 'default:stone', 'default:cobble' ],
        8: [ 'default:stone', 'default:stome', 'default:stone', 'default:stone', 'default:stone', 'default:snow' ],
        0x17: [ 'default:sand', 'default:water_source', 'default:water_source', 'air', 'default:stone' ],
        0x4C: [ 'default:lava' ] * 6
}

# The idea here is to integrate towns into the map so
# there's just a single map.  Towns have a 32x32 map size
# so the obvious thing would be to make each "world" 
# tile into a 32x32 area but that just seems a little
# too big a scale, so instead I think I'll make it 16 
# and the towns will just have to hang over into
# neighbouring tiles.

# mini world for now
SCALE = 5

with open("dat/WORLD.MAP", "rb") as fh:
    ultima_world = fh.read(256*256)

# the Ultima map is broken up into 8x8 chunks
# each of which is 32x32 tiles.

for tx in range(0, 256):
    print(tx)
    for ty in range(0, 256):
        tile = ultima_world[
            (ty // 32) * 8192 +
            (tx // 32) * 1024 +
            (ty % 32) * 32 +
            (tx % 32)
        ]
        blocks = blocks_for_tile.get(tile)
        if not blocks: continue
        for ox in range(SCALE):
            for oy in range(SCALE):
                for (oz, block) in enumerate(blocks):
                    bb = get_block_byte(block)
                    set_block(tx*SCALE+ox, oz, ty*SCALE+oy, bb)

for k, v in block_map.items():
    print(k,v)

valid_blocks = set(block_map.values())

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
    pos = z * 4096 * 4096 + y * 4096 + x
    data = bytes(block_to_binary(block))
    db.execute("insert or replace into blocks (pos, data) values (?, ?)", (pos, data))

for (x, y, z), bb in World.items():
    print(x,y,z)
    write_block(x, y, z, bb)

db.commit()
db.close()




import sqlite3
import zstd
import random
from collections import defaultdict
import random

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

# Load the Ultima IV world map into memory.  It's only 256x256 bytes!

with open("dat/WORLD.MAP", "rb") as fh:
    ultima_world = fh.read(256*256)

# This maps the Ultima IV tile types to little stacks of Minetest
# blocks.

blocks_for_tile = {
        0: lambda: [ 'default:sand', 'default:water_source', 'default:water_source' ],
        1: lambda: [ 'default:sand', 'default:sand', 'default:water_source' ],
        2: lambda: [ 'default:stone', 'default:sand', 'default:river_water_source' ],
        3: lambda: [ 'default:stone', 'default:dirt', 'default:dirt_with_grass' ],
        4: lambda: [ 'default:stone', 'default:dirt', 'default:dirt', 'default:dirt_with_grass' ],
        5: lambda: [ 'default:stone', 'default:dirt', 'default:dirt', 'default:dirt_with_rainforest_litter', random.choice(('default:junglegrass', 'default:junglegrass', 'default:junglesapling')) ],
        6: lambda: [ 'default:stone', 'default:dirt', 'default:gravel', 'default:dirt', 'default:dirt' ] + random.choices((['default:dirt'], ['default:dirt_with_coniferous_litter'], ['default:dirt', 'default:pine_sapling'], ['default:dirt', 'default:aspen_sapling']), (9,5,1,1))[0],
        7: lambda: [ 'default:stone' ] * random.randint(4,5),
        8: lambda: [ 'default:stone' ] * random.randint(8,12) + [ 'default:snow' ],
        0x16: lambda: [ 'default:stone' ] * 3 + [ 'default:cobble' ],
        0x17: lambda: [ 'default:stone', 'default:gravel', 'default:water_source', 'air', 'default:stone' ],
        0x3E: lambda: [ 'default:brick' ] * 4,
        0x4C: lambda: [ 'default:lava' ] * random.randint(8,10),
        0x7F: lambda: [ 'default:brick' ] * 8,
}

# The idea here is to integrate towns into the map so
# there's just a single map.  Towns have a 32x32 map size
# so the obvious thing would be to make each "world" 
# tile into a 32x32 area but that just seems a little
# too big a scale, so instead I think I'll make it 16 
# and the towns will just have to hang over into
# neighbouring tiles.

# XXX maybe even 12 is more like it, towns would then 
# overlap most of the tiles around them but that's okay.

SCALE = 5

# the Ultima map is broken up into 8x8 chunks
# each of which is 32x32 tiles.

for ty in range(0, 256):
    print(ty)
    for tx in range(0, 256):
        tile = ultima_world[
            (ty // 32) * 8192 +
            (tx // 32) * 1024 +
            (ty % 32) * 32 +
            (tx % 32)
        ]
        block_generator = blocks_for_tile.get(tile)
        if not block_generator:
            print("Unknown tile %02x at world (%d, %d)" % (tile, tx, ty))
            continue

        for ox in range(SCALE):
            for oy in range(SCALE):
                for (oz, block) in enumerate(block_generator()):
                    bb = get_block_byte(block)
                    set_block(tx*SCALE+ox, oz, ty*SCALE+oy, bb)

def read_town(map_name, x, y, z=0):
    with open(f"dat/{map_name}.ULT", "rb") as fh:
        ultima_town = fh.read(32*32)
        for tx in range(0,32):
            for ty in range(0,32):
                tile = ultima_town[ty*32+tx]
                block_generator = blocks_for_tile.get(tile)
                if not block_generator:
                    print("Unknown tile %02x at town %s (%d, %d)" % (tile, map_name, tx, ty))
                    continue
                for (oz, block) in enumerate(block_generator()):
                    bb = get_block_byte(block)
                    set_block(int((x+0.5)*SCALE)+tx, z + oz, int((y+0.5)*SCALE)+ty, bb)


read_town('LCB_1', 107, 86)
read_town('LCB_2', 107, 86, 10)
read_town('BRITAIN', 50, 50)

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




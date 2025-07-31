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

# Add new block types as they get seen.  The world chunk bytearrays 
# are initialized to all zeros, so we start with 0 mapped to "air".

block_map = {
        "air": 0,
}

def get_block_byte(itemstring):
    return block_map.setdefault(itemstring, len(block_map))

# Load the Ultima IV world map into memory.  It's only 256x256 bytes!

print("Loading World")

with open("dat/WORLD.MAP", "rb") as fh:
    ultima_world = fh.read(256*256)

# This maps the Ultima IV tile types to little stacks of Minetest
# blocks.

# XXX might have to be different for world and towns but worry about
# that later.

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
        0x16: lambda: [ 'default:cobble' ],
        0x17: lambda: [ 'default:stone', 'default:gravel', 'default:water_source', 'air', 'default:stone' ],
        0x1b: lambda: [ 'default:brick' ] + [ 'default:ladder_wood'] * 4,
        0x1c: lambda: [ 'default:ladder_wood' ] * 2,
        0x3a: lambda: [ 'default:brick', 'air', 'air', 'air', 'default:brick', 'default:brick' ],
        0x3b: lambda: [ 'default:brick', 'air', 'air', 'air', 'default:brick', 'default:brick' ],
        0x37: lambda: [ 'default:stone', 'default:slab_cobble' ],
        0x39: lambda: [ 'default:stone', 'default:cobble' ],

        0x3D: lambda: [ 'default:diamondblock' ] * 10,
        0x3E: lambda: [ 'default:brick' ],
        0x46: lambda: [ 'default:obsidian_block'] * 6,
        0x4C: lambda: [ 'default:lava' ] * random.randint(8,10),
        0x6c: lambda: [ 'default:glass' ] * 6,
        0x6d: lambda: [ 'default:glass' ] * 6,
        0x7F: lambda: [ 'default:brick' ] * 6,
}

default_blocks_for_tile = lambda: [ 'default:goldblock' ] * 4

# The idea here is to integrate towns into the map so
# there's just a single map.  Towns have a 32x32 map size
# so the obvious thing would be to make each "world" 
# tile into a 32x32 area but that just seems a little
# too big a scale, so instead I think I'll make it 
# smaller and the towns will just have to hang over into
# neighbouring tiles.

# With scale=12, towns overlap most of the tiles around them,
# but it looks about right. 

SCALE = 12

# the Ultima map is broken up into 8x8 chunks
# each of which is 32x32 tiles.
# X axis runs West -> East
# Y axis runs North -> South, which is the opposite direction
# to the minetest Z axis.

print("Processing World (scale %d) ..." % SCALE)

unknown_tiles = defaultdict(int)

progress = 0

for ty in range(0, 256):
    percent = 100 * ty // 256
    if percent > progress + 4:
        print("... %d%%" % percent)
        progress = percent
    
    for tx in range(0, 256):
        tile = ultima_world[
            (ty // 32) * 8192 +
            (tx // 32) * 1024 +
            (ty % 32) * 32 +
            (tx % 32)
        ]
        block_generator = blocks_for_tile.get(tile)
        if not block_generator:
            unknown_tiles[tile] += 1
            block_generator = default_blocks_for_tile

        for ox in range(SCALE):
            for oy in range(SCALE):
                for (oz, block) in enumerate(block_generator()):
                    bb = get_block_byte(block)
                    set_block(tx*SCALE+ox, oz, (256*SCALE)-(ty*SCALE+oy), bb)


# towns are a single 32x32 chunk of tiles

def read_town(map_name, x, y, z=4):
    xo = x * SCALE + SCALE//2 - 16
    yo = (255-y) * SCALE + SCALE//2 + 16
    with open(f"dat/{map_name}.ULT", "rb") as fh:
        ultima_town = fh.read(32*32)
        for tx in range(0,32):
            for ty in range(0,32):
                tile = ultima_town[ty*32+tx]
                block_generator = blocks_for_tile.get(tile)
                if not block_generator:
                    unknown_tiles[tile] += 1
                    continue
                for (oz, block) in enumerate(block_generator()):
                    bb = get_block_byte(block)
                    set_block(xo + tx, z + oz, yo - ty, bb)
    print("... %s at (%d, %d)" % (map_name, x * SCALE, (255-y) * SCALE))

# locations based on ...
# https://tartarus.rpgclassics.com/ultima4/worldmap.php
# ... but some of these were off by a couple in whatever direction

print("Adding Towns ...")

read_town('LCB_1', 86, 107)
read_town('LCB_2', 86, 107, 10)
read_town('BRITAIN', 82, 106)
read_town('MOONGLOW', 232, 135)
read_town('JHELOM', 36, 222)
read_town('YEW', 58, 43)
read_town('MINOC', 159, 20)
read_town('TRINSIC', 106, 184)
read_town('SKARA', 22, 128)
read_town('MAGINCIA', 187, 169)
read_town('DEN', 136, 158)
read_town('COVE', 136, 90)
read_town('PAWS', 98, 145)
read_town('VESPER', 201, 59)
read_town('LYCAEUM', 218, 107)
read_town('EMPATH', 28, 50)
read_town('SERPENT', 146, 241)

# XXX need something for dungeons
#
# WRONG 126, 20
# COVETOUS 156, 27
# DESPISE 91, 67
# DECEIT 240, 73
# SHAME 58, 102
# DESTARD 72, 168
# HYTHLOTH 239, 240

# XXX need something for shrines
#
# HONESTY 233, 66
# COMPASSION 128,92
# VALOR 38, 227
# JUSTICE 73, 11
# SACRIFICE 205, 45
# HONOR 81, 207
# SPIRITUALITY 166, 19 ?
# HUMILITY 231, 215
# AVATAR 231, 235

print("Materials Used:")

for k, v in block_map.items():
    print("  %d %s" % (v, k))

print("Unknown Tiles Found:")

for k, v in sorted(unknown_tiles.items()):
    print("  %02x %d" % (k, v))

# ============================================================
# LUANTI / MINETEST FILE FORMAT STUFF

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
    yield 2 # content_width (always 2)
    yield 2 # params_width  (always 2)

    for b in block:
        yield from u16(b) # param0

    for b in block:
        yield 0           # param1

    for b in block:
        yield 0           # param2

    yield from u32(0)

    yield 10             # timer record size (always 10)
    yield from u16(0)  # no timers


def block_to_binary(block):
    yield 29              # chunk version number
    yield from zstd.compress(bytes(block_to_data(block)))

db = sqlite3.connect('/home/nick/.minetest/worlds/x/map.sqlite')

def write_block(x, y, z, block):
    pos = z * 4096 * 4096 + y * 4096 + x
    data = bytes(block_to_binary(block))
    db.execute("insert or replace into blocks (pos, data) values (?, ?)", (pos, data))

print("Writing %d blocks ..." % len(World))
progress = 0
for n, ((x, y, z), bb) in enumerate(World.items()):
    percent = 100 * n // len(World)
    write_block(x, y, z, bb)
    if percent > progress + 4:
        db.commit()
        print("... %d%%" % percent)
        progress = percent
print("Done.")

db.commit()
db.close()




"""Unpack / pack Sobixel projects (.sobixel = zip) and add Lua scripts.

  python3 pack_sobixel.py unpack SboxB.sobixel proj/
  python3 pack_sobixel.py script proj/ 23 "My game" game.lua      # minify game.lua into Scripts/Script23
  python3 pack_sobixel.py pack proj/ MyGame.sobixel

`script` wraps the Lua file into a script with one onStart event and one
requestApi block (one line, validated by luamin.py), adds the id to
game.json "scripts" and to the first script folder. `pack` writes the zip
the way Sobixel does: entry order, version made by 0x0314, deflate for
files, stored directories, unix attributes, no extra fields.
"""
import json
import os
import struct
import sys
import time
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import luamin  # noqa: E402

DIR_ATTR, FILE_ATTR = 0x41c00000, 0x81800000


def jdump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def unpack(src, out):
    with zipfile.ZipFile(src) as z:
        for i in z.infolist():
            p = os.path.join(out, i.filename)
            if i.is_dir():
                os.makedirs(p, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(z.read(i))
    for d in ('Scenes', 'Resources', 'Levels', 'Images', 'Sounds', 'Fonts', 'Videos', 'Scripts'):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    print('unpacked into', out)


def add_script(proj, sid, title, lua_path):
    code = luamin.minify(open(lua_path).read(), lua_path)
    sc = {'title': title, 'funs': [], 'tables': [], 'vars': [], 'comment': False, 'params': [
        {'tables': [], 'vars': [], 'name': 'onStart', 'event': True, 'nested': [], 'comment': False,
         'params': [[[title, 't']]]},
        {'name': 'requestApi', 'event': False, 'comment': False, 'params': [[[code, 't']]]}]}
    open(os.path.join(proj, 'Scripts', 'Script%d' % sid), 'wb').write(jdump(sc))
    gp = os.path.join(proj, 'game.json')
    g = json.load(open(gp, encoding='utf-8'))
    if sid not in g['scripts']:
        g['scripts'].append(sid)
    folders = g.setdefault('folders', {}).setdefault('scripts', [['1', [], False]])
    if not any(sid in f[1] for f in folders):
        folders[0][1].append(sid)
    open(gp, 'wb').write(jdump(g))
    print('Script%d: %d chars of Lua' % (sid, len(code)))


def num(name):
    digits = ''.join(c for c in name if c.isdigit())
    return int(digits) if digits else 0


def listing(proj):
    def files(d):
        p = os.path.join(proj, d)
        if not os.path.isdir(p):
            return []
        return sorted((f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f))), key=num)
    out = []
    scenes = os.path.join(proj, 'Scenes')
    for sc in sorted(os.listdir(scenes)) if os.path.isdir(scenes) else []:
        if os.path.isdir(os.path.join(scenes, sc)):
            out.append(('Scenes/%s/' % sc, None))
            for f in sorted(os.listdir(os.path.join(scenes, sc))):
                out.append(('Scenes/%s/%s' % (sc, f), os.path.join(scenes, sc, f)))
    out.append(('Scenes/', None))
    for d in ('Resources', 'Levels', 'Images', 'Sounds', 'Fonts', 'Videos', 'Scripts'):
        for f in files(d):
            out.append(('%s/%s' % (d, f), os.path.join(proj, d, f)))
        out.append(('%s/' % d, None))
    for f in ('game.json', 'hash.txt', 'custom.json', 'icon.png'):
        if os.path.exists(os.path.join(proj, f)):
            out.append((f, os.path.join(proj, f)))
    return out


def pack(proj, dst):
    lt = time.localtime()
    dtime = (lt.tm_hour << 11) | (lt.tm_min << 5) | (lt.tm_sec // 2)
    ddate = ((lt.tm_year - 1980) << 9) | (lt.tm_mon << 5) | lt.tm_mday
    parts, central, offset = [], [], 0
    for name, path in listing(proj):
        nb = name.encode('utf-8')
        if path is None:
            method, comp, crc, usize, attr = 0, b'', 0, 0, DIR_ATTR
        else:
            data = open(path, 'rb').read()
            usize, crc, attr = len(data), zlib.crc32(data) & 0xffffffff, FILE_ATTR
            if usize == 0:
                method, comp = 0, b''
            else:
                c = zlib.compressobj(6, zlib.DEFLATED, -15, 8)
                method, comp = 8, c.compress(data) + c.flush()
        hdr = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0, method, dtime, ddate, crc, len(comp), usize, len(nb), 0)
        parts.append(hdr + nb + comp)
        central.append(struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 0x0314, 20, 0, method, dtime, ddate, crc,
                                   len(comp), usize, len(nb), 0, 0, 0, 0, attr, offset) + nb)
        offset += len(hdr) + len(nb) + len(comp)
    cd = b''.join(central)
    eocd = struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, len(central), len(central), len(cd), offset, 0)
    open(dst, 'wb').write(b''.join(parts) + cd + eocd)
    print('packed %s (%d entries)' % (dst, len(central)))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == 'unpack':
        unpack(a[1], a[2])
    elif len(a) >= 5 and a[0] == 'script':
        add_script(a[1], int(a[2]), a[3], a[4])
    elif len(a) >= 3 and a[0] == 'pack':
        pack(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(1)

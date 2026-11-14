#!/usr/bin/env python3
"""Android boot image (header v0) unpack/repack + gzip/lz4 ramdisk + cpio (newc) tools.
MTK 6735/6737 boot images: header v0 (magic, 8 size/addr fields, unused[2], name[16], cmdline[512], id[32]),
page size 2048, kernel area may be gzip(kernel)+appended DTB, and a 4096-byte MTK signature block follows
the ramdisk. Usage:
  python bootimg.py unpack <boot.img> <outdir>
  python bootimg.py repack <outdir> <out.img> [gzip|lz4|none] [--partition <bytes>]
  python bootimg.py info <boot.img>
"""
import struct, os, sys, gzip, io, subprocess, zlib

PAGE = 2048


def read_boot(path):
    with open(path, 'rb') as f:
        d = f.read()
    assert d[:8] == b'ANDROID!', f'bad magic {d[:8]!r}'
    ks, ka, rs, ra, ss, sa, ta, ps, un1, un2 = struct.unpack('<10I', d[8:48])
    name = d[48:64].split(b'\0')[0].decode('latin1')
    cmdline = d[64:64+512].split(b'\0')[0].decode('latin1')
    id_ = d[576:608].hex()
    def pagesz(n):
        return ((n + ps - 1) // ps) * ps
    off = ps
    kernel = d[off:off+ks]; off += pagesz(ks)
    ramdisk = d[off:off+rs]; off += pagesz(rs)
    second = d[off:off+ss]; off += pagesz(ss)
    sig = d[off:off+4096]
    return dict(kernel=kernel, ramdisk=ramdisk, second=second, name=name, cmdline=cmdline,
                id=id_, page_size=ps, unused=(un1, un2),
                addr=dict(kernel=ka, ramdisk=ra, second=sa, tags=ta),
                sig=sig, total=len(d))


def write_boot(out, b, append_pad=0):
    page_size = b['page_size']
    ks, rs, ss = len(b['kernel']), len(b['ramdisk']), len(b['second'])
    def pagesz(n):
        return ((n + page_size - 1) // page_size) * page_size
    un1, un2 = b.get('unused', (0, 0))
    hdr = b'ANDROID!' + struct.pack('<10I', ks, b['addr']['kernel'], rs, b['addr']['ramdisk'],
                                    ss, b['addr']['second'], b['addr']['tags'], page_size, un1, un2)
    hdr += b['name'].encode('latin1').ljust(16, b'\0')[:16]
    hdr += b['cmdline'].encode('latin1').ljust(512, b'\0')[:512]
    hdr += bytes.fromhex(b['id']) if len(b['id']) == 64 else b'\0' * 32
    hdr = hdr.ljust(page_size, b'\0')
    data = hdr + b['kernel'] + b'\0' * (pagesz(ks) - ks) + b['ramdisk'] + b'\0' * (pagesz(rs) - rs)
    if ss:
        data += b['second'] + b'\0' * (pagesz(ss) - ss)
    if b.get('sig'):
        data += b['sig']
    if append_pad > len(data):
        data += b'\0' * (append_pad - len(data))
    open(out, 'wb').write(data)
    return len(data)


# ---------- ramdisk decompress / compress ----------
def decompress_ramdisk(data):
    if data[:2] == b'\x1f\x8b':
        o = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = o.decompress(data)
        return 'gzip', out, o.unused_data
    if data[:4] in (b'\x02\x21\x4c\x18', b'\x04\x22\x4d\x18'):
        return 'lz4', subprocess.run(['lz4', '-d', '-c'], input=data, capture_output=True).stdout, b''
    if data[:6] == b'\xfd7zXZ\x00':
        return 'xz', __import__('lzma').decompress(data), b''
    if data[:4] == b'\x28\xb5\x2f\xfd':
        return 'zstd', subprocess.run(['zstd', '-d', '-c'], input=data, capture_output=True).stdout, b''
    return 'raw', data, b''


def compress_ramdisk(data, comp):
    if comp == 'gzip':
        return gzip.compress(data, 9)
    if comp == 'lz4':
        return subprocess.run(['lz4', '-l', '-9', '-c'], input=data, capture_output=True).stdout
    if comp == 'xz':
        return __import__('lzma').compress(data)
    return data


# ---------- cpio newc ----------
def cpio_list(data):
    out, i = [], 0
    while True:
        if data[i:i+6] not in (b'070701', b'070702'):
            raise ValueError(f'bad cpio magic at {i}: {data[i:i+8]!r}')
        hdr = data[i:i+110]
        f = [int(hdr[6+j*8:6+j*8+8], 16) for j in range(13)]
        ino, mode, uid, gid, nlink, mtime, filesize, devmajor, devminor, rdevmajor, rdevminor, namesize, check = f
        name = data[i+110:i+110+namesize-1].decode('utf-8', 'surrogateescape')
        off = (i + 110 + namesize + 3) & ~3
        filedata = data[off:off+filesize]
        off = (off + filesize + 3) & ~3
        out.append(dict(name=name, mode=mode, uid=uid, gid=gid, mtime=mtime, data=filedata,
                        ino=ino, nlink=nlink, devmajor=devmajor, devminor=devminor,
                        rdevmajor=rdevmajor, rdevminor=rdevminor))
        i = off
        if name == 'TRAILER!!!':
            break
    return out


def cpio_pack(entries):
    buf = io.BytesIO()
    def w(name, mode, data=b'', ino=0, nlink=1, mtime=0, uid=0, gid=0, devmajor=0, devminor=0, rdevmajor=0, rdevminor=0):
        namez = name.encode('utf-8', 'surrogateescape') + b'\0'
        hdr = b'070701' + b''.join(f'{x:08x}'.encode() for x in (
            ino, mode, uid, gid, nlink, mtime, len(data), devmajor, devminor, rdevmajor, rdevminor, len(namez), 0))
        buf.write(hdr); buf.write(namez)
        p = buf.tell() & 3
        if p: buf.write(b'\0' * (4 - p))
        buf.write(data)
        p = buf.tell() & 3
        if p: buf.write(b'\0' * (4 - p))
    for idx, e in enumerate(entries):
        w(e['name'], e['mode'], e['data'], ino=e.get('ino') or idx+1, nlink=e.get('nlink', 1),
          mtime=e['mtime'], uid=e['uid'], gid=e['gid'], devmajor=e.get('devmajor', 0),
          devminor=e.get('devminor', 0), rdevmajor=e.get('rdevmajor', 0), rdevminor=e.get('rdevminor', 0))
    w('TRAILER!!!', 0)
    return buf.getvalue()


def unpack_cpio(data, outdir):
    ents = cpio_list(data)
    os.makedirs(outdir, exist_ok=True)
    for e in ents:
        name = e['name']
        if name == 'TRAILER!!!':
            continue
        rel = name.rstrip('/')
        p = os.path.join(outdir, rel.replace('/', os.sep))
        if name.endswith('/') or (e['mode'] & 0o170000) == 0o040000:
            os.makedirs(p, exist_ok=True)
        elif (e['mode'] & 0o170000) == 0o120000:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if os.path.lexists(p): os.unlink(p)
            os.symlink(e['data'].decode('latin1'), p)
        elif (e['mode'] & 0o170000) == 0o020000:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not os.path.exists(p):
                open(p, 'wb').close()
        else:
            os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
            with open(p, 'wb') as f:
                f.write(e['data'])
            os.chmod(p, e['mode'] & 0o7777)
    return ents


def pack_dir_cpio(root, base=''):
    entries = []
    def walk(rel):
        full = os.path.join(root, rel) if rel else root
        for n in sorted(os.listdir(full)):
            r = os.path.join(rel, n) if rel else n
            f = os.path.join(root, r)
            st = os.lstat(f)
            nm = r.replace(os.sep, '/')
            if os.path.islink(f):
                target = os.readlink(f)
                if target.startswith('/'):  # keep absolute symlinks as-is (cpio data holds target)
                    pass
                entries.append(dict(name=nm, mode=0o120777, uid=0, gid=0, mtime=int(st.st_mtime),
                                    data=target.encode('latin1'), nlink=1))
            elif os.path.isdir(f):
                entries.append(dict(name=nm + '/', mode=0o040000 | (st.st_mode & 0o7777), uid=0, gid=0,
                                    mtime=int(st.st_mtime), data=b'', nlink=2))
                walk(r)
            elif os.path.isfile(f):
                data = open(f, 'rb').read()
                mode = 0o100000 | (st.st_mode & 0o7777)
                entries.append(dict(name=nm, mode=mode, uid=0, gid=0, mtime=int(st.st_mtime),
                                    data=data, nlink=1))
    walk(base)
    return cpio_pack(entries)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'unpack':
        path, outdir = sys.argv[2], sys.argv[3]
        b = read_boot(path)
        os.makedirs(outdir, exist_ok=True)
        open(os.path.join(outdir, 'kernel'), 'wb').write(b['kernel'])
        if b['second']:
            open(os.path.join(outdir, 'second'), 'wb').write(b['second'])
        open(os.path.join(outdir, 'sig'), 'wb').write(b['sig'])
        with open(os.path.join(outdir, 'info.txt'), 'w') as f:
            f.write(f"name={b['name']}\ncmdline={b['cmdline']}\npage={b['page_size']}\n"
                    f"addr={b['addr']}\nunused={b['unused']}\nid={b['id']}\n"
                    f"kernel_size={len(b['kernel'])}\nramdisk_size={len(b['ramdisk'])}\n"
                    f"sig_size={len(b['sig'])}\ntotal={b['total']}\n")
        comp, rd, tail = decompress_ramdisk(b['ramdisk'])
        open(os.path.join(outdir, 'ramdisk.' + comp), 'wb').write(b['ramdisk'])
        if tail:
            open(os.path.join(outdir, 'ramdisk_tail.bin'), 'wb').write(tail)
        os.makedirs(os.path.join(outdir, 'ramdisk'), exist_ok=True)
        ents = unpack_cpio(rd, os.path.join(outdir, 'ramdisk'))
        print(f'{path}: comp={comp} entries={len(ents)} kernel={len(b["kernel"])} '
              f'ramdisk={len(b["ramdisk"])} sig={len(b["sig"])} total={b["total"]}')
    elif cmd == 'info':
        path = sys.argv[2]
        b = read_boot(path)
        comp, rd, tail = decompress_ramdisk(b['ramdisk'])
        print(f"name={b['name']!r} cmdline={b['cmdline']!r} page={b['page_size']} addr={b['addr']}")
        print(f"kernel={len(b['kernel'])} (gzip? {b['kernel'][:2] == b'\x1f\x8b'}) ramdisk={len(b['ramdisk'])} "
              f"comp={comp} entries={len(cpio_list(rd))} sig={len(b['sig'])} total={b['total']}")
    elif cmd == 'repack':
        src_dir, out = sys.argv[2], sys.argv[3]
        info = {}
        for line in open(os.path.join(src_dir, 'info.txt')):
            k, v = line.rstrip('\n').split('=', 1)
            info[k] = v
        b = dict(kernel=open(os.path.join(src_dir, 'kernel'), 'rb').read(),
                 second=open(os.path.join(src_dir, 'second'), 'rb').read() if os.path.exists(os.path.join(src_dir, 'second')) else b'',
                 name=info['name'], cmdline=info['cmdline'], id=info.get('id', ''),
                 page_size=int(info['page']), addr=eval(info['addr']),
                 sig=open(os.path.join(src_dir, 'sig'), 'rb').read() if os.path.exists(os.path.join(src_dir, 'sig')) else b'')
        if 'unused' in info:
            b['unused'] = tuple(eval(info['unused']))
        rd = pack_dir_cpio(os.path.join(src_dir, 'ramdisk'))
        comp = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else 'gzip'
        rd_c = compress_ramdisk(rd, comp)
        b['ramdisk'] = rd_c
        pad = 0
        for i, a in enumerate(sys.argv):
            if a == '--partition' and i + 1 < len(sys.argv):
                pad = int(sys.argv[i+1], 0)
        n = write_boot(out, b, pad)
        print(f'wrote {out}: {n} bytes (kernel={len(b["kernel"])} ramdisk={len(rd_c)} comp={comp})')
    elif cmd == 'repack-with-kernel':
        # repack using kernel/sig from one unpack dir and ramdisk from another
        info_dir, rd_dir, out = sys.argv[2], sys.argv[3], sys.argv[4]
        info = {}
        for line in open(os.path.join(info_dir, 'info.txt')):
            k, v = line.rstrip('\n').split('=', 1)
            info[k] = v
        b = dict(kernel=open(os.path.join(info_dir, 'kernel'), 'rb').read(),
                 second=b'', name=info['name'], cmdline=info['cmdline'], id=info.get('id', ''),
                 page_size=int(info['page']), addr=eval(info['addr']),
                 sig=open(os.path.join(info_dir, 'sig'), 'rb').read(),
                 unused=tuple(eval(info['unused'])) if 'unused' in info else (0, 0))
        comp = 'gzip'
        rd_c = compress_ramdisk(pack_dir_cpio(os.path.join(rd_dir, 'ramdisk')), comp)
        b['ramdisk'] = rd_c
        n = write_boot(out, b)
        print(f'wrote {out}: {n} bytes')
    else:
        print(__doc__)

# test append

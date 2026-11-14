#!/usr/bin/env python3
"""Build v3: UleFone 'power' LineageOS 14.1 (7.1.2, arm64, FULL Chinese, MT6735,
kernel 3.18.19) system tree + our stock 6.0 kernel/dtb + adapted donor ramdisk.
"""
import os, re, io, sys, json, shutil, stat

W = 'E:/刷机/YUXIN K01/Work'
SRC = os.path.join(W, 'recon/power_system')
STOCK = os.path.join(W, 'recon/stock_system')
DST = os.path.join(W, 'rom/v3/system')
DONOR_SCRIPT = os.path.join(W, 'recon/tmp/power_updater-script')
DONOR_BOOT = os.path.join(W, 'recon/tmp/power_boot.img')
OUR_BOOT = os.path.join(W, 'rom/build/boot.img')

sys.path.insert(0, os.path.join(W, 'tools'))
import bootimg


def shutil_rm(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.unlink(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)


# ---------------------------------------------------------------- ramdisk
def build_boot():
    b_our = bootimg.read_boot(OUR_BOOT)
    b_don = bootimg.read_boot(DONOR_BOOT)
    comp, rd, tail = bootimg.decompress_ramdisk(b_don['ramdisk'])
    ents = bootimg.cpio_list(rd)
    n_fstab = n_usb = n_prop = 0
    for e in ents:
        if e['name'] in ('fstab.mt6735', 'fstab.mt6753'):
            t = e['data'].decode('utf-8', 'replace')
            t2 = t.replace('mtk-msdc.0/11230000.msdc0/by-name', 'mtk-msdc.0/by-name')
            e['data'] = t2.encode('utf-8')
            if t2 != t:
                n_fstab += 1
                print('fstab adapted:', e['name'])
        elif e['name'] == 'init.mt6735.usb.rc':
            t = e['data'].decode('utf-8', 'replace')
            # adb block -> composite 18D1:4EE2
            i = t.find('on property:sys.usb.config=adb\n')
            if i >= 0:
                j = t.index('\n\n', i)
                blk = t[i:j].replace('idVendor 0BB4', 'idVendor 18D1').replace('idProduct 0C01', 'idProduct 4EE2').replace('functions ${sys.usb.config}', 'functions mtp,adb')
                t = t[:i] + blk + t[j:]
                n_usb += 1
            i = t.find('on property:sys.usb.config=mtp,adb\n')
            if i >= 0:
                j = t.index('\n\n', i)
                blk = t[i:j].replace('idVendor 0BB4', 'idVendor 18D1').replace('idProduct 0C02', 'idProduct 4EE2')
                t = t[:i] + blk + t[j:]
                n_usb += 1
            e['data'] = t.encode('utf-8')
        elif e['name'] == 'default.prop':
            t = e['data'].decode('utf-8', 'replace')
            add = []
            for line in ['ro.adb.secure=0', 'persist.sys.usb.config=mtp,adb', 'service.adb.tcp.port=5555']:
                if line.split('=')[0] not in t:
                    add.append(line)
            if add:
                t = t.rstrip() + '\n' + '\n'.join(add) + '\n'
                e['data'] = t.encode('utf-8')
                n_prop += 1
    print('usb rc patched blocks:', n_usb, 'prop patched:', n_prop)
    newrd = bootimg.cpio_pack(ents)
    rb = dict(b_our)
    rb['ramdisk'] = bootimg.compress_ramdisk(newrd, 'gzip')
    rb['cmdline'] = 'bootopt=64S3,32N2,64N2 androidboot.selinux=permissive androidboot.hardware=mt6735'
    out = os.path.join(W, 'rom/v3/boot.img')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bootimg.write_boot(out, rb, append_pad=16777216)
    print('boot_v3 written', os.path.getsize(out), 'cmdline', rb['cmdline'])
    return out


# ---------------------------------------------------------------- manifest
def build_manifest():
    """Parse donor updater-script metadata + apply our overrides."""
    script = open(DONOR_SCRIPT, encoding='utf-8', errors='replace').read()
    links = []   # (target, linkpath_under_system)
    for m in re.finditer(r'symlink\(([^;]*?)\);', script):
        args = re.findall(r'"([^"]*)"', m.group(1))
        if not args:
            continue
        target = args[0]
        for lp in args[1:]:
            rel = lp
            if rel.startswith('/system/'):
                rel = rel[len('/system/'):]
            else:
                rel = rel.lstrip('/')
            links.append((target, rel))
    print('symlink lines parsed:', len(links))
    meta = {}  # path -> dict(uid,gid,mode,selabel)
    for m in re.finditer(r'set_metadata\("([^"]+)",([^;]*?)\);', script):
        path, opts = m.group(1), m.group(2)
        d = {}
        for k, v in re.findall(r'"(\w+)",\s*"?([^",]+)"?', opts):
            d[k] = v
        mode = int(d['mode'], 8) if 'mode' in d else 0o644
        meta[path] = dict(uid=int(d.get('uid', 0)), gid=int(d.get('gid', 0)), mode=mode,
                          selabel=d.get('selabel', 'u:object_r:system_file:s0'))
    print('set_metadata entries:', len(meta))
    # defaults by rule
    def default_for(rel):
        p = '/' + rel
        mode, gid, sel = 0o644, 0, 'u:object_r:system_file:s0'
        if rel.startswith(('bin/', 'xbin/', 'sbin/', 'usr/')):
            mode, gid = 0o755, 2000
        elif rel.startswith('etc/init.d/'):
            mode, gid, sel = 0o755, 2000, 'u:object_r:userinit_exec:s0'
        elif rel.startswith('vendor/lib') or rel.startswith('vendor/etc'):
            gid = 2000
        return mode, gid, sel
    entries = []
    have = set()
    # dirs
    for root, dirs, files in os.walk(DST):
        for d in dirs:
            full = os.path.join(root, d)
            rel = os.path.relpath(full, DST).replace(os.sep, '/')
            entries.append(dict(path='/' + rel, mode=0o755, uid=0, gid=0, size=0, type='dir',
                                selinux='u:object_r:system_file:s0'))
            have.add('/' + rel)
    # symlinks (create in tree) + entries
    conv = {0o120777: 'link'}
    for target, rel in links:
        lp = '/system/' + rel
        dest = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            if os.path.islink(dest) or os.path.isfile(dest):
                os.unlink(dest)
            else:
                shutil.rmtree(dest)
        try:
            os.symlink(target, dest)
        except OSError as e:
            print('symlink fail', rel, e)
            continue
        entries.append(dict(path=lp, mode=0o777, uid=0, gid=0, size=0, type='symlink',
                            target=target, selinux='u:object_r:system_file:s0'))
        have.add(lp)
    # files
    for root, dirs, files in os.walk(DST):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, DST).replace(os.sep, '/')
            p = '/' + rel
            if p in have:
                continue
            if p in meta:
                mm = meta[p]
                mode, gid, sel = mm['mode'], mm['gid'], mm['selabel']
                uid = mm['uid']
            else:
                mode, gid, sel = default_for(rel)
                uid = 0
            entries.append(dict(path=p, mode=mode, uid=uid, gid=gid, size=0, type='file', selinux=sel))
            have.add(p)
    # our added files: Via / Xunfei / init.d handled by default rules; ensure init.d selabel
    for e in entries:
        if e['path'].startswith('/etc/init.d/'):
            e['mode'] = 0o755
            e['gid'] = 2000
            e['selinux'] = 'u:object_r:userinit_exec:s0'
        if e['path'].startswith('/etc/init.d'):
            e['mode'] = 0o755
    man = os.path.join(W, 'rom/v3/manifest.json')
    json.dump(entries, open(man, 'w', encoding='utf-8'), ensure_ascii=False)
    print('manifest entries:', len(entries), '->', man)
    return man


def main():
    if not os.path.isdir(SRC):
        raise SystemExit('missing donor tree ' + SRC)
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    print('copy donor tree...')
    shutil.copytree(SRC, DST, symlinks=True)
    os.makedirs(os.path.join(W, 'rom/v3'), exist_ok=True)

    # delete unwanted
    for rel in ['app/Camera2', 'app/MtkCamera', 'priv-app/Gallery2', 'app/Gallery2',
                'priv-app/Camera2', 'app/Browser', 'app/Jelly',
                'lib/hw/camera.mt6735.so', 'lib64/hw/camera.mt6735.so',
                'recovery-from-boot.p', 'bin/install-recovery.sh', 'addon.d/50-cm.sh']:
        shutil_rm(os.path.join(DST, rel))

    # stock firmware / thermal (kernel-paired)
    for rel in ['etc/firmware', 'etc/.tp']:
        src = os.path.join(STOCK, rel)
        dst = os.path.join(DST, rel)
        if os.path.isdir(src):
            shutil_rm(dst)
            shutil.copytree(src, dst, symlinks=True)
            print('stock ->', rel)

    # apps + init.d
    os.makedirs(os.path.join(DST, 'app/Via'), exist_ok=True)
    shutil.copy2(os.path.join(W, 'tools/Via.apk'), os.path.join(DST, 'app/Via/Via.apk'))
    xd = os.path.join(DST, 'app/XunfeiInputWear')
    os.makedirs(os.path.join(xd, 'lib/armeabi'), exist_ok=True)
    shutil.copy2(os.path.join(W, 'tools/XunfeiInputWear.apk'), os.path.join(xd, 'XunfeiInputWear.apk'))
    import zipfile
    z = zipfile.ZipFile(os.path.join(W, 'tools/XunfeiInputWear.apk'))
    for n in z.namelist():
        if n.startswith('lib/armeabi/') and n.endswith('.so'):
            open(os.path.join(xd, 'lib/armeabi', os.path.basename(n)), 'wb').write(z.read(n))
    idd = os.path.join(DST, 'etc/init.d')
    os.makedirs(idd, exist_ok=True)
    open(os.path.join(idd, '90v3setup.sh'), 'w', newline='\n').write('''#!/system/bin/sh
if [ ! -f /data/.v3_setup_done ]; then
  i=0
  while [ "$(getprop sys.boot_completed)" != "1" ] && [ $i -lt 180 ]; do sleep 5; i=$((i+1)); done
  settings put secure default_input_method com.iflytek.inputmethod.wear.xiaomi/com.iflytek.inputmethod.wear.FlyIME
  settings put secure enabled_input_methods com.iflytek.inputmethod.wear.xiaomi/com.iflytek.inputmethod.wear.FlyIME
  settings put global captive_portal_http_url http://connect.rom.miui.com/generate_204
  settings put global captive_portal_https_url https://connect.rom.miui.com/generate_204
  settings put global captive_portal_fallback_url http://connect.rom.miui.com/generate_204
  settings put global captive_portal_use_https 0
  settings put global captive_portal_mode 1
  touch /data/.v3_setup_done
fi
''')
    os.chmod(os.path.join(idd, '90v3setup.sh'), 0o755)

    # build.prop patch
    bp = os.path.join(DST, 'build.prop')
    s = io.open(bp, encoding='utf-8').read()
    s = re.sub(r'^ro\.product\.model=.*$', 'ro.product.model=YUXIN K01', s, flags=re.M)
    s = re.sub(r'^ro\.product\.brand=.*$', 'ro.product.brand=YUXIN', s, flags=re.M)
    s = re.sub(r'^ro\.product\.manufacturer=.*$', 'ro.product.manufacturer=YUXIN', s, flags=re.M)
    s = re.sub(r'^ro\.product\.name=.*$', 'ro.product.name=lineage_s630bw_yuxin_k01', s, flags=re.M)
    s = re.sub(r'^ro\.product\.device=.*$', 'ro.product.device=s630bw_yuxin_k01', s, flags=re.M)
    s = re.sub(r'^ro\.sf\.lcd_density=.*$', 'ro.sf.lcd_density=240', s, flags=re.M)
    s = re.sub(r'^qemu\.hw\.mainkeys=.*$', 'qemu.hw.mainkeys=0', s, flags=re.M)
    s = re.sub(r'^ro\.product\.locale=.*$', 'ro.product.locale=zh-CN', s, flags=re.M)
    s = re.sub(r'^persist\.sys\.timezone=.*$', 'persist.sys.timezone=Asia/Shanghai', s, flags=re.M)
    s = re.sub(r'^dalvik\.vm\.dex2oat-filter=.*$', '', s, flags=re.M)
    s = re.sub(r'^dalvik\.vm\.image-dex2oat-filter=.*$', '', s, flags=re.M)
    s = s.replace('Lenovo/lineage', 'YUXIN/lineage')
    s = s.rstrip() + '''
# === v3 port (YUXIN K01, UleFone Power base) ===
persist.sys.locale=zh-CN
ro.setupwizard.mode=DISABLED
persist.adb.tcp.port=5555
service.adb.tcp.port=5555
ro.zygote=zygote64_32
'''
    io.open(bp, 'w', encoding='utf-8', newline='\n').write(s)
    print('build.prop patched')

    build_boot()
    build_manifest()


if __name__ == '__main__':
    main()

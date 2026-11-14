#!/usr/bin/env python3
"""Build v3.2 ROM = v3 base (power/UleFone LOS 14.1 7.1.2 CN) + all live fixes:
 - stock 6.0 audio HAL + audio configs (sound fix)
 - donor display HAL (native 240x320)
 - stock 6.0 bootanimation (original animation)
 - density 120, vsync props, timezone
 - FM/PicoTts removed, camera/gallery/browser removed
 - Via + Xunfei IME + init.d setup + first-boot relabel
 - Bluetooth fixed APK in priv-app (MAP enabled, embedded 32-bit JNI, our signature)
 - Email/Exchange2 re-signed with same key, mac_permissions/platform.xml patched
 - SELinux enforcing boot image (enforce after boot_completed)
"""
import os, io, re, json, shutil, sys, zipfile

W = 'E:/刷机/YUXIN K01/Work'
SRC = os.path.join(W, 'rom/v3/system')
STOCK = os.path.join(W, 'recon/stock_system')
POWER = os.path.join(W, 'recon/power_system')
DST = os.path.join(W, 'rom/v32/system')
OUT = os.path.join(W, 'rom/v32/out')


def rm(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.unlink(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)


def cp(src, rel):
    dst = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def main():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    print('copy v3 tree ->', DST)
    shutil.copytree(SRC, DST, symlinks=True)
    os.makedirs(OUT, exist_ok=True)

    # ---- audio: stock 6.0 HAL (kernel-paired) + configs ----
    cp(os.path.join(STOCK, 'lib64/hw/audio.primary.mt6737m.so'), 'lib64/hw/audio.primary.mt6735.so')
    cp(os.path.join(STOCK, 'lib/hw/audio.primary.mt6737m.so'), 'lib/hw/audio.primary.mt6735.so')
    for rel in ['etc/audio_device.xml', 'etc/audio_policy.conf', 'etc/audio_effects.conf', 'etc/audio_em.xml']:
        if os.path.isfile(os.path.join(STOCK, rel)):
            cp(os.path.join(STOCK, rel), rel)
    if os.path.isdir(os.path.join(STOCK, 'etc/audio_param')):
        rm(os.path.join(DST, 'etc/audio_param'))
        shutil.copytree(os.path.join(STOCK, 'etc/audio_param'), os.path.join(DST, 'etc/audio_param'))

    # ---- original boot animation ----
    cp(os.path.join(STOCK, 'media/bootanimation.zip'), 'media/bootanimation.zip')

    # ---- debloat: FM / PicoTts ----
    for rel in ['priv-app/FMRadio', 'app/FMRadio', 'app/PicoTts', 'priv-app/PicoTts']:
        rm(os.path.join(DST, rel))

    # ---- Bluetooth fixed apk in priv-app ----
    rm(os.path.join(DST, 'app/Bluetooth'))
    rm(os.path.join(DST, 'priv-app/Bluetooth'))
    bt_dir = os.path.join(DST, 'priv-app/Bluetooth')
    os.makedirs(os.path.join(bt_dir, 'lib/arm'), exist_ok=True)
    shutil.copy2(os.path.join(W, 'mods/btfix/BT_map_signed.apk'), os.path.join(bt_dir, 'Bluetooth.apk'))
    os.symlink('/system/lib/libbluetooth_jni.so', os.path.join(bt_dir, 'lib/arm/libbluetooth_jni.so'))

    # ---- Email / Exchange2 re-signed with our key (shared ACCESS_PROVIDER) ----
    cp(os.path.join(W, 'mods/btfix/Email_signed.apk'), 'app/Email/Email.apk')
    cp(os.path.join(W, 'mods/btfix/Exchange2_signed.apk'), 'app/Exchange2/Exchange2.apk')

    # ---- mac_permissions (our cert -> seinfo platform) + platform.xml (bluetooth assigns) ----
    cp(os.path.join(POWER, 'etc/security/mac_permissions.xml'), 'etc/security/mac_permissions.xml')
    cp(os.path.join(POWER, 'etc/permissions/platform.xml'), 'etc/permissions/platform.xml')

    # ---- init.d: first-boot relabel + existing setup ----
    idd = os.path.join(DST, 'etc/init.d')
    os.makedirs(idd, exist_ok=True)
    open(os.path.join(idd, '80relabel.sh'), 'w', newline='\n').write('''#!/system/bin/sh
# first boot after clean flash: relabel /system for SELinux domains
if [ ! -f /data/.v32_relabeled ]; then
  mount -o rw,remount /system 2>/dev/null
  restorecon -R /system 2>/dev/null
  touch /data/.v32_relabeled
  sync
fi
''')
    os.chmod(os.path.join(idd, '80relabel.sh'), 0o755)

    # ---- build.prop ----
    bp = os.path.join(DST, 'build.prop')
    s = io.open(bp, encoding='utf-8').read()
    s = re.sub(r'^ro\.sf\.lcd_density=.*$', 'ro.sf.lcd_density=120', s, flags=re.M)
    s = re.sub(r'^persist\.sys\.timezone=.*$', 'persist.sys.timezone=Asia/Shanghai', s, flags=re.M)
    s = re.sub(r'^dalvik\.vm\.dex2oat-filter=.*$', '', s, flags=re.M)
    s = re.sub(r'^dalvik\.vm\.image-dex2oat-filter=.*$', '', s, flags=re.M)
    extra = ['persist.sys.timezone=Asia/Shanghai', 'debug.sf.no_hw_vsync=1',
             'debug.sf.sw_vsync_fps=45', 'debug.hwc.skip_log=1',
             'ro.adb.secure=0', 'service.adb.tcp.port=5555', 'persist.adb.tcp.port=5555']
    for line in extra:
        key = line.split('=')[0]
        if not re.search(r'^%s=' % re.escape(key), s, flags=re.M):
            s = s.rstrip() + '\n' + line + '\n'
    io.open(bp, 'w', encoding='utf-8', newline='\n').write(s)
    print('build.prop patched')

    # ---- manifest: base from v3 + new entries ----
    man = json.load(open(os.path.join(W, 'rom/v3/manifest.json'), encoding='utf-8'))
    base = {e['path'] for e in man}

    def add(path, typ='file', mode=0o644, gid=0, sel='u:object_r:system_file:s0', target=None):
        if path in base:
            return
        e = dict(path=path, mode=mode, uid=0, gid=gid, size=0, type=typ, selinux=sel)
        if target:
            e['target'] = target
        man.append(e)
        base.add(path)

    add('/priv-app/Bluetooth', 'dir', 0o755)
    add('/priv-app/Bluetooth/lib', 'dir', 0o755)
    add('/priv-app/Bluetooth/lib/arm', 'dir', 0o755)
    add('/priv-app/Bluetooth/lib/arm/libbluetooth_jni.so', 'symlink', 0o777,
        target='/system/lib/libbluetooth_jni.so')
    add('/etc/init.d/80relabel.sh', 'file', 0o755, gid=2000, sel='u:object_r:userinit_exec:s0')
    for p in ['/priv-app/Bluetooth/Bluetooth.apk', '/app/Email/Email.apk', '/app/Exchange2/Exchange2.apk',
              '/media/bootanimation.zip', '/etc/security/mac_permissions.xml', '/etc/permissions/platform.xml',
              '/lib64/hw/audio.primary.mt6735.so', '/lib/hw/audio.primary.mt6735.so']:
        add(p)
    # make sure existing paths keep their labels; dirs 0755
    out_man = os.path.join(W, 'rom/v32/manifest.json')
    json.dump(man, open(out_man, 'w', encoding='utf-8'), ensure_ascii=False)
    print('manifest entries', len(man), '->', out_man)


if __name__ == '__main__':
    main()

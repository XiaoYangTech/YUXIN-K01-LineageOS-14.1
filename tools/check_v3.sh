#!/system/bin/sh
# v3 post-boot verification (run as root via adb shell)
echo "===== PROPS ====="
getprop ro.build.version.release
getprop ro.product.model
getprop persist.sys.locale
getprop ro.product.locale
getprop ro.sf.lcd_density
getprop sys.boot_completed
echo "===== DISPLAY ====="
dumpsys display 2>/dev/null | grep -oE 'Built-in Screen[^}]*fps=[0-9.]+' | head -1
wm size 2>/dev/null
wm density 2>/dev/null
echo "===== PACKAGES ====="
pm list packages 2>/dev/null | grep -iE 'via|iflytek|browser|camera|gallery|webview|pico' | head -20
echo "===== IME ====="
settings get secure default_input_method
ime list -s 2>/dev/null | head -5
echo "===== CAPTIVE ====="
settings get global captive_portal_http_url
settings get global captive_portal_use_https
echo "===== SENSORS ====="
dumpsys sensorservice 2>/dev/null | head -20
echo "===== AUDIO ====="
dumpsys media.audio_flinger 2>/dev/null | grep -iE 'HAL|open|error' | head -10
logcat -d -b all 2>/dev/null | grep -iE 'AudioALSAPlayback|AudioALSAHardware|AudioFlinger.*(error|fail)|audio.primary' | tail -10
echo "===== BLUETOOTH ====="
dumpsys bluetooth_manager 2>/dev/null | head -8
logcat -d -b all 2>/dev/null | grep -iE 'bluetooth|bluedroid' | tail -8
echo "===== BRIGHTNESS ====="
cat /sys/class/leds/lcd-backlight/brightness 2>/dev/null
cat /sys/class/leds/lcd-backlight/max_brightness 2>/dev/null
echo "===== TOUCH ====="
getevent -pl 2>/dev/null | grep -E 'name:|ABS_MT' | head -8
echo "===== CRASHES ====="
ls /data/tombstones 2>/dev/null | tail -3
logcat -d -b crash 2>/dev/null | tail -20

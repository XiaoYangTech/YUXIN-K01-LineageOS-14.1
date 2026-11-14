#!/system/bin/sh
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
  settings put secure install_non_market_apps 1
  settings put global development_settings_enabled 1
  settings put global window_animation_scale 0
  settings put global transition_animation_scale 0
  settings put global animator_duration_scale 0
  cmd package set-home-activity com.ss.squarehome2/.MainActivity 2>/dev/null
  settings put system screen_brightness_mode 0
  settings put system screen_brightness 128
  settings put secure user_setup_complete 1
  settings put global device_provisioned 1
  setprop persist.sys.usb.config mtp,adb
  touch /data/.v3_setup_done
fi

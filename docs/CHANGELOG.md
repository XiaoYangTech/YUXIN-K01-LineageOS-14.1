# 更新记录

## v3.3 (2026-11-14)

- 底包：UleFone Power LineageOS 14.1（Android 7.1.2，中文完整）
- 内核：设备原厂 6.0 内核 3.18.19
- 显示：UleFone 7.1 显示 HAL（hwcomposer/gralloc/memtrack），修复唤醒、截图
- 音频：原厂 6.0 音频 HAL + 配置；无听筒时通话走扬声器；集成 Dolby Atmos；删除 AudioFX
- 蓝牙：修复 32 位 JNI / priv-app / 系统权限问题，MAP 恢复
- 系统：MiSans 字体、Square Home 桌面（默认）、LineageOS 开机动画、中文字体/时区/输入法
- 删除：电话、通讯录、短信、SIM 卡工具包、相机/图库/Snap、指纹、LineageOS 更新、开机向导、CPL 桌面
- 默认：未知来源安装、开发者选项、动画 0、手动亮度、MTP+ADB
- SELinux：首启 relabel，二启 Enforcing
- 基带：原厂 6.0 RIL 栈，移除 fakeiccid（修复网络注册），APN 3gnet，NVRAM 固定 WiFi MAC
- 修复：home 键失效 / 通知栏详细面板展不开 / 亮度不可调（user_setup_complete 未置位）
- 修复：锁屏音效后杂音（AudioFlinger standby 3000ms→500ms）
- 修复：设置中 "Build author" 英文与底包作者（资源 overlay → ROM 维护者 / B站-小杨聊科技）
- 刷机脚本：按目录分段写入 + 进度条

## v3.2 之前
- v1/v2：早期探索版（porridge/其他底包），未发布

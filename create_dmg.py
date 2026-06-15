# -*- coding: utf-8 -*-
"""
创建 Drifox DMG 安装包
"""
import os
import dmgbuild

def build_dmg():
    app_path = "dist/Drifox.app"
    dmg_path = "dist/Drifox.dmg"
    
    # 删除旧的 dmg
    if os.path.exists(dmg_path):
        os.remove(dmg_path)
    
    # DMG 配置
    settings = {
        "format": "ULFO",
        "compression_level": 9,
        "files": [
            (app_path, "Drifox.app"),
        ],
        "symlinks": {
            "Applications": "/Applications",
        },
        "volume_name": "Drifox",
        "volume_icon_file": None,
    }
    
    print(f"正在创建 DMG: {dmg_path}")
    dmgbuild.build_dmg(
        dmg_path,
        "Drifox",
        settings=settings,
        # 不使用符号链接
        detach_retries=5,
    )
    print(f"✅ DMG 创建完成: {dmg_path}")

if __name__ == "__main__":
    build_dmg()

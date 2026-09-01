from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "delivery"
PACKAGE_NAME = "八字紫微排盘微信小程序交付包"


def write_txt(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.replace("\n", "\r\n"), encoding="utf-8-sig", newline="")


def build_text_files() -> None:
    write_txt(
        DELIVERY / "运行说明.txt",
        """八字紫微排盘微信小程序运行说明

一、工程位置
微信小程序工程位于本交付包的 miniprogram 目录。
后端工程位于本交付包的 backend 目录。
运营配置页面位于本交付包的 admin 目录。

二、Windows 本地检查
在项目根目录执行：
python -m pip install -r requirements.txt
python scripts\\manage.py test
python scripts\\check_miniprogram.py

三、打开微信开发者工具
使用微信开发者工具导入 miniprogram 目录。
也可以执行：
python scripts\\open_miniprogram.py
生成预览包：
python scripts\\preview_miniprogram.py

四、后端本地运行
启动：python scripts\\manage.py start
健康检查：python scripts\\manage.py health
停止：python scripts\\manage.py stop
重启：python scripts\\manage.py restart

五、线上 API 地址
正式发布前，在 miniprogram\\config\\runtime.js 中填写备案 HTTPS API 地址。
地址为空或不是 HTTPS 时，本地排盘、运势、六爻、合婚、名号和本地记录仍可使用；登录、同步、咨询和支付会显示 local-mode 原因。

六、运营配置
部署后访问同一站点的 /admin/ops-config.html。
ADMIN_TOKEN 只在页面中输入，不写入工程或浏览器存储。
运营页面支持维护专家与排班、查看订单和更新服务状态；支付状态只读，不能手工改为已支付。

七、微信支付
微信支付仅用于真人咨询订单。生产环境需配置正式 AppID、AppSecret、商户号、商户私钥、API v3 Key、平台证书、HTTPS 通知地址和咨询价格。
支付成功以服务端收到并验证微信支付 API v3 通知为准，小程序只查询订单状态。
缺少正式参数时，不代表真实支付已经完成验收。

八、日志
日志统一保存在项目 logs 目录。
""",
    )
    write_txt(
        DELIVERY / "部署说明.txt",
        """八字紫微排盘服务器部署说明

一、目标服务器
地址：124.223.182.85
SSH 用户：ubuntu
系统：Ubuntu 24.04.4 LTS
架构：x86_64
服务目录：/home/ubuntu/bazi-ziwei
服务名称：bazi-ziwei.service

二、部署前提
服务器已安装 python3、Caddy 和 systemd；部署脚本会检查并安装 python3-venv。
ubuntu 用户需要具备脚本所用 sudo -n 权限。
正式模式需要备案域名已经解析到服务器，腾讯云安全组已放行 80 和 443 端口。

三、执行部署
以下命令均在项目根目录执行，脚本会提示输入 SSH 密码：
内部 HTTP 验收模式：python scripts\\deploy_server.py
正式 HTTPS 域名模式：python scripts\\deploy_server.py --domain api.example.com

脚本会上传后端和运营页面、创建 .venv、安装 requirements.txt、备份并验证 Caddy 配置、重启服务和执行健康检查。
域名模式下，如果 DNS、证书签发或 HTTPS 健康检查未完成，部署会明确失败，不会把内部 HTTP 当成正式 HTTPS 通过。

四、服务器运维
以下命令在项目根目录执行，脚本会提示输入 SSH 密码，也可以通过 REMOTE_PASSWORD 环境变量传入：
python scripts\\server_manage.py status
python scripts\\server_manage.py health
python scripts\\server_manage.py restart
python scripts\\server_manage.py backup
python scripts\\server_manage.py verify-restore
python scripts\\server_manage.py logs

五、发布配置
将正式 HTTPS 地址写入 miniprogram\\config\\runtime.js，然后重新在微信开发者工具中编译和上传。
在微信公众平台配置 request 合法域名和支付相关域名。
ADMIN_TOKEN、SESSION_SECRET、AppSecret、商户私钥、API v3 Key 和证书只保存在服务器，不进入小程序和交付包。
""",
    )
    write_txt(
        DELIVERY / "待配置清单.txt",
        """八字紫微排盘微信小程序待配置清单

一、微信基础配置
微信小程序 AppID
微信小程序 AppSecret
微信开发者工具正式项目配置
request 合法域名和支付相关域名

二、服务器公网配置
备案域名
腾讯云安全组 HTTP/HTTPS 端口
域名解析到 124.223.182.85
正式 HTTPS API 地址写入 miniprogram\\config\\runtime.js

三、商业化配置
微信支付商户号
商户证书序列号和商户私钥
API v3 Key
微信支付平台证书序列号和公钥文件
HTTPS 支付通知地址
正式专家资料、咨询价格和排班
咨询服务状态处理规则

四、专业规则
客户认可的八字、紫微、合婚和年度运势基准样例
五行旺衰、喜用神、格局、流月的正式口径
名号测算的繁体、异体字补充口径

五、本次不包含
AI 解读、会员、深度付费报告、分佣、完整客户关系管理、退款后台和服务评价运营。
""",
    )
    write_txt(
        DELIVERY / "测试报告.txt",
        """八字紫微排盘微信小程序测试报告

测试日期：2026 年 8 月 27 日

一、小程序检查
工程文件、页面路由、WXML 结构检查通过。
JavaScript 语法检查通过。
599 组常规日期和 55 组闰月往返检查通过。
四柱、紫微十二宫、每日运势五项、财富、六爻、合婚和名号固定样例检查通过。
康熙笔画“李明”识别为 7 画、8 画。
微信开发者工具 CLI 编译和预览包生成通过，预览包为 1,257,510 Byte（约 1.2 MB）。

二、后端检查
数据库基础读写检查通过。
用户鉴权、记录归属、专家和排班运营接口、订单查询与服务状态更新检查通过。
无 ADMIN_TOKEN 的运营写操作拒绝，运营接口不能把订单伪造为已支付。
微信支付 API v3 签名、解密、AppID、商户号、金额、币种和通知幂等检查通过。
Caddy 内部 HTTP 与域名 HTTPS 配置渲染检查通过。
最新代码已部署到 Ubuntu 服务器，systemd、后端健康检查和服务器内部 Caddy 转发通过。

三、运营页面检查
配置、专家、排班和订单四个视图切换通过。
桌面 1440×1000 和移动端 390×844 页面无文本溢出或控件重叠，浏览器控制台为 0 errors。
公网 80 端口从开发机访问仍超时，不作为公网发布验收通过。

四、待外部验证
正式微信 AppID 和真机登录流程。
备案域名、HTTPS、腾讯云安全组和微信小程序服务器域名白名单。
微信支付真实下单、真机支付和真实回调。
客户专业基准样例复核。

五、日志与截图位置
本地检查日志：logs\\check-miniprogram.log
后端部署日志：logs\\deploy-server.log
服务器运维日志：logs\\server-manage.log
微信预览日志：logs\\wechat-preview.log
运营页面预览日志：logs\\admin-preview.log
运营页面桌面截图：output\\playwright\\ops-desktop-final.png
运营页面移动截图：output\\playwright\\ops-mobile-final.png
""",
    )


def copy_tree(relative: str) -> None:
    source = ROOT / relative
    target = DELIVERY / relative
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "rejected"),
        )
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_zip() -> Path:
    archive = ROOT / f"{PACKAGE_NAME}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in DELIVERY.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(DELIVERY).as_posix())
    return archive


def main() -> int:
    if DELIVERY.exists():
        shutil.rmtree(DELIVERY)
    DELIVERY.mkdir(parents=True)
    for relative in (
        "miniprogram",
        "backend",
        "scripts/check_miniprogram.py",
        "scripts/check_miniprogram.sh",
        "scripts/fixtures",
        "scripts/manage.py",
        "scripts/manage.sh",
        "scripts/server_manage.py",
        "scripts/server_manage.sh",
        "scripts/deploy_server.py",
        "scripts/deploy_server.sh",
        "scripts/open_miniprogram.py",
        "scripts/open_miniprogram.sh",
        "scripts/preview_miniprogram.py",
        "scripts/preview_miniprogram.sh",
        "scripts/preview_admin.py",
        "scripts/preview_admin.sh",
        "scripts/test_backend.py",
        "scripts/test_backend_api.py",
        "scripts/test_payment.py",
        "scripts/test_deploy_config.py",
        "requirements.txt",
        "scripts/generate_word_docs.py",
        "scripts/generate_word_docs.sh",
        "admin",
        "docs/third-party",
        "docs/八字紫微排盘产品PRD-微信小程序版.docx",
        "discuss/八字紫微排盘Phase计划-微信小程序版.docx",
        "logs/check-miniprogram.log",
        "logs/deploy-server.log",
        "logs/server-manage.log",
        "logs/wechat-preview.log",
        "logs/admin-preview.log",
        "logs/ui-qa",
        "output/playwright",
    ):
        copy_tree(relative)
    build_text_files()
    archive = build_zip()
    print(f"交付目录：{DELIVERY}")
    print(f"交付压缩包：{archive}")
    print(f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

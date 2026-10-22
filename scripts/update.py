#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""佳佳在线 / TVBox 配置聚合更新脚本（仅依赖 Python 标准库）。

流程：
  读取 config/sources.json
    → 逐个源按 urls 顺序尝试主/备地址抓取
    → 校验并解析 JSON（自动剔除 // 行注释、中文域名转 punycode）
    → 聚合单仓（合并 sites/lives/parses/rules，key 冲突加源前缀去重）
    → 生成 多仓订阅 / 单仓聚合 / 各源独立文件 / status.json / shield.json
    → 刷新 README 状态表与订阅链接（占位符 {{REPO}} 替换为实际仓库）

环境变量：
  REPO   目标 GitHub 仓库（owner/repo）。GitHub Actions 会自动注入 github.repository；
         本地运行若不设置，则沿用 DEFAULT_REPO 占位符，README 链接需手动替换。
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.json")
OUTPUT_DIR = os.path.join(ROOT, "output")
README_PATH = os.path.join(ROOT, "README.md")

DEFAULT_REPO = os.environ.get("REPO", "GITHUB_USER/workbuddy-ysc-config")
# 内部引用的订阅文件统一走 jsDelivr CDN（国内直连 raw 被 DNS 污染，见踩坑文档 #13）
URL_BASE_TEMPLATE = "https://cdn.jsdelivr.net/gh/{repo}@main/output/{file}"

UA = "okHttp/3.8.1"
TIMEOUT = 20
RETRIES = 2

# 单仓聚合时，从首个成功源继承的顶层字段
SCALAR_FIELDS = ["spider", "logo", "wallpaper", "ads", "doh", "hosts", "headers"]
LIST_FIELDS = ["sites", "lives", "parses", "rules"]


def log(msg):
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    print("[%s] %s" % (ts, msg), flush=True)


def to_punycode_url(url):
    """把 URL 里的中文（非 ASCII）主机名转成 punycode，避免 DNS 解析失败。"""
    m = re.match(r"^(https?://)([^/?#]+)(.*)$", url, re.I)
    if not m:
        return url
    scheme, host, rest = m.group(1), m.group(2), m.group(3)
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        pass
    return scheme + host + rest


def fetch(url):
    url = to_punycode_url(url.strip())
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                # utf-8-sig 兼容带 BOM 的源（如小马）
                data = resp.read().decode("utf-8-sig", "replace")
            if not data.strip():
                raise ValueError("空响应")
            return data
        except Exception as e:
            last = e
            if attempt < RETRIES - 1:
                time.sleep(2)
    raise last


def strip_json_comments(text):
    """剔除不在字符串内、且不是 http(s):// 一部分的 // 行注释。"""
    out = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            # 行注释：仅当不是 http:// https:// 的一部分（前一个非空白字符是 ':'）
            prev = ""
            for k in range(len(out) - 1, -1, -1):
                if out[k] not in " \t\r\n":
                    prev = out[k]
                    break
            if prev == ":":
                out.append(c)  # 保留，当作 scheme 的一部分
                i += 1
                continue
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_config(text):
    """解析配置：优先标准解析（strict=False 容忍未转义控制字符），
    失败则剔除 // 注释后重试，再失败则用 raw_decode 取首个 JSON 对象
    （兼容多个 JSON 拼接的 .txt，如拾光多仓）。"""
    for attempt_text in (text, strip_json_comments(text)):
        try:
            return json.loads(attempt_text, strict=False)
        except json.JSONDecodeError:
            pass
        try:
            dec = json.JSONDecoder()
            obj, _ = dec.raw_decode(attempt_text, strict=False)
            return obj
        except Exception:
            pass
    raise ValueError("无法解析为 JSON")


def load_sources():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("sources", [])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sources = load_sources()
    repo = os.environ.get("REPO", DEFAULT_REPO)
    base = URL_BASE_TEMPLATE.format(repo=repo, file="{file}")

    results = {}
    aggregated = {"sites": [], "lives": [], "parses": [], "rules": [], "proxy": []}
    seen_keys = {}

    log("开始聚合，共 %d 个源" % len(sources))
    for src in sources:
        sid = src["id"]
        name = src.get("name", sid)
        urls = src.get("urls", [])
        raw = None
        err = None
        for u in urls:
            try:
                raw = fetch(u)
                break
            except Exception as e:
                err = "%s: %s" % (u, e)
                log("  x %s 失败: %s" % (u, e))
        if raw is None:
            log("  x %s 全部失败" % name)
            results[sid] = {"name": name, "ok": False, "file": None, "type": None, "error": err}
            continue

        stripped = raw.lstrip()
        data = None
        parse_err = None
        try:
            data = parse_config(raw)
        except Exception as e:
            parse_err = str(e)

        if data is None and stripped[:1] not in ("{", "["):
            # 拿到非配置内容（挑战页 / HTML 等），视为源失效，不保存、不引用
            log("  x %s 返回非配置内容，视为失效" % name)
            results[sid] = {"name": name, "ok": False, "file": None, "type": None,
                            "error": parse_err or err}
            continue

        # 可用：原样保存原始文件（客户端自行解析，保留源站原始格式）
        fname = "%s.json" % sid
        with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
            f.write(raw)
        if data is None:
            log("  √ %s 抓取成功（原始格式，未聚合）" % name)
            ctype = None
        else:
            log("  √ %s 抓取成功" % name)
            ctype = "multi" if "urls" in data else "single"
        results[sid] = {"name": name, "ok": True, "file": fname, "type": ctype,
                        "error": parse_err if data is None else None}
        if data is not None and ctype == "single":
            for key in LIST_FIELDS:
                items = data.get(key) or []
                if key == "sites":
                    for it in items:
                        k = it.get("key")
                        if k in seen_keys:
                            it["key"] = "%s_%s" % (sid, k)
                        seen_keys[it.get("key")] = True
                        aggregated["sites"].append(it)
                else:
                    for it in items:
                        if it not in aggregated[key]:
                            aggregated[key].append(it)
            # 继承顶层字段
            for field in SCALAR_FIELDS:
                if field not in aggregated and data.get(field) is not None:
                    aggregated[field] = data[field]
            for p in (data.get("proxy") or []):
                if p not in aggregated["proxy"]:
                    aggregated["proxy"].append(p)

    # 单仓聚合 all.json（顶层必须有 sites，否则单仓盒子报「解析配置失败」）
    all_conf = {k: v for k, v in aggregated.items() if v}
    with open(os.path.join(OUTPUT_DIR, "all.json"), "w", encoding="utf-8") as f:
        json.dump(all_conf, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "单仓聚合.json"), "w", encoding="utf-8") as f:
        json.dump(all_conf, f, ensure_ascii=False, indent=2)
    log("  单仓聚合: %d sites / %d parses / %d lives" % (
        len(all_conf.get("sites", [])), len(all_conf.get("parses", [])), len(all_conf.get("lives", []))))

    # 多仓订阅 subscribe.json：每个成功源一个入口，url 指向本仓库的该源文件（走 CDN）
    sub = {"urls": []}
    for sid, r in results.items():
        if r["ok"]:
            sub["urls"].append({"name": r["name"], "url": base.format(file=r["file"])})
    with open(os.path.join(OUTPUT_DIR, "subscribe.json"), "w", encoding="utf-8") as f:
        json.dump(sub, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "多仓订阅.json"), "w", encoding="utf-8") as f:
        json.dump(sub, f, ensure_ascii=False, indent=2)

    # status.json
    success = sum(1 for r in results.values() if r["ok"])
    total = len(results)
    status = {
        "updated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "success": success,
        "total": total,
        "sources": {
            sid: {"name": r["name"], "ok": r["ok"], "type": r["type"], "error": r["error"]}
            for sid, r in results.items()
        },
    }
    with open(os.path.join(OUTPUT_DIR, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    # shield.json（shields.io 端点）
    color = "green" if success == total else ("orange" if success > 0 else "red")
    shield = {"schemaVersion": 1, "label": "源可用性", "message": "%d/%d" % (success, total), "color": color}
    with open(os.path.join(OUTPUT_DIR, "shield.json"), "w", encoding="utf-8") as f:
        json.dump(shield, f, ensure_ascii=False)

    update_readme(status, repo)
    log("完成：成功 %d/%d 个源" % (success, total))
    return 0 if success > 0 else 1


def update_readme(status, repo):
    if not os.path.exists(README_PATH):
        return
    bj = timezone(timedelta(hours=8))
    now = datetime.now(bj).strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for sid, s in status["sources"].items():
        mark = "✅ 成功" if s["ok"] else "❌ 失败"
        rows.append("| %s | %s | %s | %s |" % (
            s["name"], mark, s.get("type") or "-", (s.get("error") or "-")[:120]))
    table = (
        "## 一、源可用性状态\n\n"
        "> 🔄 最近更新：%s（北京时间） · 成功 **%d/%d** 个源\n\n"
        "| 配置源 | 状态 | 类型 | 说明 |\n|---|---|---|---|\n"
        "%s\n"
    ) % (now, status["success"], status["total"], "\n".join(rows))

    text = open(README_PATH, encoding="utf-8").read()
    start = "<!--STATUS_START-->"
    end = "<!--STATUS_END-->"
    if start in text and end in text:
        pre = text.split(start)[0] + start + "\n"
        post = text.split(end)[1]
        text = pre + table + end + post
    # 把订阅链接里的仓库占位符替换为实际仓库
    text = text.replace("{{REPO}}", repo)
    open(README_PATH, "w", encoding="utf-8").write(text)
    log("  README 状态表与订阅链接已刷新")


if __name__ == "__main__":
    sys.exit(main())

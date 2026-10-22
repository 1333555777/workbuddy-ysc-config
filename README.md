# 佳佳在线配置聚合仓库（TVBox Config Aggregator）

聚合 **肥猫、王二小、老刘备、小马、4K小盒子、小盒子单仓、拾光多仓、挺好分享多仓、佳佳在线·小沙、佳佳在线·论坛** 等多个影视仓 / TVBox 配置源，通过 **GitHub Actions 定时自动更新**，把结果直接提交回本仓库，供影视仓、TVBox、OK影视等软件随时拉取最新接口。

> 所有配置均来自互联网公开分享，版权归原作者所有；本仓库仅做聚合与镜像，仅供学习交流，请勿商用。

<!--STATUS_START-->
## 一、源可用性状态

> 🔄 最近更新：2026-10-22 16:54:23（北京时间） · 成功 **3/10** 个源

| 配置源 | 状态 | 类型 | 说明 |
|---|---|---|---|
| 肥猫 | ❌ 失败 | - | https://6296.kstore.vip/facat.json: HTTP Error 401:  |
| 饭太硬 | ❌ 失败 | - | http://www.饭太硬.xyz/tv: HTTP Error 403: Forbidden |
| 王二小 | ✅ 成功 | single | - |
| 老刘备 | ✅ 成功 | single | - |
| 小马 | ✅ 成功 | single | - |
| 讴歌 | ❌ 失败 | - | https://欧歌.v.nxog.top/m/: <urlopen error [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] ssl/tls alert handshake failure (_ssl.c:10 |
| 4K小盒子 | ❌ 失败 | - | http://xhztv.top/xhz: HTTP Error 403: Forbidden |
| 小盒子单仓 | ❌ 失败 | - | http://xhztv.top/xhz: HTTP Error 403: Forbidden |
| 拾光多仓 | ❌ 失败 | - | http://xmbjm.fh4u.org/dc.txt: HTTP Error 403: Forbidden |
| 挺好分享多仓 | ❌ 失败 | - | http://ztha.top/TVBox/GYCK.json: HTTP Error 403: Forbidden |
<!--STATUS_END-->

## 二、在影视仓 / TVBox 中使用

把下面任一地址填入 App 的「设置 → 配置地址」。

> ⚠️ 国内**不要**直接填 `raw.githubusercontent.com`（被 DNS 污染，会一直「拉取配置失败」）。下面已统一走 jsDelivr CDN。

| 客户端类型 | 该填的文件 | 地址 | 说明 |
|---|---|---|---|
| 影视仓 / 支持多仓切源的客户端 | 多仓订阅 | `https://cdn.jsdelivr.net/gh/GITHUB_USER/workbuddy-ysc-config@main/output/subscribe.json` | App 内可在各源间切换（推荐） |
| 鳄鱼影视仓 / takagen99-Box 编译版 | 单仓聚合 | `https://cdn.jsdelivr.net/gh/GITHUB_USER/workbuddy-ysc-config@main/output/all.json` | 所有源站点合并成一个，开箱即用 |

> 单仓盒子（如 takagen99-Box）**必须**填 `all.json`；填 `subscribe.json` 会因顶层没有 `sites` 字段而报「解析配置失败」。

各源独立文件（按需单独引用）：
`https://cdn.jsdelivr.net/gh/GITHUB_USER/workbuddy-ysc-config@main/output/<源id>.json`
（源 id：feimao / wangerxiao / laoliubei / xiaoma / 4k / xiaohezi / shiguang / tinghao / jiajia_xiaosha / jiajia_jieluntan）

## 三、仓库结构

```
workbuddy-ysc-config/
├── .github/workflows/update.yml   # GitHub Actions 自动更新工作流
├── config/sources.json            # 配置源列表（主地址 + 备用地址），可自行增删改
├── scripts/update.py              # 核心聚合脚本（stdlib-only，无需 pip 安装依赖）
├── output/                        # 更新产物（脚本自动生成并提交）
│   ├── subscribe.json             # 多仓订阅（推荐）
│   ├── all.json                   # 单仓聚合
│   ├── status.json                # 各源状态（机器可读）
│   ├── shield.json                # shields.io 状态徽章数据
│   └── <源id>.json                # 各源独立配置
└── README.md
```

## 四、自动更新机制

- 默认每天 **02:00 和 14:00（UTC，即北京时间 10:00 和 22:00）** 自动更新一次。
- 也可在 **Actions → Auto Update TVBox Configs → Run workflow** 手动触发。
- 更新结果自动提交回 `main` 分支，README 状态表与订阅链接同步刷新。
- 工作流使用内置 `GITHUB_TOKEN`，无需配置任何密钥；`REPO` 由 `github.repository` 自动注入。

## 五、自定义配置源

编辑 `config/sources.json` 即可增删配置源或更换地址：

```json
{
  "id": "mysource",
  "name": "我的源",
  "urls": [
    "https://example.com/tv",
    "https://backup.example.com/tv"
  ]
}
```

- `id`：输出文件名（建议英文小写）。
- `name`：在多仓订阅与状态表中展示的名字。
- `urls`：依次尝试的地址列表，第一个成功的会被使用。

## 六、本地手动更新（可选）

```bash
# 不设置 REPO 时 README 链接为占位符，建议显式指定自己的仓库
REPO=你的用户名/workbuddy-ysc-config python scripts/update.py
```

脚本仅用 Python 标准库，无需 `pip install` 任何依赖。

## 七、常见问题

- **某个源一直失败？** 影视源域名寿命普遍很短，受地区/频率限制影响。脚本按 `urls` 顺序自动尝试所有备用地址，只把成功的写入。
- **App 报「解析配置失败」？** 那是文件格式不对——单仓盒子填了多仓订阅文件（顶层没有 `sites`）。换成 `all.json`。
- **App 报「拉取配置失败」？** 那是网络层问题（DNS 污染/代理/超时），不是配置格式问题。
- **分类栏出来了但内容区一直转圈？** 这是部分 Box 编译版的冷启动竞态 bug，与配置无关，需重编译修复。

## 八、免责声明

本项目仅用于学习、测试与个人使用；聚合的接口资源来自互联网公开分享，版权归原作者所有。若涉及侵权，请联系删除相应内容。

# drissionpage-devtools-mcp

单一 MCP 服务，内部把 `DrissionPage` 和 `js-reverse-mcp` 合成到一起：

- `DrissionPage` 负责启动或接管浏览器
- `js-reverse-mcp` 负责 devtools 工具能力
- 对外只暴露一个 MCP server

客户端只需要连接这一个服务，不需要再分别调用两个 MCP。

## 运行方式

启动时会按这个顺序工作：

1. 用 `DrissionPage` 在指定端口启动或接管 Chrome
2. 在服务内部启动 vendored `js-reverse-mcp`
3. 将子 MCP 的 devtools 工具原样代理出来

## 仓库内容

- `src/drissionpage_devtools_mcp/`：统一 MCP 服务
- `vendor/js-reverse-mcp/build/`：`js-reverse-mcp` 运行时产物
- `vendor/js-reverse-mcp/package.json`：运行时元数据

仓库已经内置 `js-reverse-mcp` 的运行时文件，默认不需要额外 clone 它的源码仓库，也不需要额外执行 `npm install`。

## 环境要求

- Python 3.11+
- Node.js 20+
- Chrome 或兼容 Chromium 浏览器

默认会优先寻找 macOS 上的 Chrome / Edge。其他系统或自定义路径请传 `--browser-path`，或设置环境变量 `DRISSIONPAGE_BROWSER_PATH`。

## 安装

从 GitHub 拉取并安装：

```bash
git clone https://github.com/asidExxX/drissionpage-devtools-mcp.git
cd drissionpage-devtools-mcp
chmod +x install.sh
./install.sh
```

一键安装：

```bash
chmod +x install.sh
./install.sh
```

等价的手动安装：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
```

安装完成后可执行命令为：

```bash
./.venv/bin/drissionpage-devtools-mcp
```

## 启动

直接启动：

```bash
./.venv/bin/drissionpage-devtools-mcp
```

传浏览器端口和 devtools 参数：

```bash
./.venv/bin/drissionpage-devtools-mcp \
  --port 9222 \
  -- --hideCanvas --blockWebrtc --no-category-network
```

检查安装是否正常：

```bash
./.venv/bin/drissionpage-devtools-mcp --help
```

## MCP 配置示例

见 [mcp-config.example.json](/Users/windchime/Desktop/codextemp/drissionpage-devtools-mcp/mcp-config.example.json)。

## 注意

- 不要再额外传 `--browserUrl` 或 `--wsEndpoint`，统一服务会自动设置。
- 如果 `vendor/js-reverse-mcp/build/src/index.js` 缺失，服务会尝试在 `vendor/js-reverse-mcp` 下执行一次 `npm run build`。
- 当前实现默认不会在退出时主动关闭已存在的浏览器实例，避免误关你正在使用的窗口。

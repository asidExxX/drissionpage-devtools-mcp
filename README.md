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

## mcpServers 配置

推荐这样写：

```json
{
  "mcpServers": {
    "drissionpage-devtools": {
      "command": "/absolute/path/to/drissionpage-devtools-mcp/.venv/bin/drissionpage-devtools-mcp",
      "args": [
        "--port",
        "9222",
        "--chrome-arg",
        "--fingerprinting-canvas-image-data-noise",
        "--chrome-arg",
        "--webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--chrome-arg",
        "--force-webrtc-ip-handling-policy"
      ]
    }
  }
}
```

如果你只要最基础的浏览器接管能力，也可以只保留：

```json
{
  "mcpServers": {
    "drissionpage-devtools": {
      "command": "/absolute/path/to/drissionpage-devtools-mcp/.venv/bin/drissionpage-devtools-mcp",
      "args": [
        "--port",
        "9222"
      ]
    }
  }
}
```

如果还要把其他参数继续转发给内部的 `js-reverse-mcp`，再在最后加 `--`，例如：

```json
{
  "mcpServers": {
    "drissionpage-devtools": {
      "command": "/absolute/path/to/drissionpage-devtools-mcp/.venv/bin/drissionpage-devtools-mcp",
      "args": [
        "--port",
        "9222",
        "--",
        "--no-category-network"
      ]
    }
  }
}
```

## 参数说明

- `--fingerprinting-canvas-image-data-noise`
  作用：给 Canvas 指纹加噪，降低基于 canvas 渲染结果做指纹识别的稳定性。
- `--webrtc-ip-handling-policy=disable_non_proxied_udp`
  作用：限制 WebRTC 的非代理 UDP，避免走代理时通过 WebRTC 直连泄露真实 IP。
- `--force-webrtc-ip-handling-policy`
  作用：强制应用上面的 WebRTC 策略。

上面这三项是当前这套集成里推荐的写法，因为浏览器是由 `DrissionPage` 先启动的。

`js-reverse-mcp` 原本也支持下面两个参数：

- `--hideCanvas`
- `--blockWebrtc`

但它们只在 `js-reverse-mcp` 自己负责启动浏览器时才真正生效。当前模式下浏览器已经由 `DrissionPage` 拉起，所以更推荐把等价能力直接写成 `--chrome-arg` 放在启动器这一层。

## 启动

直接启动：

```bash
./.venv/bin/drissionpage-devtools-mcp
```

传浏览器端口和 Chrome 启动参数：

```bash
./.venv/bin/drissionpage-devtools-mcp \
  --port 9222 \
  --chrome-arg --fingerprinting-canvas-image-data-noise \
  --chrome-arg --webrtc-ip-handling-policy=disable_non_proxied_udp \
  --chrome-arg --force-webrtc-ip-handling-policy \
  -- --no-category-network
```

检查安装是否正常：

```bash
./.venv/bin/drissionpage-devtools-mcp --help
```

## MCP 配置示例

见 `mcp-config.example.json`。

## 注意

- `--chrome-arg` 是传给 `DrissionPage` 启动的浏览器实例本身的。
- `--` 后面的参数会继续转发给内部的 `js-reverse-mcp`。
- 不要再额外传 `--browserUrl` 或 `--wsEndpoint`，统一服务会自动设置。
- 如果 `vendor/js-reverse-mcp/build/src/index.js` 缺失，服务会尝试在 `vendor/js-reverse-mcp` 下执行一次 `npm run build`。
- 当前实现默认不会在退出时主动关闭已存在的浏览器实例，避免误关你正在使用的窗口。

#!/bin/bash
# 在 macOS 15 上从源码编译安装 cliclick（打补丁绕过 CGWindowListCreateImage 废弃）。
# evolving 仅使用 click/doubleclick，不需要 ColorPicker 功能。
set -e
BUILD_DIR="${BUILD_DIR:-/tmp/cliclick-build}"
VERSION="5.0"
URL="https://github.com/BlueM/cliclick/archive/${VERSION}.tar.gz"

echo "==> 创建构建目录 $BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [[ ! -f "cliclick-${VERSION}.tar.gz" ]]; then
  echo "==> 下载 cliclick ${VERSION}（若超时可重试或手动下载到 $BUILD_DIR）"
  curl -fSL -o "cliclick-${VERSION}.tar.gz" "$URL"
fi
if [[ ! -d "cliclick-${VERSION}" ]]; then
  tar xzf "cliclick-${VERSION}.tar.gz"
fi
cd "cliclick-${VERSION}"

echo "==> 应用 macOS 15 补丁（禁用 ColorPicker 中的废弃 API）"
FILE="Actions/ColorPickerAction.m"
python3 << 'PY'
import re
path = "Actions/ColorPickerAction.m"
with open(path) as f:
    s = f.read()
old = r"""            CGRect imageRect = CGRectMake(p.x, p.y, 1, 1);
            CGImageRef imageRef = CGWindowListCreateImage(imageRect, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault);
            NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc] initWithCGImage:imageRef];
            CGImageRelease(imageRef);
            NSColor *color = [bitmap colorAtX:0 y:0];
            [bitmap release];

            [options.commandOutputHandler write:[NSString stringWithFormat:@"%d %d %d\n", (int)(color.redComponent*255), (int)(color.greenComponent*255), (int)(color.blueComponent*255)]];
"""
new = r"""            CGRect imageRect = CGRectMake(p.x, p.y, 1, 1);
#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000
            /* CGWindowListCreateImage obsoleted in macOS 15; evolving only needs click/dc */
            [options.commandOutputHandler write:@"0 0 0\n"];
#else
            CGImageRef imageRef = CGWindowListCreateImage(imageRect, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault);
            NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc] initWithCGImage:imageRef];
            CGImageRelease(imageRef);
            NSColor *color = [bitmap colorAtX:0 y:0];
            [bitmap release];

            [options.commandOutputHandler write:[NSString stringWithFormat:@"%d %d %d\n", (int)(color.redComponent*255), (int)(color.greenComponent*255), (int)(color.blueComponent*255)]];
#endif
"""
if old in s:
    s = s.replace(old, new)
    with open(path, "w") as f:
        f.write(s)
    print("    补丁已应用")
else:
    if "#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000" in s:
        print("    已是 macOS 15 补丁版本，跳过")
    else:
        print("    未找到预期代码块")
        exit(1)
PY

echo "==> 编译"
make

echo "==> 安装（需要 sudo）"
sudo mkdir -p /usr/local/bin
sudo cp cliclick /usr/local/bin/
echo "    已安装: /usr/local/bin/cliclick"
if [[ -d /opt/homebrew/bin ]]; then
  sudo cp cliclick /opt/homebrew/bin/ 2>/dev/null && echo "    已复制到: /opt/homebrew/bin/cliclick" || true
fi
/usr/local/bin/cliclick 2>&1 | head -3

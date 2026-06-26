# Mouse Remapper

键盘/鼠标按键重映射工具，支持将按键映射为其他快捷键组合。

## 安装

```bash
pip install -r requirements.txt
```

## 使用

双击 `mouse_remapper.bat` 或运行：

```bash
python app.py
```

### 功能

- 键盘快捷键重映射（如 Ctrl+P → Ctrl+Alt+W）
- 鼠标按键重映射（如侧键X1 → Ctrl+W）
- 每个映射可单独启用/禁用
- 可视化添加/编辑/删除映射
- 支持录制按键组合
- 系统托盘图标，最小化到托盘
- 开机启动 / 固定到开始菜单

## 项目结构

```
app.py               # 入口
engine.py            # 核心引擎
gui.py               # 图形界面
config.json          # 配置文件
mouse_remapper.bat   # 启动脚本
```

## 配置文件

`config.json` 示例：

```json
{
  "mappings": [
    {
      "trigger": ["ctrl", "p"],
      "output": ["ctrl", "alt", "w"],
      "description": "Ctrl+P -> Ctrl+Alt+W",
      "enabled": true
    }
  ],
  "mouse_mappings": [
    {
      "button": "x1",
      "output": ["ctrl", "w"],
      "description": "鼠标侧键X1 -> Ctrl+W",
      "enabled": true
    }
  ]
}
```

## 辅助脚本

| 脚本 | 说明 |
|------|------|
| `install_startup.bat` | 添加开机启动 |
| `uninstall_startup.bat` | 移除开机启动 |
| `pin_to_start.bat` | 创建快捷方式，可固定到开始菜单 |

## 支持的按键

**修饰键：** `ctrl`, `shift`, `alt`, `cmd`

**字母/数字：** `a-z`, `0-9`

**特殊键：** `space`, `tab`, `enter`, `esc`, `backspace`, `delete`, `up`, `down`, `left`, `right`, `home`, `end`, `page_up`, `page_down`, `f1-f12`

**鼠标按键：** `left`, `right`, `middle`, `x1`, `x2`

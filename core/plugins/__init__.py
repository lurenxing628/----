"""
可选插件/可选依赖框架（Win7 离线交付）。

目标：
- vendor/：额外 site-packages 目录（启动时注入 sys.path）
- plugins/：自研插件模块（动态加载）
- 缺失/失败可回退，且状态可观测（系统页展示 + 日志/留痕）
- 包本身不重导出任何名字，调用方从 core.plugins.manager 导入
"""

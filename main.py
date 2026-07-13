"""手势控制 PPT 第一阶段入口。"""

from app.logging_config import configure_logging


def main() -> int:
    """初始化中文日志并启动 Qt 应用。"""
    configure_logging()
    try:
        from app.main_window import run_application
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print("未安装 PySide6，请先执行：.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
            return 2
        raise
    return run_application()


if __name__ == "__main__":
    raise SystemExit(main())

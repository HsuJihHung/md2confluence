from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker
from ui.main_layout import MainLayout
from ui.config_page import build_config_page

config = ConfluenceConfig()
tracker = FileTracker()


@ui.page("/")
def index():
    dark = ui.dark_mode()
    if config.theme == "dark":
        dark.enable()
    else:
        dark.disable()
    layout = MainLayout(config, tracker)
    layout.build()


@ui.page("/config")
def config_page():
    dark = ui.dark_mode()
    if config.theme == "dark":
        dark.enable()
    else:
        dark.disable()
    build_config_page(config)


def main():
    ui.run(title="md2confluence", port=0, reload=False)


if __name__ == "__main__":
    main()

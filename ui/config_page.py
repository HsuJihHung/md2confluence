# ui/config_page.py — stub, filled in Task 7
from services.confluence_config import ConfluenceConfig


def build_config_page(config: ConfluenceConfig):
    from nicegui import ui
    ui.label("Config page — coming soon").classes("text-gray-400 p-8")

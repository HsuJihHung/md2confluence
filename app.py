import asyncio
from nicegui import app, background_tasks, ui
from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker
from ui.main_layout import MainLayout
from ui.config_page import build_config_page
from ui.readme_page import build_readme_page

config = ConfluenceConfig()
tracker = FileTracker()

connected_clients = 0


@app.on_connect
def handle_connect(*args, **kwargs):
    global connected_clients
    connected_clients += 1


@app.on_disconnect
def handle_disconnect(*args, **kwargs):
    global connected_clients
    connected_clients -= 1

    async def delayed_shutdown():
        await asyncio.sleep(3)
        if connected_clients <= 0:
            app.shutdown()

    background_tasks.create(delayed_shutdown())



@ui.page("/")
def index():
    dark = ui.dark_mode()
    if config.theme == "dark":
        dark.enable()
    else:
        dark.disable()
    ui.add_head_html("""
        <style>
            html {
                zoom: 1.25;
            }
        </style>
    """)
    layout = MainLayout(config, tracker)
    layout.build()
    # Auto-refresh when opening/switching to the index page if a directory is selected
    if config.last_directory:
        asyncio.create_task(layout._refresh())


@ui.page("/config")
def config_page():
    dark = ui.dark_mode()
    if config.theme == "dark":
        dark.enable()
    else:
        dark.disable()
    ui.add_head_html("""
        <style>
            html {
                zoom: 1.25;
            }
        </style>
    """)
    build_config_page(config)


@ui.page("/readme")
def readme_page():
    dark = ui.dark_mode()
    if config.theme == "dark":
        dark.enable()
    else:
        dark.disable()
    ui.add_head_html("""
        <style>
            html {
                zoom: 1.25;
            }
        </style>
    """)
    build_readme_page()


def main():
    ui.run(title="md2confluence", port=0, reload=False)


if __name__ == "__main__":
    main()


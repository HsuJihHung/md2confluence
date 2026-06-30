import os
from nicegui import ui

def build_readme_page():
    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
    content = ""
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading README.md: {e}"
    else:
        content = "README.md file not found in the project root."

    with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Project Documentation").classes("text-xl font-bold text-indigo-600 dark:text-indigo-400")
            ui.button("Back to App", on_click=lambda: ui.navigate.to("/")).props("flat icon=arrow_back")

        with ui.card().classes("w-full p-6"):
            ui.markdown(content).classes("prose dark:prose-invert max-w-none")

        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Back to App", on_click=lambda: ui.navigate.to("/")).props("flat")

from nicegui import ui
from services.confluence_config import ConfluenceConfig, DeploymentType


def build_config_page(config: ConfluenceConfig):
    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
        ui.label("Configuration").classes("text-xl font-bold text-indigo-600 dark:text-indigo-400")

        # --- Connection ---
        with ui.card().classes("w-full"):
            ui.label("Confluence Connection").classes("font-bold text-indigo-600 dark:text-indigo-300 mb-2")

            deployment_toggle = ui.toggle(
                {DeploymentType.CLOUD: "Cloud", DeploymentType.SERVER: "Server / DC"},
                value=config.deployment,
            )

            cloud_section = ui.column().classes("w-full gap-2")
            server_section = ui.column().classes("w-full gap-2")

            with cloud_section:
                ui.label("Cloud Settings").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mt-2")
                cloud_domain = ui.input("Domain", value=config.cloud_domain,
                                        placeholder="yourcompany.atlassian.net").classes("w-full")
                cloud_email = ui.input("Email", value=config.cloud_email).classes("w-full")
                cloud_token = ui.input("API Token", value=config.cloud_api_token,
                                       password=True, password_toggle_button=True).classes("w-full")

            with server_section:
                ui.label("Server Settings").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mt-2")
                server_url = ui.input("Server URL", value=config.server_url,
                                      placeholder="https://confluence.yourcompany.com").classes("w-full")
                server_path = ui.input("Context Path", value=config.server_context_path,
                                       placeholder="/confluence").classes("w-full")
                server_user = ui.input("Username", value=config.server_username).classes("w-full")
                server_pass = ui.input("Password or PAT", value=config.server_password or config.server_pat,
                                       password=True, password_toggle_button=True).classes("w-full")

            default_space = ui.input("Default Space Key", value=config.default_space,
                                     placeholder="TEAM").classes("w-full mt-2")

            def _update_visibility():
                is_cloud = deployment_toggle.value == DeploymentType.CLOUD
                cloud_section.set_visibility(is_cloud)
                server_section.set_visibility(not is_cloud)

            deployment_toggle.on_value_change(lambda _: _update_visibility())
            _update_visibility()

            conn_status = ui.label("").classes("text-xs mt-2")

            async def _test_connection():
                conn_status.classes(replace="text-xs mt-2 text-yellow-600 dark:text-yellow-400")
                conn_status.set_text("Testing connection...")

                domain = cloud_domain.value if deployment_toggle.value == DeploymentType.CLOUD else server_url.value
                if not domain:
                    conn_status.set_text("Domain/URL is required")
                    conn_status.classes(replace="text-xs mt-2 text-red-600 dark:text-red-400")
                    return

                # Create a temporary config object with current UI inputs to test connection
                test_config = ConfluenceConfig()
                test_config.deployment = deployment_toggle.value
                test_config.cloud_domain = cloud_domain.value
                test_config.cloud_email = cloud_email.value
                test_config.cloud_api_token = cloud_token.value
                test_config.server_url = server_url.value
                test_config.server_context_path = server_path.value
                test_config.server_username = server_user.value
                test_config.server_password = server_pass.value
                test_config.default_space = default_space.value

                from nicegui import run
                success, msg = await run.io_bound(test_config.test_connection)
                if success:
                    conn_status.set_text(msg)
                    conn_status.classes(replace="text-xs mt-2 text-green-600 dark:text-green-400")
                else:
                    conn_status.set_text(msg)
                    conn_status.classes(replace="text-xs mt-2 text-red-600 dark:text-red-400")

            ui.button("Test Connection", on_click=_test_connection).classes("mt-2")

        # --- Diagram Rendering ---
        with ui.card().classes("w-full"):
            ui.label("Diagram Rendering").classes("font-bold text-indigo-600 dark:text-indigo-300 mb-2")
            mermaid_toggle = ui.toggle(
                {"local": "Render locally (mmdc)", "macro": "Confluence macro"},
                value=config.mermaid_mode,
            )
            ui.label("Local rendering requires @mermaid-js/mermaid-cli (npm)").classes("text-xs text-gray-600 dark:text-gray-500")
            plantuml_toggle = ui.toggle(
                {"remote": "Remote server", "local": "Local jar", "macro": "Confluence macro"},
                value=config.plantuml_mode,
            ).classes("mt-2")
            plantuml_server_input = ui.input("PlantUML Server URL", value=config.plantuml_server).classes("w-full mt-1")

        # --- Upload Defaults ---
        with ui.card().classes("w-full"):
            ui.label("Upload Defaults").classes("font-bold text-indigo-600 dark:text-indigo-300 mb-2")
            parent_page = ui.input("Default Parent Page ID (optional)",
                                   value=config.default_parent_page_id).classes("w-full")
            skip_title = ui.checkbox("Remove H1 that duplicates page title",
                                     value=config.skip_title_heading)
            auto_images = ui.checkbox("Auto-upload local images as attachments",
                                      value=config.auto_upload_images)

        # --- App Preferences ---
        with ui.card().classes("w-full"):
            ui.label("App Preferences").classes("font-bold text-indigo-600 dark:text-indigo-300 mb-2")
            theme_toggle = ui.toggle({"dark": "Dark", "light": "Light"}, value=config.theme)
            view_toggle = ui.toggle({"flat": "Flat list", "tree": "Tree view"},
                                    value=config.default_view).classes("mt-2")

        # --- Save ---
        def _save():
            config.deployment = deployment_toggle.value
            config.cloud_domain = cloud_domain.value
            config.cloud_email = cloud_email.value
            config.cloud_api_token = cloud_token.value
            config.server_url = server_url.value
            config.server_context_path = server_path.value
            config.server_username = server_user.value
            config.server_password = server_pass.value
            config.default_space = default_space.value
            config.mermaid_mode = mermaid_toggle.value
            config.plantuml_mode = plantuml_toggle.value
            config.plantuml_server = plantuml_server_input.value
            config.default_parent_page_id = parent_page.value
            config.skip_title_heading = skip_title.value
            config.auto_upload_images = auto_images.value
            config.theme = theme_toggle.value
            config.default_view = view_toggle.value
            config.save()
            ui.notify("Settings saved — reload the page for theme changes to take effect", type="positive")

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Back", on_click=lambda: ui.navigate.to("/")).props("flat")
            ui.button("Save Settings", on_click=_save).classes("bg-indigo-600 text-white")

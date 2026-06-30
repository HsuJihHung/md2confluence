import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class DeploymentType(str, Enum):
    CLOUD = "cloud"
    SERVER = "server"


@dataclass
class ConfluenceConfig:
    config_dir: Path = field(default_factory=lambda: Path.home() / ".md2confluence")

    deployment: DeploymentType = DeploymentType.CLOUD

    cloud_domain: str = ""
    cloud_email: str = ""
    cloud_api_token: str = ""

    server_url: str = ""
    server_context_path: str = ""
    server_username: str = ""
    server_password: str = ""
    server_pat: str = ""

    default_space: str = ""

    mermaid_mode: str = "local"       # "local" | "macro"
    plantuml_mode: str = "remote"     # "remote" | "local" | "macro"
    plantuml_server: str = "https://www.plantuml.com/plantuml"

    default_parent_page_id: str = ""
    skip_title_heading: bool = True
    auto_upload_images: bool = True

    theme: str = "dark"               # "dark" | "light"
    default_view: str = "flat"        # "flat" | "tree"
    last_directory: str = ""

    def __post_init__(self):
        self.config_dir = Path(self.config_dir)
        self._settings_file = self.config_dir / "settings.json"
        self._load()

    def _load(self):
        if not self._settings_file.exists():
            return
        try:
            data = json.loads(self._settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return  # fall back to defaults if file is corrupted
        for key, value in data.items():
            try:
                if key == "deployment":
                    value = DeploymentType(value)
                if hasattr(self, key) and key != "config_dir":
                    setattr(self, key, value)
            except ValueError:
                pass  # skip invalid enum values, keep default

    def save(self):
        import os
        import sys
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if k != "config_dir"}
        tmp = self._settings_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._settings_file)
        if sys.platform != "win32":
            import stat
            self._settings_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600 — owner read/write only

    def as_env_dict(self) -> dict[str, str]:
        # default_parent_page_id is passed separately as a CLI flag, not an env var
        if self.deployment == DeploymentType.CLOUD:
            res = {
                "CONFLUENCE_DOMAIN": self.cloud_domain,
                "CONFLUENCE_PATH": "",
                "CONFLUENCE_USER_NAME": self.cloud_email,
                "CONFLUENCE_API_KEY": self.cloud_api_token,
                "CONFLUENCE_SPACE_KEY": self.default_space,
                "CONFLUENCE_API_VERSION": "v2",
            }
        else:
            parsed = urlparse(self.server_url)
            domain = parsed.netloc or self.server_url
            password = self.server_pat or self.server_password
            res = {
                "CONFLUENCE_DOMAIN": domain,
                "CONFLUENCE_PATH": self.server_context_path,
                "CONFLUENCE_USER_NAME": self.server_username,
                "CONFLUENCE_API_KEY": password,
                "CONFLUENCE_SPACE_KEY": self.default_space,
                "CONFLUENCE_API_VERSION": "v1",
            }
        if self.plantuml_server:
            res["PLANTUML_SERVER"] = self.plantuml_server
        return res

    def test_connection(self) -> tuple[bool, str]:
        from md2conf.environment import ConnectionProperties
        from md2conf.api import ConfluenceAPI
        from urllib.parse import urlparse

        if self.deployment == DeploymentType.CLOUD:
            domain = self.cloud_domain
            username = self.cloud_email
            api_key = self.cloud_api_token
            space_key = self.default_space
            api_version = "v2"
            base_path = "/wiki/"
        else:
            parsed = urlparse(self.server_url)
            domain = parsed.netloc or self.server_url
            username = self.server_username
            api_key = self.server_pat or self.server_password
            space_key = self.default_space
            api_version = "v1"

            # Format server context path to start and end with '/' to satisfy validation
            bp = self.server_context_path or "/"
            if not bp.startswith("/"):
                bp = "/" + bp
            if not bp.endswith("/"):
                bp = bp + "/"
            base_path = bp

        if not domain:
            return False, "Domain/URL is required"
        if not api_key:
            return False, "API Token/Password is required"

        try:
            properties = ConnectionProperties(
                domain=domain,
                base_path=base_path,
                user_name=username,
                api_key=api_key,
                space_key=space_key or "DUMMY",
                api_version=api_version,
            )
            with ConfluenceAPI(properties) as session:
                # Always execute a real HTTP request first to verify credentials (especially on Server where space_key_to_id is a no-op)
                session.page_exists("DUMMY_PAGE_FOR_CONNECTION_TEST")

                if space_key:
                    try:
                        session.space_key_to_id(space_key)
                        return True, f"Connection successful! Valid space key '{space_key}'."
                    except Exception as e:
                        err_str = str(e)
                        if "404" in err_str and "space" in err_str.lower():
                            return True, f"Connection successful, but Space Key '{space_key}' was not found (404)."
                        raise e
                else:
                    return True, "Connection successful! (No default space specified)"
        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "Unauthorized" in err_msg:
                return False, "Authentication failed: 401 Unauthorized. Check your email/username and API token/password."
            elif "403" in err_msg or "Forbidden" in err_msg:
                return False, "Access forbidden: 403 Forbidden. Check your permissions."
            elif "Failed to establish a new connection" in err_msg or "Max retries exceeded" in err_msg:
                return False, f"Could not reach server: {domain}. Check your network and URL."
            return False, f"Connection failed: {err_msg}"

    def fetch_space_key_for_page(self, page_id: str) -> str:
        from md2conf.environment import ConnectionProperties
        from md2conf.api import ConfluenceAPI
        from urllib.parse import urlparse

        if self.deployment == DeploymentType.CLOUD:
            domain = self.cloud_domain
            username = self.cloud_email
            api_key = self.cloud_api_token
            space_key = self.default_space
            api_version = "v2"
            base_path = "/wiki/"
        else:
            parsed = urlparse(self.server_url)
            domain = parsed.netloc or self.server_url
            username = self.server_username
            api_key = self.server_pat or self.server_password
            space_key = self.default_space
            api_version = "v1"

            bp = self.server_context_path or "/"
            if not bp.startswith("/"):
                bp = "/" + bp
            if not bp.endswith("/"):
                bp = bp + "/"
            base_path = bp

        if not domain:
            raise ValueError("Domain/URL is required")
        if not api_key:
            raise ValueError("API Token/Password is required")

        properties = ConnectionProperties(
            domain=domain,
            base_path=base_path,
            user_name=username,
            api_key=api_key,
            space_key=space_key or "DUMMY",
            api_version=api_version,
        )
        with ConfluenceAPI(properties) as session:
            page = session.get_page(page_id)
            if not page or not page.spaceId:
                raise ValueError("Could not retrieve space information for this page.")
            return session.space_id_to_key(page.spaceId)


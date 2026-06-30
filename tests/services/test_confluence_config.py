from pathlib import Path
from services.confluence_config import ConfluenceConfig, DeploymentType


def test_default_is_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    assert cfg.deployment == DeploymentType.CLOUD


def test_save_and_load_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "user@co.com"
    cfg.cloud_api_token = "secret"
    cfg.default_space = "TEAM"
    cfg.save()

    cfg2 = ConfluenceConfig(config_dir=tmp_path)
    assert cfg2.cloud_domain == "co.atlassian.net"
    assert cfg2.cloud_email == "user@co.com"
    assert cfg2.cloud_api_token == "secret"
    assert cfg2.default_space == "TEAM"


def test_save_and_load_server(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_url = "https://confluence.co.com"
    cfg.server_context_path = "/wiki"
    cfg.server_username = "jsmith"
    cfg.server_password = "pass"
    cfg.save()

    cfg2 = ConfluenceConfig(config_dir=tmp_path)
    assert cfg2.deployment == DeploymentType.SERVER
    assert cfg2.server_url == "https://confluence.co.com"
    assert cfg2.server_context_path == "/wiki"


def test_as_env_dict_cloud(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "co.atlassian.net"
    cfg.cloud_email = "user@co.com"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "TEAM"
    env = cfg.as_env_dict()
    assert env["CONFLUENCE_DOMAIN"] == "co.atlassian.net"
    assert env["CONFLUENCE_USER_NAME"] == "user@co.com"
    assert env["CONFLUENCE_API_KEY"] == "tok"
    assert env["CONFLUENCE_SPACE_KEY"] == "TEAM"


def test_as_env_dict_server(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_url = "https://confluence.co.com"
    cfg.server_context_path = "/wiki"
    cfg.server_username = "jsmith"
    cfg.server_password = "pass"
    cfg.default_space = "DEV"
    env = cfg.as_env_dict()
    assert env["CONFLUENCE_DOMAIN"] == "confluence.co.com"
    assert env["CONFLUENCE_PATH"] == "/wiki"
    assert env["CONFLUENCE_USER_NAME"] == "jsmith"
    assert env["CONFLUENCE_API_KEY"] == "pass"
    assert env["CONFLUENCE_SPACE_KEY"] == "DEV"


def test_as_env_dict_server_pat_takes_priority(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_url = "https://confluence.co.com"
    cfg.server_username = "jsmith"
    cfg.server_password = "password"
    cfg.server_pat = "my-pat-token"
    env = cfg.as_env_dict()
    assert env["CONFLUENCE_API_KEY"] == "my-pat-token"


def test_load_ignores_unknown_keys(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"bogus_key": "value", "cloud_domain": "test.atlassian.net"}', encoding="utf-8")
    cfg = ConfluenceConfig(config_dir=tmp_path)
    assert cfg.cloud_domain == "test.atlassian.net"  # known key loaded
    assert not hasattr(cfg, "bogus_key")  # unknown key ignored


def test_load_handles_corrupted_json(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{ not valid json !!!", encoding="utf-8")
    cfg = ConfluenceConfig(config_dir=tmp_path)  # should not raise
    assert cfg.deployment == DeploymentType.CLOUD  # falls back to defaults


def test_save_and_load_server_credentials(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.deployment = DeploymentType.SERVER
    cfg.server_username = "jsmith"
    cfg.server_password = "mypassword"
    cfg.save()
    cfg2 = ConfluenceConfig(config_dir=tmp_path)
    assert cfg2.server_username == "jsmith"
    assert cfg2.server_password == "mypassword"


def test_test_connection_validation_errors(tmp_path):
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = ""
    cfg.cloud_api_token = ""
    success, msg = cfg.test_connection()
    assert not success
    assert "Domain/URL is required" in msg

    cfg.cloud_domain = "test.atlassian.net"
    cfg.cloud_api_token = ""
    success, msg = cfg.test_connection()
    assert not success
    assert "API Token/Password is required" in msg


def test_test_connection_success_with_space(tmp_path):
    from unittest.mock import patch, MagicMock
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "test.atlassian.net"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "SPACE"

    with patch("md2conf.api.ConfluenceAPI") as mock_api_class:
        mock_api_instance = MagicMock()
        mock_api_class.return_value.__enter__.return_value = mock_api_instance
        
        success, msg = cfg.test_connection()
        assert success
        assert "Valid space key" in msg
        mock_api_instance.page_exists.assert_called_once_with("DUMMY_PAGE_FOR_CONNECTION_TEST")
        mock_api_instance.space_key_to_id.assert_called_once_with("SPACE")


def test_test_connection_space_not_found(tmp_path):
    from unittest.mock import patch, MagicMock
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "test.atlassian.net"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "SPACE"

    with patch("md2conf.api.ConfluenceAPI") as mock_api_class:
        mock_api_instance = MagicMock()
        mock_api_instance.space_key_to_id.side_effect = Exception("404 Space Not Found")
        mock_api_class.return_value.__enter__.return_value = mock_api_instance
        
        success, msg = cfg.test_connection()
        assert success
        assert "Space Key 'SPACE' was not found (404)" in msg
        mock_api_instance.page_exists.assert_called_once_with("DUMMY_PAGE_FOR_CONNECTION_TEST")


def test_test_connection_unauthorized(tmp_path):
    from unittest.mock import patch, MagicMock
    cfg = ConfluenceConfig(config_dir=tmp_path)
    cfg.cloud_domain = "test.atlassian.net"
    cfg.cloud_api_token = "tok"
    cfg.default_space = "SPACE"

    with patch("md2conf.api.ConfluenceAPI") as mock_api_class:
        mock_api_instance = MagicMock()
        mock_api_instance.page_exists.side_effect = Exception("401 Unauthorized")
        mock_api_class.return_value.__enter__.return_value = mock_api_instance
        
        success, msg = cfg.test_connection()
        assert not success
        assert "Authentication failed" in msg

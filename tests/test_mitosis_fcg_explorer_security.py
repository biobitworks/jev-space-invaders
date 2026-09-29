from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_credential_bearing_mitosis_path_does_not_run_npx():
    text = (ROOT / "tools/vithia_e2e_lib.py").read_text()
    assert 'cmd = [str(mitosis_binary()), *args]' in text
    assert 'cmd = ["npx"' not in text


def test_mitosis_binary_requires_prebootstrap_override():
    text = (ROOT / "tools/vithia_e2e_lib.py").read_text()
    assert "VITHIA_MI_BIN_NOT_SET" in text
    assert 'os.environ.get("VITHIA_MI_BIN")' in text


def test_bootstrap_strips_provider_secrets_before_npm_install():
    text = (ROOT / "tools/bootstrap_mitosis_cli.sh").read_text()
    install_at = text.index("npm install")
    for token in (
        "unset MI_API_KEY MITOSIS_API_KEY TENKI_API_KEY TYPESAFE_API_KEY",
        "unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN",
    ):
        assert text.index(token) < install_at


def test_bootstrap_pins_exact_sdk_version():
    text = (ROOT / "tools/bootstrap_mitosis_cli.sh").read_text()
    assert 'VERSION="0.27.2"' in text
    assert '@mitosislabs/sdk@$VERSION' in text
    assert "@latest" not in text


def test_gum_bootstraps_before_password_prompt():
    text = (ROOT / "tools/gum_mitosis_fcg_explorer.sh").read_text()
    assert text.index("bootstrap_mitosis_cli.sh") < text.index("gum input --password")


def test_typesafe_is_not_silently_substituted():
    text = (ROOT / "docs/MITOSIS_FCG_EXPLORER_V1.md").read_text()
    assert "TYPESAFE_BILLING=NOT_CONFIGURED" in text
    assert "TYPESAFE_PLAYGROUND=UNAVAILABLE" in text
    assert "HOSTED_JEV=NOT_EXECUTED" in text

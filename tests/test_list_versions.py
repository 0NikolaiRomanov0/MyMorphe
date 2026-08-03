"""
Tests for MyMorphe's morphe-cli version detection and parsing.

These are pure-logic tests: no network, no Java, no real CLI invocation.
They use captured sample output from a real `morphe-desktop list-versions`
run so format drift in upstream output is caught here, not silently in CI.
"""

import re
import sys
from pathlib import Path

import pytest

# Make the repo root importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.morphe import Morphe
from utils.common import APP_YOUTUBE, APP_YOUTUBE_MUSIC, APP_REDDIT

# ---------------------------------------------------------------------------
# Fixtures: REAL output captured from morphe-desktop-1.12.0-all.jar with
# patches-1.38.0.mpp on Java 21. This is the exact format the CLI emits today.
# ---------------------------------------------------------------------------
REAL_LIST_VERSIONS_OUTPUT = """\
INFO: Package name: com.google.android.apps.youtube.music
Most common compatible versions:
\t9.15.51 (37 patches)
\t7.29.52 (37 patches)

Package name: com.google.android.youtube
Most common compatible versions:
\t21.04.223 (74 patches)
\t20.51.39 (74 patches)
\t20.31.42 (74 patches)
\t20.21.37 (74 patches)

Package name: com.reddit.frontpage
Most common compatible versions:
\t2026.14.0 (16 patches)
\t2026.04.0 (16 patches)
 
"""

# ---------------------------------------------------------------------------
# Parser test (the mpp bug)
# ---------------------------------------------------------------------------
class TestListVersionsParser:
    """The parser must turn real CLI output into the expected dict."""

    def test_real_output_parses_all_apps(self):
        """The exact real output must produce all 3 apps with their versions."""
        m = Morphe()
        parsed = m._parse_versions(REAL_LIST_VERSIONS_OUTPUT)
        assert parsed[APP_YOUTUBE] == ["21.04.223", "20.51.39", "20.31.42", "20.21.37"]
        assert parsed[APP_YOUTUBE_MUSIC] == ["9.15.51", "7.29.52"]
        assert parsed[APP_REDDIT] == ["2026.14.0", "2026.04.0"]

    def test_real_output_without_info_prefix(self):
        """Older CLI emitted no 'INFO: ' prefix; parser must still work."""
        m = Morphe()
        parsed = m._parse_versions(REAL_LIST_VERSIONS_OUTPUT.replace("INFO: ", ""))
        assert parsed[APP_YOUTUBE] == ["21.04.223", "20.51.39", "20.31.42", "20.21.37"]

    def test_empty_output_raises(self):
        """Empty output must raise, never silently return an empty dict."""
        m = Morphe()
        with pytest.raises(RuntimeError):
            m._parse_versions("")

    def test_whitespace_only_output_raises(self):
        m = Morphe()
        with pytest.raises(RuntimeError):
            m._parse_versions("   \n  \n")

    def test_unknown_package_is_skipped(self):
        """A package we don't track must not pollute results."""
        m = Morphe()
        out = "Package name: com.something.else\nMost common compatible versions:\n\t1.0.0 (5 patches)\n"
        parsed = m._parse_versions(out)
        assert parsed[APP_YOUTUBE] == []
        assert parsed[APP_YOUTUBE_MUSIC] == []
        assert parsed[APP_REDDIT] == []

    def test_any_placeholder_is_ignored(self):
        """CLI prints 'Any' when no versions are compatible; parser must not crash."""
        m = Morphe()
        out = "Package name: com.google.android.youtube\nMost common compatible versions:\n\tAny\n"
        parsed = m._parse_versions(out)
        assert parsed[APP_YOUTUBE] == []


# ---------------------------------------------------------------------------
# CLI jar version extraction test (the renamed-jar bug)
# ---------------------------------------------------------------------------
class TestCliVersionExtraction:
    @pytest.mark.parametrize(
        "asset_name,expected",
        [
            ("morphe-cli-1.12.0.jar", "1.12.0"),                       # legacy
            ("morphe-cli-morphe-desktop-1.12.0-all.jar", "1.12.0"),     # new full name
            ("morphe-desktop-1.12.0-all.jar", "1.12.0"),                # new bare name
            ("morphe-cli-2.0.1.jar", "2.0.1"),
        ],
    )
    def test_version_extraction(self, asset_name, expected):
        m = Morphe()
        version = m._extract_cli_version_from_asset_name(asset_name)
        assert version == expected

    @pytest.mark.parametrize(
        "bad_name",
        ["morphe-cli.jar", "morphe-desktop-all.jar", "no-version-here.jar", "random.jar"],
    )
    def test_bad_name_raises(self, bad_name):
        m = Morphe()
        with pytest.raises(Exception):
            m._extract_cli_version_from_asset_name(bad_name)

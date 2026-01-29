import pytest

from kivoll_worker.scrape import kletterzentrum


def test_parse_html_extracts_sections(mock_cli) -> None:
    html = """
    <html>
      <body>
        <h2 class="x-text-content-text-primary">Overall 55%</h2>
        <div class="bar-container">
          <span class="label">Seil</span>
          <div class="bar" data-percentage="42"></div>
        </div>
        <div class="bar-container">
          <span class="label">Boulder</span>
          <div class="bar" data-percentage="68"></div>
        </div>
        <h3>Offene Sektoren</h3>
        <span class="first">7</span>
        <span class="second">12</span>
      </body>
    </html>
    """
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall == 55
    assert parsed.seil == 42
    assert parsed.boulder == 68
    assert parsed.open_sectors == 7
    assert parsed.total_sectors == 12


def test_parse_html_css_fallback_for_sections(mock_cli) -> None:
    html = """
    <html>
      <body>
        <h2>Auslastung 30%</h2>
        <div style="height: 11%"></div>
        <div style="height: 22%"></div>
      </body>
    </html>
    """
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall == 30
    assert parsed.seil == 11
    assert parsed.boulder == 22
    assert parsed.open_sectors is None
    assert parsed.total_sectors is None


def test_cache_html(mock_cli, monkeypatch, tmp_path) -> None:
    # Mock config.data_dir to return tmp_path
    from unittest.mock import Mock

    mock_config = Mock()
    mock_config.data_dir.return_value = tmp_path
    monkeypatch.setattr(kletterzentrum, "config", mock_config)

    html = "<html>Test</html>"
    path = kletterzentrum._cache_html(html)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == html


def test_load_cached_html(mock_cli, monkeypatch, tmp_path) -> None:
    # Mock config.data_dir to return tmp_path
    from unittest.mock import Mock

    mock_config = Mock()
    mock_config.data_dir.return_value = tmp_path
    monkeypatch.setattr(kletterzentrum, "config", mock_config)

    html = "<html>Test</html>"
    file_path = tmp_path / "last_request.html"
    file_path.write_text(html, encoding="utf-8")

    loaded = kletterzentrum._load_cached_html()
    assert loaded == html


def test_load_cached_html_file_not_found(mock_cli, monkeypatch, tmp_path) -> None:
    # Mock config.data_dir to return tmp_path
    from unittest.mock import Mock

    mock_config = Mock()
    mock_config.data_dir.return_value = tmp_path
    monkeypatch.setattr(kletterzentrum, "config", mock_config)
    monkeypatch.setattr(kletterzentrum, "log_error", lambda *args, **kwargs: None)

    with pytest.raises(FileNotFoundError):
        kletterzentrum._load_cached_html()


def test_parse_html_overall_parsing_error(mock_cli, monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "log_error", lambda *args, **kwargs: None)
    html = """
    <html>
      <body>
        <h2>Invalid Overall</h2>
      </body>
    </html>
    """
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall is None  # Should be None due to no match


def test_parse_html_sections_parsing_error(mock_cli, monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "log_error", lambda *args, **kwargs: None)
    html = """
    <html>
      <body>
        <h2>Overall 50%</h2>
        <div class="bar-container">
          <span class="label">Seil</span>
          <div class="bar" data-percentage="invalid"></div>
        </div>
      </body>
    </html>
    """
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall == 50
    assert parsed.seil is None  # Should be None due to invalid percentage


def test_parse_html_open_sectors_parsing_error(mock_cli, monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "log_error", lambda *args, **kwargs: None)
    html = """
    <html>
      <body>
        <h2>Overall 50%</h2>
        <h3>Offene Sektoren</h3>
        <span class="first">invalid</span>
        <span class="second">12</span>
      </body>
    </html>
    """
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall == 50
    assert parsed.open_sectors is None  # Should be None due to invalid number
    assert parsed.total_sectors == 12


def test_parse_html_malformed_html(mock_cli, monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "log_error", lambda *args, **kwargs: None)
    html = "<html><body>Malformed</body></html>"
    parsed = kletterzentrum._parse_html(html)
    assert parsed.overall is None
    assert parsed.seil is None
    assert parsed.boulder is None
    assert parsed.open_sectors is None
    assert parsed.total_sectors is None

from kivoll_worker.scrape import kletterzentrum


class _DummyCli:
    def log(self, *args, **kwargs) -> None:
        return None

    def success(self, *args, **kwargs) -> None:
        return None

    def warn(self, *args, **kwargs) -> None:
        return None

    def fail(self, *args, **kwargs) -> None:
        return None


def test_parse_html_extracts_sections(monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "cli", _DummyCli())
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


def test_parse_html_css_fallback_for_sections(monkeypatch) -> None:
    monkeypatch.setattr(kletterzentrum, "cli", _DummyCli())
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

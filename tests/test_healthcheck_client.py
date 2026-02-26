from unittest.mock import MagicMock, patch

from kivoll_worker.healthcheck_client import check_health, main


def test_check_health_success():
    """check_health() returns True when the server responds with HTTP 200."""
    with patch("http.client.HTTPConnection") as mock_conn:
        mock_instance = mock_conn.return_value
        mock_response = MagicMock()
        mock_response.status = 200

        mock_instance.getresponse.return_value = mock_response

        assert check_health(8000, "/health", 5) is True
        mock_conn.assert_called_once_with("localhost", 8000, timeout=5)
        mock_instance.request.assert_called_once_with("GET", "/health")


def test_check_health_failure_status():
    """check_health() returns False when the server responds with a non-200 status."""
    with patch("http.client.HTTPConnection") as mock_conn:
        mock_instance = mock_conn.return_value
        mock_response = MagicMock()
        mock_response.status = 503
        mock_instance.getresponse.return_value = mock_response

        assert check_health(8000, "/health", 5) is False


def test_check_health_exception():
    """check_health() returns False when the HTTP connection raises an exception."""
    with patch("http.client.HTTPConnection") as mock_conn:
        mock_instance = mock_conn.return_value
        mock_instance.request.side_effect = Exception("Network error")

        assert check_health(8000, "/health", 5) is False


def test_main_success():
    """main() exits with code 0 when the healthcheck succeeds."""
    with patch("kivoll_worker.healthcheck_client.check_health", return_value=True):
        with patch("sys.exit") as mock_exit:
            main([])
            mock_exit.assert_called_once_with(0)


def test_main_failure():
    """main() exits with code 1 when the healthcheck fails."""
    with patch("kivoll_worker.healthcheck_client.check_health", return_value=False):
        with patch("sys.exit") as mock_exit:
            main([])
            mock_exit.assert_called_once_with(1)

import argparse
import http.client
import sys


def check_health(port: int, host: str, path: str, timeout: int) -> bool:
    """
    Perform a healthcheck by sending a GET request to the specified port and path.
    :param port: Port of the health server
    :param host: Host of the health server
    :param path: Path of the health endpoint
    :param timeout: Timeout in seconds for the HTTP request
    :return: True if the healthcheck is successful (HTTP 200), False otherwise
    """
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        if response.status == 200:
            return True
        else:
            print(f"Healthcheck failed with status: {response.status}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Healthcheck failed with error: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simple Python healthcheck client")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port of the health server"
    )
    parser.add_argument(
        "--path", type=str, default="/health", help="Path of the health endpoint"
    )
    parser.add_argument("--timeout", type=int, default=5, help="Timeout in seconds")
    parser.add_argument(
        "--host", type=str, default="localhost", help="Host of the health server"
    )
    args = parser.parse_args(argv)

    if check_health(args.port, args.host, args.path, args.timeout):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

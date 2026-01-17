"""Prediction CLI stub for kivoll_worker-predict."""

from kivoll_worker.common.arguments import parse_predict_args


def main() -> int:
    args = parse_predict_args()
    print(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

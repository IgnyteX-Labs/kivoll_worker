from kivoll_worker.common.arguments import parse_manage_args


def main() -> int:
    args = parse_manage_args()
    print(args)
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass

if __name__ == "__main__":
    raise SystemExit(main())

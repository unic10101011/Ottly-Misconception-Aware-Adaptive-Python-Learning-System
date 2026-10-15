"""JSON entry point used only by the parent code runner."""
import json
import sys

from .sandbox import run_code


def main():
    request = json.load(sys.stdin)
    # The parent must terminate the whole process before the old thread timer.
    result = run_code(request['code'], timeout=request['timeout'] + 5, stdin=request.get('stdin', ''))
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

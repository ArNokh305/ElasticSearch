import json

from app.main import app

OUTPUT_PATH = "docs.json"


def main() -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, ensure_ascii=False, indent=2)
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

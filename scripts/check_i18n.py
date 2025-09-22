"""Check that every documentation page has English and Chinese sources."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LOCALES = ("en", "zh")


def localized_pages(locale: str) -> set[str]:
    suffix = f".{locale}.md"
    return {
        path.relative_to(DOCS).as_posix()[: -len(suffix)]
        for path in DOCS.rglob(f"*{suffix}")
    }


def main() -> int:
    pages = {locale: localized_pages(locale) for locale in LOCALES}
    missing = {
        locale: pages[other] - pages[locale]
        for locale, other in (("en", "zh"), ("zh", "en"))
        if pages[other] - pages[locale]
    }
    if missing:
        for locale, paths in missing.items():
            print(f"Missing {locale} documentation:")
            for path in sorted(paths):
                print(f"  - {path}")
        return 1

    print(f"Checked {len(pages['en'])} bilingual documentation pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

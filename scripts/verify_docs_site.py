"""Check generated site destinations and heading anchors before publication."""
from html.parser import HTMLParser
from pathlib import Path
import json
import posixpath
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1] / ".vitepress" / "dist"
BASE = "/python-agent-lab/"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])


def verify(root=ROOT, base=BASE):
    root = root.resolve()
    pages = {file.resolve(): Page(file.read_text(encoding="utf-8")) for file in root.rglob("*.html")}
    failures = []
    count = 0
    if not pages:
        failures.append("No built HTML pages; run npm run docs:build first")
    for file, page in pages.items():
        for href in page.links:
            target = urlsplit(href)
            if target.scheme or target.netloc:
                continue
            path = unquote(target.path)
            if path.startswith("/"):
                if not path.startswith(base):
                    failures.append(f"{file.relative_to(root)}: outside site base: {href}")
                    continue
                relative = path[len(base):]
            else:
                parent = file.parent.relative_to(root).as_posix()
                relative = posixpath.join(parent, path) if path else file.relative_to(root).as_posix()
            destination = (root / relative).resolve()
            if not destination.is_relative_to(root):
                failures.append(f"{file.relative_to(root)}: outside build: {href}")
                continue
            if destination.is_dir():
                destination /= "index.html"
            if not destination.is_file():
                failures.append(f"{file.relative_to(root)}: missing destination: {href}")
                continue
            count += 1
            fragment = unquote(target.fragment)
            if fragment and destination in pages and fragment not in pages[destination].ids:
                failures.append(f"{file.relative_to(root)}: missing anchor: {href}")
    return {"pages": len(pages), "internal_links": count, "failures": failures}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["failures"]))

"""web/ 폴더의 조각(head.html, body.html, app.js)을 합쳐 docs/index.html을 만듭니다.
페이지 모양을 고친 뒤 python build_page.py 를 한 번 실행하세요."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(p):
    with open(os.path.join(ROOT, "web", p), encoding="utf-8") as f:
        return f.read()


def main():
    head, body, js = read("head.html"), read("body.html"), read("app.js")
    head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    html = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + head + '<style>html{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}</style>\n'
            '</head>\n<body>\n' + body + "<script>\n" + js + "</script>\n</body>\n</html>\n")
    with open(os.path.join(ROOT, "docs", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("docs/index.html", len(html) // 1024, "KB")


if __name__ == "__main__":
    main()

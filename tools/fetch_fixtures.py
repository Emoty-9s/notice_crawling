"""Download the five M05 HTML fixture pairs with the Python standard library.

Run explicitly from a regular Windows Python environment with network access.
Importing this module never performs I/O. Stored HTML retains its original
bytes/character encoding; no parsing, selectors or scraper logic is included.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_USER_AGENT = "NoticeMonitor-FixtureFetcher/1.0"

# Confirmed M01 sample URLs. Update a detail URL here if that sample is removed.
TARGETS = {
    "khidi_business": {
        "list": "https://www.khidi.or.kr/board?menuId=MENU01108",
        "detail": "https://www.khidi.or.kr/board/view?boardStyle=&categoryId=&continent=&country=&linkId=48951946&maxIndex=00489508879998&menuId=MENU01108&minIndex=00489499069998&no1=9999999998&pageNum=1&rowCnt=10&schEndDate=&schStartDate=&schText=&schType=0",
    },
    "kised_bid_public": {
        "list": "https://www.kised.or.kr/board.es?bid=0005&mid=a10303000000",
        "detail": "https://www.kised.or.kr/board.es?act=view&bid=0005&list_no=4648&mid=a10303000000&nPage=1&tag=",
    },
    "rda_bid": {
        "list": "https://www.rda.go.kr/board/board.do?mode=list&prgId=bid_bidancmEntry",
        "detail": "https://www.rda.go.kr/board/board.do?boardId=bidancm&currPage=1&dataNo=100000813836&menu_id=ofc&mode=updateCnt&prgId=bid_bidancmEntry&searchKey=&searchVal=",
    },
    "seoul_rnd_notice": {
        "list": "https://seoul.rnbd.kr/client/c030200/c030200_00.jsp",
        "detail": "https://seoul.rnbd.kr/client/c030200/c030200_04.jsp?cPage=1&sField=&sWord=&seqNo=1129",
    },
    "kipa_bid": {
        "list": "https://www.kipa.org/kipa/notice/kw_0402.jsp",
        "detail": "https://www.kipa.org/kipa/notice/kw_0402.jsp?article_no=134746&board_no=15&board_wrapper=/kipa/notice/kw_0402.jsp&mode=view&pager.offset=0",
    },
}


def validate_options(timeout: float, user_agent: str) -> None:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")
    if not user_agent.strip() or any(ord(c) < 32 or ord(c) == 127 for c in user_agent):
        raise ValueError("user-agent must be nonempty and contain no control characters")


def check_html(data: bytes, content_type: str | None) -> None:
    """Reject empty/non-HTML downloads, without assuming any site's DOM."""
    if content_type and content_type.split(";", 1)[0].strip().lower() not in {
        "text/html", "application/xhtml+xml",
    }:
        raise ValueError(f"expected HTML, received {content_type}")
    preview = data[:8192]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        preview = preview.decode("utf-16", errors="replace").encode("utf-8")
    if not re.search(rb"<!doctype\s+html\b|<html\b", preview, re.IGNORECASE):
        raise ValueError("response is empty or has no HTML document marker")


def fetch_fixture(
    url: str, destination: Path, *, timeout: float, user_agent: str,
    overwrite: bool = False, opener: Callable | None = None,
) -> str:
    """Return SAVED/SKIPPED, or raise; download completely before opening a file.

    Default exclusive creation protects an existing file, including a file
    created concurrently. Overwrite uses a temporary file and atomic replace
    so a failed request/write cannot truncate an existing fixture.
    """
    validate_options(timeout, user_agent)
    if destination.exists():
        if not destination.is_file():
            raise ValueError("destination exists and is not a file")
        if not overwrite:
            return "SKIPPED"
    request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    open_url = opener if opener is not None else urlopen
    with open_url(request, timeout=timeout) as response:
        if response.getcode() != 200:
            raise ValueError(f"expected HTTP 200, received {response.getcode()}")
        data = response.read()
        check_html(data, response.headers.get("Content-Type"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as temp:
            temporary = Path(temp.name)
            try:
                temp.write(data)
            except BaseException:
                temp.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        try:
            handle = destination.open("xb")
        except FileExistsError:
            if not destination.is_file():
                raise
            return "SKIPPED"
        try:
            with handle:
                handle.write(data)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return "SAVED"


def collect(
    sources: list[str], *, output: Path = DEFAULT_OUTPUT, timeout: float = 30.0,
    user_agent: str = DEFAULT_USER_AGENT, overwrite: bool = False,
    opener: Callable | None = None,
) -> dict[str, int]:
    """Isolate each download, including detail after a failed list request."""
    validate_options(timeout, user_agent)
    counts = {"SAVED": 0, "SKIPPED": 0, "FAILED": 0}
    for source_id in dict.fromkeys(sources):
        for kind, url in TARGETS[source_id].items():
            destination = output / source_id / f"{kind}.html"
            try:
                status = fetch_fixture(
                    url, destination, timeout=timeout, user_agent=user_agent,
                    overwrite=overwrite, opener=opener,
                )
            except Exception as error:
                counts["FAILED"] += 1
                print(f"FAILED {source_id}/{kind}.html: {type(error).__name__}: {error}")
                continue
            counts[status] += 1
            print(f"{status} {destination}")
    print("SUMMARY " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", nargs="+", choices=list(TARGETS), help="only selected sources (default: all five)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=30.0, help="socket timeout in seconds (default: 30)")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--overwrite", action="store_true", help="replace existing fixtures (default: skip)")
    args = parser.parse_args(argv)
    try:
        validate_options(args.timeout, args.user_agent)
    except ValueError as error:
        parser.error(str(error))
    counts = collect(
        args.site or list(TARGETS), output=args.output_dir.resolve(), timeout=args.timeout,
        user_agent=args.user_agent, overwrite=args.overwrite,
    )
    return 1 if counts["FAILED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

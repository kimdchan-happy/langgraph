"""
Selenium과 pandas를 활용한 **반자동 대학교 게시판 크롤러** 예시입니다.

실행 전 준비사항
-----------------
1. 필요한 패키지를 설치합니다: ``pip install selenium pandas``
2. 로컬 Chrome 버전에 맞는 ChromeDriver를 설치하고 PATH에 추가합니다.
3. 아래 CSS 선택자를 게시판 구조에 맞게 수정합니다. (필요 시 개발자 도구로 확인)

실행 방법
---------
1. ``python examples/board_crawler.py`` 를 실행합니다.
2. 자동으로 열린 Chrome 창에서 **보안 로그인을 직접 진행**하고, 원하는 게시판 **목록 페이지**로 이동합니다.
3. 터미널에 표시되는 단계 안내를 확인하고, 준비가 되면 터미널에서 Enter를 눌러 수집을 시작합니다.
4. 스크립트가 목록의 모든 게시글을 방문하여 제목/작성자/본문/댓글을 수집합니다.
5. 결과가 ``board_data.csv``(UTF-8-sig 인코딩)로 저장되었는지 확인합니다.

필요한 CSS 선택자 값만 수정하면 다른 게시판에도 재사용할 수 있습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ===== CSS selectors (edit these to match your board) =====
# List page
LIST_POST_LINK_SELECTOR = "a.post-link"  # anchors pointing to each post

# Post detail page
TITLE_SELECTOR = "h1.post-title"
AUTHOR_SELECTOR = ".post-author"
CONTENT_SELECTOR = ".post-content"

# Comments
COMMENT_CONTAINER_SELECTOR = ".comment"  # container for each comment
COMMENT_AUTHOR_SELECTOR = ".comment-author"
COMMENT_CONTENT_SELECTOR = ".comment-content"
# ========================================================


@dataclass
class PostData:
    url: str
    title: str
    author: str
    content: str
    comments: str


class BoardCrawler:
    def __init__(self, wait_timeout: int = 10) -> None:
        options = Options()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, wait_timeout)

    def wait_for_user(self) -> None:
        print(
            "Chrome이 열렸습니다. 보안 로그인을 진행하고 원하는 게시판 목록 페이지로 이동하세요."
        )
        print_usage_steps()
        input("준비되면 엔터를 누르세요: ")

    def collect_post_links(self) -> List[str]:
        print("목록 페이지의 게시글 링크를 수집합니다...")
        anchors = self.driver.find_elements(By.CSS_SELECTOR, LIST_POST_LINK_SELECTOR)
        links: List[str] = []
        for anchor in anchors:
            href = anchor.get_attribute("href")
            if href and href not in links:
                links.append(href)
        print(f"{len(links)}개의 링크를 찾았습니다.")
        return links

    def _get_text(self, by: By, selector: str) -> str:
        element = self.wait.until(EC.presence_of_element_located((by, selector)))
        return element.text.strip()

    def _get_optional_text(self, parent, selector: str) -> str:
        try:
            element = parent.find_element(By.CSS_SELECTOR, selector)
            return element.text.strip()
        except NoSuchElementException:
            return ""

    def extract_post(self, url: str) -> PostData:
        print(f"게시글을 수집하는 중: {url}")
        self.driver.get(url)

        title = self._get_text(By.CSS_SELECTOR, TITLE_SELECTOR)
        author = self._get_text(By.CSS_SELECTOR, AUTHOR_SELECTOR)
        content = self._get_text(By.CSS_SELECTOR, CONTENT_SELECTOR)

        comments_text: List[str] = []
        for comment_el in self.driver.find_elements(By.CSS_SELECTOR, COMMENT_CONTAINER_SELECTOR):
            comment_author = self._get_optional_text(comment_el, COMMENT_AUTHOR_SELECTOR)
            comment_content = self._get_optional_text(comment_el, COMMENT_CONTENT_SELECTOR)
            if comment_author or comment_content:
                comments_text.append(f"{comment_author}: {comment_content}".strip())

        return PostData(
            url=url,
            title=title,
            author=author,
            content=content,
            comments="\n".join(comments_text),
        )

    def close(self) -> None:
        self.driver.quit()


def save_to_csv(posts: List[PostData], filename: str = "board_data.csv") -> None:
    df = pd.DataFrame([post.__dict__ for post in posts])
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"{len(posts)}개 게시글을 {filename}에 저장했습니다.")


def print_korean_quickstart() -> None:
    """터미널에 한글 실행 가이드를 출력합니다."""

    print(
        """
==================== 한글 실행 가이드 ====================
1) 사전 준비
   - pip install selenium pandas
   - Chrome 버전에 맞는 ChromeDriver를 설치하고 PATH에 추가
   - 아래 CSS 선택자를 목표 게시판 구조에 맞게 수정

2) 실행 절차
   - python examples/board_crawler.py 실행 후 자동으로 열린 Chrome 창 확인
   - 직접 로그인 및 2차 인증(필요 시) 완료
   - 스크립트에서 안내하는 목록 페이지(게시글 리스트)로 이동
   - 터미널로 돌아와 Enter를 누르면 현재 페이지의 게시글을 수집 시작

3) 결과 확인
   - 수집 완료 후 board_data.csv 파일을 열어 제목/작성자/본문/댓글 확인
   - 한글 깨짐 방지를 위해 UTF-8-sig 인코딩을 사용
=========================================================
"""
    )


def print_usage_steps() -> None:
    print(
        "\n[다음 단계]",
        "1) Chrome 창에서 보안 로그인을 완료합니다.",
        "2) 원하는 게시판의 목록 페이지로 이동합니다.",
        "3) 아래 CSS 선택자가 페이지 구조와 맞는지 확인합니다.",
        f"   - LIST_POST_LINK_SELECTOR: {LIST_POST_LINK_SELECTOR}",
        f"   - TITLE_SELECTOR: {TITLE_SELECTOR}",
        f"   - AUTHOR_SELECTOR: {AUTHOR_SELECTOR}",
        f"   - CONTENT_SELECTOR: {CONTENT_SELECTOR}",
        f"   - COMMENT_CONTAINER_SELECTOR: {COMMENT_CONTAINER_SELECTOR}",
        f"   - COMMENT_AUTHOR_SELECTOR: {COMMENT_AUTHOR_SELECTOR}",
        f"   - COMMENT_CONTENT_SELECTOR: {COMMENT_CONTENT_SELECTOR}",
        "4) 터미널로 돌아와 엔터를 누르면 현재 목록에 있는 모든 게시글을 수집합니다.",
        "5) 수집이 끝나면 board_data.csv 파일을 확인합니다.",
        sep="\n",
    )


def main() -> None:
    print_korean_quickstart()
    crawler = BoardCrawler()
    try:
        crawler.wait_for_user()
        links = crawler.collect_post_links()
        posts = [crawler.extract_post(link) for link in links]
        save_to_csv(posts)
    finally:
        crawler.close()


if __name__ == "__main__":
    main()

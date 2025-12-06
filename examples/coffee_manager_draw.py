"""커피 담당자 추첨 프로그램.

이 스크립트는 커피 담당자를 공정하게 추첨하기 위해 작성되었습니다.
다음과 같은 특징을 제공합니다.

1. CLI 인자로 참여자를 직접 입력하거나 파일에서 불러올 수 있습니다.
2. `--count` 옵션으로 한 번에 여러 명을 추첨할 수 있습니다.
3. `--history-file` 옵션을 사용하면 직전에 당첨된 사람을 피하면서
   모든 사람이 한 번씩 당첨될 때까지 균등하게 분배할 수 있습니다.
4. `--seed` 옵션으로 재현 가능한 결과를 얻을 수 있습니다.

사용 예시
---------

참여자 이름을 직접 나열하고 2명을 뽑기
```
python examples/coffee_manager_draw.py -p 철수 -p 영희 -p 민수 --count 2
```

텍스트 파일에서 참여자를 읽고 당첨 기록을 저장하기
```
python examples/coffee_manager_draw.py --file members.txt --history-file coffee_history.json
```

`members.txt`는 줄마다 한 명씩 이름이 들어 있는 UTF-8 텍스트 파일입니다.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Iterable, List, Sequence


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    """입력 순서를 유지하면서 중복을 제거한다."""
    seen = set()
    result: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def load_participants(participants: Sequence[str], source_file: Path | None) -> List[str]:
    """CLI 인자와 파일에서 참여자 목록을 읽어온다."""
    collected = list(participants)
    if source_file:
        if not source_file.exists():
            raise FileNotFoundError(f"참여자 파일을 찾을 수 없습니다: {source_file}")
        with source_file.open("r", encoding="utf-8") as f:
            collected.extend(line.strip() for line in f if line.strip())
    cleaned = [name for name in collected if name]
    unique_cleaned = unique_preserve_order(cleaned)
    if not unique_cleaned:
        raise ValueError("추첨할 참여자가 최소 1명 이상 필요합니다.")
    return unique_cleaned


def load_history(history_file: Path | None) -> List[str]:
    if not history_file or not history_file.exists():
        return []
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        return data
    return []


def save_history(history_file: Path, history: Sequence[str]) -> None:
    history_file.write_text(json.dumps(list(history), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def draw_participants(participants: Sequence[str], count: int, *, history: Sequence[str] | None = None) -> List[str]:
    """역사 기록을 고려하여 무작위로 참여자를 추첨한다."""
    if count < 1:
        raise ValueError("선발 인원은 1 이상이어야 합니다.")
    pool = list(participants)
    if count > len(pool):
        raise ValueError("선발 인원이 참여자 수보다 많습니다.")

    if not history:
        history = []

    # 최근 당첨자를 제외하여 공정하게 순환하도록 한다.
    available = [name for name in pool if name not in history]
    if len(available) < count:
        # 모두 한 번씩 당첨되었다면 기록을 초기화하고 전체에서 다시 추첨.
        available = pool
    winners = random.sample(available, count)
    return winners


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="커피 담당자를 공정하게 추첨합니다.")
    parser.add_argument(
        "-p",
        "--participant",
        action="append",
        default=[],
        help="참여자 이름. 여러 번 지정하여 여러 명을 추가할 수 있습니다.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="참여자 목록이 들어 있는 텍스트 파일 경로 (줄마다 한 명씩).",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=1,
        help="선발할 인원 수 (기본값: 1).",
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        help="추첨 결과를 저장할 JSON 파일 경로. 공정 분배를 위해 사용됩니다.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="무작위 시드를 지정하여 재현 가능한 결과를 얻습니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    participants = load_participants(args.participant, args.file)

    if args.count > len(participants):
        raise SystemExit("선발 인원 수가 참여자 수보다 많습니다. 인원을 줄여주세요.")

    if args.seed is not None:
        random.seed(args.seed)

    history = load_history(args.history_file)
    winners = draw_participants(participants, args.count, history=history)

    print("☕️ 이번 커피 담당자:")
    for idx, winner in enumerate(winners, start=1):
        print(f"  {idx}. {winner}")

    if args.history_file:
        updated_history = history + winners
        # 중복을 방지하기 위해 마지막 len(participants)개만 유지한다.
        updated_history = updated_history[-len(participants) :]
        args.history_file.parent.mkdir(parents=True, exist_ok=True)
        save_history(args.history_file, updated_history)
        print(f"(결과가 {args.history_file} 파일에 저장되었습니다.)")


if __name__ == "__main__":
    main()

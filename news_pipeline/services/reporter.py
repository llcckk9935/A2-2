"""SQLite 데이터를 집계해 차트와 종합 리포트를 생성한다."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from news_pipeline.database import Database


class ReporterService:
    def __init__(
        self,
        database_path: str | Path,
        *,
        output_directory: str | Path = "reports",
        chart_dpi: int = 150,
    ) -> None:
        self.database = Database(database_path)
        self.output_directory = Path(output_directory)
        self.chart_dpi = chart_dpi

    def generate(
        self,
        *,
        date_from: str | None,
        date_to: str | None,
        category: str | None,
        top_n: int,
        output_format: str,
        output: str | None,
    ) -> list[Path]:
        self._setup_korean_font()
        news = self.database.list_news(
            category=None if category == "all" else category,
            date_from=date_from,
            date_to=date_to,
            limit=None,
        )
        category_counts = self._count_by_category(news)
        date_counts = self._count_by_date(news)
        top_categories = self._top_n_categories(category_counts, top_n)

        pipeline = self.database.get_pipeline_counts()
        summarized_count = sum(
            item.get("summary_status") == "summarized" for item in news
        )
        required_complete_count = sum(
            all(item.get(field) for field in ("source", "category", "title", "canonical_url"))
            for item in news
        )
        content_count = sum(bool(item.get("content")) for item in news)
        metrics = self._calculate_quality_metrics(
            raw_count=pipeline["raw_count"],
            clean_count=len(news),
            duplicate_count=pipeline["duplicate_count"],
            summarized_count=summarized_count,
            required_complete_count=required_complete_count,
            content_count=content_count,
        )
        insight = self.database.get_latest_analysis_result(category)

        output_dir = Path(output) if output else self.output_directory
        output_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = [
            self._draw_category_bar_chart(
                category_counts, output_dir / "category_bar_chart.png"
            ),
            self._draw_date_trend_chart(
                date_counts, output_dir / "date_trend_chart.png"
            ),
        ]
        text = self._build_report_text(
            date_from=date_from,
            date_to=date_to,
            category=category,
            raw_count=pipeline["raw_count"],
            clean_count=len(news),
            metrics=metrics,
            top_categories=top_categories,
            insight=insight,
            chart_paths=chart_paths,
        )
        print(text)
        return chart_paths + [
            self._save_report_file(text, output_dir, output_format)
        ]

    @staticmethod
    def _count_by_category(news_list: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for news in news_list:
            name = news.get("category") or "unknown"
            counts[name] = counts.get(name, 0) + 1
        return counts

    @staticmethod
    def _top_n_categories(
        category_counts: dict[str, int], top_n: int
    ) -> list[tuple[str, int]]:
        return sorted(category_counts.items(), key=lambda pair: (-pair[1], pair[0]))[
            :top_n
        ]

    @staticmethod
    def _calculate_quality_metrics(
        *,
        raw_count: int,
        clean_count: int,
        duplicate_count: int,
        summarized_count: int,
        required_complete_count: int = 0,
        content_count: int = 0,
    ) -> dict[str, float]:
        def safe_ratio(numerator: int, denominator: int) -> float:
            return round(numerator / denominator, 4) if denominator else 0.0

        return {
            "clean_rate": safe_ratio(clean_count, raw_count),
            "duplicate_rate": safe_ratio(duplicate_count, raw_count),
            "summarized_rate": safe_ratio(summarized_count, clean_count),
            "required_field_rate": safe_ratio(required_complete_count, clean_count),
            "content_rate": safe_ratio(content_count, clean_count),
        }

    @staticmethod
    def _count_by_date(news_list: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for news in news_list:
            published_at = news.get("published_at")
            if not published_at:
                continue
            date_only = str(published_at)[:10]
            counts[date_only] = counts.get(date_only, 0) + 1
        return dict(sorted(counts.items()))

    def _draw_category_bar_chart(
        self, category_counts: dict[str, int], output_path: Path
    ) -> Path:
        fig, ax = plt.subplots()
        ax.bar(list(category_counts), list(category_counts.values()))
        ax.set_title("카테고리별 뉴스 수")
        ax.set_xlabel("카테고리")
        ax.set_ylabel("건수")
        fig.tight_layout()
        fig.savefig(output_path, dpi=self.chart_dpi)
        plt.close(fig)
        return output_path

    def _draw_date_trend_chart(
        self, date_counts: dict[str, int], output_path: Path
    ) -> Path:
        fig, ax = plt.subplots()
        ax.plot(list(date_counts), list(date_counts.values()), marker="o")
        ax.set_title("일자별 뉴스 수집 추이")
        ax.set_xlabel("날짜")
        ax.set_ylabel("건수")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_path, dpi=self.chart_dpi)
        plt.close(fig)
        return output_path

    @staticmethod
    def _setup_korean_font() -> None:
        logger = logging.getLogger(__name__)
        candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic"]
        installed_fonts = {font.name for font in font_manager.fontManager.ttflist}
        for name in candidates:
            if name in installed_fonts:
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return
        logger.warning("사용 가능한 한글 폰트를 찾지 못했습니다. 차트의 한글이 깨질 수 있습니다.")

    @staticmethod
    def _build_report_text(
        *,
        date_from: str | None,
        date_to: str | None,
        category: str | None,
        raw_count: int,
        clean_count: int,
        metrics: dict[str, float],
        top_categories: list[tuple[str, int]],
        insight: dict | None,
        chart_paths: list[Path],
    ) -> str:
        lines = [
            "# 뉴스 데이터 파이프라인 리포트",
            f"- 생성 시각: {datetime.now().isoformat()}",
            f"- 기간: {date_from or '전체'} ~ {date_to or '전체'}",
            f"- 카테고리: {category or '전체'}",
            "",
            "## 데이터 현황",
            f"- raw 뉴스 수: {raw_count}",
            f"- clean 뉴스 수: {clean_count}",
            "",
            "## 품질 지표",
            f"- 정제 성공률(clean/raw): {metrics['clean_rate']}",
            f"- 중복 발생률(duplicate/raw): {metrics['duplicate_rate']}",
            f"- 요약 완료율(summarized/clean): {metrics['summarized_rate']}",
            f"- 필수 필드 완성률: {metrics['required_field_rate']}",
            f"- 본문 확보율: {metrics['content_rate']}",
            "",
            "## 카테고리별 TOP N",
        ]
        lines.extend(f"- {name}: {count}건" for name, count in top_categories)
        if not top_categories:
            lines.append("- 집계할 뉴스가 없습니다.")
        lines.extend(["", "## AI 인사이트"])
        if insight is None:
            lines.append("- AI 분석 결과가 없습니다.")
        else:
            for label, key in (
                ("주요 트렌드", "trends"),
                ("핵심 키워드", "keywords"),
                ("주요 이슈", "major_issues"),
                ("공통점", "common_points"),
                ("차이점", "differences"),
                ("시사점", "implications"),
            ):
                values = insight.get(key) or []
                lines.append(f"- {label}: {', '.join(values) if values else '없음'}")
        lines.extend(["", "## 생성된 차트"])
        lines.extend(f"- {path}" for path in chart_paths)
        return "\n".join(lines)

    @staticmethod
    def _save_report_file(
        text: str, output_dir: Path, output_format: str
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = output_dir / f"report_{timestamp}.{output_format}"
        file_path.write_text(text, encoding="utf-8")
        logging.getLogger(__name__).info("리포트 파일 저장 완료: %s", file_path)
        return file_path

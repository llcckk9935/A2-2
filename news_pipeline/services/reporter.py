"""차트와 종합 리포트 생성 서비스 계약."""

from pathlib import Path
import matplotlib.pyplot as plt
import logging
from datetime import datetime
from matplotlib import font_manager


class ReporterService:
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

        all_news = self._fetch_mock_news()
        news = self._filter_news(
            all_news, date_from=date_from, date_to=date_to, category=category
        )

        category_counts = self._count_by_category(news)
        date_counts = self._count_by_date(news)
        top_categories = self._top_n_categories(category_counts, top_n)

        pipeline = self._fetch_mock_pipeline_counts()
        metrics = self._calculate_quality_metrics(
            raw_count=pipeline["raw_count"],
            clean_count=len(news),
            duplicate_count=pipeline["duplicate_count"],
            summarized_count=len(news),
        )

        insight = self._fetch_mock_insight()

        output_dir = Path(output) if output else Path("reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        bar_chart_path = self._draw_category_bar_chart(
            category_counts, output_dir / "category_bar_chart.png"
        )
        trend_chart_path = self._draw_date_trend_chart(
            date_counts, output_dir / "date_trend_chart.png"
        )
        chart_paths = [bar_chart_path, trend_chart_path]

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

        report_path = self._save_report_file(text, output_dir, output_format)

        return chart_paths + [report_path]

    def _fetch_mock_news(self) -> list[dict]:
        """임시 mock 뉴스 데이터. 나중에 실제 DB 조회 함수로 교체 예정."""
        return [
            {
                "id": 1,
                "source": "inews24",
                "category": "it",
                "title": "AI 반도체 시장 급성장",
                "canonical_url": "https://example.com/1",
                "published_at": "2026-08-20",
                "summary_status": "summarized",
                "summary": "AI 반도체 수요가 늘고 있다.",
                "key_points": ["수요 증가", "가격 상승"],
                "summarized_at": "2026-08-20T10:00:00",
                "created_at": "2026-08-20T09:00:00",
                "updated_at": "2026-08-20T09:00:00",
            },
            {
                "id": 2,
                "source": "inews24",
                "category": "economy",
                "title": "금리 동결 발표",
                "canonical_url": "https://example.com/2",
                "published_at": "2026-08-21",
                "summary_status": "summarized",
                "summary": "한국은행이 금리를 동결했다.",
                "key_points": ["금리 동결", "물가 안정"],
                "summarized_at": "2026-08-21T10:00:00",
                "created_at": "2026-08-21T09:00:00",
                "updated_at": "2026-08-21T09:00:00",
            },
        ]
    
    def _fetch_mock_pipeline_counts(self) -> dict[str, int]:
        """raw/중복 처리 mock 통계. 나중에 실제 DB 집계 쿼리로 교체 예정."""
        return {"raw_count": 3, "duplicate_count": 1}
    
    def _count_by_category(self, news_list: list[dict]) -> dict[str, int]:
        """카테고리별 뉴스 개수를 센다."""
        counts: dict[str, int] = {}
        for news in news_list:
            category = news["category"]
            counts[category] = counts.get(category, 0) + 1
        return counts
    
    def _filter_news(
        self,
        news_list: list[dict],
        *,
        date_from: str | None,
        date_to: str | None,
        category: str | None,
    ) -> list[dict]:
        """조건에 맞는 뉴스만 걸러낸다."""
        filtered = []
        for news in news_list:
            if date_from and news["published_at"] < date_from:
                continue
            if date_to and news["published_at"] > date_to:
                continue
            if category and news["category"] != category:
                continue
            filtered.append(news)
        return filtered

    def _top_n_categories(self, category_counts: dict[str, int], top_n: int) -> list[tuple[str, int]]:
        """카테고리별 개수를 많은 순으로 top_n개 뽑는다. 개수가 같으면 이름순으로 정렬해 결과를 안정적으로 만든다."""
        items = list(category_counts.items())
        items.sort(key=lambda pair: (-pair[1], pair[0]))
        return items[:top_n]
    
    def _calculate_quality_metrics(
            self,
            *,
            raw_count: int,
            clean_count: int,
            duplicate_count: int,
            summarized_count: int,
        ) -> dict[str, float]:
            """품질 지표 3개를 계산한다. 분모가 0이어도 오류 없이 0.0을 반환한다."""

            def safe_ratio(numerator: int, denominator: int) -> float:
                if denominator == 0:
                    return 0.0
                return round(numerator / denominator, 4)

            return {
                "clean_rate": safe_ratio(clean_count, raw_count),
                "duplicate_rate": safe_ratio(duplicate_count, raw_count),
                "summarized_rate": safe_ratio(summarized_count, clean_count),
            }
    
    def _count_by_date(self, news_list: list[dict]) -> dict[str, int]:
        """날짜별 뉴스 개수를 센다. published_at 기준 날짜만 사용한다."""
        counts: dict[str, int] = {}
        for news in news_list:
            date_only = news["published_at"][:10]
            counts[date_only] = counts.get(date_only, 0) + 1
        return dict(sorted(counts.items()))
    
    def _draw_category_bar_chart(self, category_counts: dict[str, int], output_path: Path) -> Path:
        """카테고리별 뉴스 수 막대 차트를 그려서 PNG로 저장한다."""
        categories = list(category_counts.keys())
        values = list(category_counts.values())

        fig, ax = plt.subplots()
        ax.bar(categories, values)
        ax.set_title("카테고리별 뉴스 수")
        ax.set_xlabel("카테고리")
        ax.set_ylabel("건수")

        fig.savefig(output_path)
        plt.close(fig)
        return output_path
    
    def _draw_date_trend_chart(self, date_counts: dict[str, int], output_path: Path) -> Path:
        """일자별 수집 추이 선 차트를 그려서 PNG로 저장한다."""
        dates = list(date_counts.keys())
        values = list(date_counts.values())

        fig, ax = plt.subplots()
        ax.plot(dates, values, marker="o")
        ax.set_title("일자별 뉴스 수집 추이")
        ax.set_xlabel("날짜")
        ax.set_ylabel("건수")
        fig.autofmt_xdate()

        fig.savefig(output_path)
        plt.close(fig)
        return output_path
    
    def _setup_korean_font(self) -> None:
        """한글 폰트를 자동 탐색해 matplotlib에 적용한다. 못 찾으면 WARNING 로그만 남기고 계속 진행한다."""
        logger = logging.getLogger(__name__)
        candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic"]
        installed_fonts = {f.name for f in font_manager.fontManager.ttflist}

        for name in candidates:
            if name in installed_fonts:
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return

        logger.warning("사용 가능한 한글 폰트를 찾지 못했습니다. 차트의 한글이 깨질 수 있습니다.")

    def _fetch_mock_insight(self) -> dict | None:
        """임시 mock AI 인사이트. 나중에 analysis_results 조회 함수로 교체 예정."""
        return {
            "trends": ["AI 반도체 관련 뉴스 증가", "금융 정책 뉴스 꾸준함"],
            "keywords": ["AI", "반도체", "금리"],
            "major_issues": ["반도체 공급망 이슈"],
            "implications": ["관련 산업 투자 확대 가능성"],
            "common_points": ["기술과 경제 모두 정책 영향 강조"],
            "differences": ["IT는 성장 전망, 경제는 안정 기조 강조"],
        }
    
    def _build_report_text(
        self,
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
        """리포트 본문 텍스트를 조합한다."""
        lines: list[str] = []
        lines.append("# 뉴스 데이터 파이프라인 리포트")
        lines.append(f"- 생성 시각: {datetime.now().isoformat()}")
        lines.append(f"- 기간: {date_from or '전체'} ~ {date_to or '전체'}")
        lines.append(f"- 카테고리: {category or '전체'}")
        lines.append("")
        lines.append("## 데이터 현황")
        lines.append(f"- raw 뉴스 수: {raw_count}")
        lines.append(f"- clean 뉴스 수: {clean_count}")
        lines.append("")
        lines.append("## 품질 지표")
        lines.append(f"- 정제 성공률(clean/raw): {metrics['clean_rate']}")
        lines.append(f"- 중복 발생률(duplicate/raw): {metrics['duplicate_rate']}")
        lines.append(f"- 요약 완료율(summarized/clean): {metrics['summarized_rate']}")
        lines.append("")
        lines.append("## 카테고리별 TOP N")
        for name, count in top_categories:
            lines.append(f"- {name}: {count}건")
        lines.append("")
        lines.append("## AI 인사이트")
        if insight is None:
            lines.append("- AI 분석 결과가 없습니다.")
        else:
            lines.append(f"- 주요 트렌드: {', '.join(insight['trends'])}")
            lines.append(f"- 핵심 키워드: {', '.join(insight['keywords'])}")
            lines.append(f"- 주요 이슈: {', '.join(insight['major_issues'])}")
            lines.append(f"- 시사점: {', '.join(insight['implications'])}")
        lines.append("")
        lines.append("## 생성된 차트")
        for path in chart_paths:
            lines.append(f"- {path}")
        return "\n".join(lines)

    def _save_report_file(self, text: str, output_dir: Path, output_format: str) -> Path:
        """리포트 텍스트를 파일로 저장한다. 디렉터리가 없으면 만든다."""
        logger = logging.getLogger(__name__)

        output_dir.mkdir(parents=True, exist_ok=True)

        extension = "md" if output_format == "md" else "txt"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = output_dir / f"report_{timestamp}.{extension}"

        file_path.write_text(text, encoding="utf-8")
        logger.info("리포트 파일 저장 완료: %s", file_path)
        return file_path
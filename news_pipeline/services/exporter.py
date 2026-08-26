"""CSV·JSONL·Excel 내보내기 서비스 계약."""

from pathlib import Path
import logging
import csv
import json
from openpyxl import Workbook
from datetime import datetime
from news_pipeline.config import AppConfig, resolve_project_path

class ExporterService:
    def export(
        self,
        *,
        output_format: str,
        status: str,
        category: str | None,
        date_from: str | None,
        date_to: str | None,
        output: str | None,
        config: AppConfig,
        project_root: Path,
    ) -> Path:
        logger = logging.getLogger(__name__)

        logger.info(
            "필터 조건: status=%s, category=%s, date_from=%s, date_to=%s",
            status, category, date_from, date_to,
        )

        all_news = self._fetch_clean_news(config, project_root)
        news = self._filter_clean_news(
            all_news,
            status=status,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )

        if output:
            output_path_candidate = resolve_project_path(project_root, output)
            if output_path_candidate.suffix:
                if output_path_candidate.suffix.lstrip(".") != output_format:
                    raise ValueError(
                        f"--output 확장자({output_path_candidate.suffix})가 "
                        f"--format({output_format})과 일치하지 않습니다."
                    )
                output_path = output_path_candidate
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = output_path_candidate
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"clean_news_{timestamp}.{output_format}"
                output_path = output_dir / filename
        else:
            output_dir = resolve_project_path(project_root, config.export.output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clean_news_{timestamp}.{output_format}"
            output_path = output_dir / filename

        if not news:
            logger.info("조회 결과가 없습니다. 내보낼 데이터가 0건입니다.")

        if output_format == "csv":
            result_path = self._save_csv(news, output_path)
        elif output_format == "jsonl":
            result_path = self._save_jsonl(news, output_path)
        elif output_format == "xlsx":
            result_path = self._save_xlsx(news, output_path)
        else:
            raise ValueError(f"지원하지 않는 형식입니다: {output_format}")

        logger.info("내보내기 완료: %d건, 경로: %s", len(news), result_path)

        return result_path

    def _fetch_clean_news(self, config: AppConfig, project_root: Path) -> list[dict]:
        """config.database.path의 실제 SQLite clean_news 테이블을 조회한다."""
        from news_pipeline.database import Database

        db_path = resolve_project_path(project_root, config.database.path)
        db = Database(str(db_path))
        rows = db.list_news(limit=1_000_000)

        for row in rows:
            key_points = row.get("key_points")
            if isinstance(key_points, str):
                try:
                    row["key_points"] = json.loads(key_points)
                except (json.JSONDecodeError, TypeError):
                    row["key_points"] = []

        return [{col: row.get(col) for col in self.EXPORT_COLUMNS} for row in rows]
        
    def _filter_clean_news(
        self,
        news_list: list[dict],
        *,
        status: str,
        category: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict]:
        """조건에 맞는 clean_news만 걸러낸다."""
        filtered = []
        for news in news_list:
            if status == "summarized" and news["summary_status"] != "summarized":
                continue
            if status == "unsummarized" and news["summary_status"] == "summarized":
                continue
            if category and news["category"] != category:
                continue
            if date_from and news["published_at"] < date_from:
                continue
            if date_to and news["published_at"] > date_to:
                continue
            filtered.append(news)
        return filtered
        
    # 내보낼 컬럼 순서 — 기사 전문, raw_payload 등 내부/민감 정보는 제외
    EXPORT_COLUMNS = (
        "id",
        "source",
        "category",
        "title",
        "canonical_url",
        "published_at",
        "summary_status",
        "summary",
        "key_points",
        "summarized_at",
        "created_at",
        "updated_at",
    )

    def _save_csv(self, news_list: list[dict], output_path: Path) -> Path:
        """clean_news 목록을 CSV 파일로 저장한다."""
        with open(output_path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=self.EXPORT_COLUMNS)
            writer.writeheader()
            for news in news_list:
                row = dict(news)
                row["key_points"] = ", ".join(row["key_points"]) if row["key_points"] else ""
                writer.writerow(row)
        return output_path
    
    def _save_jsonl(self, news_list: list[dict], output_path: Path) -> Path:
        """clean_news 목록을 JSONL 파일로 저장한다. 한 줄에 뉴스 하나씩 기록한다."""
        with open(output_path, "w", encoding="utf-8") as file:
            for news in news_list:
                row = {key: news[key] for key in self.EXPORT_COLUMNS}
                file.write(json.dumps(row, ensure_ascii=False))
                file.write("\n")
        return output_path
    
    def _save_xlsx(self, news_list: list[dict], output_path: Path) -> Path:
        """clean_news 목록을 Excel 파일로 저장한다."""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "clean_news"

        sheet.append(self.EXPORT_COLUMNS)

        for news in news_list:
            key_points = ", ".join(news["key_points"]) if news["key_points"] else ""
            row = []
            for column in self.EXPORT_COLUMNS:
                value = key_points if column == "key_points" else news[column]
                row.append(value)
            sheet.append(row)

        for column_cells in sheet.columns:
            max_length = max(len(str(cell.value)) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = max_length + 2

        workbook.save(output_path)
        return output_path
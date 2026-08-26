"""정제 뉴스를 CSV·JSONL·Excel 파일로 내보낸다."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from news_pipeline.config import AppConfig, resolve_project_path
from news_pipeline.database import Database


LOGGER = logging.getLogger(__name__)


class ExporterService:
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
        news = self._fetch_clean_news(config, project_root)
        news = self._filter_clean_news(
            news,
            status=status,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )
        output_path = self._resolve_output_path(
            output_format, output, config, project_root
        )

        writers = {
            "csv": self._save_csv,
            "jsonl": self._save_jsonl,
            "xlsx": self._save_xlsx,
        }
        try:
            writer = writers[output_format]
        except KeyError as exc:
            raise ValueError(f"지원하지 않는 형식입니다: {output_format}") from exc

        result = writer(news, output_path)
        LOGGER.info("내보내기 완료: %d건, 경로=%s", len(news), result)
        return result

    @staticmethod
    def _fetch_clean_news(config: AppConfig, project_root: Path) -> list[dict]:
        database_path = resolve_project_path(project_root, config.database.path)
        return Database(database_path).list_news(limit=None)

    @staticmethod
    def _date_part(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text[:10] if len(text) >= 10 else None

    def _filter_clean_news(
        self,
        news_list: list[dict],
        *,
        status: str,
        category: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict]:
        filtered: list[dict] = []
        for news in news_list:
            summary_status = news.get("summary_status")
            if status == "summarized" and summary_status != "summarized":
                continue
            if status == "unsummarized" and summary_status == "summarized":
                continue
            if category and category != "all" and news.get("category") != category:
                continue
            published_date = self._date_part(news.get("published_at"))
            if (date_from or date_to) and published_date is None:
                continue
            if date_from and published_date < date_from:
                continue
            if date_to and published_date > date_to:
                continue
            filtered.append(news)
        return filtered

    def _resolve_output_path(
        self,
        output_format: str,
        output: str | None,
        config: AppConfig,
        project_root: Path,
    ) -> Path:
        candidate = resolve_project_path(
            project_root, output or config.export.output_directory
        )
        if candidate.suffix:
            if candidate.suffix.lower() != f".{output_format}":
                raise ValueError(
                    f"--output 확장자({candidate.suffix})가 "
                    f"--format({output_format})과 일치하지 않습니다."
                )
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if candidate.exists():
                raise ValueError(f"기존 파일을 덮어쓸 수 없습니다: {candidate}")
            return candidate
        candidate.mkdir(parents=True, exist_ok=True)
        return self._build_output_path(candidate, output_format)

    @staticmethod
    def _build_output_path(output_dir: Path, output_format: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        base_name = f"clean_news_{timestamp}"
        path = output_dir / f"{base_name}.{output_format}"
        counter = 1
        while path.exists():
            path = output_dir / f"{base_name}_{counter}.{output_format}"
            counter += 1
        return path

    @classmethod
    def _serializable_row(cls, news: dict) -> dict:
        row = {column: news.get(column) for column in cls.EXPORT_COLUMNS}
        key_points = row.get("key_points")
        if isinstance(key_points, str):
            try:
                key_points = json.loads(key_points)
            except (json.JSONDecodeError, TypeError):
                key_points = []
        row["key_points"] = key_points if isinstance(key_points, list) else []
        return row

    def _save_csv(self, news_list: list[dict], output_path: Path) -> Path:
        with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.EXPORT_COLUMNS)
            writer.writeheader()
            for news in news_list:
                row = self._serializable_row(news)
                row["key_points"] = ", ".join(row["key_points"])
                writer.writerow(row)
        return output_path

    def _save_jsonl(self, news_list: list[dict], output_path: Path) -> Path:
        with output_path.open("w", encoding="utf-8") as handle:
            for news in news_list:
                handle.write(
                    json.dumps(self._serializable_row(news), ensure_ascii=False) + "\n"
                )
        return output_path

    def _save_xlsx(self, news_list: list[dict], output_path: Path) -> Path:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "clean_news"
        sheet.append(self.EXPORT_COLUMNS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

        for news in news_list:
            row = self._serializable_row(news)
            row["key_points"] = ", ".join(row["key_points"])
            sheet.append([row[column] for column in self.EXPORT_COLUMNS])

        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for column_cells in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(
                max(max_length + 2, 10), 50
            )
        workbook.save(output_path)
        return output_path

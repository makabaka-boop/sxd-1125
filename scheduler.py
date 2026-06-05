import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from data_processor import load_new_csvs, archive_processed_csvs
from report_generator import generate_html_report

logger = logging.getLogger(__name__)

_scheduler = None
_last_report_path = None


def scheduled_job(hours_threshold=30.0, load_threshold=20.0, coverage_threshold=3):
    global _last_report_path
    logger.info("定时任务：检查新CSV文件...")
    new_data = load_new_csvs()
    if new_data.empty:
        logger.info("未发现新CSV文件，跳过报表生成")
        return
    logger.info(f"发现 {len(new_data)} 条新记录，开始生成报表")
    report_path = generate_html_report(hours_threshold, load_threshold, coverage_threshold)
    _last_report_path = report_path
    archive_processed_csvs()
    logger.info(f"报表已生成：{report_path}")


def start_scheduler(interval_seconds=60, hours_threshold=30.0, load_threshold=20.0, coverage_threshold=3):
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        scheduled_job,
        "interval",
        seconds=interval_seconds,
        args=[hours_threshold, load_threshold, coverage_threshold],
        id="daily_report_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"定时调度器已启动，间隔 {interval_seconds} 秒")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("定时调度器已停止")


def update_thresholds(hours_threshold, load_threshold, coverage_threshold):
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.remove_job("daily_report_job")
        _scheduler.add_job(
            scheduled_job,
            "interval",
            seconds=60,
            args=[hours_threshold, load_threshold, coverage_threshold],
            id="daily_report_job",
            replace_existing=True,
        )


def get_last_report_path():
    return _last_report_path


def trigger_manual_report(hours_threshold=30.0, load_threshold=20.0, coverage_threshold=3):
    global _last_report_path
    report_path = generate_html_report(hours_threshold, load_threshold, coverage_threshold)
    _last_report_path = report_path
    return report_path

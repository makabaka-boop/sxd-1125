import os
import glob
import shutil
import pandas as pd
from datetime import datetime


CSV_INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv_input")
CSV_ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv_archive")


EMPTY_DF_COLUMNS = [
    "记录ID", "日期", "人员姓名", "人员角色",
    "服务时长_小时", "区域", "活动类型", "活动备注", "复核状态", "驳回原因"
]


def load_all_records() -> pd.DataFrame:
    csv_files = glob.glob(os.path.join(CSV_INPUT_DIR, "*.csv"))
    archive_files = glob.glob(os.path.join(CSV_ARCHIVE_DIR, "*.csv"))
    all_files = csv_files + archive_files
    if not all_files:
        return pd.DataFrame(columns=EMPTY_DF_COLUMNS)
    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f, dtype=str)
            if "驳回原因" not in df.columns:
                df["驳回原因"] = ""
            dfs.append(df)
        except Exception:
            continue
    if not dfs:
        return pd.DataFrame(columns=EMPTY_DF_COLUMNS)
    result = pd.concat(dfs, ignore_index=True)
    result["服务时长_小时"] = pd.to_numeric(result["服务时长_小时"], errors="coerce").fillna(0)
    result["日期"] = pd.to_datetime(result["日期"], errors="coerce")
    if "驳回原因" not in result.columns:
        result["驳回原因"] = ""
    result["驳回原因"] = result["驳回原因"].fillna("")
    result["活动备注"] = result["活动备注"].fillna("")
    result["复核状态"] = result["复核状态"].fillna("待复核")
    return result


def load_new_csvs() -> pd.DataFrame:
    csv_files = sorted(glob.glob(os.path.join(CSV_INPUT_DIR, "*.csv")))
    if not csv_files:
        return pd.DataFrame()
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f, dtype=str)
            df["_source_file"] = os.path.basename(f)
            dfs.append(df)
        except Exception:
            continue
    if not dfs:
        return pd.DataFrame()
    result = pd.concat(dfs, ignore_index=True)
    result["服务时长_小时"] = pd.to_numeric(result["服务时长_小时"], errors="coerce").fillna(0)
    result["日期"] = pd.to_datetime(result["日期"], errors="coerce")
    return result


def archive_processed_csvs() -> list:
    csv_files = glob.glob(os.path.join(CSV_INPUT_DIR, "*.csv"))
    moved = []
    for f in csv_files:
        try:
            dest = os.path.join(CSV_ARCHIVE_DIR, os.path.basename(f))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(f))
                dest = os.path.join(CSV_ARCHIVE_DIR, f"{base}_{datetime.now().strftime('%H%M%S')}{ext}")
            shutil.move(f, dest)
            moved.append(os.path.basename(f))
        except Exception:
            continue
    return moved


def add_service_record(record: dict) -> pd.DataFrame:
    csv_dir = CSV_INPUT_DIR
    os.makedirs(csv_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(csv_dir, f"service_{today}_manual.csv")

    new_row = pd.DataFrame([record])
    if os.path.exists(filepath):
        existing = pd.read_csv(filepath, dtype=str)
        if "驳回原因" not in existing.columns:
            existing["驳回原因"] = ""
        if "驳回原因" not in new_row.columns:
            new_row["驳回原因"] = ""
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        if "驳回原因" not in new_row.columns:
            new_row["驳回原因"] = ""
        combined = new_row
    combined.to_csv(filepath, index=False, encoding="utf-8-sig")
    return combined


def update_record_note(record_id: str, note: str) -> bool:
    for dir_path in [CSV_INPUT_DIR, CSV_ARCHIVE_DIR]:
        csv_files = glob.glob(os.path.join(dir_path, "*.csv"))
        for f in csv_files:
            try:
                df = pd.read_csv(f, dtype=str)
                if "记录ID" in df.columns and record_id in df["记录ID"].values:
                    df.loc[df["记录ID"] == record_id, "活动备注"] = note
                    df.to_csv(f, index=False, encoding="utf-8-sig")
                    return True
            except Exception:
                continue
    return False


def reject_record(record_id: str, reason: str) -> bool:
    for dir_path in [CSV_INPUT_DIR, CSV_ARCHIVE_DIR]:
        csv_files = glob.glob(os.path.join(dir_path, "*.csv"))
        for f in csv_files:
            try:
                df = pd.read_csv(f, dtype=str)
                if "记录ID" in df.columns and record_id in df["记录ID"].values:
                    if "驳回原因" not in df.columns:
                        df["驳回原因"] = ""
                    df.loc[df["记录ID"] == record_id, "复核状态"] = "待补充"
                    df.loc[df["记录ID"] == record_id, "驳回原因"] = reason
                    df.to_csv(f, index=False, encoding="utf-8-sig")
                    return True
            except Exception:
                continue
    return False


def resubmit_record(record_id: str, note: str) -> bool:
    for dir_path in [CSV_INPUT_DIR, CSV_ARCHIVE_DIR]:
        csv_files = glob.glob(os.path.join(dir_path, "*.csv"))
        for f in csv_files:
            try:
                df = pd.read_csv(f, dtype=str)
                if "记录ID" in df.columns and record_id in df["记录ID"].values:
                    if "驳回原因" not in df.columns:
                        df["驳回原因"] = ""
                    df.loc[df["记录ID"] == record_id, "活动备注"] = note
                    df.loc[df["记录ID"] == record_id, "复核状态"] = "待复核"
                    df.loc[df["记录ID"] == record_id, "驳回原因"] = ""
                    df.to_csv(f, index=False, encoding="utf-8-sig")
                    return True
            except Exception:
                continue
    return False


def compute_review_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"待复核": 0, "已复核": 0, "待补充": 0, "总计": 0}
    status_col = df["复核状态"].fillna("未知")
    counts = status_col.value_counts().to_dict()
    return {
        "待复核": int(counts.get("待复核", 0)),
        "已复核": int(counts.get("已复核", 0)),
        "待补充": int(counts.get("待补充", 0)),
        "总计": len(df),
    }


def compute_rejection_reasons(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "驳回原因" not in df.columns:
        return pd.DataFrame(columns=["记录ID", "人员姓名", "驳回原因", "日期"])
    rejected = df[df["复核状态"] == "待补充"].copy()
    if rejected.empty:
        return pd.DataFrame(columns=["记录ID", "人员姓名", "驳回原因", "日期"])
    result = rejected[["记录ID", "人员姓名", "驳回原因"]].copy()
    result["日期"] = rejected["日期"].dt.strftime("%Y-%m-%d")
    return result.reset_index(drop=True)


def update_record_status(record_id: str, status: str) -> bool:
    for dir_path in [CSV_INPUT_DIR, CSV_ARCHIVE_DIR]:
        csv_files = glob.glob(os.path.join(dir_path, "*.csv"))
        for f in csv_files:
            try:
                df = pd.read_csv(f, dtype=str)
                if "记录ID" in df.columns and record_id in df["记录ID"].values:
                    df.loc[df["记录ID"] == record_id, "复核状态"] = status
                    df.to_csv(f, index=False, encoding="utf-8-sig")
                    return True
            except Exception:
                continue
    return False


def compute_service_hours_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["日期", "总服务时长", "记录数", "平均服务时长"])
    summary = df.groupby(df["日期"].dt.date).agg(
        总服务时长=("服务时长_小时", "sum"),
        记录数=("服务时长_小时", "count"),
        平均服务时长=("服务时长_小时", "mean")
    ).reset_index()
    summary.columns = ["日期", "总服务时长", "记录数", "平均服务时长"]
    summary = summary.sort_values("日期")
    return summary


def compute_personnel_load(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["人员姓名", "人员角色", "总服务时长", "活动次数", "平均单次时长"])
    summary = df.groupby(["人员姓名", "人员角色"]).agg(
        总服务时长=("服务时长_小时", "sum"),
        活动次数=("服务时长_小时", "count"),
        平均单次时长=("服务时长_小时", "mean")
    ).reset_index()
    summary = summary.sort_values("总服务时长", ascending=False)
    return summary


def compute_region_coverage(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["区域", "服务时长", "活动次数", "覆盖人数"])
    summary = df.groupby("区域").agg(
        服务时长=("服务时长_小时", "sum"),
        活动次数=("服务时长_小时", "count"),
        覆盖人数=("人员姓名", "nunique")
    ).reset_index()
    summary = summary.sort_values("服务时长", ascending=False)
    return summary


def compute_warnings(df: pd.DataFrame, hours_threshold: float, load_threshold: float, coverage_threshold: float) -> dict:
    warnings = {"服务时长预警": [], "人员负载预警": [], "区域覆盖预警": []}

    daily = compute_service_hours_summary(df)
    for _, row in daily.iterrows():
        if row["总服务时长"] < hours_threshold:
            warnings["服务时长预警"].append({
                "日期": str(row["日期"]),
                "类型": "服务时长不足",
                "当前值": round(row["总服务时长"], 1),
                "阈值": hours_threshold,
                "详情": f"当日总服务时长 {row['总服务时长']:.1f}h 低于阈值 {hours_threshold}h"
            })

    personnel = compute_personnel_load(df)
    for _, row in personnel.iterrows():
        if row["总服务时长"] > load_threshold:
            warnings["人员负载预警"].append({
                "人员": row["人员姓名"],
                "角色": row["人员角色"],
                "类型": "负载过高",
                "当前值": round(row["总服务时长"], 1),
                "阈值": load_threshold,
                "详情": f"{row['人员姓名']} 总服务时长 {row['总服务时长']:.1f}h 超过阈值 {load_threshold}h"
            })

    region = compute_region_coverage(df)
    for _, row in region.iterrows():
        if row["覆盖人数"] < coverage_threshold:
            warnings["区域覆盖预警"].append({
                "区域": row["区域"],
                "类型": "覆盖不足",
                "当前值": int(row["覆盖人数"]),
                "阈值": int(coverage_threshold),
                "详情": f"{row['区域']} 覆盖人数 {int(row['覆盖人数'])} 低于阈值 {int(coverage_threshold)}"
            })

    return warnings

import os
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from data_processor import (
    load_all_records,
    add_service_record,
    update_record_note,
    update_record_status,
    compute_service_hours_summary,
    compute_personnel_load,
    compute_region_coverage,
    compute_warnings,
)
from scheduler import (
    start_scheduler,
    stop_scheduler,
    trigger_manual_report,
    get_last_report_path,
)
from report_generator import generate_html_report

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "公益服务报表生成系统"

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

NAV_STYLE = {
    "display": "flex",
    "background": "linear-gradient(135deg, #0984e3, #6c5ce7)",
    "padding": "0",
    "boxShadow": "0 2px 10px rgba(0,0,0,0.15)",
}

NAV_TAB_STYLE = {
    "padding": "16px 28px",
    "color": "rgba(255,255,255,0.75)",
    "cursor": "pointer",
    "fontWeight": "500",
    "fontSize": "15px",
    "borderBottom": "3px solid transparent",
    "transition": "all 0.2s",
    "background": "transparent",
    "display": "flex",
    "alignItems": "center",
    "gap": "8px",
}

NAV_TAB_SELECTED_STYLE = {
    **NAV_TAB_STYLE,
    "color": "#ffffff",
    "borderBottom": "3px solid #ffffff",
    "background": "rgba(255,255,255,0.1)",
}

CARD_STYLE = {
    "background": "white",
    "borderRadius": "12px",
    "padding": "24px",
    "boxShadow": "0 2px 12px rgba(0,0,0,0.06)",
    "marginBottom": "20px",
}

STAT_CARD = {
    "background": "white",
    "borderRadius": "10px",
    "padding": "20px",
    "textAlign": "center",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
    "flex": "1",
    "minWidth": "160px",
}

app.layout = html.Div([
    html.Div([
        html.H1("公益服务报表生成系统", style={
            "color": "white", "margin": "0", "fontSize": "22px",
            "fontWeight": "600", "letterSpacing": "1px"
        }),
    ], style={
        "background": "linear-gradient(135deg, #0984e3, #6c5ce7)",
        "padding": "18px 30px",
        "display": "flex", "alignItems": "center",
        "boxShadow": "0 2px 10px rgba(0,0,0,0.15)",
    }),

    dcc.Tabs(
        id="role-tabs",
        value="tab-manager",
        children=[
            dcc.Tab(label="📋 管理者 — 上传服务记录", value="tab-manager", style=NAV_TAB_STYLE, selected_style=NAV_TAB_SELECTED_STYLE),
            dcc.Tab(label="✏️ 执行者 — 补充活动备注", value="tab-executor", style=NAV_TAB_STYLE, selected_style=NAV_TAB_SELECTED_STYLE),
            dcc.Tab(label="✅ 复核者 — 确认日报输出", value="tab-reviewer", style=NAV_TAB_STYLE, selected_style=NAV_TAB_SELECTED_STYLE),
        ],
        style=NAV_STYLE,
    ),

    html.Div(id="tab-content", style={"padding": "24px 30px", "maxWidth": "1400px", "margin": "0 auto"}),

    dcc.Store(id="session-data"),
    dcc.Store(id="session-thresholds", data={"hours": 30.0, "load": 20.0, "coverage": 3}),
    dcc.Store(id="session-scheduler-running", data=False),
    dcc.Interval(id="scheduler-interval", interval=60000, n_intervals=0, disabled=True),

    html.Div(id="toast-container", style={
        "position": "fixed", "bottom": "20px", "right": "20px", "zIndex": "9999"
    }),
])


@app.callback(
    Output("tab-content", "children"),
    Input("role-tabs", "value"),
    State("session-thresholds", "data"),
)
def render_tab(tab, thresholds):
    if tab == "tab-manager":
        return _render_manager_tab(thresholds)
    elif tab == "tab-executor":
        return _render_executor_tab()
    elif tab == "tab-reviewer":
        return _render_reviewer_tab(thresholds)
    return html.Div()


def _render_manager_tab(thresholds):
    df = load_all_records()
    daily = compute_service_hours_summary(df)
    personnel = compute_personnel_load(df)
    region = compute_region_coverage(df)
    warnings = compute_warnings(df, thresholds["hours"], thresholds["load"], thresholds["coverage"])
    warning_count = sum(len(v) for v in warnings.values())

    return html.Div([
        html.Div([
            html.H2("📊 数据概览", style={"marginTop": "0", "color": "#2d3436"}),
            html.Div([
                html.Div([
                    html.Div(f"{df['服务时长_小时'].sum():.1f}", style={"fontSize": "32px", "fontWeight": "bold", "color": "#0984e3"}),
                    html.Div("总服务时长(h)", style={"color": "#636e72", "marginTop": "5px"}),
                ], style=STAT_CARD),
                html.Div([
                    html.Div(str(len(df)), style={"fontSize": "32px", "fontWeight": "bold", "color": "#0984e3"}),
                    html.Div("总记录数", style={"color": "#636e72", "marginTop": "5px"}),
                ], style=STAT_CARD),
                html.Div([
                    html.Div(str(df["人员姓名"].nunique()), style={"fontSize": "32px", "fontWeight": "bold", "color": "#0984e3"}),
                    html.Div("参与人数", style={"color": "#636e72", "marginTop": "5px"}),
                ], style=STAT_CARD),
                html.Div([
                    html.Div(str(df["区域"].nunique()), style={"fontSize": "32px", "fontWeight": "bold", "color": "#0984e3"}),
                    html.Div("覆盖区域", style={"color": "#636e72", "marginTop": "5px"}),
                ], style=STAT_CARD),
                html.Div([
                    html.Div(str(warning_count), style={"fontSize": "32px", "fontWeight": "bold", "color": "#d63031" if warning_count > 0 else "#00b894"}),
                    html.Div("预警条数", style={"color": "#636e72", "marginTop": "5px"}),
                ], style={**STAT_CARD, "borderLeft": "4px solid #d63031" if warning_count > 0 else "4px solid #00b894"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginBottom": "20px"}),
        ]),

        html.Div([
            html.H2("🚨 阈值预警设置（拖动滑块调整）", style={"marginTop": "0", "color": "#2d3436"}),
            html.Div([
                html.Div([
                    html.Label("服务时长下限阈值（h）", style={"fontWeight": "600", "marginBottom": "5px", "display": "block"}),
                    dcc.Slider(
                        id="threshold-hours", min=10, max=100, step=5,
                        value=thresholds["hours"],
                        marks={i: f"{i}h" for i in range(10, 101, 15)},
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                ], style={"flex": "1", "minWidth": "280px"}),
                html.Div([
                    html.Label("人员负载上限阈值（h）", style={"fontWeight": "600", "marginBottom": "5px", "display": "block"}),
                    dcc.Slider(
                        id="threshold-load", min=10, max=60, step=5,
                        value=thresholds["load"],
                        marks={i: f"{i}h" for i in range(10, 61, 10)},
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                ], style={"flex": "1", "minWidth": "280px"}),
                html.Div([
                    html.Label("区域覆盖人数下限阈值", style={"fontWeight": "600", "marginBottom": "5px", "display": "block"}),
                    dcc.Slider(
                        id="threshold-coverage", min=1, max=10, step=1,
                        value=thresholds["coverage"],
                        marks={i: f"{i}人" for i in range(1, 11)},
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                ], style={"flex": "1", "minWidth": "280px"}),
            ], style={"display": "flex", "gap": "30px", "flexWrap": "wrap"}),
            html.Div(id="warning-list", style={"marginTop": "20px"}),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("📈 每日服务时长趋势", style={"marginTop": "0", "color": "#2d3436"}),
            dcc.Graph(id="chart-daily-hours", figure=_make_daily_hours_chart(daily, thresholds["hours"])),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("👥 人员负载分析", style={"marginTop": "0", "color": "#2d3436"}),
            dcc.Graph(id="chart-personnel-load", figure=_make_personnel_load_chart(personnel, thresholds["load"])),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("🗺 区域覆盖情况", style={"marginTop": "0", "color": "#2d3436"}),
            dcc.Graph(id="chart-region-coverage", figure=_make_region_coverage_chart(region, thresholds["coverage"])),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("📝 新增服务记录", style={"marginTop": "0", "color": "#2d3436"}),
            html.Div([
                html.Div([
                    dcc.Input(id="input-name", placeholder="人员姓名", style={"width": "100%", "padding": "8px 12px", "border": "1px solid #dfe6e9", "borderRadius": "6px"}),
                ], style={"flex": "1", "minWidth": "120px"}),
                html.Div([
                    dcc.Dropdown(id="input-role", options=[
                        {"label": "管理者", "value": "管理者"},
                        {"label": "执行者", "value": "执行者"},
                        {"label": "复核者", "value": "复核者"},
                    ], placeholder="人员角色", style={"width": "100%"}),
                ], style={"flex": "1", "minWidth": "120px"}),
                html.Div([
                    dcc.Input(id="input-hours", type="number", placeholder="服务时长(h)", style={"width": "100%", "padding": "8px 12px", "border": "1px solid #dfe6e9", "borderRadius": "6px"}),
                ], style={"flex": "1", "minWidth": "120px"}),
                html.Div([
                    dcc.Dropdown(id="input-region", options=[
                        {"label": "朝阳区", "value": "朝阳区"},
                        {"label": "海淀区", "value": "海淀区"},
                        {"label": "西城区", "value": "西城区"},
                        {"label": "东城区", "value": "东城区"},
                        {"label": "丰台区", "value": "丰台区"},
                    ], placeholder="区域", style={"width": "100%"}),
                ], style={"flex": "1", "minWidth": "120px"}),
                html.Div([
                    dcc.Dropdown(id="input-activity", options=[
                        {"label": "社区清洁", "value": "社区清洁"},
                        {"label": "助老服务", "value": "助老服务"},
                        {"label": "义诊活动", "value": "义诊活动"},
                        {"label": "环境巡查", "value": "环境巡查"},
                        {"label": "数据整理", "value": "数据整理"},
                    ], placeholder="活动类型", style={"width": "100%"}),
                ], style={"flex": "1", "minWidth": "120px"}),
                html.Div([
                    html.Button("添加记录", id="btn-add-record", n_clicks=0, style={
                        "background": "linear-gradient(135deg, #0984e3, #6c5ce7)",
                        "color": "white", "border": "none", "padding": "8px 20px",
                        "borderRadius": "6px", "cursor": "pointer", "fontWeight": "600",
                        "width": "100%", "fontSize": "14px",
                    }),
                ], style={"flex": "1", "minWidth": "120px"}),
            ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "alignItems": "flex-end"}),
            html.Div(id="add-record-feedback", style={"marginTop": "10px"}),
        ], style=CARD_STYLE),

        html.Div([
            dcc.Upload(
                id="upload-csv",
                children=html.Div([
                    html.I(className="fas fa-cloud-upload-alt", style={"fontSize": "36px", "color": "#0984e3"}),
                    html.P("拖拽或点击上传CSV文件", style={"margin": "10px 0 5px", "color": "#636e72"}),
                    html.Small("支持 .csv 格式，文件将自动解析", style={"color": "#b2bec3"}),
                ]),
                style={
                    "width": "100%", "height": "120px", "lineHeight": "80px",
                    "borderWidth": "2px", "borderStyle": "dashed", "borderRadius": "10px",
                    "borderColor": "#dfe6e9", "textAlign": "center", "background": "#f8f9fa",
                    "cursor": "pointer", "transition": "all 0.2s",
                },
                multiple=True,
            ),
            html.Div(id="upload-feedback", style={"marginTop": "10px"}),
        ], style=CARD_STYLE),
    ])


def _render_executor_tab():
    df = load_all_records()
    records = df.to_dict("records") if not df.empty else []
    table_data = []
    for r in records:
        table_data.append({
            "记录ID": r.get("记录ID", ""),
            "日期": str(r.get("日期", ""))[:10],
            "人员姓名": r.get("人员姓名", ""),
            "服务时长": r.get("服务时长_小时", ""),
            "区域": r.get("区域", ""),
            "活动类型": r.get("活动类型", ""),
            "活动备注": r.get("活动备注", "") or "（空）",
        })

    return html.Div([
        html.Div([
            html.H2("✏️ 补充活动备注", style={"marginTop": "0", "color": "#2d3436"}),
            html.P("选择记录并补充活动备注信息", style={"color": "#636e72", "marginBottom": "15px"}),
            dash_table.DataTable(
                id="records-table",
                data=table_data,
                columns=[
                    {"name": "记录ID", "id": "记录ID"},
                    {"name": "日期", "id": "日期"},
                    {"name": "人员姓名", "id": "人员姓名"},
                    {"name": "服务时长(h)", "id": "服务时长"},
                    {"name": "区域", "id": "区域"},
                    {"name": "活动类型", "id": "活动类型"},
                    {"name": "活动备注", "id": "活动备注"},
                ],
                page_size=15,
                style_table={"overflowX": "auto"},
                style_header={
                    "background": "#0984e3", "color": "white",
                    "fontWeight": "600", "padding": "10px",
                },
                style_cell={
                    "padding": "8px 12px", "textAlign": "left",
                    "borderBottom": "1px solid #dfe6e9",
                    "fontFamily": "-apple-system, 'Microsoft YaHei', sans-serif",
                    "fontSize": "13px",
                },
                style_data_conditional=[
                    {"if": {"filter_query": "{活动备注} = （空）"}, "color": "#d63031", "fontStyle": "italic"},
                ],
                row_selectable="single",
                sort_action="native",
                filter_action="native",
            ),
            html.Div([
                html.Div([
                    html.Label("选择记录ID：", style={"fontWeight": "600"}),
                    dcc.Dropdown(
                        id="note-record-id",
                        options=[{"label": r.get("记录ID", ""), "value": r.get("记录ID", "")} for r in records],
                        placeholder="从表格选择或手动输入",
                        style={"width": "300px"},
                    ),
                ], style={"marginBottom": "15px"}),
                html.Div([
                    html.Label("活动备注：", style={"fontWeight": "600", "display": "block", "marginBottom": "5px"}),
                    dcc.Textarea(
                        id="note-input",
                        placeholder="请输入活动备注内容...",
                        style={"width": "100%", "height": "100px", "padding": "10px", "border": "1px solid #dfe6e9", "borderRadius": "6px", "fontSize": "14px"},
                    ),
                ]),
                html.Button("保存备注", id="btn-save-note", n_clicks=0, style={
                    "background": "linear-gradient(135deg, #0984e3, #6c5ce7)",
                    "color": "white", "border": "none", "padding": "10px 30px",
                    "borderRadius": "6px", "cursor": "pointer", "fontWeight": "600",
                    "marginTop": "10px", "fontSize": "14px",
                }),
            ], style={"marginTop": "20px", "background": "#f8f9fa", "padding": "20px", "borderRadius": "10px"}),
            html.Div(id="save-note-feedback", style={"marginTop": "10px"}),
        ], style=CARD_STYLE),
    ])


def _render_reviewer_tab(thresholds):
    df = load_all_records()
    pending = df[df["复核状态"] == "待复核"] if not df.empty else pd.DataFrame()
    approved = df[df["复核状态"] == "已复核"] if not df.empty else pd.DataFrame()

    pending_data = []
    if not pending.empty:
        for _, r in pending.iterrows():
            pending_data.append({
                "记录ID": r.get("记录ID", ""),
                "日期": str(r.get("日期", ""))[:10],
                "人员姓名": r.get("人员姓名", ""),
                "服务时长": r.get("服务时长_小时", ""),
                "区域": r.get("区域", ""),
                "活动类型": r.get("活动类型", ""),
                "活动备注": r.get("活动备注", "") or "（空）",
            })

    approved_data = []
    if not approved.empty:
        for _, r in approved.iterrows():
            approved_data.append({
                "记录ID": r.get("记录ID", ""),
                "日期": str(r.get("日期", ""))[:10],
                "人员姓名": r.get("人员姓名", ""),
                "服务时长": r.get("服务时长_小时", ""),
                "区域": r.get("区域", ""),
                "活动类型": r.get("活动类型", ""),
                "活动备注": r.get("活动备注", "") or "（空）",
            })

    report_files = []
    if os.path.exists(REPORTS_DIR):
        report_files = sorted(
            [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")],
            reverse=True,
        )[:20]

    return html.Div([
        html.Div([
            html.H2("✅ 待复核记录", style={"marginTop": "0", "color": "#2d3436"}),
            html.P(f"共 {len(pending_data)} 条待复核", style={"color": "#636e72", "marginBottom": "10px"}),
            dash_table.DataTable(
                id="pending-table",
                data=pending_data,
                columns=[
                    {"name": "记录ID", "id": "记录ID"},
                    {"name": "日期", "id": "日期"},
                    {"name": "人员姓名", "id": "人员姓名"},
                    {"name": "服务时长(h)", "id": "服务时长"},
                    {"name": "区域", "id": "区域"},
                    {"name": "活动类型", "id": "活动类型"},
                    {"name": "活动备注", "id": "活动备注"},
                ],
                page_size=10,
                style_table={"overflowX": "auto"},
                style_header={"background": "#d63031", "color": "white", "fontWeight": "600", "padding": "10px"},
                style_cell={"padding": "8px 12px", "textAlign": "left", "borderBottom": "1px solid #dfe6e9", "fontSize": "13px"},
                row_selectable="single",
                sort_action="native",
                filter_action="native",
            ),
            html.Div([
                html.Div([
                    html.Label("选择记录ID：", style={"fontWeight": "600"}),
                    dcc.Dropdown(
                        id="review-record-id",
                        options=[{"label": r["记录ID"], "value": r["记录ID"]} for r in pending_data],
                        placeholder="选择待复核记录",
                        style={"width": "300px"},
                    ),
                ], style={"marginBottom": "10px"}),
                html.Button("✅ 确认复核通过", id="btn-approve", n_clicks=0, style={
                    "background": "#00b894", "color": "white", "border": "none",
                    "padding": "10px 30px", "borderRadius": "6px", "cursor": "pointer",
                    "fontWeight": "600", "fontSize": "14px",
                }),
                html.Button("❌ 驳回", id="btn-reject", n_clicks=0, style={
                    "background": "#d63031", "color": "white", "border": "none",
                    "padding": "10px 30px", "borderRadius": "6px", "cursor": "pointer",
                    "fontWeight": "600", "fontSize": "14px", "marginLeft": "10px",
                }),
            ], style={"marginTop": "15px"}),
            html.Div(id="review-feedback", style={"marginTop": "10px"}),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("📋 已复核记录", style={"marginTop": "0", "color": "#2d3436"}),
            html.P(f"共 {len(approved_data)} 条已复核", style={"color": "#636e72", "marginBottom": "10px"}),
            dash_table.DataTable(
                data=approved_data,
                columns=[
                    {"name": "记录ID", "id": "记录ID"},
                    {"name": "日期", "id": "日期"},
                    {"name": "人员姓名", "id": "人员姓名"},
                    {"name": "服务时长(h)", "id": "服务时长"},
                    {"name": "区域", "id": "区域"},
                    {"name": "活动类型", "id": "活动类型"},
                    {"name": "活动备注", "id": "活动备注"},
                ],
                page_size=10,
                style_table={"overflowX": "auto"},
                style_header={"background": "#00b894", "color": "white", "fontWeight": "600", "padding": "10px"},
                style_cell={"padding": "8px 12px", "textAlign": "left", "borderBottom": "1px solid #dfe6e9", "fontSize": "13px"},
                sort_action="native",
                filter_action="native",
            ),
        ], style=CARD_STYLE),

        html.Div([
            html.H2("📤 日报生成与下载", style={"marginTop": "0", "color": "#2d3436"}),
            html.Div([
                html.Button("🔄 立即生成日报", id="btn-generate-report", n_clicks=0, style={
                    "background": "linear-gradient(135deg, #0984e3, #6c5ce7)",
                    "color": "white", "border": "none", "padding": "12px 30px",
                    "borderRadius": "8px", "cursor": "pointer", "fontWeight": "600",
                    "fontSize": "15px",
                }),
                html.Button("⏱ 启动定时任务", id="btn-start-scheduler", n_clicks=0, style={
                    "background": "#00b894", "color": "white", "border": "none",
                    "padding": "12px 30px", "borderRadius": "8px", "cursor": "pointer",
                    "fontWeight": "600", "fontSize": "15px", "marginLeft": "10px",
                }),
                html.Button("⏹ 停止定时任务", id="btn-stop-scheduler", n_clicks=0, style={
                    "background": "#636e72", "color": "white", "border": "none",
                    "padding": "12px 30px", "borderRadius": "8px", "cursor": "pointer",
                    "fontWeight": "600", "fontSize": "15px", "marginLeft": "10px",
                }),
            ], style={"marginBottom": "15px"}),
            html.Div(id="scheduler-status", style={"marginBottom": "15px"}),
            html.Div(id="generate-report-feedback", style={"marginBottom": "15px"}),

            html.H3("📁 已生成报告", style={"color": "#2d3436"}),
            html.Div(id="report-list", children=_render_report_list(report_files)),
        ], style=CARD_STYLE),
    ])


def _render_report_list(report_files):
    if not report_files:
        return html.P("暂无已生成的报告", style={"color": "#636e72"})
    items = []
    for f in report_files:
        items.append(html.Div([
            html.Span(f"📄 {f}", style={"fontWeight": "500"}),
            html.A("下载", href=f"/reports/{f}", download=f, style={
                "marginLeft": "15px", "color": "#0984e3",
                "textDecoration": "none", "fontWeight": "600",
            }),
        ], style={"padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))
    return html.Div(items)


def _make_daily_hours_chart(daily, threshold):
    fig = go.Figure()
    if not daily.empty:
        dates = [str(d) for d in daily["日期"]]
        fig.add_trace(go.Bar(
            x=dates, y=daily["总服务时长"],
            name="总服务时长",
            marker_color="rgba(9, 132, 227, 0.7)",
            marker_line_color="#0984e3",
            marker_line_width=1,
            hovertemplate="日期: %{x}<br>服务时长: %{y:.1f}h<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=[threshold] * len(dates),
            mode="lines", name=f"预警线 ({threshold}h)",
            line=dict(color="#d63031", width=2, dash="dash"),
            hovertemplate="预警阈值: %{y}h<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white",
        height=350,
        margin=dict(l=50, r=20, t=30, b=50),
        xaxis_title="日期",
        yaxis_title="服务时长 (h)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    return fig


def _make_personnel_load_chart(personnel, threshold):
    fig = go.Figure()
    if not personnel.empty:
        fig.add_trace(go.Bar(
            x=personnel["人员姓名"], y=personnel["总服务时长"],
            name="总服务时长",
            marker_color=personnel["总服务时长"].apply(
                lambda x: "#d63031" if x > threshold else "#0984e3"
            ),
            hovertemplate="人员: %{x}<br>总时长: %{y:.1f}h<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=personnel["人员姓名"], y=[threshold] * len(personnel),
            mode="lines", name=f"预警线 ({threshold}h)",
            line=dict(color="#d63031", width=2, dash="dash"),
            hovertemplate="预警阈值: %{y}h<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white",
        height=400,
        margin=dict(l=50, r=20, t=30, b=80),
        xaxis_title="人员",
        yaxis_title="总服务时长 (h)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        xaxis_tickangle=-30,
    )
    return fig


def _make_region_coverage_chart(region, threshold):
    fig = go.Figure()
    if not region.empty:
        fig.add_trace(go.Bar(
            x=region["区域"], y=region["覆盖人数"],
            name="覆盖人数",
            marker_color=region["覆盖人数"].apply(
                lambda x: "#d63031" if x < threshold else "#00b894"
            ),
            hovertemplate="区域: %{x}<br>覆盖人数: %{y}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=region["区域"], y=[threshold] * len(region),
            mode="lines", name=f"预警线 ({threshold}人)",
            line=dict(color="#d63031", width=2, dash="dash"),
            hovertemplate="预警阈值: %{y}人<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=region["区域"], y=region["服务时长"],
            name="服务时长(h)",
            marker_color="rgba(108, 92, 231, 0.4)",
            visible="legendonly",
            hovertemplate="区域: %{x}<br>服务时长: %{y:.1f}h<extra></extra>",
        ))
    fig.update_layout(
        template="plotly_white",
        height=350,
        margin=dict(l=50, r=20, t=30, b=50),
        xaxis_title="区域",
        yaxis_title="覆盖人数",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        barmode="group",
    )
    return fig


def _make_warning_list(warnings):
    items = []
    icons = {"服务时长预警": "⏰", "人员负载预警": "⚡", "区域覆盖预警": "📍"}
    colors = {"服务时长预警": "#d63031", "人员负载预警": "#e17055", "区域覆盖预警": "#fdcb6e"}

    for category, entries in warnings.items():
        if not entries:
            continue
        color = colors.get(category, "#636e72")
        icon = icons.get(category, "⚠️")
        for e in entries:
            items.append(html.Div([
                html.Span(f"{icon} {e['详情']}", style={"fontWeight": "500"}),
            ], style={
                "padding": "10px 15px",
                "background": f"{color}11",
                "borderLeft": f"4px solid {color}",
                "borderRadius": "6px",
                "marginBottom": "8px",
                "fontSize": "14px",
            }))

    if not items:
        return html.Div("✅ 当前无预警项目", style={"color": "#00b894", "fontWeight": "600", "padding": "10px"})

    return html.Div(items)


@app.callback(
    [
        Output("session-thresholds", "data"),
        Output("warning-list", "children"),
        Output("chart-daily-hours", "figure"),
        Output("chart-personnel-load", "figure"),
        Output("chart-region-coverage", "figure"),
    ],
    [
        Input("threshold-hours", "value"),
        Input("threshold-load", "value"),
        Input("threshold-coverage", "value"),
    ],
)
def update_thresholds(hours, load, coverage):
    thresholds = {
        "hours": float(hours) if hours else 30.0,
        "load": float(load) if load else 20.0,
        "coverage": int(coverage) if coverage else 3,
    }
    df = load_all_records()
    daily = compute_service_hours_summary(df)
    personnel = compute_personnel_load(df)
    region = compute_region_coverage(df)
    warnings = compute_warnings(df, thresholds["hours"], thresholds["load"], thresholds["coverage"])

    return (
        thresholds,
        _make_warning_list(warnings),
        _make_daily_hours_chart(daily, thresholds["hours"]),
        _make_personnel_load_chart(personnel, thresholds["load"]),
        _make_region_coverage_chart(region, thresholds["coverage"]),
    )


@app.callback(
    Output("add-record-feedback", "children"),
    Input("btn-add-record", "n_clicks"),
    [
        State("input-name", "value"),
        State("input-role", "value"),
        State("input-hours", "value"),
        State("input-region", "value"),
        State("input-activity", "value"),
    ],
)
def add_record(n_clicks, name, role, hours, region, activity):
    if n_clicks == 0:
        return ""
    if not all([name, role, hours, region, activity]):
        return html.Div("❌ 请填写所有必填字段", style={"color": "#d63031", "fontWeight": "600"})
    from datetime import datetime as dt
    record = {
        "记录ID": f"REC{dt.now().strftime('%Y%m%d%H%M%S')}",
        "日期": dt.now().strftime("%Y-%m-%d"),
        "人员姓名": name,
        "人员角色": role,
        "服务时长_小时": str(hours),
        "区域": region,
        "活动类型": activity,
        "活动备注": "",
        "复核状态": "待复核",
    }
    add_service_record(record)
    return html.Div("✅ 记录已成功添加！刷新页面查看更新。", style={"color": "#00b894", "fontWeight": "600"})


@app.callback(
    Output("save-note-feedback", "children"),
    Input("btn-save-note", "n_clicks"),
    [
        State("note-record-id", "value"),
        State("note-input", "value"),
    ],
)
def save_note(n_clicks, record_id, note):
    if n_clicks == 0:
        return ""
    if not record_id or not note:
        return html.Div("❌ 请选择记录并输入备注内容", style={"color": "#d63031", "fontWeight": "600"})
    success = update_record_note(record_id, note)
    if success:
        return html.Div(f"✅ 记录 {record_id} 的备注已保存！", style={"color": "#00b894", "fontWeight": "600"})
    return html.Div(f"❌ 未找到记录 {record_id}", style={"color": "#d63031", "fontWeight": "600"})


@app.callback(
    [
        Output("review-feedback", "children"),
        Output("note-record-id", "options", allow_duplicate=True),
    ],
    [
        Input("btn-approve", "n_clicks"),
        Input("btn-reject", "n_clicks"),
    ],
    State("review-record-id", "value"),
    prevent_initial_call=True,
)
def review_record(approve_clicks, reject_clicks, record_id):
    ctx = callback_context
    if not ctx.triggered:
        return "", []
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if not record_id:
        return html.Div("❌ 请选择待复核记录", style={"color": "#d63031", "fontWeight": "600"}), []

    if button_id == "btn-approve":
        update_record_status(record_id, "已复核")
        df = load_all_records()
        pending = df[df["复核状态"] == "待复核"] if not df.empty else pd.DataFrame()
        options = [{"label": r.get("记录ID", ""), "value": r.get("记录ID", "")} for _, r in pending.iterrows()] if not pending.empty else []
        return html.Div(f"✅ 记录 {record_id} 已复核通过", style={"color": "#00b894", "fontWeight": "600"}), options
    elif button_id == "btn-reject":
        update_record_status(record_id, "已驳回")
        df = load_all_records()
        pending = df[df["复核状态"] == "待复核"] if not df.empty else pd.DataFrame()
        options = [{"label": r.get("记录ID", ""), "value": r.get("记录ID", "")} for _, r in pending.iterrows()] if not pending.empty else []
        return html.Div(f"❌ 记录 {record_id} 已驳回", style={"color": "#d63031", "fontWeight": "600"}), options
    return "", []


@app.callback(
    Output("generate-report-feedback", "children"),
    Input("btn-generate-report", "n_clicks"),
    State("session-thresholds", "data"),
)
def generate_report(n_clicks, thresholds):
    if n_clicks == 0:
        return ""
    report_path = trigger_manual_report(
        thresholds.get("hours", 30.0),
        thresholds.get("load", 20.0),
        thresholds.get("coverage", 3),
    )
    filename = os.path.basename(report_path)
    return html.Div([
        f"✅ 日报已生成：{filename}",
        html.A(" 点击下载", href=f"/reports/{filename}", download=filename, style={"color": "#0984e3", "fontWeight": "600"}),
    ], style={"color": "#00b894", "fontWeight": "600"})


@app.callback(
    [
        Output("scheduler-status", "children"),
        Output("scheduler-interval", "disabled"),
        Output("session-scheduler-running", "data"),
    ],
    [
        Input("btn-start-scheduler", "n_clicks"),
        Input("btn-stop-scheduler", "n_clicks"),
    ],
    State("session-thresholds", "data"),
    State("session-scheduler-running", "data"),
)
def toggle_scheduler(start_clicks, stop_clicks, thresholds, is_running):
    ctx = callback_context
    if not ctx.triggered:
        return html.Span("⏹ 定时任务未启动", style={"color": "#636e72"}), True, False

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "btn-start-scheduler":
        start_scheduler(
            interval_seconds=60,
            hours_threshold=thresholds.get("hours", 30.0),
            load_threshold=thresholds.get("load", 20.0),
            coverage_threshold=thresholds.get("coverage", 3),
        )
        return html.Span("⏱ 定时任务运行中（每60秒检查一次）", style={"color": "#00b894", "fontWeight": "600"}), False, True
    elif button_id == "btn-stop-scheduler":
        stop_scheduler()
        return html.Span("⏹ 定时任务已停止", style={"color": "#636e72"}), True, False

    return html.Span("⏹ 定时任务未启动", style={"color": "#636e72"}), True, False


@app.callback(
    Output("upload-feedback", "children"),
    Input("upload-csv", "contents"),
    State("upload-csv", "filename"),
)
def handle_upload(contents, filenames):
    if not contents:
        return ""
    import base64
    from io import StringIO

    results = []
    if not isinstance(contents, list):
        contents = [contents]
    if not isinstance(filenames, list):
        filenames = [filenames]

    csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv_input")
    os.makedirs(csv_dir, exist_ok=True)

    for content, filename in zip(contents, filenames):
        if not filename.endswith(".csv"):
            results.append(html.Div(f"❌ {filename} 不是CSV文件，已跳过", style={"color": "#d63031"}))
            continue
        try:
            content_type, content_string = content.split(",")
            decoded = base64.b64decode(content_string).decode("utf-8")
            df = pd.read_csv(StringIO(decoded))
            dest = os.path.join(csv_dir, filename)
            df.to_csv(dest, index=False, encoding="utf-8-sig")
            results.append(html.Div(f"✅ {filename} 上传成功（{len(df)}条记录）", style={"color": "#00b894"}))
        except Exception as e:
            results.append(html.Div(f"❌ {filename} 解析失败：{str(e)}", style={"color": "#d63031"}))

    return html.Div(results)


@app.callback(
    Output("note-record-id", "value"),
    Input("records-table", "selected_rows"),
    State("records-table", "data"),
)
def on_table_select(selected_rows, data):
    if selected_rows and data:
        idx = selected_rows[0]
        if idx < len(data):
            return data[idx].get("记录ID", "")
    return None


@app.callback(
    Output("review-record-id", "value"),
    Input("pending-table", "selected_rows"),
    State("pending-table", "data"),
)
def on_pending_table_select(selected_rows, data):
    if selected_rows and data:
        idx = selected_rows[0]
        if idx < len(data):
            return data[idx].get("记录ID", "")
    return None


@app.server.route("/reports/<path:filename>")
def serve_report(filename):
    from flask import send_from_directory
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)

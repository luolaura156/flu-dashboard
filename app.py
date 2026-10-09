import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="流感监测面板", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_excel("data.xlsx")
    df.columns = df.columns.str.strip()
    df = df.dropna(how="all")

    numeric_cols = [
        "ILI", "阳性率", "成人ILI", "儿童ILI",
        "甲型H1N1", "甲型H3N2", "乙型Victoria", "甲型未分型", "乙型",
        "A_untyped", "总阳性数", "哨点医院报告病例总数", "平均病例数",
    ]
    for col in numeric_cols:
        if col in df.columns:
            raw = df[col].astype(str).str.strip()
            cleaned = (raw.str.replace("%", "", regex=False)
                          .str.replace("‰", "", regex=False)
                          .str.strip())
            df[col] = pd.to_numeric(cleaned, errors="coerce")

    # 按地区区分：哪些列需要把 0~1 的小数乘 100
    # 香港 ILI 是 ‰，不乘；其余地区的 ILI 和阳性率都是 %，要乘
    pct_cols_by_region = {
        "中国南方": ["ILI", "阳性率"],
        "中国北方": ["ILI", "阳性率"],
        "中国香港": ["阳性率"],          # ILI 是 ‰，不动
        "澳门":     ["成人ILI", "儿童ILI", "阳性率"],
        "台湾":     ["ILI", "阳性率"],
        "韩国":     ["ILI", "阳性率"],   # 韩国 ILI 也是 %
    }

    for region, cols in pct_cols_by_region.items():
        mask = df["region"] == region
        for col in cols:
            if col in df.columns:
                sub_mask = mask & (df[col] > 0) & (df[col] < 1)
                df.loc[sub_mask, col] = df.loc[sub_mask, col] * 100

    df["week"] = (df["week"].astype(str)
                  .str.replace("周", "", regex=False)
                  .str.strip())
    df["week"] = pd.to_numeric(df["week"], errors="coerce")

    df = df.sort_values(["region", "week"]).reset_index(drop=True)
    return df

df = load_data()

REGION_CONFIG = {
    "中国南方": {
        "type": "flu",
        "trend": [
            {"col": "ILI", "unit": "%", "color": "#d62728"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["甲型H1N1", "甲型H3N2", "乙型Victoria"],
    },
    "中国北方": {
        "type": "flu",
        "trend": [
            {"col": "ILI", "unit": "%", "color": "#d62728"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["甲型H1N1", "甲型H3N2", "乙型Victoria"],
    },
    "中国香港": {
        "type": "flu",
        "trend": [
            {"col": "ILI", "unit": "‰", "color": "#d62728"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["甲型H1N1", "甲型H3N2", "乙型"],
    },
    "澳门": {
        "type": "flu",
        "trend": [
            {"col": "成人ILI", "unit": "%", "color": "#d62728"},
            {"col": "儿童ILI", "unit": "%", "color": "#ff7f0e"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["甲型H1N1", "甲型H3N2", "甲型未分型", "乙型"],
    },
    "台湾": {
        "type": "flu",
        "trend": [
            {"col": "ILI", "unit": "%", "color": "#d62728"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["A_untyped", "乙型", "甲型H3N2", "甲型H1N1"],
    },
    "韩国": {
        "type": "flu",
        "trend": [
            {"col": "ILI", "unit": "%", "color": "#d62728"},
            {"col": "阳性率", "unit": "%", "color": "#1f77b4"},
        ],
        "subtype_cols": ["甲型H1N1", "甲型H3N2", "乙型Victoria"],
    },
    "日本": {"type": "japan"},
}


def render_flu_region(region, cfg):
    sub = df[df["region"] == region].sort_values("week").reset_index(drop=True)
    if sub.empty:
        st.warning(f"{region} 没有数据")
        return

    latest = sub.iloc[-1]
    st.subheader(f"{region} · 最新一周（第 {int(latest['week'])} 周）")

    trend_cfgs = cfg["trend"]
    show_total = "总阳性数" in sub.columns and pd.notna(latest.get("总阳性数"))
    n_cards = len(trend_cfgs) + (1 if show_total else 0) + 1
    cards = st.columns(n_cards)

    for i, t in enumerate(trend_cfgs):
        col_name = t["col"]
        unit = t["unit"]
        val = latest.get(col_name)

        if pd.isna(val):
            cards[i].metric(col_name, "N/A")
            continue

        delta_unit = "百分点" if unit == "%" else unit

        delta_str = None
        if len(sub) >= 2:
            prev_val = sub.iloc[-2].get(col_name)
            if pd.notna(prev_val):
                delta = val - prev_val
                delta_str = f"{delta:+.2f} {delta_unit}"

        cards[i].metric(
            col_name,
            f"{val:.2f}{unit}",
            delta=delta_str,
            delta_color="inverse",
        )

    idx = len(trend_cfgs)
    if show_total:
        cards[idx].metric("总阳性数", f"{int(latest['总阳性数'])}")
        idx += 1
    cards[idx].metric("最新周数", f"第 {int(latest['week'])} 周")

    st.divider()
    st.markdown("**周变化趋势（每张图独立）**")

    n = len(trend_cfgs)
    trend_cols = st.columns(n) if n >= 2 else st.columns(1)

    for i, t in enumerate(trend_cfgs):
        col_name = t["col"]
        unit = t["unit"]
        color = t["color"]

        with trend_cols[i]:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=sub["week"], y=sub[col_name],
                mode="lines+markers",
                name=col_name,
                line=dict(width=3, color=color),
                marker=dict(size=8),
            ))
            fig.update_layout(
                title=f"{col_name}（{unit}）",
                xaxis_title="周数",
                height=340,
                margin=dict(l=40, r=20, t=50, b=40),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    subtype_cols = [c for c in cfg["subtype_cols"] if c in sub.columns]

    if subtype_cols:
        st.markdown("**主要毒株占比（最新一周）**")
        row = latest[subtype_cols]
        total = row.sum()
        ratios = {c: (row[c] / total if total > 0 else 0) for c in subtype_cols}

        sorted_ratios = sorted(ratios.items(), key=lambda x: -x[1])
        top_two = [item[0] for item in sorted_ratios[:2]]

        cols2 = st.columns(len(subtype_cols))
        for i, c in enumerate(subtype_cols):
            val = ratios[c]
            if c in top_two:
                cols2[i].markdown(
                    f"<b>{c}</b><br><b style='font-size:20px; color:#d62728;'>{val:.1%}</b>",
                    unsafe_allow_html=True,
                )
            else:
                cols2[i].markdown(
                    f"{c}<br><span style='font-size:20px'>{val:.1%}</span>",
                    unsafe_allow_html=True,
                )

        st.markdown("**各周病毒分型占比**")
        rows = []
        for _, r in sub.iterrows():
            s = r[subtype_cols].sum()
            if s > 0:
                for c in subtype_cols:
                    if pd.notna(r[c]):
                        rows.append({
                            "week": r["week"],
                            "分型": c,
                            "占比": r[c] / s,
                        })
        df_long = pd.DataFrame(rows)

        if not df_long.empty:
            fig_stack = px.bar(
                df_long, x="week", y="占比", color="分型",
                barmode="stack", text_auto=".1%",
            )
            fig_stack.update_layout(
                yaxis_tickformat=".1%",
                xaxis_title="周数",
                yaxis_title="占比",
                height=360,
                legend_title="分型",
            )
            fig_stack.update_traces(textposition="inside")
            st.plotly_chart(fig_stack, use_container_width=True)

    with st.expander(f"查看 {region} 数据明细"):
        st.dataframe(sub, use_container_width=True)


def render_japan():
    sub = df[df["region"] == "日本"].sort_values("week").reset_index(drop=True)
    if sub.empty:
        st.warning("日本没有数据")
        return

    latest = sub.iloc[-1]
    st.subheader(f"日本 · 最新一周（第 {int(latest['week'])} 周）")

    c1, c2, c3 = st.columns(3)

    def delta_of(col):
        if len(sub) < 2:
            return None, None
        val = latest.get(col)
        prev = sub.iloc[-2].get(col)
        if pd.isna(val) or pd.isna(prev):
            return val, None
        return val, val - prev

    v1, d1 = delta_of("哨点医院报告病例总数")
    v2, d2 = delta_of("平均病例数")

    if pd.notna(v1):
        pct1 = (d1 / (v1 - d1) * 100) if d1 is not None and (v1 - d1) != 0 else None
        c1.metric("哨点医院报告病例总数", f"{int(v1):,}",
                  delta=f"{pct1:+.2f}%" if pct1 is not None else None,
                  delta_color="inverse")
    if pd.notna(v2):
        pct2 = (d2 / (v2 - d2) * 100) if d2 is not None and (v2 - d2) != 0 else None
        c2.metric("平均病例数", f"{v2:.2f}",
                  delta=f"{pct2:+.2f}%" if pct2 is not None else None,
                  delta_color="inverse")
    c3.metric("最新周数", f"第 {int(latest['week'])} 周")

    st.divider()
    st.markdown("**周变化趋势**")

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["哨点医院报告病例总数"],
            mode="lines+markers",
            line=dict(width=3, color="#d62728"),
            marker=dict(size=8),
        ))
        fig.update_layout(title="哨点医院报告病例总数", xaxis_title="周数", height=340)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["平均病例数"],
            mode="lines+markers",
            line=dict(width=3, color="#1f77b4"),
            marker=dict(size=8),
        ))
        fig.update_layout(title="平均病例数", xaxis_title="周数", height=340)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看 日本 数据明细"):
        st.dataframe(sub, use_container_width=True)


regions_order = ["中国南方", "中国北方", "中国香港", "澳门", "台湾", "韩国", "日本"]
available = [r for r in regions_order if r in df["region"].unique()]

st.title("流感监测面板")

if not available:
    st.error("没有找到任何区域数据，请检查 data.xlsx 中的 region 列")
else:
    tabs = st.tabs(available)
    for tab, region in zip(tabs, available):
        with tab:
            cfg = REGION_CONFIG.get(region)
            if cfg is None:
                st.warning(f"未配置 {region} 的展示方式")
                continue
            if cfg["type"] == "japan":
                render_japan()
            else:
                render_flu_region(region, cfg)
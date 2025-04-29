import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import datetime
import re
import io

st.set_page_config(page_title="基金回测系统 - 高级版", layout="wide")
st.title("📈 基金定投回测系统（测试版）")

fund_code = st.text_input("基金代码（如：161725）", value="161725")
start_date = st.date_input("起始日期", value=datetime.date(2020, 1, 1))
end_date = st.date_input("结束日期", value=datetime.date.today())
initial_cash = st.number_input("初始资金（元）", value=10000)
invest_amount = st.number_input("每期定投金额", value=1000)
freq = st.selectbox("定投频率", ["每月", "每周"])

stop_profit = st.number_input("止盈比例（%）", value=30.0)
stop_loss = st.number_input("止损比例（%）", value=20.0)

def fetch_fund_nav(code):
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    r = requests.get(url)
    r.encoding = "utf-8"
    if r.status_code != 200:
        return None

    match = re.search(r"var Data_netWorthTrend = (\[.*?\]);", r.text)
    if not match:
        return None
    raw_data = eval(match.group(1))
    df = pd.DataFrame(raw_data)
    df["date"] = pd.to_datetime(df["x"], unit="ms")
    df["nav"] = df["y"]
    return df[["date", "nav"]]

def get_invest_dates(df, freq):
    if freq == "每月":
        return df["date"].dt.to_period("M").drop_duplicates().dt.to_timestamp()
    elif freq == "每周":
        return df["date"].dt.to_period("W").drop_duplicates().dt.to_timestamp()
    else:
        return []

if st.button("开始回测"):
    df = fetch_fund_nav(fund_code)
    if df is None or df.empty:
        st.error("❌ 获取数据失败，请检查基金代码是否正确")
    else:
        st.success("✅ 数据获取成功！")

        st.line_chart(df.set_index("date")["nav"])
        with st.expander("📋 查看原始数据"):
            st.dataframe(df)

        # 导出报告 CSV
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载原始数据 CSV", data=csv, file_name="原始数据.csv", mime="text/csv")

        df = df[(df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))].copy()
        df.reset_index(drop=True, inplace=True)

        invest_dates = get_invest_dates(df, freq)
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        invest_dates = [d for d in invest_dates if d >= start_ts and d <= end_ts]

        invest_records = []

        position = 0
        cash = initial_cash
        reached_stop = False

        for date in invest_dates:
            row = df[df["date"] >= date].head(1)
            if row.empty:
                continue
            price = row["nav"].values[0]
            date = row["date"].values[0]

            if reached_stop:
                break

            # 定投
            shares = invest_amount / price
            position += shares
            cash -= invest_amount
            current_value = position * price
            total_asset = cash + current_value
            return_pct = (total_asset - initial_cash) / initial_cash * 100

            # 止盈止损判断
            if return_pct >= stop_profit:
                reached_stop = True
                reason = "止盈"
            elif return_pct <= -stop_loss:
                reached_stop = True
                reason = "止损"
            else:
                reason = ""

            invest_records.append({
                "date": pd.to_datetime(str(date)).date(),
                "price": price,
                "shares": shares,
                "cash": cash,
                "position_value": position * price,
                "total_asset": total_asset,
                "return_pct": return_pct,
                "reason": reason
            })

        if not invest_records:
            st.warning("没有执行任何定投。")
        else:
            result_df = pd.DataFrame(invest_records)
            st.metric("最终资产净值", f"¥{result_df['total_asset'].iloc[-1]:,.2f}")
            st.metric("累计收益率", f"{result_df['return_pct'].iloc[-1]:.2f}%")

            st.line_chart(result_df.set_index("date")[["total_asset"]])

            # 展示表格
            with st.expander("📋 回测交易记录"):
                st.dataframe(result_df)

            # 导出报告 CSV
            csv = result_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下载回测报告 CSV", data=csv, file_name="回测报告.csv", mime="text/csv")

            st.caption("数据来源：天天基金网 (fund.eastmoney.com)")

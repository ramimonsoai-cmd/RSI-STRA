import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# הגדרת עמוד בסיסית
st.set_page_config(page_title="סימולטור מסחר חי", layout="wide")

st.title("📈 סימולטור מסחר חי: RSI + SMA + Stop Loss")
st.caption("סימולציה מבוססת שווי שוק, ניהול סיכונים כפול והשוואה למדד S&P 500")

# מאגר מניות ושווי שוק משוער במיליארדים (מונע קריסות וחסימות רשת)
STOCK_MARKET_CAPS = {
    "MSFT": 3100, "AAPL": 3400, "NVDA": 3000, "GOOGL": 2000, "AMZN": 1950,
    "META": 1300, "BRK-B": 950, "LLY": 850, "AVGO": 800, "TSLA": 750,
    "JPM": 600, "WMT": 550, "UNH": 530, "V": 520, "XOM": 470, "MA": 430,
    "PG": 380, "COST": 370, "HD": 360, "JNJ": 380, "ORCL": 380, "BAC": 310,
    "ABBV": 310, "NFLX": 290, "MRK": 280, "KO": 270, "CVX": 270, "AMD": 240,
    "PEP": 230, "LIN": 220, "ADBE": 220, "TMO": 220, "MCD": 210, "CSCO": 200,
    "WFC": 190, "DIS": 180, "GE": 180, "INTU": 180, "CAT": 170, "IBM": 170
}

# --- סרגל צד: פרמטרים ---
st.sidebar.header("⚙️ הגדרות אסטרטגיה")

# 1. שווי שוק
min_cap = st.sidebar.slider("1. שווי שוק מינימלי ($B)", min_value=150, max_value=500, value=200, step=25)

# 2 + 3. RSI
col_rsi1, col_rsi2 = st.sidebar.columns(2)
with col_rsi1:
    rsi_entry = st.sidebar.number_input("2. RSI כניסה (<)", min_value=15, max_value=45, value=40, step=1)
with col_rsi2:
    rsi_exit = st.sidebar.number_input("3. RSI יציאה (>=)", min_value=50, max_value=85, value=60, step=1)
rsi_period = st.sidebar.slider("תקופת RSI (ימים)", min_value=7, max_value=28, value=14)

# 4 + 5. הון והקצאה
col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    initial_capital = st.sidebar.number_input("4. הון התחלתי ($)", min_value=1000, max_value=500000, value=10000, step=1000)
with col_c2:
    position_pct = st.sidebar.number_input("5. גודל עסקה (% מהתיק)", min_value=2.0, max_value=100.0, value=10.0, step=1.0) / 100.0

# 6. ממוצע נע SMA
use_sma = st.sidebar.checkbox("6. כניסה רק מעל SMA", value=True)
sma_length = st.sidebar.number_input("אורך SMA", min_value=20, max_value=300, value=200, step=10, disabled=not use_sma)

# ניהול סיכונים Stop Loss
st.sidebar.markdown("---")
st.sidebar.subheader("🛑 ניהול סיכונים (Stop Loss)")
use_sl = st.sidebar.checkbox("הפעל מנגנון Stop Loss", value=True)

sl_type = st.sidebar.radio("שיטת חישוב ה-Stop Loss:", ["לפי אחוזים מפוזיציה (%)", "לפי סכום נקוב בדולרים ($)"], disabled=not use_sl)

if sl_type == "לפי אחוזים מפוזיציה (%)":
    sl_pct_val = st.sidebar.number_input("אחוז הפסד מקסימלי (%):", min_value=1.0, max_value=30.0, value=6.0, step=0.5, disabled=not use_sl) / 100.0
    sl_usd_val = None
else:
    sl_usd_val = st.sidebar.number_input("הפסד דולרי מקסימלי לעסקה ($):", min_value=10.0, max_value=2000.0, value=100.0, step=10.0, disabled=not use_sl)
    sl_pct_val = None

# תקופת הרצה
st.sidebar.markdown("---")
today = datetime.today().date()
one_year_ago = today - timedelta(days=365)
start_date = st.sidebar.date_input("תאריך התחלה", value=one_year_ago)
end_date = st.sidebar.date_input("תאריך סיום", value=today)

run_button = st.sidebar.button("🚀 הפעל סימולציה", type="primary")

# פונקציית RSI
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# בדיקת המניות שעוברות את רף השווי
active_tickers = [sym for sym, cap in STOCK_MARKET_CAPS.items() if cap >= min_cap]

st.info(f"נמצאו **{len(active_tickers)}** חברות מעל סף שווי שוק של **${min_cap}B**")

# --- הרצת הבדיקה בלחיצת כפתור ---
if run_button:
    if not active_tickers:
        st.error("לא נמצאו מניות העונות על סף שווי השוק שנבחר.")
    else:
        with st.spinner("מושך נתוני מסחר ומריץ סימולציה..."):
            lookback_days = int(sma_length * 2 + 60)
            data_start = start_date - timedelta(days=lookback_days)
            all_syms = list(set(active_tickers + ["^GSPC"]))
            
            data = yf.download(all_syms, start=data_start, end=end_date, progress=False)

            if data.empty or "Close" not in data:
                st.error("שגיאה במשיכת נתוני מניות מ-Yahoo Finance.")
            else:
                close_df = data["Close"]
                indicators = {}
                for sym in active_tickers:
                    if sym in close_df.columns:
                        s = close_df[sym].dropna()
                        if len(s) > sma_length:
                            rsi = compute_rsi(s, rsi_period)
                            sma = s.rolling(window=sma_length).mean()
                            indicators[sym] = pd.DataFrame({"Close": s, "RSI": rsi, "SMA": sma})

                benchmark_close = close_df["^GSPC"].loc[str(start_date):str(end_date)].dropna()
                trading_days = benchmark_close.index

                # מנוע ה-Backtest
                cash = float(initial_capital)
                portfolio_history = []
                open_positions = {}
                closed_trades = []

                for day in trading_days:
                    # 1. שערוך שווי תיק
                    holdings_val = 0.0
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            px = indicators[sym].loc[day, "Close"]
                            holdings_val += pos["shares"] * px
                        else:
                            holdings_val += pos["cost_basis"]

                    total_equity = cash + holdings_val
                    portfolio_history.append({"Date": day, "Equity": total_equity, "Cash": cash})

                    # 2. בדיקת יציאות (RSI או Stop Loss)
                    to_close = []
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            cur_px = row["Close"]
                            cost = pos["cost_basis"]
                            cur_val = pos["shares"] * cur_px
                            pnl_dollar = cur_val - cost
                            pnl_pct = (cur_px / pos["entry_price"]) - 1.0

                            # בדיקת Stop Loss
                            hit_sl = False
                            if use_sl:
                                if sl_pct_val is not None and pnl_pct <= -sl_pct_val:
                                    hit_sl = True
                                elif sl_usd_val is not None and pnl_dollar <= -sl_usd_val:
                                    hit_sl = True

                            # בדיקת רווח RSI
                            hit_tp = row["RSI"] >= rsi_exit

                            if hit_sl or hit_tp:
                                cash += cur_val
                                reason = "Stop Loss 🛑" if hit_sl else "RSI Target 🎯"
                                closed_trades.append({
                                    "מניה": sym,
                                    "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                    "יציאה": day.strftime("%Y-%m-%d"),
                                    "מחיר קנייה": round(pos["entry_price"], 2),
                                    "מחיר מכירה": round(cur_px, 2),
                                    "רווח/הפסד ($)": round(pnl_dollar, 2),
                                    "תשואה (%)": round(pnl_pct * 100, 2),
                                    "סיבת יציאה": reason
                                })
                                to_close.append(sym)

                    for sym in to_close:
                        del open_positions[sym]

                    # 3. בדיקת כניסות
                    for sym in active_tickers:
                        if sym in open_positions or sym not in indicators:
                            continue
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            c_rsi = row["RSI"] < rsi_entry
                            c_sma = (row["Close"] > row["SMA"]) if use_sma else True

                            if c_rsi and c_sma:
                                alloc = total_equity * position_pct
                                if cash >= alloc and alloc > 0:
                                    px = row["Close"]
                                    shares = alloc / px
                                    cash -= alloc
                                    open_positions[sym] = {
                                        "shares": shares,
                                        "entry_price": px,
                                        "cost_basis": alloc,
                                        "entry_date": day
                                    }

                # חישוב תוצאות ומדדים
                df_equity = pd.DataFrame(portfolio_history).set_index("Date")
                bm_start = benchmark_close.iloc[0]
                df_equity["Benchmark"] = (benchmark_close / bm_start) * initial_capital

                strat_final = df_equity["Equity"].iloc[-1]
                bm_final = df_equity["Benchmark"].iloc[-1]
                strat_ret = ((strat_final / initial_capital) - 1) * 100
                bm_ret = ((bm_final / initial_capital) - 1) * 100

                roll_max = df_equity["Equity"].cummax()
                dd = (df_equity["Equity"] - roll_max) / roll_max
                max_dd = dd.min() * 100

                # הצגת מדדים
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("שווי תיק סופי", f"${strat_final:,.2f}", delta=f"{strat_ret:.2f}%")
                m2.metric("תשואת S&P 500", f"${bm_final:,.2f}", delta=f"{bm_ret:.2f}%")
                m3.metric("Alpha (עודף על המדד)", f"{(strat_ret - bm_ret):+.2f}%")
                m4.metric("Max Drawdown", f"{max_dd:.2f}%")

                # גרף
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Equity"], mode="lines", name="תיק האסטרטגיה", line=dict(color="#00BA38", width=2.5)))
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Benchmark"], mode="lines", name="S&P 500", line=dict(color="#619CFF", dash="dot")))
                fig.update_layout(title="שווי תיק מול מדד הייחוס", template="plotly_dark", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # יומן עסקאות
                with st.expander("📋 יומן עסקאות מפורט", expanded=True):
                    if closed_trades:
                        df_tr = pd.DataFrame(closed_trades)
                        wins = len(df_tr[df_tr["רווח/הפסד ($)"] > 0])
                        sl_hits = len(df_tr[df_tr["סיבת יציאה"].str.contains("Stop")])
                        st.write(f"**סה\"כ עסקאות:** {len(df_tr)} | **שיעור הצלחה:** {(wins / len(df_tr))*100:.1f}% | **יציאות ב-Stop Loss:** {sl_hits}")
                        st.dataframe(df_tr, use_container_width=True)
                    else:
                        st.info("לא נוצרו עסקאות בתנאים אלו.")

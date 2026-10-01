import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="סימולטור מסחר מתקדם", layout="wide")

st.title("📈 סימולטור מסחר מתקדם: RSI + SMA + הגנה מסכינים נופלות")
st.caption("סימולציית Backtest מותאמת אישית, ניהול סיכונים כפול, 4 מסנני היפוך והשוואה למדד S&P 500")

# מאגר מניות מגה-קאפ
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
st.sidebar.header("⚙️ הגדרות אסטרטגיה בסיסיות")

# 1. שווי שוק
min_cap = st.sidebar.slider("1. שווי שוק מינימלי ($B)", min_value=150, max_value=500, value=200, step=25)

# 2 + 3. RSI
col_rsi1, col_rsi2 = st.sidebar.columns(2)
with col_rsi1:
    rsi_entry = st.sidebar.number_input("2. RSI כניסה", min_value=15, max_value=45, value=40, step=1)
with col_rsi2:
    rsi_exit = st.sidebar.number_input("3. RSI יציאה (>=)", min_value=50, max_value=85, value=60, step=1)
rsi_period = st.sidebar.slider("תקופת RSI (ימים)", min_value=7, max_value=28, value=14)

# 4 + 5. הון והקצאה
col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    initial_capital = st.sidebar.number_input("4. הון התחלתי ($)", min_value=1000, max_value=500000, value=10000, step=1000)
with col_c2:
    position_pct = st.sidebar.number_input("5. גודל עסקה (% מהתיק)", min_value=2.0, max_value=100.0, value=10.0, step=1.0) / 100.0

# 6. ממוצע נע SMA בסיסי
use_sma = st.sidebar.checkbox("6. כניסה רק כאשר המחיר מעל SMA", value=True)
sma_length = st.sidebar.number_input("אורך SMA", min_value=20, max_value=300, value=200, step=10, disabled=not use_sma)

# --- 4 שיפורים למניעת סכינים נופלות (חדש!) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ מניעת סכינים נופלות ושיפור דיוק")

use_rsi_hook = st.sidebar.checkbox(
    "1. חציית RSI כלפי מעלה (RSI Hook)",
    value=True,
    help="נכנס רק כשה-RSI חוצה חזרה כלפי מעלה את סף הכניסה (לא כשהוא עדיין צולל)."
)

use_green_candle = st.sidebar.checkbox(
    "2. אישור נר ירוק (Close > Open)",
    value=True,
    help="כניסה רק ביום שבו מחיר הסגירה גבוה מהפתיחה (הקונים בשליטה בנר האיתות)."
)

use_sma_slope = st.sidebar.checkbox(
    "3. שיפוע SMA חיובי (SMA בעלייה)",
    value=False,
    disabled=not use_sma,
    help="ה-SMA עצמו חייב להיות גבוה יותר מערכו לפני מספר שבועות."
)
sma_slope_lookback = st.sidebar.number_input(
    "בדיקת שיפוע SMA מול ימים לאחור:",
    min_value=5, max_value=60, value=20, step=5,
    disabled=not (use_sma and use_sma_slope)
)

use_max_dist_sma = st.sidebar.checkbox(
    "4. הגבלת מרחק מקסימלי מעל ה-SMA (אזור תמיכה)",
    value=False,
    disabled=not use_sma,
    help="כניסה רק אם המניה לא מתוחה מדי מעל הממוצע (בטווח תמיכה הגיוני)."
)
max_dist_pct = st.sidebar.slider(
    "מרחק מרבי מעל ה-SMA (%):",
    min_value=3.0, max_value=25.0, value=10.0, step=0.5,
    disabled=not (use_sma and use_max_dist_sma)
)

# 7. סינון מחזורי מסחר RVOL
st.sidebar.markdown("---")
st.sidebar.subheader("📊 סינון מחזורי מסחר (RVOL)")
use_rvol = st.sidebar.checkbox("סנן כניסה לפי RVOL", value=False)
min_rvol = st.sidebar.slider("סף RVOL מינימלי:", min_value=0.5, max_value=3.0, value=1.0, step=0.1, disabled=not use_rvol)
rvol_window = st.sidebar.number_input("תקופת ממוצע מחזורים (ימים)", min_value=5, max_value=60, value=20, step=5, disabled=not use_rvol)

# תזמון ביצוע
st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ תזמון ביצוע פקודות")
exec_timing = st.sidebar.radio(
    "באיזה מחיר לבצע קנייה/מכירה?",
    options=["מחיר פתיחה ביום שלמחרת (Next Day Open)", "מחיר נעילה באותו יום (Same Day Close)"],
    index=0
)

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

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

active_tickers = [sym for sym, cap in STOCK_MARKET_CAPS.items() if cap >= min_cap]
st.info(f"נמצאו **{len(active_tickers)}** חברות מעל סף שווי שוק של **${min_cap}B**")

if run_button:
    if not active_tickers:
        st.error("לא נמצאו מניות העונות על סף שווי השוק שנבחר.")
    else:
        with st.spinner("מושך נתוני מחירים ומחשב אינדיקטורים..."):
            max_lookback = int(max(sma_length + sma_slope_lookback, rvol_window) * 2 + 60)
            data_start = start_date - timedelta(days=max_lookback)
            all_syms = list(set(active_tickers + ["^GSPC"]))
            
            data = yf.download(all_syms, start=data_start, end=end_date, progress=False)

            if data.empty or "Close" not in data or "Open" not in data or "Volume" not in data:
                st.error("שגיאה במשיכת נתוני מניות מ-Yahoo Finance.")
            else:
                close_df = data["Close"]
                open_df = data["Open"]
                vol_df = data["Volume"]
                
                indicators = {}
                for sym in active_tickers:
                    if sym in close_df.columns and sym in open_df.columns and sym in vol_df.columns:
                        c_series = close_df[sym].dropna()
                        o_series = open_df[sym].dropna()
                        v_series = vol_df[sym].dropna()
                        
                        if len(c_series) > (sma_length + sma_slope_lookback):
                            rsi = compute_rsi(c_series, rsi_period)
                            sma = c_series.rolling(window=sma_length).mean()
                            sma_slope = sma - sma.shift(sma_slope_lookback)
                            
                            vol_avg = v_series.rolling(window=rvol_window).mean()
                            rvol = v_series / vol_avg
                            
                            indicators[sym] = pd.DataFrame({
                                "Close": c_series,
                                "Open": o_series,
                                "Volume": v_series,
                                "RVOL": rvol,
                                "RSI": rsi,
                                "RSI_prev": rsi.shift(1),
                                "SMA": sma,
                                "SMA_slope": sma_slope
                            }).dropna()

                benchmark_close = close_df["^GSPC"].loc[str(start_date):str(end_date)].dropna()
                trading_days = list(benchmark_close.index)

                cash = float(initial_capital)
                portfolio_history = []
                open_positions = {}
                closed_trades = []
                executed_buys = []
                
                pending_buys = []
                pending_sells = []

                for day in trading_days:
                    # 1. ביצוע פקודות ממתינות (Next Day Open)
                    if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                        for sell in pending_sells:
                            sym = sell["ticker"]
                            if sym in open_positions and day in indicators[sym].index:
                                pos = open_positions[sym]
                                exit_px = indicators[sym].loc[day, "Open"]
                                proceeds = pos["shares"] * exit_px
                                cash += proceeds
                                pnl_dollar = proceeds - pos["cost_basis"]
                                pnl_pct = (exit_px / pos["entry_price"]) - 1.0
                                
                                closed_trades.append({
                                    "מניה": sym,
                                    "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                    "יציאה": day.strftime("%Y-%m-%d"),
                                    "מחיר קנייה": round(pos["entry_price"], 2),
                                    "מחיר מכירה": round(exit_px, 2),
                                    "רווח/הפסד ($)": round(pnl_dollar, 2),
                                    "תשואה (%)": round(pnl_pct * 100, 2),
                                    "סיבת יציאה": sell["reason"],
                                    "exit_date_raw": day
                                })
                                del open_positions[sym]
                        pending_sells = []

                        for buy in pending_buys:
                            sym = buy["ticker"]
                            if sym not in open_positions and day in indicators[sym].index:
                                row_buy = indicators[sym].loc[day]
                                
                                pass_rvol = True
                                if use_rvol:
                                    if row_buy.get("RVOL", 1.0) < min_rvol:
                                        pass_rvol = False
                                
                                if pass_rvol:
                                    entry_px = row_buy["Open"]
                                    alloc = buy["allocation"]
                                    if cash >= alloc and alloc > 0 and entry_px > 0:
                                        shares = alloc / entry_px
                                        cash -= alloc
                                        open_positions[sym] = {
                                            "shares": shares,
                                            "entry_price": entry_px,
                                            "cost_basis": alloc,
                                            "entry_date": day
                                        }
                                        executed_buys.append({
                                            "date": day,
                                            "ticker": sym,
                                            "price": entry_px
                                        })
                        pending_buys = []

                    # 2. שערוך שווי התיק בסגירה
                    holdings_val = 0.0
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            holdings_val += pos["shares"] * indicators[sym].loc[day, "Close"]
                        else:
                            holdings_val += pos["cost_basis"]

                    total_equity = cash + holdings_val
                    portfolio_history.append({"Date": day, "Equity": total_equity, "Cash": cash})

                    # 3. בדיקת איתותי יציאה בסגירה
                    to_close_today = []
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            cur_px = row["Close"]
                            cost = pos["cost_basis"]
                            cur_val = pos["shares"] * cur_px
                            pnl_dollar = cur_val - cost
                            pnl_pct = (cur_px / pos["entry_price"]) - 1.0

                            hit_sl = False
                            if use_sl:
                                if sl_pct_val is not None and pnl_pct <= -sl_pct_val:
                                    hit_sl = True
                                elif sl_usd_val is not None and pnl_dollar <= -sl_usd_val:
                                    hit_sl = True

                            hit_tp = row["RSI"] >= rsi_exit

                            if hit_sl or hit_tp:
                                reason = "Stop Loss 🛑" if hit_sl else "RSI Target 🎯"
                                if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                                    if not any(s["ticker"] == sym for s in pending_sells):
                                        pending_sells.append({"ticker": sym, "reason": reason})
                                else:
                                    cash += cur_val
                                    closed_trades.append({
                                        "מניה": sym,
                                        "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                        "יציאה": day.strftime("%Y-%m-%d"),
                                        "מחיר קנייה": round(pos["entry_price"], 2),
                                        "מחיר מכירה": round(cur_px, 2),
                                        "רווח/הפסד ($)": round(pnl_dollar, 2),
                                        "תשואה (%)": round(pnl_pct * 100, 2),
                                        "סיבת יציאה": reason,
                                        "exit_date_raw": day
                                    })
                                    to_close_today.append(sym)

                    for sym in to_close_today:
                        del open_positions[sym]

                    # 4. בדיקת איתותי כניסה (כולל 4 השיפורים החדשים)
                    for sym in active_tickers:
                        if sym in open_positions or any(b["ticker"] == sym for b in pending_buys) or sym not in indicators:
                            continue
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            
                            # תנאי 1: RSI (רגיל או Hook)
                            if use_rsi_hook:
                                rsi_entry_cond = (row["RSI_prev"] < rsi_entry) and (row["RSI"] >= rsi_entry)
                            else:
                                rsi_entry_cond = row["RSI"] < rsi_entry

                            # תנאי 2: נר ירוק (Close > Open)
                            green_cond = (row["Close"] > row["Open"]) if use_green_candle else True

                            # תנאי 3: מעל SMA
                            sma_cond = (row["Close"] > row["SMA"]) if use_sma else True

                            # תנאי 4: שיפוע SMA חיובי
                            slope_cond = (row["SMA_slope"] > 0) if (use_sma and use_sma_slope) else True

                            # תנאי 5: מרחק מקסימלי מעל SMA (אינו מתוח מדי)
                            if use_sma and use_max_dist_sma:
                                pct_above_sma = ((row["Close"] / row["SMA"]) - 1.0) * 100
                                dist_cond = (pct_above_sma <= max_dist_pct)
                            else:
                                dist_cond = True

                            # בדיקת סיכום תנאי כניסה
                            if rsi_entry_cond and green_cond and sma_cond and slope_cond and dist_cond:
                                alloc = total_equity * position_pct
                                if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                                    pending_buys.append({"ticker": sym, "allocation": alloc})
                                else:
                                    pass_rvol = True
                                    if use_rvol:
                                        if row.get("RVOL", 1.0) < min_rvol:
                                            pass_rvol = False
                                            
                                    if pass_rvol and cash >= alloc and alloc > 0:
                                        px = row["Close"]
                                        shares = alloc / px
                                        cash -= alloc
                                        open_positions[sym] = {
                                            "shares": shares,
                                            "entry_price": px,
                                            "cost_basis": alloc,
                                            "entry_date": day
                                        }
                                        executed_buys.append({
                                            "date": day,
                                            "ticker": sym,
                                            "price": px
                                        })

                # חישוב תוצאות
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

                # KPI Metrics
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("שווי תיק סופי", f"${strat_final:,.2f}", delta=f"{strat_ret:.2f}%")
                m2.metric("תשואת S&P 500", f"${bm_final:,.2f}", delta=f"{bm_ret:.2f}%")
                m3.metric("Alpha (עודף על המדד)", f"{(strat_ret - bm_ret):+.2f}%")
                m4.metric("Max Drawdown", f"{max_dd:.2f}%")

                # גרף עם עסקאות
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Equity"], mode="lines", name="תיק האסטרטגיה", line=dict(color="#00BA38", width=2.5)))
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Benchmark"], mode="lines", name="S&P 500", line=dict(color="#619CFF", dash="dot")))

                if executed_buys:
                    buy_dates = [b["date"] for b in executed_buys if b["date"] in df_equity.index]
                    buy_equities = [df_equity.loc[b["date"], "Equity"] for b in executed_buys if b["date"] in df_equity.index]
                    buy_texts = [f"קנייה: {b['ticker']}<br>מחיר: ${b['price']:.2f}" for b in executed_buys if b["date"] in df_equity.index]
                    
                    fig.add_trace(go.Scatter(
                        x=buy_dates,
                        y=buy_equities,
                        mode="markers",
                        name="עסקת קנייה (Buy)",
                        marker=dict(symbol="triangle-up", size=11, color="#2ECC71", line=dict(width=1, color="white")),
                        hoverinfo="text",
                        hovertext=buy_texts
                    ))

                if closed_trades:
                    tp_trades = [t for t in closed_trades if "Target" in t["סיבת יציאה"] and t["exit_date_raw"] in df_equity.index]
                    if tp_trades:
                        tp_dates = [t["exit_date_raw"] for t in tp_trades]
                        tp_equities = [df_equity.loc[t["exit_date_raw"], "Equity"] for t in tp_trades]
                        tp_texts = [f"יציאה ביעד: {t['מניה']}<br>+{t['תשואה (%)']}% (${t['רווח/הפסד ($)']})" for t in tp_trades]
                        fig.add_trace(go.Scatter(
                            x=tp_dates, y=tp_equities, mode="markers", name="יציאה ביעד RSI 🎯",
                            marker=dict(symbol="circle", size=10, color="#F1C40F", line=dict(width=1, color="white")),
                            hoverinfo="text", hovertext=tp_texts
                        ))

                    sl_trades = [t for t in closed_trades if "Stop" in t["סיבת יציאה"] and t["exit_date_raw"] in df_equity.index]
                    if sl_trades:
                        sl_dates = [t["exit_date_raw"] for t in sl_trades]
                        sl_equities = [df_equity.loc[t["exit_date_raw"], "Equity"] for t in sl_trades]
                        sl_texts = [f"Stop Loss: {t['מניה']}<br>{t['תשואה (%)']}% (${t['רווח/הפסד ($)']})" for t in sl_trades]
                        fig.add_trace(go.Scatter(
                            x=sl_dates, y=sl_equities, mode="markers", name="יציאה ב-Stop Loss 🛑",
                            marker=dict(symbol="triangle-down", size=12, color="#E74C3C", line=dict(width=1, color="white")),
                            hoverinfo="text", hovertext=sl_texts
                        ))

                fig.update_layout(
                    title=f"שווי תיק, מדד S&P 500 ועסקאות שבוצעו ({exec_timing})",
                    template="plotly_dark",
                    hovermode="closest",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("📋 יומן עסקאות מפורט", expanded=True):
                    if closed_trades:
                        clean_trades = [{k: v for k, v in t.items() if k != "exit_date_raw"} for t in closed_trades]
                        df_tr = pd.DataFrame(clean_trades)
                        wins = len(df_tr[df_tr["רווח/הפסד ($)"] > 0])
                        sl_hits = len(df_tr[df_tr["סיבת יציאה"].str.contains("Stop")])
                        st.write(f"**סה\"כ עסקאות:** {len(df_tr)} | **שיעור הצלחה:** {(wins / len(df_tr))*100:.1f}% | **יציאות ב-Stop Loss:** {sl_hits}")
                        st.dataframe(df_tr, use_container_width=True)
                    else:
                        st.info("לא נסגרו עסקאות בתקופה שנבחרה לפי תנאי הסף שהוגדרו.")

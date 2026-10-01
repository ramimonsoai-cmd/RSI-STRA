import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="סימולטור מסחר עם סינון שוק SPY", layout="wide")

st.title("📈 סימולטור מסחר: RSI + SMA + מימוש 50% + סינון שוק SPY")
st.caption("ניהול פוזיציה מתקדם, בדיקת מגמת השוק הכללי (SPY > SMA 200) והשוואה ל-S&P 500")

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

# --- סרגל צד: הגדרות ---
st.sidebar.header("⚙️ 1. כללי כניסה והון")

min_cap = st.sidebar.slider("שווי שוק מינימלי ($B)", min_value=150, max_value=500, value=200, step=25)

col_rsi1, col_rsi2 = st.sidebar.columns(2)
with col_rsi1:
    rsi_entry = st.sidebar.number_input("RSI כניסה (<)", min_value=15, max_value=45, value=40, step=1)
with col_rsi2:
    rsi_exit = st.sidebar.number_input("RSI יעד ראשון (>=)", min_value=50, max_value=85, value=60, step=1)
rsi_period = st.sidebar.slider("תקופת RSI (ימים)", min_value=7, max_value=28, value=14)

col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    initial_capital = st.sidebar.number_input("הון התחלתי ($)", min_value=1000, max_value=500000, value=10000, step=1000)
with col_c2:
    position_pct = st.sidebar.number_input("גודל כניסה (% מהתיק)", min_value=2.0, max_value=100.0, value=10.0, step=1.0) / 100.0

# תנאי ממוצע נע של המניה הבודדת
use_sma = st.sidebar.checkbox("כניסה רק כאשר המניה מעל SMA שלה", value=True)
sma_length = st.sidebar.number_input("אורך SMA של המניה", min_value=20, max_value=300, value=200, step=10, disabled=not use_sma)

# תנאי חדש: מדד SPY מעל SMA 200
use_spy_filter = st.sidebar.checkbox(
    "🌐 סינון שוק: כניסה רק כאשר SPY נסחר מעל SMA 200", 
    value=True,
    help="מונע פתיחת עסקאות חדשות כאשר השוק הכללי נמצא במגמת ירידה או בשוק דובי."
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 2. ניהול מימושים ויציאות")

use_scale_out = st.sidebar.checkbox("1. מימוש 50% ביעד RSI + Trailing Stop לחצי הנותר", value=True)

trailing_pct = st.sidebar.slider(
    "מרחק Trailing Stop מהשיא לחצי הנותר (%):",
    min_value=0.5,
    max_value=15.0,
    value=1.0,
    step=0.1,
    disabled=not use_scale_out,
    help="מרחק נסיגה מהשיא לסגירת החצי הנותר. ניתן לרדת עד 0.5% ליציאות מהירות."
)

lock_breakeven = st.sidebar.checkbox(
    "🔒 נעל רצפת איזון (Breakeven Floor)",
    value=True,
    disabled=not use_scale_out,
    help="מבטיח שהסטופ של החצי השני לעולם לא ירד מתחת למחיר הקנייה המקורי."
)

use_time_stop = st.sidebar.checkbox("2. יציאה מעסקה שלא פרצה לאחר מספר ימים (Time Stop)", value=True)
max_holding_days = st.sidebar.number_input(
    "מספר ימי מסחר מקסימלי ללא פריצה:",
    min_value=3, max_value=40, value=12, step=1,
    disabled=not use_time_stop
)

st.sidebar.markdown("---")
st.sidebar.subheader("🛑 3. Stop Loss הגנתי ראשוני")
use_sl = st.sidebar.checkbox("הפעל Stop Loss קשיח מהכניסה", value=True)
sl_type = st.sidebar.radio("חישוב Stop Loss:", ["לפי אחוזים מפוזיציה (%)", "לפי סכום נקוב בדולרים ($)"], disabled=not use_sl)

if sl_type == "לפי אחוזים מפוזיציה (%)":
    sl_pct_val = st.sidebar.number_input("אחוז הפסד מקסימלי (%):", min_value=1.0, max_value=30.0, value=6.0, step=0.5, disabled=not use_sl) / 100.0
    sl_usd_val = None
else:
    sl_usd_val = st.sidebar.number_input("הפסד דולרי מקסימלי לעסקה ($):", min_value=10.0, max_value=2000.0, value=100.0, step=10.0, disabled=not use_sl)
    sl_pct_val = None

st.sidebar.markdown("---")
exec_timing = st.sidebar.radio(
    "תזמון ביצוע פקודות:",
    options=["מחיר פתיחה ביום שלמחרת (Next Day Open)", "מחיר נעילה באותו יום (Same Day Close)"],
    index=0
)

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

# --- הרצת הסימולציה ---
if run_button:
    if not active_tickers:
        st.error("לא נמצאו מניות העונות על סף שווי השוק שנבחר.")
    else:
        with st.spinner("מושך נתוני מסחר (מניות + SPY) ומחשב אינדיקטורים..."):
            max_lookback = int(max(sma_length, 200) * 2 + 60)
            data_start = start_date - timedelta(days=max_lookback)
            
            # הוספת SPY ו-^GSPC להורדה
            all_syms = list(set(active_tickers + ["SPY", "^GSPC"]))
            
            data = yf.download(all_syms, start=data_start, end=end_date, progress=False)

            if data.empty or "Close" not in data or "Open" not in data:
                st.error("שגיאה במשיכת נתונים מ-Yahoo Finance.")
            else:
                close_df = data["Close"]
                open_df = data["Open"]
                
                # חישוב נתוני SPY
                spy_series = close_df["SPY"].dropna()
                spy_sma200 = spy_series.rolling(window=200).mean()
                spy_filter_series = spy_series > spy_sma200

                # חישוב אינדיקטורים לכל מניה
                indicators = {}
                for sym in active_tickers:
                    if sym in close_df.columns and sym in open_df.columns:
                        c_series = close_df[sym].dropna()
                        o_series = open_df[sym].dropna()
                        if len(c_series) > sma_length:
                            rsi = compute_rsi(c_series, rsi_period)
                            sma = c_series.rolling(window=sma_length).mean()
                            indicators[sym] = pd.DataFrame({
                                "Close": c_series,
                                "Open": o_series,
                                "RSI": rsi,
                                "SMA": sma
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
                    # 1. ביצוע פקודות שממתינות מהיום הקודם (Next Day Open)
                    if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                        for sell in pending_sells:
                            sym = sell["ticker"]
                            if sym in open_positions and day in indicators[sym].index:
                                pos = open_positions[sym]
                                exit_px = indicators[sym].loc[day, "Open"]
                                shares_selling = sell["shares"]
                                proceeds = shares_selling * exit_px
                                cost_of_these_shares = shares_selling * pos["entry_price"]
                                
                                cash += proceeds
                                pnl_dollar = proceeds - cost_of_these_shares
                                pnl_pct = (exit_px / pos["entry_price"]) - 1.0

                                closed_trades.append({
                                    "מניה": sym,
                                    "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                    "יציאה": day.strftime("%Y-%m-%d"),
                                    "מחיר קנייה": round(pos["entry_price"], 2),
                                    "מחיר מכירה": round(exit_px, 2),
                                    "כמות שנמכרה": round(shares_selling, 2),
                                    "רווח/הפסד ($)": round(pnl_dollar, 2),
                                    "תשואה (%)": round(pnl_pct * 100, 2),
                                    "ימי החזקה": pos["days_held"],
                                    "סיבת יציאה": sell["reason"],
                                    "exit_date_raw": day
                                })
                                
                                pos["shares"] -= shares_selling
                                if pos["shares"] <= 0.0001:
                                    del open_positions[sym]
                        pending_sells = []

                        for buy in pending_buys:
                            sym = buy["ticker"]
                            if sym not in open_positions and day in indicators[sym].index:
                                entry_px = indicators[sym].loc[day, "Open"]
                                alloc = buy["allocation"]
                                if cash >= alloc and alloc > 0 and entry_px > 0:
                                    shares = alloc / entry_px
                                    cash -= alloc
                                    open_positions[sym] = {
                                        "shares": shares,
                                        "entry_price": entry_px,
                                        "cost_basis": alloc,
                                        "entry_date": day,
                                        "days_held": 0,
                                        "scaled_out": False,
                                        "peak_after_scale": entry_px
                                    }
                                    executed_buys.append({
                                        "date": day,
                                        "ticker": sym,
                                        "price": entry_px
                                    })
                        pending_buys = []

                    # 2. עדכון פוזיציות ושערוך שווי תיק
                    holdings_val = 0.0
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            cur_px = indicators[sym].loc[day, "Close"]
                            holdings_val += pos["shares"] * cur_px
                            pos["days_held"] += 1
                            if pos["scaled_out"] and cur_px > pos["peak_after_scale"]:
                                pos["peak_after_scale"] = cur_px
                        else:
                            holdings_val += pos["shares"] * pos["entry_price"]

                    total_equity = cash + holdings_val
                    portfolio_history.append({"Date": day, "Equity": total_equity, "Cash": cash})

                    # 3. בדיקת תנאי יציאה בסגירת יום המסחר
                    sells_to_process = []
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            cur_px = row["Close"]
                            cur_val = pos["shares"] * cur_px
                            cost = pos["shares"] * pos["entry_price"]
                            pnl_dollar = cur_val - cost
                            pnl_pct = (cur_px / pos["entry_price"]) - 1.0

                            # א. Stop Loss ראשוני
                            hit_sl = False
                            if use_sl:
                                if sl_pct_val is not None and pnl_pct <= -sl_pct_val:
                                    hit_sl = True
                                elif sl_usd_val is not None and pnl_dollar <= -sl_usd_val:
                                    hit_sl = True

                            if hit_sl:
                                sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Stop Loss 🛑"})
                                continue

                            # ב. Time Stop
                            if use_time_stop and not pos["scaled_out"]:
                                if pos["days_held"] >= max_holding_days:
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Time Stop (לא פרצה) ⏳"})
                                    continue

                            # ג. יעד RSI ראשון
                            if row["RSI"] >= rsi_exit and not pos["scaled_out"]:
                                if use_scale_out:
                                    half_shares = pos["shares"] * 0.5
                                    pos["scaled_out"] = True
                                    pos["peak_after_scale"] = cur_px
                                    sells_to_process.append({"ticker": sym, "shares": half_shares, "reason": "מימוש 50% ביעד RSI 🎯"})
                                else:
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "RSI Target 100% 🎯"})
                                continue

                            # ד. Trailing Stop מוגן Breakeven ל-50% הנותרים
                            if pos["scaled_out"] and use_scale_out:
                                trailing_stop_price = pos["peak_after_scale"] * (1.0 - (trailing_pct / 100.0))
                                
                                if lock_breakeven:
                                    effective_stop_price = max(trailing_stop_price, pos["entry_price"])
                                else:
                                    effective_stop_price = trailing_stop_price

                                if cur_px <= effective_stop_price:
                                    reason_label = "Trailing Stop (נעול באיזון) 🔒" if (cur_px <= pos["entry_price"] and lock_breakeven) else f"Trailing Stop {trailing_pct}% 📈"
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": reason_label})

                    # ביצוע המכירות
                    for s in sells_to_process:
                        sym = s["ticker"]
                        if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                            if not any(ps["ticker"] == sym and ps["reason"] == s["reason"] for ps in pending_sells):
                                pending_sells.append(s)
                        else:
                            pos = open_positions[sym]
                            cur_px = indicators[sym].loc[day, "Close"]
                            shares_selling = s["shares"]
                            proceeds = shares_selling * cur_px
                            cost_of_these = shares_selling * pos["entry_price"]
                            
                            cash += proceeds
                            pnl_d = proceeds - cost_of_these
                            pnl_p = (cur_px / pos["entry_price"]) - 1.0
                            
                            closed_trades.append({
                                "מניה": sym,
                                "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                "יציאה": day.strftime("%Y-%m-%d"),
                                "מחיר קנייה": round(pos["entry_price"], 2),
                                "מחיר מכירה": round(cur_px, 2),
                                "כמות שנמכרה": round(shares_selling, 2),
                                "רווח/הפסד ($)": round(pnl_d, 2),
                                "תשואה (%)": round(pnl_p * 100, 2),
                                "ימי החזקה": pos["days_held"],
                                "סיבת יציאה": s["reason"],
                                "exit_date_raw": day
                            })
                            pos["shares"] -= shares_selling
                            if pos["shares"] <= 0.0001:
                                del open_positions[sym]

                    # 4. בדיקת איתותי כניסה (כולל תנאי SPY > SMA 200)
                    is_spy_bullish = True
                    if use_spy_filter:
                        if day in spy_filter_series.index:
                            is_spy_bullish = bool(spy_filter_series.loc[day])
                        else:
                            is_spy_bullish = False

                    # אם השוק כולו לא מעל SMA 200, לא נכנסים לאף עסקה חדשה
                    if is_spy_bullish:
                        for sym in active_tickers:
                            if sym in open_positions or any(b["ticker"] == sym for b in pending_buys) or sym not in indicators:
                                continue
                            if day in indicators[sym].index:
                                row = indicators[sym].loc[day]
                                c_rsi = row["RSI"] < rsi_entry
                                c_sma = (row["Close"] > row["SMA"]) if use_sma else True

                                if c_rsi and c_sma:
                                    alloc = total_equity * position_pct
                                    if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                                        pending_buys.append({"ticker": sym, "allocation": alloc})
                                    else:
                                        if cash >= alloc and alloc > 0:
                                            px = row["Close"]
                                            shares = alloc / px
                                            cash -= alloc
                                            open_positions[sym] = {
                                                "shares": shares,
                                                "entry_price": px,
                                                "cost_basis": alloc,
                                                "entry_date": day,
                                                "days_held": 0,
                                                "scaled_out": False,
                                                "peak_after_scale": px
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

                # גרף
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Equity"], mode="lines", name="תיק האסטרטגיה", line=dict(color="#00BA38", width=2.5)))
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Benchmark"], mode="lines", name="S&P 500", line=dict(color="#619CFF", dash="dot")))

                fig.update_layout(
                    title="שווי תיק מול S&P 500 (כולל סינון שוק SPY מעל SMA 200)",
                    template="plotly_dark",
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

                # יומן עסקאות
                with st.expander("📋 יומן עסקאות מפורט", expanded=True):
                    if closed_trades:
                        clean_trades = [{k: v for k, v in t.items() if k != "exit_date_raw"} for t in closed_trades]
                        df_tr = pd.DataFrame(clean_trades)
                        wins = len(df_tr[df_tr["רווח/הפסד ($)"] >= 0])
                        st.write(f"**סה\"כ פעולות מכירה:** {len(df_tr)} | **שיעור פעולות ללא הפסד:** {(wins / len(df_tr))*100:.1f}%")
                        st.dataframe(df_tr, use_container_width=True)
                    else:
                        st.info("לא נסגרו עסקאות בתקופה זו.")

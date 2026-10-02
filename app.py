import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="סימולטור מסחר כמותי מוסדי מלא", layout="wide")

st.title("📈 סימולטור מסחר כמותי: ניתוח מוסדי + הגנת Gap-Up")
st.caption("ניתוח תיק מקיף: מדדי איכות, סינון שוק SPY, מניעת סכינים נופלות, RVOL, הגנת פערים וניהול מימושים")

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
st.sidebar.header("⚙️ 1. כללי כניסה והון בסיסיים")

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

use_sma = st.sidebar.checkbox("כניסה רק כאשר המניה מעל SMA שלה", value=True)
sma_length = st.sidebar.number_input("אורך SMA של המניה", min_value=20, max_value=300, value=200, step=10, disabled=not use_sma)

use_spy_filter = st.sidebar.checkbox("🌐 סינון שוק: כניסה רק כאשר SPY נסחר מעל SMA 200", value=True)

# הגנת פערי פתיחה (Max Gap-Up)
use_max_gap = st.sidebar.checkbox(
    "🚪 הגבלת פער פתיחה מקסימלי (Max Gap-Up)",
    value=False,
    help="מונע כניסה אם המניה פותחת בבוקר בזינוק חד מדי מעל שער הנעילה של יום האיתות."
)
max_gap_pct = st.sidebar.slider(
    "פער פתיחה מקסימלי מותר (%):",
    min_value=0.5, max_value=10.0, value=2.0, step=0.1,
    disabled=not use_max_gap,
    help="אם שער הפתיחה גבוה ביותר מאחוז זה משער הסגירה של אתמול - הפקודה תבוטל."
)

# --- 2. מסנני מניעת סכינים נופלות (לבחירה נפרדת) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 2. מסנני היפוך ומניעת סכינים נופלות")

use_rsi_hook = st.sidebar.checkbox(
    "1. חציית RSI כלפי מעלה (RSI Hook)",
    value=False,
    help="כניסה רק כשה-RSI היה ביום הקודם מתחת לסף והיום חוצה אותו חזרה מעלה."
)

use_green_candle = st.sidebar.checkbox(
    "2. אישור נר ירוק ביום האיתות (Close > Open)",
    value=False,
    help="כניסה רק אם נר האיתות סיים חיובי (הקונים חזרו לשלוט)."
)

use_sma_slope = st.sidebar.checkbox(
    "3. שיפוע SMA חיובי (SMA במגמת עלייה)",
    value=False,
    disabled=not use_sma,
    help="מוודא שהממוצע הנע עצמו עולה ביחס לעברו."
)
sma_slope_lookback = st.sidebar.number_input(
    "בדיקת שיפוע SMA מול ימים לאחור:",
    min_value=5, max_value=60, value=20, step=5,
    disabled=not (use_sma and use_sma_slope)
)

use_max_dist_sma = st.sidebar.checkbox(
    "4. הגבלת מרחק מקסימלי מעל SMA (אזור תמיכה)",
    value=False,
    disabled=not use_sma,
    help="מונע כניסה במניות שנמתחו מדי מעל הממוצע הנע."
)
max_dist_pct = st.sidebar.slider(
    "מרחק מרבי מעל ה-SMA (%):",
    min_value=3.0, max_value=25.0, value=10.0, step=0.5,
    disabled=not (use_sma and use_max_dist_sma)
)

# --- 3. סינון מחזורי מסחר RVOL ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 3. סינון מחזורי מסחר (RVOL)")
use_rvol = st.sidebar.checkbox("סנן כניסה לפי RVOL של יום הקנייה", value=False)
min_rvol = st.sidebar.slider(
    "סף RVOL מינימלי:",
    min_value=0.5, max_value=3.0, value=1.0, step=0.1,
    disabled=not use_rvol,
    help="1.0 = מחזור ממוצע, מעל 1.2 = מחזור ער וחריג."
)
rvol_window = st.sidebar.number_input(
    "תקופת ממוצע מחזורים (ימים):",
    min_value=5, max_value=60, value=20, step=5,
    disabled=not use_rvol
)

# --- 4. ניהול מימושים ויציאות ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 4. ניהול מימושים ויציאות")

use_scale_out = st.sidebar.checkbox("1. מימוש 50% ביעד RSI + Trailing Stop לחצי הנותר", value=True)
trailing_pct = st.sidebar.slider(
    "מרחק Trailing Stop מהשיא לחצי הנותר (%):",
    min_value=0.5, max_value=15.0, value=1.0, step=0.1,
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

# --- 5. ניהול סיכונים Stop Loss הגנתי ראשוני ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛑 5. Stop Loss הגנתי ראשוני")
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
        with st.spinner("מושך נתוני מסחר מ-Yahoo Finance ומחשב אינדיקטורים..."):
            required_lookback = max(sma_length + sma_slope_lookback, rvol_window, 200)
            max_lookback = int(required_lookback * 2 + 60)
            data_start = start_date - timedelta(days=max_lookback)
            all_syms = list(set(active_tickers + ["SPY", "^GSPC"]))
            
            data = yf.download(all_syms, start=data_start, end=end_date, progress=False)

            if data.empty or "Close" not in data or "Open" not in data or "Volume" not in data:
                st.error("שגיאה במשיכת נתונים מ-Yahoo Finance.")
            else:
                close_df = data["Close"]
                open_df = data["Open"]
                vol_df = data["Volume"]
                
                spy_series = close_df["SPY"].dropna()
                spy_sma200 = spy_series.rolling(window=200).mean()
                spy_filter_series = spy_series > spy_sma200

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

                        # ביצוע קניות ממתינות (כולל סינון RVOL והגנת Max Gap-Up)
                        for buy in pending_buys:
                            sym = buy["ticker"]
                            if sym not in open_positions and day in indicators[sym].index:
                                row_buy = indicators[sym].loc[day]
                                entry_px = row_buy["Open"]
                                signal_close_px = buy["signal_close_price"]
                                
                                # בדיקת RVOL
                                pass_rvol = True
                                if use_rvol:
                                    if row_buy.get("RVOL", 1.0) < min_rvol:
                                        pass_rvol = False
                                
                                # בדיקת הגנת פער פתיחה מקסימלי (Max Gap-Up)
                                pass_gap = True
                                if use_max_gap and signal_close_px > 0:
                                    gap_pct = ((entry_px / signal_close_px) - 1.0) * 100.0
                                    if gap_pct > max_gap_pct:
                                        pass_gap = False  # פער גדול מדי - מבוטל
                                
                                if pass_rvol and pass_gap:
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
                            cost = pos["shares"] * pos["entry_price"]
                            cur_val = pos["shares"] * cur_px
                            pnl_dollar = cur_val - cost
                            pnl_pct = (cur_px / pos["entry_price"]) - 1.0

                            hit_sl = False
                            if use_sl:
                                if sl_pct_val is not None and pnl_pct <= -sl_pct_val:
                                    hit_sl = True
                                elif sl_usd_val is not None and pnl_dollar <= -sl_usd_val:
                                    hit_sl = True

                            if hit_sl:
                                sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Stop Loss 🛑"})
                                continue

                            if use_time_stop and not pos["scaled_out"]:
                                if pos["days_held"] >= max_holding_days:
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Time Stop (לא פרצה) ⏳"})
                                    continue

                            if row["RSI"] >= rsi_exit and not pos["scaled_out"]:
                                if use_scale_out:
                                    half_shares = pos["shares"] * 0.5
                                    pos["scaled_out"] = True
                                    pos["peak_after_scale"] = cur_px
                                    sells_to_process.append({"ticker": sym, "shares": half_shares, "reason": "מימוש 50% ביעד RSI 🎯"})
                                else:
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "RSI Target 100% 🎯"})
                                continue

                            if pos["scaled_out"] and use_scale_out:
                                trailing_stop_price = pos["peak_after_scale"] * (1.0 - (trailing_pct / 100.0))
                                effective_stop_price = max(trailing_stop_price, pos["entry_price"]) if lock_breakeven else trailing_stop_price

                                if cur_px <= effective_stop_price:
                                    reason_label = "Trailing Stop (נעול באיזון) 🔒" if (cur_px <= pos["entry_price"] and lock_breakeven) else f"Trailing Stop {trailing_pct}% 📈"
                                    sells_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": reason_label})

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
                                del 

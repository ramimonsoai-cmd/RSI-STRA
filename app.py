import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="סימולטור מסחר כמותי מוסדי מלא", layout="wide")

# אתחול זיכרון הדפדפן/הסשן לשמירת הסימולציות
if "saved_simulations" not in st.session_state:
    st.session_state.saved_simulations = []

st.title("📈 סימולטור מסחר כמותי: Long / Short / משולב + יומן Excel")
st.caption("ניתוח תיק מקיף, תמיכה בעסקאות לונג ושורט בהיפוך סימטרי מלא, מדדי איכות והורדה לאקסל")

# מאגר מניות מגה-קאפ
STOCK_MARKET_CAPS = {
    "NVDA": 3500, "AAPL": 3400, "MSFT": 3100, "AMZN": 2000, "GOOGL": 2000,
    "META": 1450, "TSLA": 850, "BRK-B": 980, "AVGO": 850, "LLY": 820,
    "JPM": 650, "V": 540, "MA": 460, "BAC": 340, "WFC": 240, 
    "MS": 220, "GS": 210, "AXP": 220, "BLK": 210,
    "WMT": 680, "COST": 410, "PG": 380, "HD": 380, "KO": 280, 
    "PEP": 230, "MCD": 210, "NFLX": 350, "DIS": 210, "PM": 230,
    "ORCL": 420, "CRM": 290, "NOW": 210, "ADBE": 220, "INTU": 200, 
    "CSCO": 230, "QCOM": 220, "AMD": 240, "TXN": 210, "AMAT": 200, 
    "MU": 210, "PLTR": 210, "PANW": 200, "LRCX": 200,
    "UNH": 530, "JNJ": 380, "ABBV": 350, "MRK": 280, "TMO": 230, 
    "ABT": 220, "DHR": 200, "ISRG": 210, "PFE": 180, "BMY": 150,
    "XOM": 480, "CVX": 280, "COP": 180, "GE": 230, "CAT": 230, 
    "RTX": 200, "HON": 180, "LIN": 220, "UNP": 170, "BA": 150, "IBM": 210
}

# --- סרגל צד: הגדרות ---
st.sidebar.header("🧭 כיוון אסטרטגיה")
trade_mode = st.sidebar.radio(
    "בחר כיוון עסקאות:",
    options=["Long בלבד", "Short בלבד", "משולב (Long & Short במקביל)"],
    index=0,
    help="ברירת המחדל היא Long בלבד לשמירה על תאימות מלאה לתוצאות המקוריות."
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 1. כללי כניסה והון בסיסיים")

min_cap = st.sidebar.slider("שווי שוק מינימלי ($B)", min_value=150, max_value=500, value=200, step=25)

col_rsi1, col_rsi2 = st.sidebar.columns(2)
with col_rsi1:
    rsi_entry = st.sidebar.number_input("RSI כניסה לונג (<)", min_value=15, max_value=45, value=40, step=1)
with col_rsi2:
    rsi_exit = st.sidebar.number_input("RSI יעד יציאה לונג (>=)", min_value=50, max_value=85, value=60, step=1)
rsi_period = st.sidebar.slider("תקופת RSI (ימים)", min_value=7, max_value=28, value=14)

# חישוב ערכי שורט סימטריים
rsi_short_entry = 100 - rsi_entry  # לדוגמה: 100 - 40 = 60
rsi_short_exit = 100 - rsi_exit    # לדוגמה: 100 - 60 = 40

col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    initial_capital = st.sidebar.number_input("הון התחלתי ($)", min_value=1000, max_value=500000, value=10000, step=1000)
with col_c2:
    position_pct = st.sidebar.number_input("גודל כניסה (% מהתיק)", min_value=2.0, max_value=100.0, value=10.0, step=1.0) / 100.0

use_sma = st.sidebar.checkbox("סינון מניה מול SMA (מעל בלונג / מתחת בשורט)", value=True)
sma_length = st.sidebar.number_input("אורך SMA של המניה", min_value=20, max_value=300, value=200, step=10, disabled=not use_sma)

use_spy_filter = st.sidebar.checkbox("🌐 סינון שוק SPY מול SMA 200 (מעל בלונג / מתחת בשורט)", value=True)

# הגנת פערי פתיחה (Max Gap)
use_max_gap = st.sidebar.checkbox(
    "🚪 הגבלת פער פתיחה מקסימלי (Max Gap-Up בלונג / Gap-Down בשורט)",
    value=False,
    help="מונע כניסה אם המניה מזנקת בלונג או מתרסקת בשורט מעבר לסף שהוגדר מול סגירת אתמול."
)
max_gap_pct = st.sidebar.slider(
    "פער פתיחה מקסימלי מותר (%):",
    min_value=0.5, max_value=10.0, value=2.0, step=0.1,
    disabled=not use_max_gap
)

# --- 2. מסנני מניעת סכינים נופלות והיפוך ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 2. מסנני היפוך ומניעת סכינים נופלות")

use_rsi_hook = st.sidebar.checkbox(
    "1. חציית RSI (RSI Hook: מעלה בלונג / מטה בשורט)",
    value=False
)

use_green_candle = st.sidebar.checkbox(
    "2. אישור כיוון נר (ירוק בלונג / אדום בשורט)",
    value=False
)

use_sma_slope = st.sidebar.checkbox(
    "3. שיפוע SMA (עולה בלונג / יורד בשורט)",
    value=False,
    disabled=not use_sma
)
sma_slope_lookback = st.sidebar.number_input(
    "בדיקת שיפוע SMA מול ימים לאחור:",
    min_value=5, max_value=60, value=20, step=5,
    disabled=not (use_sma and use_sma_slope)
)

use_max_dist_sma = st.sidebar.checkbox(
    "4. הגבלת מרחק מקסימלי מה-SMA",
    value=False,
    disabled=not use_sma
)
max_dist_pct = st.sidebar.slider(
    "מרחק מרבי מה-SMA (%):",
    min_value=3.0, max_value=25.0, value=10.0, step=0.5,
    disabled=not (use_sma and use_max_dist_sma)
)

# --- 3. סינון מחזורי מסחר RVOL ---
st.sidebar.markdown("---")
st.sidebar.subheader("📊 3. סינון מחזורי מסחר (RVOL)")
use_rvol = st.sidebar.checkbox("סנן כניסה לפי RVOL של יום הקנייה/מכירה", value=False)
min_rvol = st.sidebar.slider(
    "סף RVOL מינימלי:",
    min_value=0.5, max_value=3.0, value=1.0, step=0.1,
    disabled=not use_rvol
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
    "מרחק Trailing Stop מהקיצון לחצי הנותר (%):",
    min_value=0.5, max_value=15.0, value=1.0, step=0.1,
    disabled=not use_scale_out
)
lock_breakeven = st.sidebar.checkbox(
    "🔒 נעל רצפת איזון (Breakeven Floor)",
    value=True,
    disabled=not use_scale_out
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

# --- הודעה ויזואלית על מצב המסחר הנבחר ---
if trade_mode == "Long בלבד":
    st.info("🟢 **מצב פעיל: Long בלבד** | כניסה: RSI < {0}, יעד: RSI >= {1} | שוק: SPY מעל SMA 200".format(rsi_entry, rsi_exit))
elif trade_mode == "Short בלבד":
    st.warning("🔴 **מצב פעיל: Short בלבד (היפוך סימטרי)** | כניסה: RSI > {0}, יעד: RSI <= {1} | שוק: SPY מתחת ל-SMA 200 | הגנת Max Gap-Down מופעלת".format(rsi_short_entry, rsi_short_exit))
else:
    st.success("🔄 **מצב פעיל: משולב (Long & Short במקביל)** | כניסות לשני הכיוונים בהתאם למצב השוק ואינדיקטורי המניה".format())

active_tickers = [sym for sym, cap in STOCK_MARKET_CAPS.items() if cap >= min_cap]
st.write(f"נמצאו **{len(active_tickers)}** חברות מעל סף שווי שוק של **${min_cap}B** (מתוך {len(STOCK_MARKET_CAPS)} במאגר)")

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
                spy_bullish = spy_series > spy_sma200
                spy_bearish = spy_series < spy_sma200

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
                
                pending_entries = []
                pending_exits = []

                for day in trading_days:
                    # 1. ביצוע יציאות שממתינות מהיום הקודם (Next Day Open)
                    if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                        for exit_order in pending_exits:
                            sym = exit_order["ticker"]
                            if sym in open_positions and day in indicators[sym].index:
                                pos = open_positions[sym]
                                exit_px = indicators[sym].loc[day, "Open"]
                                shares_to_close = exit_order["shares"]
                                
                                if pos["side"] == "LONG":
                                    proceeds = shares_to_close * exit_px
                                    cost_part = shares_to_close * pos["entry_price"]
                                    pnl_dollar = proceeds - cost_part
                                    pnl_pct = (exit_px / pos["entry_price"]) - 1.0
                                    cash += proceeds
                                else:  # SHORT
                                    liability_cost = shares_to_close * exit_px
                                    short_open_val = shares_to_close * pos["entry_price"]
                                    pnl_dollar = short_open_val - liability_cost
                                    pnl_pct = 1.0 - (exit_px / pos["entry_price"])
                                    cash += (short_open_val + pnl_dollar)

                                closed_trades.append({
                                    "מניה": sym,
                                    "כיוון": pos["side"],
                                    "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                    "יציאה": day.strftime("%Y-%m-%d"),
                                    "מחיר כניסה": round(pos["entry_price"], 2),
                                    "מחיר יציאה": round(exit_px, 2),
                                    "כמות": round(shares_to_close, 2),
                                    "רווח/הפסד ($)": round(pnl_dollar, 2),
                                    "תשואה (%)": round(pnl_pct * 100, 2),
                                    "ימי החזקה": pos["days_held"],
                                    "סיבת יציאה": exit_order["reason"],
                                    "exit_date_raw": day
                                })
                                
                                pos["shares"] -= shares_to_close
                                if pos["shares"] <= 0.0001:
                                    del open_positions[sym]
                        pending_exits = []

                        # ביצוע כניסות ממתינות (לונג ושורט)
                        for entry_order in pending_entries:
                            sym = entry_order["ticker"]
                            side = entry_order["side"]
                            if sym not in open_positions and day in indicators[sym].index:
                                row_e = indicators[sym].loc[day]
                                entry_px = row_e["Open"]
                                signal_close_px = entry_order.get("signal_close_price", entry_px)
                                
                                # בדיקת RVOL
                                pass_rvol = True
                                if use_rvol and row_e.get("RVOL", 1.0) < min_rvol:
                                    pass_rvol = False
                                
                                # בדיקת פערי פתיחה: Max Gap-Up בלונג / Max Gap-Down בשורט
                                pass_gap = True
                                if use_max_gap and signal_close_px > 0:
                                    gap_pct = ((entry_px / signal_close_px) - 1.0) * 100.0
                                    if side == "LONG" and gap_pct > max_gap_pct:
                                        pass_gap = False
                                    elif side == "SHORT" and gap_pct < -max_gap_pct:
                                        pass_gap = False  # קריסה חדה מדי למטה בשורט
                                
                                if pass_rvol and pass_gap:
                                    alloc = entry_order["allocation"]
                                    if cash >= alloc and alloc > 0 and entry_px > 0:
                                        shares = alloc / entry_px
                                        cash -= alloc
                                        open_positions[sym] = {
                                            "side": side,
                                            "shares": shares,
                                            "entry_price": entry_px,
                                            "cost_basis": alloc,
                                            "entry_date": day,
                                            "days_held": 0,
                                            "scaled_out": False,
                                            "extreme_after_scale": entry_px  # שיא בלונג, שפל בשורט
                                        }
                        pending_entries = []

                    # 2. עדכון פוזיציות ושערוך שווי תיק יומי
                    holdings_val = 0.0
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            cur_px = indicators[sym].loc[day, "Close"]
                            pos["days_held"] += 1
                            
                            if pos["side"] == "LONG":
                                holdings_val += pos["shares"] * cur_px
                                if pos["scaled_out"] and cur_px > pos["extreme_after_scale"]:
                                    pos["extreme_after_scale"] = cur_px
                            else:  # SHORT
                                unrealized_pnl = (pos["entry_price"] - cur_px) * pos["shares"]
                                holdings_val += pos["cost_basis"] + unrealized_pnl
                                if pos["scaled_out"] and cur_px < pos["extreme_after_scale"]:
                                    pos["extreme_after_scale"] = cur_px
                        else:
                            holdings_val += pos["cost_basis"]

                    total_equity = cash + holdings_val
                    portfolio_history.append({"Date": day, "Equity": total_equity, "Cash": cash})

                    # 3. בדיקת תנאי יציאה בסגירת יום המסחר
                    exits_to_process = []
                    for sym, pos in open_positions.items():
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            cur_px = row["Close"]
                            
                            # חישוב רווח/הפסד פוזיציה
                            if pos["side"] == "LONG":
                                pnl_pct = (cur_px / pos["entry_price"]) - 1.0
                                pnl_dollar = (cur_px - pos["entry_price"]) * pos["shares"]
                            else:
                                pnl_pct = 1.0 - (cur_px / pos["entry_price"])
                                pnl_dollar = (pos["entry_price"] - cur_px) * pos["shares"]

                            # בדיקת Stop Loss ראשוני
                            hit_sl = False
                            if use_sl:
                                if sl_pct_val is not None and pnl_pct <= -sl_pct_val:
                                    hit_sl = True
                                elif sl_usd_val is not None and pnl_dollar <= -sl_usd_val:
                                    hit_sl = True

                            if hit_sl:
                                exits_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Stop Loss 🛑"})
                                continue

                            # בדיקת Time Stop
                            if use_time_stop and not pos["scaled_out"]:
                                if pos["days_held"] >= max_holding_days:
                                    exits_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "Time Stop ⏳"})
                                    continue

                            # בדיקת מימוש 50% ביעד RSI
                            hit_target = False
                            if pos["side"] == "LONG" and row["RSI"] >= rsi_exit:
                                hit_target = True
                            elif pos["side"] == "SHORT" and row["RSI"] <= rsi_short_exit:
                                hit_target = True

                            if hit_target and not pos["scaled_out"]:
                                if use_scale_out:
                                    half_shares = pos["shares"] * 0.5
                                    pos["scaled_out"] = True
                                    pos["extreme_after_scale"] = cur_px
                                    exits_to_process.append({"ticker": sym, "shares": half_shares, "reason": "מימוש 50% ביעד RSI 🎯"})
                                else:
                                    exits_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": "RSI Target 100% 🎯"})
                                continue

                            # בדיקת Trailing Stop לחצי הנותר
                            if pos["scaled_out"] and use_scale_out:
                                if pos["side"] == "LONG":
                                    trailing_price = pos["extreme_after_scale"] * (1.0 - (trailing_pct / 100.0))
                                    eff_stop = max(trailing_price, pos["entry_price"]) if lock_breakeven else trailing_price
                                    if cur_px <= eff_stop:
                                        lbl = "Trailing Stop (איזון) 🔒" if (cur_px <= pos["entry_price"] and lock_breakeven) else f"Trailing Stop {trailing_pct}% 📈"
                                        exits_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": lbl})
                                else:  # SHORT Trailing Stop (עוקב אחרי שפל כלפי מטה)
                                    trailing_price = pos["extreme_after_scale"] * (1.0 + (trailing_pct / 100.0))
                                    eff_stop = min(trailing_price, pos["entry_price"]) if lock_breakeven else trailing_price
                                    if cur_px >= eff_stop:
                                        lbl = "Trailing Stop שורט (איזון) 🔒" if (cur_px >= pos["entry_price"] and lock_breakeven) else f"Trailing Stop שורט {trailing_pct}% 📉"
                                        exits_to_process.append({"ticker": sym, "shares": pos["shares"], "reason": lbl})

                    for ex in exits_to_process:
                        sym = ex["ticker"]
                        if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                            if not any(pe["ticker"] == sym and pe["reason"] == ex["reason"] for pe in pending_exits):
                                pending_exits.append(ex)
                        else:
                            pos = open_positions[sym]
                            cur_px = indicators[sym].loc[day, "Close"]
                            shares_to_close = ex["shares"]
                            
                            if pos["side"] == "LONG":
                                proceeds = shares_to_close * cur_px
                                cost_part = shares_to_close * pos["entry_price"]
                                pnl_d = proceeds - cost_part
                                pnl_p = (cur_px / pos["entry_price"]) - 1.0
                                cash += proceeds
                            else:
                                liability_cost = shares_to_close * cur_px
                                short_open_val = shares_to_close * pos["entry_price"]
                                pnl_d = short_open_val - liability_cost
                                pnl_p = 1.0 - (cur_px / pos["entry_price"])
                                cash += (short_open_val + pnl_d)

                            closed_trades.append({
                                "מניה": sym,
                                "כיוון": pos["side"],
                                "כניסה": pos["entry_date"].strftime("%Y-%m-%d"),
                                "יציאה": day.strftime("%Y-%m-%d"),
                                "מחיר כניסה": round(pos["entry_price"], 2),
                                "מחיר יציאה": round(cur_px, 2),
                                "כמות": round(shares_to_close, 2),
                                "רווח/הפסד ($)": round(pnl_d, 2),
                                "תשואה (%)": round(pnl_p * 100, 2),
                                "ימי החזקה": pos["days_held"],
                                "סיבת יציאה": ex["reason"],
                                "exit_date_raw": day
                            })
                            pos["shares"] -= shares_to_close
                            if pos["shares"] <= 0.0001:
                                del open_positions[sym]

                    # 4. בדיקת איתותי כניסה חדשים (Long / Short / משולב)
                    spy_is_bull = bool(spy_bullish.loc[day]) if (use_spy_filter and day in spy_bullish.index) else True
                    spy_is_bear = bool(spy_bearish.loc[day]) if (use_spy_filter and day in spy_bearish.index) else True

                    allow_long = trade_mode in ["Long בלבד", "משולב (Long & Short במקביל)"]
                    allow_short = trade_mode in ["Short בלבד", "משולב (Long & Short במקביל)"]

                    for sym in active_tickers:
                        if sym in open_positions or any(pe["ticker"] == sym for pe in pending_entries) or sym not in indicators:
                            continue
                        if day in indicators[sym].index:
                            row = indicators[sym].loc[day]
                            
                            # --- בדיקת כניסת LONG ---
                            long_signal = False
                            if allow_long and (spy_is_bull or not use_spy_filter):
                                rsi_cond = (row["RSI_prev"] < rsi_entry and row["RSI"] >= rsi_entry) if use_rsi_hook else (row["RSI"] < rsi_entry)
                                green_cond = (row["Close"] > row["Open"]) if use_green_candle else True
                                sma_cond = (row["Close"] > row["SMA"]) if use_sma else True
                                slope_cond = (row["SMA_slope"] > 0) if (use_sma and use_sma_slope) else True
                                dist_cond = (((row["Close"] / row["SMA"]) - 1.0) * 100 <= max_dist_pct) if (use_sma and use_max_dist_sma) else True
                                rvol_cond = (row.get("RVOL", 1.0) >= min_rvol) if (use_rvol and exec_timing == "מחיר נעילה באותו יום (Same Day Close)") else True
                                
                                if rsi_cond and green_cond and sma_cond and slope_cond and dist_cond and rvol_cond:
                                    long_signal = True

                            # --- בדיקת כניסת SHORT (היפוך סימטרי מלא) ---
                            short_signal = False
                            if allow_short and not long_signal and (spy_is_bear or not use_spy_filter):
                                rsi_cond_s = (row["RSI_prev"] > rsi_short_entry and row["RSI"] <= rsi_short_entry) if use_rsi_hook else (row["RSI"] > rsi_short_entry)
                                red_cond_s = (row["Close"] < row["Open"]) if use_green_candle else True
                                sma_cond_s = (row["Close"] < row["SMA"]) if use_sma else True
                                slope_cond_s = (row["SMA_slope"] < 0) if (use_sma and use_sma_slope) else True
                                dist_cond_s = (((row["SMA"] / row["Close"]) - 1.0) * 100 <= max_dist_pct) if (use_sma and use_max_dist_sma) else True
                                rvol_cond_s = (row.get("RVOL", 1.0) >= min_rvol) if (use_rvol and exec_timing == "מחיר נעילה באותו יום (Same Day Close)") else True
                                
                                if rsi_cond_s and red_cond_s and sma_cond_s and slope_cond_s and dist_cond_s and rvol_cond_s:
                                    short_signal = True

                            chosen_side = "LONG" if long_signal else ("SHORT" if short_signal else None)
                            
                            if chosen_side:
                                alloc = total_equity * position_pct
                                if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                                    pending_entries.append({
                                        "ticker": sym,
                                        "side": chosen_side,
                                        "allocation": alloc,
                                        "signal_close_price": float(row["Close"])
                                    })
                                else:
                                    if cash >= alloc and alloc > 0:
                                        px = row["Close"]
                                        shares = alloc / px
                                        cash -= alloc
                                        open_positions[sym] = {
                                            "side": chosen_side,
                                            "shares": shares,
                                            "entry_price": px,
                                            "cost_basis": alloc,
                                            "entry_date": day,
                                            "days_held": 0,
                                            "scaled_out": False,
                                            "extreme_after_scale": px
                                        }

                # --- מדדי ביצוע מוסדיים ---
                df_equity = pd.DataFrame(portfolio_history).set_index("Date")
                bm_start = benchmark_close.iloc[0]
                df_equity["Benchmark"] = (benchmark_close / bm_start) * initial_capital

                strat_final = df_equity["Equity"].iloc[-1]
                bm_final = df_equity["Benchmark"].iloc[-1]
                strat_ret = ((strat_final / initial_capital) - 1) * 100
                bm_ret = ((bm_final / initial_capital) - 1) * 100

                df_equity["Daily_Return"] = df_equity["Equity"].pct_change().fillna(0)
                rf_daily = (1 + 0.04) ** (1/252) - 1
                excess_returns = df_equity["Daily_Return"] - rf_daily
                daily_std = df_equity["Daily_Return"].std()
                sharpe_ratio = (excess_returns.mean() / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

                downside_returns = df_equity["Daily_Return"][df_equity["Daily_Return"] < 0]
                downside_std = downside_returns.std()
                sortino_ratio = (excess_returns.mean() / downside_std * np.sqrt(252)) if (downside_std > 0 and not np.isnan(downside_std)) else 0.0

                roll_max = df_equity["Equity"].cummax()
                dd = (df_equity["Equity"] - roll_max) / roll_max
                max_dd = dd.min() * 100

                total_days = max((end_date - start_date).days, 1)
                years = total_days / 365.25
                cagr = ((strat_final / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0.0
                calmar_ratio = abs(cagr / max_dd) if abs(max_dd) > 0 else 0.0

                df_trades = pd.DataFrame(closed_trades) if closed_trades else pd.DataFrame()
                if not df_trades.empty:
                    wins = df_trades[df_trades["רווח/הפסד ($)"] > 0]
                    losses = df_trades[df_trades["רווח/הפסד ($)"] < 0]

                    win_count = len(wins)
                    total_count = len(df_trades)
                    win_rate = (win_count / total_count) * 100

                    gross_profit = wins["רווח/הפסד ($)"].sum()
                    gross_loss = abs(losses["רווח/הפסד ($)"].sum())

                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

                    avg_win = wins["רווח/הפסד ($)"].mean() if win_count > 0 else 0.0
                    avg_loss = abs(losses["רווח/הפסד ($)"].mean()) if len(losses) > 0 else 0.0
                    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 999.0
                    avg_hold_days = df_trades["ימי החזקה"].mean()
                else:
                    win_rate, profit_factor, payoff_ratio, avg_win, avg_loss, avg_hold_days = 0, 0, 0, 0, 0, 0

                alpha_val = strat_ret - bm_ret
                st.session_state["last_sim_data"] = {
                    "זמן הרצה": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "כיוון עסקאות": trade_mode,
                    "תאריך התחלה": str(start_date),
                    "תאריך סיום": str(end_date),
                    "שווי שוק מינימלי ($B)": min_cap,
                    "הון התחלתי ($)": initial_capital,
                    "אחוז פוזיציה (%)": position_pct * 100.0,
                    "RSI כניסה לונג": rsi_entry,
                    "RSI כניסה שורט": rsi_short_entry,
                    "תזמון ביצוע": exec_timing,
                    "סינון שוק SPY": "מופעל" if use_spy_filter else "כבוי",
                    "סינון SMA מניה": f"מופעל ({sma_length})" if use_sma else "כבוי",
                    "מימוש 50% ביעד": "מופעל" if use_scale_out else "כבוי",
                    "מרחק Trailing Stop (%)": trailing_pct if use_scale_out else "ללא",
                    "הגנת פער פתיחה Max Gap": f"מופעל ({max_gap_pct}%)" if use_max_gap else "כבוי",
                    "שווי תיק סופי ($)": round(strat_final, 2),
                    "תשואת אסטרטגיה (%)": round(strat_ret, 2),
                    "תשואת S&P 500 (%)": round(bm_ret, 2),
                    "אלפא (%)": round(alpha_val, 2),
                    "Max Drawdown (%)": round(max_dd, 2),
                    "Win Rate (%)": round(win_rate, 2),
                    "Profit Factor": round(profit_factor, 2),
                    "Sharpe Ratio": round(sharpe_ratio, 2),
                    "Sortino Ratio": round(sortino_ratio, 2),
                    "Calmar Ratio": round(calmar_ratio, 2),
                    "Payoff Ratio": round(payoff_ratio, 2),
                    "זמן החזקה ממוצע (ימים)": round(avg_hold_days, 1),
                    "סה\"כ פעולות": len(df_trades)
                }

                # KPIs עליונים
                st.markdown("---")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("שווי תיק סופי", f"${strat_final:,.2f}", delta=f"{strat_ret:.2f}%")
                col_m2.metric("תשואת מדד S&P 500", f"${bm_final:,.2f}", delta=f"{bm_ret:.2f}%")
                col_m3.metric("Alpha (עודף על המדד)", f"{(strat_ret - bm_ret):+.2f}%")
                col_m4.metric("Max Drawdown (נסיגה משיא)", f"{max_dd:.2f}%")

                # טבלת מדדים מוסדיים
                st.markdown("### 📊 מדדי איכות ניהול תיק וסיכון (Institutional Metrics)")
                q1, q2, q3, q4, q5, q6 = st.columns(6)
                q1.metric("Win Rate", f"{win_rate:.1f}%")
                q2.metric("Profit Factor", f"{profit_factor:.2f}")
                q3.metric("Sharpe", f"{sharpe_ratio:.2f}")
                q4.metric("Sortino", f"{sortino_ratio:.2f}")
                q5.metric("Calmar", f"{calmar_ratio:.2f}")
                q6.metric("Payoff Ratio", f"{payoff_ratio:.2f}")

                perf_summary = pd.DataFrame({
                    "מדד": [
                        "Win Rate (שיעור הצלחה)", "Profit Factor (PF)", "Sharpe Ratio (מדד שארפ)",
                        "Sortino Ratio (מדד סורטינו)", "Calmar Ratio (מדד קלמר)", "Payoff Ratio (יחס רווח/הפסד)",
                        "Max Drawdown (נסיגה מקסימלית)", "זמן החזקה ממוצע"
                    ],
                    "ערך בתיק שלך": [
                        f"{win_rate:.1f}%", f"{profit_factor:.2f}", f"{sharpe_ratio:.2f}",
                        f"{sortino_ratio:.2f}", f"{calmar_ratio:.2f}", f"{payoff_ratio:.2f}",
                        f"{max_dd:.2f}%", f"{avg_hold_days:.1f} ימים"
                    ],
                    "סף ייחוס מקצועי": [
                        "> 60%", "> 1.60", "> 1.20", "> 1.80", "> 1.20", "> 1.30", "< 10.0%", "3 – 15 ימי מסחר"
                    ]
                })
                st.table(perf_summary)

                # גרף עקומת תיק
                st.markdown("### 📈 עקומת שווי התיק (Equity Curve)")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Equity"], mode="lines", name="תיק האסטרטגיה", line=dict(color="#00BA38", width=2.5)))
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Benchmark"], mode="lines", name="S&P 500", line=dict(color="#619CFF", dash="dot")))
                fig.update_layout(title="שווי תיק מול S&P 500", template="plotly_dark", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # יומן עסקאות
                with st.expander("📋 יומן עסקאות מפורט (פירוט עסקאות Long ו-Short)", expanded=False):
                    if not df_trades.empty:
                        clean_trades = [{k: v for k, v in t.items() if k != "exit_date_raw"} for t in closed_trades]
                        df_tr = pd.DataFrame(clean_trades)
                        st.write(f"**סה\"כ פעולות:** {len(df_tr)} | **רווח ממוצע לטרייד מנצח:** ${avg_win:.2f} | **הפסד ממוצע לטרייד מפסיד:** ${avg_loss:.2f}")
                        st.dataframe(df_tr, use_container_width=True)
                    else:
                        st.info("לא נסגרו עסקאות בתקופה זו.")

# --- 5. אזור שמירה והורדת אקסל ---
st.markdown("---")
st.subheader("📁 יומן שמירת סימולציות והורדה לאקסל (Excel)")

col_save, col_clear = st.columns([2, 1])

with col_save:
    if "last_sim_data" in st.session_state:
        if st.button("💾 הוסף סימולציה נוכחית ליומן", type="primary"):
            st.session_state.saved_simulations.append(st.session_state["last_sim_data"].copy())
            st.success("הסימולציה נשמרה בהצלחה כשורה חדשה ביומן!")
    else:
        st.caption("הפעל סימולציה כדי שתוכל להוסיף את תוצאותיה ליומן.")

with col_clear:
    if st.session_state.saved_simulations:
        if st.button("🗑️ נקה יומן סימולציות"):
            st.session_state.saved_simulations = []
            st.rerun()

if st.session_state.saved_simulations:
    df_saved = pd.DataFrame(st.session_state.saved_simulations)
    st.write(f"**סה\"כ סימולציות שנצברו ביומן:** {len(df_saved)}")
    st.dataframe(df_saved, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saved.to_excel(writer, index=False, sheet_name="Simulations_Log")
    excel_data = output.getvalue()

    st.download_button(
        label="📥 הורד יומן סימולציות (Excel)",
        data=excel_data,
        file_name=f"simulations_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

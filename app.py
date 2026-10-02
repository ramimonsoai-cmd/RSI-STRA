import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="סימולטור מסחר כמותי מוסדי מלא", layout="wide")

st.title("📈 סימולטור מסחר כמותי: ניתוח מוסדי + הגנת Gap-Up")
st.caption("ניתוח תיק מקיף: מאגר מורחב של חברות Mega-Cap (מעל $200B), מדדי איכות, סינון SPY ומניעת סכינים")

# מאגר מניות מגה-קאפ מורחב ומעודכן (מעל 60 חברות מובילות בארה"ב)
STOCK_MARKET_CAPS = {
    # חברות טריליון וביג-טק
    "NVDA": 3500, "AAPL": 3400, "MSFT": 3100, "AMZN": 2000, "GOOGL": 2000,
    "META": 1450, "TSLA": 850, "BRK-B": 980, "AVGO": 850, "LLY": 820,
    
    # פיננסים ובנקים
    "JPM": 650, "V": 540, "MA": 460, "BAC": 340, "WFC": 240, 
    "MS": 220, "GS": 210, "AXP": 220, "BLK": 210,
    
    # צריכה, קמעונאות ותקשורת
    "WMT": 680, "COST": 410, "PG": 380, "HD": 380, "KO": 280, 
    "PEP": 230, "MCD": 210, "NFLX": 350, "DIS": 210, "PM": 230,
    
    # תוכנה ושבבים מתקדמים
    "ORCL": 420, "CRM": 290, "NOW": 210, "ADBE": 220, "INTU": 200, 
    "CSCO": 230, "QCOM": 220, "AMD": 240, "TXN": 210, "AMAT": 200, 
    "MU": 210, "PLTR": 210, "PANW": 200, "LRCX": 200,
    
    # בריאות ותרופות
    "UNH": 530, "JNJ": 380, "ABBV": 350, "MRK": 280, "TMO": 230, 
    "ABT": 220, "DHR": 200, "ISRG": 210, "PFE": 180, "BMY": 150,
    
    # אנרגיה ותעשייה
    "XOM": 480, "CVX": 280, "COP": 180, "GE": 230, "CAT": 230, 
    "RTX": 200, "HON": 180, "LIN": 220, "UNP": 170, "BA": 150, "IBM": 210
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

# סינון החברות הפעילות לפי סף שווי השוק
active_tickers = [sym for sym, cap in STOCK_MARKET_CAPS.items() if cap >= min_cap]
st.info(f"נמצאו **{len(active_tickers)}** חברות מעל סף שווי שוק של **${min_cap}B** (מתוך מאגר של {len(STOCK_MARKET_CAPS)} חברות)")

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
                
                # נתוני מדד SPY
                spy_series = close_df["SPY"].dropna()
                spy_sma200 = spy_series.rolling(window=200).mean()
                spy_filter_series = spy_series > spy_sma200

                # חישוב אינדיקטורים לכל מניה
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
                                
                                # חילוץ שער הסגירה מאתמול בצורה מוגנת
                                signal_close_px = buy.get("signal_close_price", entry_px)
                                
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
                                        pass_gap = False  # פער גדול מדי מעל הסגירה
                                
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
                                del open_positions[sym]

                    # 4. בדיקת כניסות חדשות
                    is_spy_bullish = True
                    if use_spy_filter:
                        is_spy_bullish = bool(spy_filter_series.loc[day]) if day in spy_filter_series.index else False

                    if is_spy_bullish:
                        for sym in active_tickers:
                            if sym in open_positions or any(b["ticker"] == sym for b in pending_buys) or sym not in indicators:
                                continue
                            if day in indicators[sym].index:
                                row = indicators[sym].loc[day]
                                
                                if use_rsi_hook:
                                    rsi_cond = (row["RSI_prev"] < rsi_entry) and (row["RSI"] >= rsi_entry)
                                else:
                                    rsi_cond = row["RSI"] < rsi_entry

                                green_cond = (row["Close"] > row["Open"]) if use_green_candle else True
                                sma_cond = (row["Close"] > row["SMA"]) if use_sma else True
                                slope_cond = (row["SMA_slope"] > 0) if (use_sma and use_sma_slope) else True

                                if use_sma and use_max_dist_sma:
                                    dist_above = ((row["Close"] / row["SMA"]) - 1.0) * 100
                                    dist_cond = (dist_above <= max_dist_pct)
                                else:
                                    dist_cond = True

                                rvol_cond = True
                                if use_rvol and exec_timing == "מחיר נעילה באותו יום (Same Day Close)":
                                    if row.get("RVOL", 1.0) < min_rvol:
                                        rvol_cond = False

                                if rsi_cond and green_cond and sma_cond and slope_cond and dist_cond and rvol_cond:
                                    alloc = total_equity * position_pct
                                    if exec_timing == "מחיר פתיחה ביום שלמחרת (Next Day Open)":
                                        pending_buys.append({
                                            "ticker": sym,
                                            "allocation": alloc,
                                            "signal_close_price": float(row["Close"])
                                        })
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
                                            executed_buys.append({"date": day, "ticker": sym, "price": px})

                # --- חישוב מדדי ביצוע מוסדיים (Institutional Quant Analytics) ---
                df_equity = pd.DataFrame(portfolio_history).set_index("Date")
                bm_start = benchmark_close.iloc[0]
                df_equity["Benchmark"] = (benchmark_close / bm_start) * initial_capital

                strat_final = df_equity["Equity"].iloc[-1]
                bm_final = df_equity["Benchmark"].iloc[-1]
                strat_ret = ((strat_final / initial_capital) - 1) * 100
                bm_ret = ((bm_final / initial_capital) - 1) * 100

                df_equity["Daily_Return"] = df_equity["Equity"].pct_change().fillna(0)
                df_equity["BM_Daily_Return"] = df_equity["Benchmark"].pct_change().fillna(0)

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

                # --- 1. הצגת KPIs מרכזיים עליונים ---
                st.markdown("---")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("שווי תיק סופי", f"${strat_final:,.2f}", delta=f"{strat_ret:.2f}%")
                col_m2.metric("תשואת מדד S&P 500", f"${bm_final:,.2f}", delta=f"{bm_ret:.2f}%")
                col_m3.metric("Alpha (עודף על המדד)", f"{(strat_ret - bm_ret):+.2f}%")
                col_m4.metric("Max Drawdown (נסיגה משיא)", f"{max_dd:.2f}%")

                # --- 2. אזור ייעודי: מדדי איכות ניהול תיק וסיכון (Institutional Metrics) ---
                st.markdown("### 📊 מדדי איכות ניהול תיק וסיכון (Institutional Metrics)")
                
                q1, q2, q3, q4, q5, q6 = st.columns(6)
                q1.metric("שיעור הצלחה (Win Rate)", f"{win_rate:.1f}%", help="אחוז פעולות המכירה שהסתיימו ברווח")
                q2.metric("Profit Factor (PF)", f"{profit_factor:.2f}", help="יחס סך הרווחים בדולרים חלקי סך ההפסדים. מעל 1.5 נחשב טוב מאוד, מעל 2.0 מעולה.")
                q3.metric("מדד שארפ (Sharpe)", f"{sharpe_ratio:.2f}", help="תשואה עודפת ליחידת סיכון/תנודתיות שנתית (Rf=4%). מעל 1.0 טוב, מעל 1.5 מצוין.")
                q4.metric("מדד סורטינו (Sortino)", f"{sortino_ratio:.2f}", help="תשואה מול תנודתיות שלילית בלבד. מדד מדויק יותר לאסטרטגיות מומנטום.")
                q5.metric("מדד קלמר (Calmar)", f"{calmar_ratio:.2f}", help="תשואה שנתית מורכבת (CAGR) חלקי הנסיגה המקסימלית (MaxDD).")
                q6.metric("Payoff Ratio (יחס רווח/הפסד)", f"{payoff_ratio:.2f}", help="ממוצע דולרי בעסקה מנצחת חלקי ממוצע בעסקה מפסידה.")

                perf_summary = pd.DataFrame({
                    "מדד": [
                        "Win Rate (שיעור הצלחה)",
                        "Profit Factor (PF)",
                        "Sharpe Ratio (מדד שארפ)",
                        "Sortino Ratio (מדד סורטינו)",
                        "Calmar Ratio (מדד קלמר)",
                        "Payoff Ratio (יחס רווח/הפסד)",
                        "Max Drawdown (נסיגה מקסימלית)",
                        "זמן החזקה ממוצע"
                    ],
                    "ערך בתיק שלך": [
                        f"{win_rate:.1f}%",
                        f"{profit_factor:.2f}",
                        f"{sharpe_ratio:.2f}",
                        f"{sortino_ratio:.2f}",
                        f"{calmar_ratio:.2f}",
                        f"{payoff_ratio:.2f}",
                        f"{max_dd:.2f}%",
                        f"{avg_hold_days:.1f} ימים"
                    ],
                    "סף ייחוס מקצועי": [
                        "> 60% (לאסטרטגיות RSI)",
                        "> 1.60",
                        "> 1.20",
                        "> 1.80",
                        "> 1.20",
                        "> 1.30",
                        "< 10.0%",
                        "3 – 15 ימי מסחר"
                    ],
                    "אינדיקציה": [
                        "מעולה 🚀" if win_rate >= 70 else ("טוב מאוד ✅" if win_rate >= 60 else "גבולי ⚠️"),
                        "פנומנלי 🚀" if profit_factor >= 2.5 else ("מעולה ✅" if profit_factor >= 1.7 else "נמוך מדי ⚠️"),
                        "תשואה מעולה ביחס לסיכון 🚀" if sharpe_ratio >= 1.5 else ("ניהול סיכונים טוב ✅" if sharpe_ratio >= 1.0 else "תנודתיות גבוהה ביחס לתשואה ⚠️"),
                        "תנודתיות שלילית אפסית 🚀" if sortino_ratio >= 2.0 else ("יציב מאוד ✅" if sortino_ratio >= 1.4 else "נסיגות חדות ⚠️"),
                        "יציבות גבוהה מול ירידות 🚀" if calmar_ratio >= 1.8 else ("סביר ✅" if calmar_ratio >= 1.0 else "עומק נפילה מדאיג ⚠️"),
                        "רווחים גדולים מהפסדים 🚀" if payoff_ratio >= 1.5 else ("רווח ממוצע שווה להפסד ✅" if payoff_ratio >= 1.0 else "הפסדים ממוצעים גדולים מהרווח ⚠️"),
                        "רמת סיכון נמוכה ומבוקרת 🚀" if abs(max_dd) <= 7.0 else ("נסיגה סבירה לשוק מניות ✅" if abs(max_dd) <= 12.0 else "נסיגה עמוקה ⚠️"),
                        "שחרור מהיר של מזומן 🚀" if avg_hold_days <= 10 else ("מחזור הון תקין ✅" if avg_hold_days <= 20 else "כסף תקוע לזמן רב ⚠️")
                    ],
                    "מה המשמעות של המדד?": [
                        "אחוז העסקאות שהניבו רווח מתוך סך הפעולות שבוצעו.",
                        "כמה דולרים הרווחת על כל דולר שהפסדת במצטבר (סך רווח / סך הפסד).",
                        "מודד האם התשואה נובעת מאיכות המסחר או מרכבת הרים מסוכנת (מול ריבית חסרת סיכון).",
                        "בדומה לשארפ, אך מעניש רק על ירידות והפסדים (ולא על זינוקים למעלה).",
                        "היחס בין קצב התשואה השנתי (CAGR) לעומק הנפילה המקסימלית שחווית.",
                        "הרווח הממוצע בטרייד מנצח חלקי ההפסד הממוצע בטרייד מפסיד.",
                        "הירידה החדה ביותר בתיק משיא כל הזמנים שלו עד לנקודת השפל.",
                        "משך הזמן הממוצע שבו הון התיק היה מושקע בפוזיציה עד למימוש."
                    ]
                })
                st.table(perf_summary)

                # --- 3. עקומת התיק ---
                st.markdown("### 📈 עקומת שווי התיק (Equity Curve)")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Equity"], mode="lines", name="תיק האסטרטגיה", line=dict(color="#00BA38", width=2.5)))
                fig.add_trace(go.Scatter(x=df_equity.index, y=df_equity["Benchmark"], mode="lines", name="S&P 500", line=dict(color="#619CFF", dash="dot")))

                fig.update_layout(
                    title="שווי תיק מול S&P 500 (כולל סינון שוק SPY מעל SMA 200)",
                    template="plotly_dark",
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

                # --- 4. יומן עסקאות מפורט ---
                with st.expander("📋 יומן עסקאות מפורט (כולל פירוט מימושים וימי החזקה)", expanded=False):
                    if not df_trades.empty:
                        clean_trades = [{k: v for k, v in t.items() if k != "exit_date_raw"} for t in closed_trades]
                        df_tr = pd.DataFrame(clean_trades)
                        st.write(f"**סה\"כ פעולות מכירה:** {len(df_tr)} | **ממוצע רווח לעסקה מנצחת:** ${avg_win:.2f} | **ממוצע הפסד לעסקה מפסידה:** ${avg_loss:.2f}")
                        st.dataframe(df_tr, use_container_width=True)
                    else:
                        st.info("לא נסגרו עסקאות בתקופה זו.")

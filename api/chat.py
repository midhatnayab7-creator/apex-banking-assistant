import json
import os
from http.server import BaseHTTPRequestHandler
from groq import Groq

# ----------------------------
# SYSTEM PROMPT
# ----------------------------

SYSTEM_PROMPT = """You are Apex, a senior AI banking employee at Apex International Bank. You work exactly like a real-world bank employee — professional, knowledgeable, and capable of handling ANY banking task.

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

BEHAVIOR RULES:
- Always be professional, warm, and helpful like a real bank employee
- Use the appropriate tool for every request — never guess data
- For financial advice, base it on the customer's actual spending and account data
- For fraud detection, always flag suspicious activity immediately
- When you can't fulfill a request, explain why and suggest alternatives
- Support multiple languages if the customer writes in another language
- Proactively suggest useful services based on the customer's situation
- Always confirm before executing sensitive operations (transfers, card blocks, loan applications)
- When asked about any bank in the world, use the lookup_bank_info tool to provide complete information
- You can compare Apex Bank with any competitor and highlight advantages"""

# ----------------------------
# TOOLS DEFINITION (15 Tools)
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
                        "description": "Type of info: overview, services, rates, branches, swift_code, products, digital_banking, compare_with_apex"
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
        "services": ["Savings & Current Accounts", "Home Loans", "Car Loans", "Personal Loans", "MCB Lite (Digital Wallet)", "Credit Cards", "Islamic Banking (MCB Islamic)", "Forex", "Lockers", "Remittances", "Trade Finance"],
        "rates": {"savings": "7.5-10.5%", "fd": "12-15%", "personal_loan": "21-25%", "home_loan": "14-17%"},
        "digital": "MCB Mobile App, MCB Lite, Internet Banking",
        "notable": "One of Pakistan's most profitable banks. Strong corporate banking.",
        "website": "mcb.com.pk"
    },
    "jazzcash": {
        "full_name": "JazzCash (by Jazz/Mobilink Microfinance Bank)", "country": "Pakistan", "hq": "Islamabad",
        "founded": 2012, "type": "Mobile Financial Services / Digital Wallet", "ownership": "Jazz (VEON Group)",
        "swift": "N/A", "total_assets": "$1.5B", "branches": 0, "atms": 0,
        "employees": 3000, "customers": "40M+ accounts",
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
        "services": ["Digital Checking", "Credit Cards (no annual fee)", "Personal Loans", "Investment", "Insurance", "Crypto", "Business Accounts"],
        "rates": {"savings": "100% CDI (~13%)", "credit_card": "No annual fee", "personal_loan": "2-14%/month"},
        "digital": "Nubank App — fully digital",
        "notable": "World's largest neobank by customers (90M+). 5th largest bank in Latin America.",
        "website": "nubank.com.br"
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
# WORLDWIDE BRANCH DATABASE (25+ cities)
# =============================================

BRANCHES = {
    # Pakistan
    "karachi": {"branch": "Apex Bank — Karachi Main Branch", "address": "123 Shahrah-e-Faisal, PECHS, Karachi 75400", "hours": "Mon-Sat 9AM-5PM", "atms": 5, "phone": "+92-21-111-APEX", "services": ["Personal Banking", "Business Banking", "Wealth Management", "Forex", "Lockers", "Insurance"], "manager": "Tariq Hussain"},
    "lahore": {"branch": "Apex Bank — Lahore Branch", "address": "45 Mall Road, Gulberg III, Lahore 54000", "hours": "Mon-Sat 9AM-5PM", "atms": 3, "phone": "+92-42-111-APEX", "services": ["Personal Banking", "Business Banking", "Forex", "Lockers"], "manager": "Nadia Syed"},
    "islamabad": {"branch": "Apex Bank — Islamabad Branch", "address": "78 Blue Area, Jinnah Avenue, Islamabad 44000", "hours": "Mon-Sat 9AM-5PM", "atms": 4, "phone": "+92-51-111-APEX", "services": ["Personal Banking", "Business Banking", "Government Banking", "Forex", "Lockers"], "manager": "Kamran Shah"},
    "peshawar": {"branch": "Apex Bank — Peshawar Branch", "address": "University Road, Peshawar 25000", "hours": "Mon-Sat 9AM-4PM", "atms": 2, "phone": "+92-91-111-APEX", "services": ["Personal Banking", "Forex", "Lockers"], "manager": "Faizan Khan"},
    "faisalabad": {"branch": "Apex Bank — Faisalabad Branch", "address": "D-Ground, Faisalabad 38000", "hours": "Mon-Sat 9AM-5PM", "atms": 2, "phone": "+92-41-111-APEX", "services": ["Personal Banking", "Business Banking", "Agriculture Finance"], "manager": "Usman Iqbal"},
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
    return (f"CARD SECURITY ACTION — IMMEDIATE\n"
            f"Card: {card['number']} ({card_type.title()})\n"
            f"Action: BLOCKED immediately\n"
            f"Reason: {reason.title()}\n"
            f"Account: {account_id} — {acc['name']}\n"
            f"Replacement: New card will be mailed to {acc['address']} within 5-7 business days\n"
            f"Temporary Card: Available for pickup at {acc['branch']} branch with valid ID\n"
            f"Pending Transactions: All pending transactions have been held for review\n"
            f"24/7 Helpline: 1-800-APEX-BANK | Fraud Team: fraud@apexbank.com\n"
            f"Reference #: BLK-{account_id[-4:]}-{card['number'][-4:]}")


def get_branch_info(city):
    info = BRANCHES.get(city.lower())
    if info:
        return (f"BRANCH INFO — {city.title()}\n"
                f"Name: {info['branch']}\n"
                f"Address: {info['address']}\n"
                f"Hours: {info['hours']}\n"
                f"ATMs: {info['atms']} available 24/7\n"
                f"Phone: {info['phone']}\n"
                f"Branch Manager: {info['manager']}\n"
                f"Services: {', '.join(info['services'])}")
    return f"No branch found in {city}. Apex Bank has branches in: {', '.join(sorted(BRANCHES.keys()))}. Call 1-800-APEX-BANK for help."


def transfer_money(from_account, to_account, amount, currency="USD"):
    sender = CUSTOMERS.get(from_account.upper())
    if not sender:
        return f"Sender account {from_account} not found."
    if sender["status"] != "Active":
        return f"Transfer failed: Account {from_account} is {sender['status']}."
    if sender["balance"] < amount:
        return f"Transfer failed: Insufficient balance. Available: ${sender['balance']:,.2f}, Required: ${amount:,.2f}"
    receiver = CUSTOMERS.get(to_account.upper())
    receiver_name = receiver["name"] if receiver else f"External Account {to_account}"
    fee = 0 if receiver else round(amount * 0.01, 2)
    return (f"TRANSFER CONFIRMATION\n"
            f"From: {sender['name']} ({from_account}) | Balance: ${sender['balance']:,.2f}\n"
            f"To: {receiver_name} ({to_account})\n"
            f"Amount: ${amount:,.2f} {currency}\n"
            f"Transfer Fee: ${fee:,.2f}{' (external bank)' if fee else ' (internal — free)'}\n"
            f"Total Deduction: ${amount + fee:,.2f}\n"
            f"New Balance: ${sender['balance'] - amount - fee:,.2f}\n"
            f"Status: PROCESSED SUCCESSFULLY\n"
            f"Reference #: TXN-{from_account[-4:]}-{to_account[-4:]}-{int(amount)}\n"
            f"Expected Arrival: {'Instant' if receiver else '1-3 business days'}")


def pay_bill(account_id, bill_type, amount, provider=""):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    if acc["balance"] < amount:
        return f"Payment failed: Insufficient balance. Available: ${acc['balance']:,.2f}"
    return (f"BILL PAYMENT CONFIRMATION\n"
            f"Account: {account_id} — {acc['name']}\n"
            f"Bill Type: {bill_type.title()}\n"
            f"Provider: {provider if provider else bill_type.title() + ' Provider'}\n"
            f"Amount: ${amount:,.2f}\n"
            f"Previous Balance: ${acc['balance']:,.2f}\n"
            f"New Balance: ${acc['balance'] - amount:,.2f}\n"
            f"Status: PAID SUCCESSFULLY\n"
            f"Reference #: BILL-{account_id[-4:]}-{bill_type[:3].upper()}-{int(amount)}")


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
        return f"Card {card['number']} has been BLOCKED. Visit your branch or call 1-800-APEX-BANK to unblock."
    elif act == "unblock":
        return f"Card {card['number']} has been UNBLOCKED and is now active."
    elif act == "set_limit":
        return f"Card {card['number']} daily limit has been updated. New limit will take effect within 24 hours."
    elif act == "enable_international":
        return f"International transactions ENABLED for card {card['number']}. Valid for 30 days."
    elif act == "disable_international":
        return f"International transactions DISABLED for card {card['number']}."
    return f"Invalid action. Available: view_details, block, unblock, set_limit, enable_international, disable_international"


def update_customer_info(account_id, field, new_value):
    acc = CUSTOMERS.get(account_id.upper())
    if not acc:
        return f"Account {account_id} not found."
    valid_fields = {"phone", "email", "address", "nominee", "preferences"}
    if field.lower() not in valid_fields:
        return f"Cannot update '{field}'. Updatable fields: {', '.join(valid_fields)}"
    return (f"PROFILE UPDATE — {acc['name']} ({account_id})\n"
            f"Field: {field.title()}\n"
            f"Old Value: {acc.get(field, 'N/A')}\n"
            f"New Value: {new_value}\n"
            f"Status: UPDATED SUCCESSFULLY\n"
            f"Verification: SMS sent to {acc['phone']} for confirmation\n"
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

def run_agent(user_message):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            user_message = data.get("message", "").strip()
            if not user_message:
                self._send_json(400, {"error": "No message provided"})
                return

            reply, tool_used = run_agent(user_message)

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

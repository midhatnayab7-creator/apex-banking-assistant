import json
import os
from http.server import BaseHTTPRequestHandler
from groq import Groq

# ----------------------------
# SYSTEM PROMPT
# ----------------------------

SYSTEM_PROMPT = """You are Apex, a professional and knowledgeable banking AI assistant.
- Help customers with account inquiries, loan information, transaction history, and card services
- Always be professional, clear, and security-conscious
- Never share sensitive information without verification
- When you need information, use the available tools
- If a request requires human intervention, guide the customer to visit their nearest branch or call the helpline
- Provide accurate banking guidance and financial literacy tips when asked"""

# ----------------------------
# TOOLS DEFINITION
# ----------------------------

tools = [
    {
        "type": "function",
        "function": {
            "name": "check_account_balance",
            "description": "Check the balance and status of a customer's bank account",
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
            "name": "get_transaction_history",
            "description": "Retrieve recent transaction history for an account",
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
            "description": "Check if a customer is eligible for a loan based on their profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID"
                    },
                    "loan_type": {
                        "type": "string",
                        "description": "Type of loan: personal, home, auto, or business"
                    }
                },
                "required": ["customer_id", "loan_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_lost_card",
            "description": "Report a lost or stolen debit/credit card and block it immediately",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_number_last4": {
                        "type": "string",
                        "description": "Last 4 digits of the card number"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason: lost or stolen"
                    }
                },
                "required": ["card_number_last4", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_branch_info",
            "description": "Find nearest branch or ATM location by city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to search branches in"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# ----------------------------
# TOOL FUNCTIONS
# ----------------------------

def check_account_balance(account_id):
    accounts = {
        "ACC-1001": {"name": "Ahmed Khan", "balance": "$12,450.00", "type": "Savings", "status": "Active"},
        "ACC-1002": {"name": "Sara Ali", "balance": "$5,320.75", "type": "Current", "status": "Active"},
        "ACC-1003": {"name": "Omar Farooq", "balance": "$890.50", "type": "Savings", "status": "Frozen"},
        "ACC-2001": {"name": "Fatima Noor", "balance": "$28,100.00", "type": "Business", "status": "Active"},
        "ACC-2002": {"name": "Zain Malik", "balance": "$3,675.25", "type": "Current", "status": "Active"},
    }
    acc = accounts.get(account_id.upper())
    if acc:
        return f"Account: {account_id} | Name: {acc['name']} | Type: {acc['type']} | Balance: {acc['balance']} | Status: {acc['status']}"
    return f"Account {account_id} not found. Please verify your account number."


def get_transaction_history(account_id):
    transactions = {
        "ACC-1001": [
            "Mar 15 — Salary Credit: +$3,500.00",
            "Mar 14 — Grocery Store: -$85.40",
            "Mar 12 — Electricity Bill: -$120.00",
            "Mar 10 — ATM Withdrawal: -$200.00",
            "Mar 08 — Online Transfer to Sara Ali: -$500.00"
        ],
        "ACC-1002": [
            "Mar 16 — Freelance Payment: +$1,200.00",
            "Mar 14 — Restaurant: -$45.00",
            "Mar 11 — Subscription: -$14.99",
            "Mar 09 — Transfer from Ahmed Khan: +$500.00",
            "Mar 07 — Fuel Station: -$60.00"
        ],
        "ACC-2001": [
            "Mar 16 — Client Payment: +$5,000.00",
            "Mar 15 — Office Rent: -$1,500.00",
            "Mar 13 — Vendor Payment: -$2,300.00",
            "Mar 10 — Tax Payment: -$800.00",
            "Mar 08 — Client Payment: +$3,200.00"
        ],
    }
    txns = transactions.get(account_id.upper())
    if txns:
        return f"Recent transactions for {account_id}:\n" + "\n".join(txns)
    return f"No transaction history found for {account_id}."


def check_loan_eligibility(customer_id, loan_type):
    eligibility = {
        "CUST-101": {
            "personal": "Eligible — Up to $15,000 at 8.5% APR for 36 months",
            "home": "Eligible — Up to $250,000 at 5.2% APR for 25 years",
            "auto": "Eligible — Up to $35,000 at 6.0% APR for 60 months",
            "business": "Not Eligible — Minimum 2 years business history required"
        },
        "CUST-102": {
            "personal": "Eligible — Up to $8,000 at 9.0% APR for 24 months",
            "home": "Not Eligible — Credit score below minimum requirement",
            "auto": "Eligible — Up to $20,000 at 7.5% APR for 48 months",
            "business": "Not Eligible — No registered business found"
        },
    }
    customer = eligibility.get(customer_id.upper())
    if customer:
        result = customer.get(loan_type.lower())
        if result:
            return f"Loan Eligibility ({loan_type.title()} Loan) for {customer_id}: {result}"
        return f"Invalid loan type: {loan_type}. Choose from: personal, home, auto, or business."
    return f"Customer {customer_id} not found. Please verify your customer ID."


def report_lost_card(card_number_last4, reason):
    return f"URGENT: Card ending in {card_number_last4} has been BLOCKED immediately due to: {reason}. A replacement card will be mailed within 5-7 business days. For immediate assistance, call our 24/7 helpline: 1-800-APEX-BANK."


def get_branch_info(city):
    branches = {
        "karachi": "Apex Bank — Karachi Main Branch\nAddress: 123 Shahrah-e-Faisal, Karachi\nHours: Mon-Sat 9AM-5PM\nATMs: 3 available 24/7\nPhone: (021) 111-APEX",
        "lahore": "Apex Bank — Lahore Branch\nAddress: 45 Mall Road, Lahore\nHours: Mon-Sat 9AM-5PM\nATMs: 2 available 24/7\nPhone: (042) 111-APEX",
        "islamabad": "Apex Bank — Islamabad Branch\nAddress: 78 Blue Area, Jinnah Avenue, Islamabad\nHours: Mon-Sat 9AM-5PM\nATMs: 4 available 24/7\nPhone: (051) 111-APEX",
        "new york": "Apex Bank — New York Branch\nAddress: 350 Park Avenue, Manhattan, NY\nHours: Mon-Fri 9AM-4PM\nATMs: 2 available 24/7\nPhone: (212) 555-APEX",
        "london": "Apex Bank — London Branch\nAddress: 15 Canary Wharf, London E14\nHours: Mon-Fri 9AM-4:30PM\nATMs: 2 available 24/7\nPhone: +44 20 7946 APEX",
    }
    info = branches.get(city.lower())
    if info:
        return info
    return f"No branch found in {city}. Visit our website for full branch directory or call 1-800-APEX-BANK."


def run_tool(name, arguments):
    args = json.loads(arguments)
    if name == "check_account_balance":
        return check_account_balance(args["account_id"])
    elif name == "get_transaction_history":
        return get_transaction_history(args["account_id"])
    elif name == "check_loan_eligibility":
        return check_loan_eligibility(args["customer_id"], args["loan_type"])
    elif name == "report_lost_card":
        return report_lost_card(args["card_number_last4"], args["reason"])
    elif name == "get_branch_info":
        return get_branch_info(args["city"])
    return "Tool not found"


# ----------------------------
# AGENT LOGIC
# ----------------------------

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
            max_tokens=1024
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


# ----------------------------
# VERCEL HANDLER
# ----------------------------

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
                    "check_loan_eligibility": "Loan Eligibility Check",
                    "report_lost_card": "Card Security",
                    "get_branch_info": "Branch Locator"
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

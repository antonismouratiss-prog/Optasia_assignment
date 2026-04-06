import time
import threading
import queue
import psutil
import sqlite3
import logging
import sys
from typing import List, Literal
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, ValidationError, field_validator

# Main logger
logger = logging.getLogger("OptasiaApp")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(levelname)-5s,%(asctime)s (%(thread)d) [%(name)s] %(message)s [%(funcName)s: %(lineno)d]', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Error logger
error_logger = logging.getLogger("OptasiaErrors")
error_logger.setLevel(logging.WARNING)
file_handler = logging.FileHandler("validation_errors.log", mode='a', encoding='utf-8')
file_handler.setFormatter(formatter) 
error_logger.addHandler(file_handler)
error_logger.propagate = False


current_cpu: float = 0.0
def _cpu_monitor():
    global current_cpu
    while True:
        current_cpu = psutil.cpu_percent(interval=1)
 
threading.Thread(target=_cpu_monitor, daemon=True).start()

metrics_queue = queue.Queue()
def metrics_worker():
    while True:
        metric = metrics_queue.get()
        if metric is None:
            break
        with get_db() as conn:
            conn.execute("INSERT INTO api_metrics (latency_ms, cpu_usage, memory_usage) VALUES (?, ?, ?)", metric)

threading.Thread(target=metrics_worker, daemon=True).start()

@contextmanager
def get_db():
    conn = sqlite3.connect('optasia.db')
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row   
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application and initializing database...")
    try:
        conn = sqlite3.connect('optasia.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS transactions 
                     (customer_id TEXT, loan_date TEXT, amount REAL, fee REAL, 
                      loan_status INTEGER, term TEXT, annual_income REAL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS features 
                     (customer_id TEXT, total_loans INTEGER, total_amount REAL, 
                      avg_amount REAL)''')
        # conn.execute('''CREATE TABLE IF NOT EXISTS features 
        #              (customer_id TEXT, total_loans INTEGER, total_amount REAL, 
        #               avg_amount REAL, y2018, y2019, y2020, y2021, y2022, y2023, y2024, y2025)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS api_metrics 
             (latency_ms REAL,
              cpu_usage REAL,
              memory_usage REAL)''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
    yield

app = FastAPI(lifespan=lifespan)

# Validation rules
class Loan(BaseModel):
    loan_date: str
    amount: float = Field(ge=100, le=1000)
    fee: float = Field(ge=10, le=50)
    loan_status: int = Field(ge=0, le=1)
    term: Literal["short", "long"]    
    annual_income: float = Field(ge=100, le=10000000)

class Customer(BaseModel):
    customer_ID: str = Field(min_length=10, max_length=20, pattern=r"^[ -~]+$")
    loans: List[Loan]

# Endpoints
@app.get("/health")
def health():
    return {"status": "UP"}

@app.post("/feature-engineering")
async def feature_engineering(payload: dict, response: Response): 
    logger.info("Feature engineering process started.")
    start_time = time.time()
    response_data = []
    
    customers_list = payload.get("data", [])
    skip_count = 0

    with get_db() as conn:
        cursor = conn.cursor()

        for raw_cust in customers_list:
            customer_errors = []
            cust_id = raw_cust.get("customer_ID", "Unknown_ID")
            
            validated_customer = None
            try:
                validated_customer = Customer(**raw_cust)
            except ValidationError as e:
                for err in e.errors():
                    loc = " -> ".join([str(x) for x in err["loc"]])
                    customer_errors.append(f"Format Error [{loc}]: {err['msg']}")

            total_amount_sum = 0
            # loan_years = {str(y): 0 for y in range(2018, 2026)}

            if validated_customer:
                for i, loan in enumerate(validated_customer.loans):
                    total_loan_cost = loan.amount + loan.fee
                    income = loan.annual_income
                    
                    if (income <= 1000 and total_loan_cost > 110) or \
                    (income <= 10000 and total_loan_cost > 220) or \
                    (income <= 100000 and total_loan_cost > 550) or \
                    (income <= 10000000 and total_loan_cost > 1050):
                        customer_errors.append(f"Error: Cost {total_loan_cost} too high for income {income}")

                    # year = loan.loan_date.split("/")[2]
                    # if year in loan_years:
                    #     loan_years[year] += 1

                    total_amount_sum += total_loan_cost

            if customer_errors:
                formatted_errors = "\n  - " + "\n  - ".join(customer_errors)
                error_logger.warning(f"Customer {cust_id} skipped due to {len(customer_errors)} errors:{formatted_errors}")
                
                response_data.append({"customer_ID": cust_id, "status": "Skipped", "errors": customer_errors})
                skip_count += 1
            else:
                num_loans = len(validated_customer.loans)
                avg = total_amount_sum / num_loans if num_loans > 0 else 0

                # Save Transactions
                for loan in validated_customer.loans:
                    cursor.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?)", 
                                (cust_id, loan.loan_date, loan.amount, loan.fee, 
                                loan.loan_status, loan.term, loan.annual_income))

                # Save Features
                # cursor.execute("""INSERT INTO features VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", 
                cursor.execute("""INSERT INTO features VALUES (?,?,?,?)""", 
                            (cust_id, num_loans, total_amount_sum, avg
                            #   ,loan_years['2018'], loan_years['2019'], loan_years['2020'], loan_years['2021'],
                            #   loan_years['2022'], loan_years['2023'], loan_years['2024'], loan_years['2025']
                            ))
                
                response_data.append({"customer_ID": cust_id, "status": "Success"})

    if skip_count == 0:
        logger.info(f"Feature engineering completed successfully for the customer.")
    else:        
        logger.info("Feature engineering completed, but the customer was not processed successfully.")

    if skip_count > 0:
        response.status_code = 400

    latency_ms = (time.time() - start_time) * 1000
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent

    metrics_queue.put((latency_ms, cpu, mem))

    return {
        "status": "completed",
        "results": response_data,
        "metrics": {
            "request_latency_ms": round(latency_ms, 2),
            "cpu_usage_percent": cpu,
            "memory_usage_percent": mem
        }
    }

# --- 4. DATA RETRIEVAL ENDPOINTS ---
@app.get("/customer-transactions/{customer_id}")
def get_transactions(customer_id: str):
    logger.info(f"Retrieving transactions for customer: {customer_id}")
    conn = sqlite3.connect('optasia.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE customer_id = ?", (customer_id,))
    records = cursor.fetchall()
    conn.close()
    return {"customer_id": customer_id, "transactions": records}

@app.get("/customer-features/{customer_id}")
def get_features(customer_id: str):
    logger.info(f"Retrieving features for customer: {customer_id}")
    conn = sqlite3.connect('optasia.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM features WHERE customer_id = ?", (customer_id,))
    record = cursor.fetchone() 
    conn.close()
    return {"customer_id": customer_id, "features": record}

@app.delete("/delete-customer/{customer_id}")
def delete_customer(customer_id: str):
    logger.info(f"Deleting all records for customer: {customer_id}")
    conn = sqlite3.connect('optasia.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE customer_id = ?", (customer_id,))
    cursor.execute("DELETE FROM features WHERE customer_id = ?", (customer_id,))
    conn.commit()
    conn.close()
    return {"message": f"Customer {customer_id} successfully deleted from all records."}

@app.get("/metrics")
def get_system_metrics():
    return {
        "cpu_usage_percent": psutil.cpu_percent(interval=1),
        "memory_info": {
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "percent_used": psutil.virtual_memory().percent
        },
        "disk_usage_percent": psutil.disk_usage('/').percent,
        "process_threads": psutil.Process().num_threads()
    }
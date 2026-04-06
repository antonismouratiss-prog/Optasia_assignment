# Optasia Feature Engineering API

## Setup
- Library requirements, Python version, and run instructions can be found in the **Dockerfile** and **requirements.txt**

## How to Run
- First run `optasia_final4.py`
- Then run `load_data.py` while `optasia_final6.py` is running, in order to load the JSON files

## Output Files
- **`optasia.db`** — SQLite database containing all results
- **`postman.png`** — Summary screenshot from Postman
- **`validation_errors.txt`** — Log of all validation errors for skipped customers

## Validation
- Customer files 1 to 5 passed all validation rules successfully
- Customer files 6 to 10 contain several issues that do not abide by the validation rules
- An extensive summary of all errors can be found in `validation_errors.txt`

## Latency
- Latency per request varies across individual runs, sometimes exceeding the 20 ms threshold
- The average latency over 10,000 runs per file is approximately 13 ms, which is within the threshold

Instructions for library requirements, Python version and how to run the code can be found in the Dockerfile and the requirements files.
To run the script, first run optasia_final4.py and then the load_data.py while optasia_final6.py is running, in order to load the json files.
The results for the SQL database can be found in the optasia.db file, the summary from the postman can be found in the image postman.png, and the validation errors for skipped customers can be found in the validation_errors.txt.
It is observed that the customer files 6 to 10 have several problems that do not abide by the validation rules. An extensive summary can be found in the validation_errors.txt.
Last but not least, it is observed that the latency per request varies for each individual run of the script, sometimes over 20 ms, which is the threshold. However, we consider the average over 10,000 run per file, which is around 13 ms.
